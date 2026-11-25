from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import Chunk, LoginSession
from conftest import make_pdf


def test_requires_sign_in(client):
    assert client.get('/api/documents').status_code == 401
    assert client.post('/api/ask', json={'question': 'What is HDFS?'}).status_code == 401


def test_register_login_logout(client, app):
    body = {'username': 'karthik', 'password': 'safe-password-123'}
    result = client.post('/api/auth/register', json=body)
    assert result.status_code == 201
    assert 'httponly' in result.headers['set-cookie'].lower()
    assert 'samesite=strict' in result.headers['set-cookie'].lower()
    raw_token = client.cookies.get('citewise_session')
    with app.state.session_factory() as db:
        assert db.scalar(select(LoginSession.token_hash)) != raw_token
    assert client.get('/api/auth/me').json()['username'] == 'karthik'
    assert client.post('/api/auth/logout').status_code == 204
    assert client.get('/api/auth/me').status_code == 401
    assert client.post('/api/auth/login', json={**body, 'password': 'wrong-password'}).status_code == 401
    assert client.post('/api/auth/login', json=body).status_code == 200
    assert client.post('/api/auth/register', json=body).status_code == 409


def test_cross_origin_blocked(client):
    response = client.post('/api/auth/register', headers={'Origin': 'https://attacker.example'}, json={'username': 'student', 'password': 'safe-password-123'})
    assert response.status_code == 403


def test_pdf_upload_citations_and_history(signed_in, uploaded):
    assert uploaded['page_count'] == 3
    assert uploaded['chunk_count'] == 3
    answer = signed_in.post('/api/ask', json={'question': 'What is the HDFS replication factor?'}).json()
    assert answer['result']['sources'][0]['page'] == 2
    assert 'three' in answer['result']['paragraphs'][0]['text']
    assert answer['result']['mode'] == 'excerpt'
    assert not answer['result']['insufficient_evidence']
    convo = answer['conversation_id']
    second = signed_in.post('/api/ask', json={'question': 'What does virtualization do?', 'conversation_id': convo})
    assert second.json()['conversation_id'] == convo
    history = signed_in.get(f'/api/conversations/{convo}').json()
    assert len(history) == 2
    assert signed_in.get('/api/conversations').json()[0]['title'] == 'What is the HDFS replication factor?'
    pdf = signed_in.get(f"/api/documents/{uploaded['id']}/file")
    assert pdf.content.startswith(b'%PDF-')
    assert pdf.headers['content-type'] == 'application/pdf'


def test_no_evidence_does_not_invent_answer(signed_in, uploaded):
    result = signed_in.post('/api/ask', json={'question': 'Who won Wimbledon?'}).json()['result']
    assert result['insufficient_evidence']
    assert result['paragraphs'] == []
    assert result['sources'] == []


def test_ownership_isolation(app, signed_in, uploaded):
    turn = signed_in.post('/api/ask', json={'question': 'What is HDFS?'}).json()
    with TestClient(app) as other:
        other.post('/api/auth/register', json={'username': 'another', 'password': 'another-password'})
        assert other.get('/api/documents').json() == []
        assert other.get('/api/conversations').json() == []
        for method, url in [('get', f"/api/documents/{uploaded['id']}/file"), ('delete', f"/api/documents/{uploaded['id']}"), ('post', f"/api/documents/{uploaded['id']}/reindex"), ('get', f"/api/conversations/{turn['conversation_id']}")]:
            assert getattr(other, method)(url).status_code == 404
        assert other.post('/api/ask', json={'question': 'HDFS replication?', 'document_ids': [uploaded['id']]}).status_code == 404
        assert other.post('/api/ask', json={'question': 'HDFS replication?', 'conversation_id': turn['conversation_id']}).status_code == 404
        assert other.post('/api/ask', json={'question': 'HDFS replication?'}).json()['result']['insufficient_evidence']


def test_document_deletion_removes_chunks_and_saved_excerpts(signed_in, uploaded, app):
    turn = signed_in.post('/api/ask', json={'question': 'HDFS replication?'}).json()
    assert signed_in.delete(f"/api/documents/{uploaded['id']}").status_code == 204
    assert signed_in.get('/api/documents').json() == []
    assert signed_in.get(f"/api/documents/{uploaded['id']}/file").status_code == 404
    assert signed_in.get(f"/api/conversations/{turn['conversation_id']}").json() == []
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Chunk)) == 0


def test_invalid_blank_encrypted_and_duplicate_pdfs(signed_in, uploaded):
    from io import BytesIO
    from pypdf import PdfWriter
    assert signed_in.post('/api/documents', files={'file': ('fake.pdf', b'not pdf')}).status_code == 422
    blank = make_pdf([''])
    assert 'OCR' in signed_in.post('/api/documents', files={'file': ('scan.pdf', blank)}).json()['detail']
    writer = PdfWriter(); writer.add_blank_page(width=200, height=200); writer.encrypt('secret')
    encrypted = BytesIO(); writer.write(encrypted)
    assert 'Password-protected' in signed_in.post('/api/documents', files={'file': ('locked.pdf', encrypted.getvalue())}).json()['detail']
    raw = signed_in.get(f"/api/documents/{uploaded['id']}/file").content
    assert signed_in.post('/api/documents', files={'file': ('copy.pdf', raw)}).status_code == 409


def test_comparison_requires_evidence_from_both_documents(signed_in, uploaded):
    raw = make_pdf(['GFS uses a master server to manage metadata. Chunkservers store data.'])
    doc = signed_in.post('/api/documents', files={'file': ('gfs.pdf', raw)}).json()['document']
    assert signed_in.post('/api/ask', json={'question': 'Compare metadata management', 'compare': True}).status_code == 422
    result = signed_in.post('/api/ask', json={'question': 'Compare metadata management', 'compare': True, 'document_ids': [uploaded['id'], doc['id']]}).json()['result']
    assert {s['document_id'] for s in result['sources']} == {uploaded['id'], doc['id']}
    assert not result['insufficient_evidence']
    missing = signed_in.post('/api/ask', json={'question': 'HDFS replication factor', 'compare': True, 'document_ids': [uploaded['id'], doc['id']]}).json()['result']
    assert missing['insufficient_evidence']


def test_selected_document_filter(signed_in, uploaded):
    raw = make_pdf(['Dolphins are marine mammals.'])
    doc = signed_in.post('/api/documents', files={'file': ('marine.pdf', raw)}).json()['document']
    result = signed_in.post('/api/ask', json={'question': 'HDFS replication?', 'document_ids': [doc['id']]}).json()['result']
    assert result['insufficient_evidence']


def test_validation_and_reindex_in_excerpt_mode(signed_in, uploaded):
    assert signed_in.post('/api/ask', json={'question': '   '}).status_code == 422
    assert signed_in.post(f"/api/documents/{uploaded['id']}/reindex").status_code == 409


def test_upload_size_and_page_limits(tmp_path):
    from app.main import create_app
    from app.config import Settings
    settings = Settings(database_url=f'sqlite:///{tmp_path}/limits.db', data_dir=tmp_path, max_upload=3000, max_pages=1)
    with TestClient(create_app(settings)) as client:
        client.post('/api/auth/register', json={'username': 'limits', 'password': 'long-password'})
        assert client.post('/api/documents', files={'file': ('large.pdf', b'%PDF-' + b'X' * 3000)}).status_code == 413
        assert client.post('/api/documents', files={'file': ('pages.pdf', make_pdf(['first', 'second']))}).status_code == 422
