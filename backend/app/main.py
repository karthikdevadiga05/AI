import hashlib
import json
import logging
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from .ai import AIUnavailable, Ollama
from .config import Settings
from .db import Chunk, Conversation, Document, LoginSession, Turn, User, database, uid
from .pdf import extract_chunks
from .retrieval import retrieve
from .security import hash_password, token_hash, verify_password

logger = logging.getLogger('citewise')


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=10, max_length=128)


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    document_ids: list[str] = Field(default_factory=list, max_length=30)
    conversation_id: str | None = None
    compare: bool = False


def doc_json(d):
    return {key: getattr(d, key) for key in ('id', 'name', 'page_count', 'chunk_count', 'size', 'indexed_model', 'created_at')}


def create_app(settings=None):
    settings = settings or Settings()
    engine, factory = database(settings)
    ai = Ollama(settings)
    upload_dir = settings.data_dir / 'uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)
    auth_attempts = defaultdict(deque)
    attempts_lock = threading.Lock()
    ingestion_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title='CiteWise API', version='1.0.0', lifespan=lifespan)
    app.state.ai = ai
    app.state.session_factory = factory

    @app.middleware('http')
    async def same_origin(request, call_next):
        origin = request.headers.get('origin')
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} and origin and origin != settings.app_origin:
            return Response('Cross-origin request rejected', status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def session():
        with factory() as db:
            yield db

    def current_user(request: Request, db=Depends(session)):
        raw = request.cookies.get('citewise_session', '')
        login = db.get(LoginSession, token_hash(raw))
        if not login or login.expires_at < time.time():
            raise HTTPException(401, 'Please sign in to continue.')
        return db.get(User, login.user_id)

    def owned_document(doc_id, user, db):
        doc = db.get(Document, doc_id)
        if not doc or doc.user_id != user.id:
            raise HTTPException(404, 'Document not found.')
        return doc

    def owned_conversation(conversation_id, user, db):
        convo = db.get(Conversation, conversation_id)
        if not convo or convo.user_id != user.id:
            raise HTTPException(404, 'Conversation not found.')
        return convo

    def throttle(request):
        key = request.client.host if request.client else 'unknown'
        now = time.monotonic()
        with attempts_lock:
            # Bound memory and discard idle clients. This limiter is per process.
            for stale in [k for k, times in auth_attempts.items() if not times or times[-1] < now - 60]:
                del auth_attempts[stale]
            attempts = auth_attempts[key]
            while attempts and attempts[0] < now - 60:
                attempts.popleft()
            if len(attempts) >= 15:
                raise HTTPException(429, 'Too many sign-in attempts. Try again in a minute.')
            attempts.append(now)

    def set_login(user, response, db):
        raw = secrets.token_urlsafe(32)
        db.execute(delete(LoginSession).where(LoginSession.expires_at < time.time()))
        db.add(LoginSession(token_hash=token_hash(raw), user_id=user.id, expires_at=time.time() + 7 * 86400))
        db.commit()
        response.set_cookie('citewise_session', raw, httponly=True, secure=settings.cookie_secure, samesite='strict', max_age=7 * 86400)
        return {'id': user.id, 'username': user.username}

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'mode': settings.ai_mode, 'chat_model': settings.chat_model if settings.ai_mode == 'ollama' else None}

    @app.post('/api/auth/register', status_code=201)
    def register(body: Credentials, request: Request, response: Response, db=Depends(session)):
        throttle(request)
        user = User(username=body.username.lower(), password_hash=hash_password(body.password))
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'That username is already taken.')
        return set_login(user, response, db)

    @app.post('/api/auth/login')
    def login(body: Credentials, request: Request, response: Response, db=Depends(session)):
        throttle(request)
        user = db.scalar(select(User).where(User.username == body.username.lower()))
        # Run scrypt for unknown usernames too.
        stored = user.password_hash if user else '00' * 16 + ':' + '00' * 64
        valid = verify_password(body.password, stored)
        if not user or not valid:
            raise HTTPException(401, 'Incorrect username or password.')
        return set_login(user, response, db)

    @app.post('/api/auth/logout', status_code=204)
    def logout(request: Request, response: Response, db=Depends(session)):
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(request.cookies.get('citewise_session', ''))))
        db.commit()
        response.delete_cookie('citewise_session')

    @app.get('/api/auth/me')
    def me(user=Depends(current_user)):
        return {'id': user.id, 'username': user.username}

    @app.get('/api/documents')
    def documents(user=Depends(current_user), db=Depends(session)):
        return [doc_json(d) for d in db.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc()))]

    @app.post('/api/documents', status_code=201)
    def upload(file: UploadFile, user=Depends(current_user), db=Depends(session)):
        raw = file.file.read(settings.max_upload + 1)
        if len(raw) > settings.max_upload:
            raise HTTPException(413, 'PDFs must be 20 MB or smaller.')
        digest = hashlib.sha256(raw).hexdigest()
        with ingestion_lock:
            if db.scalar(select(func.count()).select_from(Document).where(Document.user_id == user.id)) >= settings.max_documents:
                raise HTTPException(409, 'Your workspace supports up to 30 documents. Delete a document first.')
            if db.scalar(select(Document).where(Document.user_id == user.id, Document.sha256 == digest)):
                raise HTTPException(409, 'This PDF is already in your workspace.')
            try:
                pages, chunks = extract_chunks(raw, settings.max_pages, settings.max_chunks)
            except ValueError as exc:
                raise HTTPException(422, str(exc))
            warning = None
            vectors = [None] * len(chunks)
            if settings.ai_mode == 'ollama':
                try:
                    vectors = ai.embed([body for _, body in chunks])
                except AIUnavailable as exc:
                    warning = str(exc) + ' Keyword search is ready; use Reindex when the model is available.'
            name = re.split(r'[/\\]', file.filename or 'document.pdf')[-1]
            name = ''.join(c for c in name if c.isprintable())[:200] or 'document.pdf'
            doc = Document(id=uid(), user_id=user.id, name=name, sha256=digest, page_count=pages,
                           chunk_count=len(chunks), size=len(raw), indexed_model=settings.embed_model if vectors[0] is not None else None)
            path = upload_dir / (doc.id + '.pdf')
            db.add(doc)
            try:
                db.flush()
                for (page, content), vector in zip(chunks, vectors):
                    db.add(Chunk(document_id=doc.id, page=page, content=content, embedding=vector))
                path.write_bytes(raw)
                db.commit()
            except Exception:
                db.rollback()
                path.unlink(missing_ok=True)
                raise
        return {'document': doc_json(doc), 'warning': warning}

    @app.get('/api/documents/{doc_id}/file')
    def pdf_file(doc_id: str, user=Depends(current_user), db=Depends(session)):
        doc = owned_document(doc_id, user, db)
        path = upload_dir / (doc.id + '.pdf')
        if not path.exists():
            raise HTTPException(404, 'The stored PDF is missing.')
        return FileResponse(path, media_type='application/pdf', filename=doc.name, content_disposition_type='inline')

    @app.delete('/api/documents/{doc_id}', status_code=204)
    def remove_document(doc_id: str, user=Depends(current_user), db=Depends(session)):
        doc = owned_document(doc_id, user, db)
        # Remove any saved turns containing this document's excerpts as well.
        turns = db.scalars(select(Turn).join(Conversation).where(Conversation.user_id == user.id)).all()
        for turn in turns:
            if any(s['document_id'] == doc_id for s in turn.result.get('sources', [])):
                db.delete(turn)
        db.delete(doc)
        db.commit()
        (upload_dir / (doc.id + '.pdf')).unlink(missing_ok=True)

    @app.post('/api/documents/{doc_id}/reindex')
    def reindex(doc_id: str, user=Depends(current_user), db=Depends(session)):
        doc = owned_document(doc_id, user, db)
        if settings.ai_mode != 'ollama':
            raise HTTPException(409, 'Enable Ollama mode to create semantic embeddings.')
        chunks = db.scalars(select(Chunk).where(Chunk.document_id == doc_id)).all()
        try:
            vectors = ai.embed([c.content for c in chunks])
        except AIUnavailable as exc:
            raise HTTPException(503, str(exc))
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding = vector
        doc.indexed_model = settings.embed_model
        db.commit()
        return doc_json(doc)

    @app.get('/api/conversations')
    def conversations(user=Depends(current_user), db=Depends(session)):
        return [{'id': c.id, 'title': c.title, 'created_at': c.created_at} for c in db.scalars(
            select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.created_at.desc()).limit(100))]

    @app.get('/api/conversations/{convo_id}')
    def conversation(convo_id: str, user=Depends(current_user), db=Depends(session)):
        owned_conversation(convo_id, user, db)
        return [{'id': t.id, 'question': t.question, 'result': t.result} for t in db.scalars(
            select(Turn).where(Turn.conversation_id == convo_id).order_by(Turn.created_at))]

    @app.delete('/api/conversations/{convo_id}', status_code=204)
    def remove_conversation(convo_id: str, user=Depends(current_user), db=Depends(session)):
        db.delete(owned_conversation(convo_id, user, db))
        db.commit()

    @app.post('/api/ask')
    def ask(body: Question, user=Depends(current_user), db=Depends(session)):
        started = time.perf_counter()
        question = body.question.strip()
        if len(question) < 3:
            raise HTTPException(422, 'Please enter a question with at least three characters.')
        ids = list(dict.fromkeys(body.document_ids))
        for doc_id in ids:
            owned_document(doc_id, user, db)
        if body.compare and not 2 <= len(ids) <= 3:
            raise HTTPException(422, 'Select two or three documents to compare.')
        convo = owned_conversation(body.conversation_id, user, db) if body.conversation_id else None
        vector, warning = None, None
        if settings.ai_mode == 'ollama':
            try:
                vector = ai.embed([question], query=True)[0]
            except AIUnavailable as exc:
                warning = str(exc)
        sources = retrieve(db, user.id, question, ids, vector, settings.embed_model, body.compare)
        paragraphs = []
        mode = 'excerpt'
        insufficient = not sources or (body.compare and set(ids) != {s['document_id'] for s in sources})
        if not insufficient:
            if settings.ai_mode == 'ollama':
                try:
                    paragraphs = ai.answer(question, sources, body.compare)
                    mode = 'ai'
                    insufficient = not paragraphs
                except AIUnavailable as exc:
                    warning = str(exc)
            if mode == 'excerpt':
                paragraphs = [{'text': s['text'], 'source_ids': [s['id']]} for s in sources]
        result = {'paragraphs': paragraphs, 'sources': sources, 'mode': mode,
                  'insufficient_evidence': insufficient, 'warning': warning,
                  'message': 'Not enough supporting evidence was found in the selected documents.' if insufficient else
                  ('Relevant source excerpts — these are not an AI-generated answer.' if mode == 'excerpt' else 'Answer grounded in your selected documents. Verify important claims against the sources.'),
                  'elapsed_ms': round((time.perf_counter() - started) * 1000), 'compare': body.compare}
        if not convo:
            convo = Conversation(id=uid(), user_id=user.id, title=question[:100])
            db.add(convo)
            db.flush()
        turn = Turn(id=uid(), conversation_id=convo.id, question=question, result=result)
        db.add(turn)
        db.commit()
        return {'id': turn.id, 'conversation_id': convo.id, 'question': question, 'result': result}

    frontend = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
    if frontend.exists():
        app.mount('/', StaticFiles(directory=frontend, html=True), name='frontend')
    return app


# Use uvicorn app.main:create_app --factory so tests can supply isolated settings.
