# Architecture and design decisions

## Data model

Users own documents and conversations. Sessions contain hashes of random bearer tokens with seven-day expiry. Documents track content hashes, counts, and embedding-model identity. Chunks store one PDF page number, text, and an optional vector. Turns contain a question and a JSON answer/source snapshot.

Foreign keys enforce cascade deletion. Deleting a document additionally removes saved turns that contain its source excerpts, preventing a PDF deletion from leaving the same text visible in history. This may leave an empty conversation that the user can delete.

## Ingestion

The API validates PDF signature, size, page count, encryption, selectable text, and chunk count. Names are display-only: PDFs are stored using server-generated IDs, preventing filename traversal. A SHA-256 uniqueness constraint rejects duplicate uploads per account. Database changes are transactional; failed uploads remove the newly written file. A process crash between filesystem write and database commit can leave an orphan file; production storage would require reconciliation.

Each page is split into 230-word windows with 40-word overlap. Page boundaries are never crossed. This makes page citations stable and directly navigable with a PDF URL fragment. Limits reduce ordinary resource usage but do not fully sandbox a hostile PDF parser workload.

## Retrieval

BM25 scores case-folded tokens with English stopword removal (`k1=1.5`, `b=0.75`). Semantic retrieval uses cosine similarity, with a 0.4 similarity floor. Rank lists are combined by reciprocal rank fusion: score = sum(1 / (60 + rank)). These are starting heuristics; they need tuning on representative data.

PostgreSQL uses the native pgvector cosine-distance operator. SQLite stores vectors in JSON and computes cosine similarity in Python, providing the same small-corpus behaviour without a database server. The current PostgreSQL path uses exact vector search and an unbounded vector column; it does not claim to have an ANN index. Vector candidates are capped at 200, and output at six chunks.

Every query is scoped to the signed-in owner before retrieval. A requested document ID or conversation ID belonging to another user is rejected. Selected-document filters apply to both lexical and semantic retrieval.

Comparison reserves up to two chunks per selected document. If any selected document lacks retrieved evidence, the app reports insufficient evidence instead of making a one-sided comparison. The model receives all selected evidence together when available.

## Generation and evidence

Ollama is configured by the server, never by an uploaded document or user-supplied URL. Source text is passed as data in a JSON payload. The system instruction explicitly treats it as untrusted and requests evidence-only answers. The model has no tools, shell, filesystem, or external-network capabilities through this app.

The response uses a JSON schema with an insufficient-evidence flag and paragraphs containing citation IDs. IDs must refer to retrieved sources and every returned paragraph must have at least one. Invalid responses are rejected and replaced with explicitly labelled verbatim excerpts. This validates citation structure and scope, not semantic entailment. Prompt injection and hallucination cannot be ruled out by the prompt alone.

Stored conversations are a history/export feature. Each question is answered independently, avoiding silent cross-turn or cross-scope context mixing. Conversational query rewriting is a future feature.

## Authentication and deployment

Passwords use scrypt with unique salts. Session tokens use 32 random bytes and only their SHA-256 hashes are stored. Cookies are HttpOnly, SameSite=Strict, and optionally Secure. Browser writes reject an unexpected Origin. No CORS is enabled; frontend and API are same-origin. Runtime data and secrets are ignored by Git and excluded from Docker build context.

The application is configured for a single backend process. SQLite WAL improves local read concurrency; it is not a substitute for PostgreSQL under load. Multiple workers require a distributed limiter and ingestion queue. Version 1 creates schema on startup with SQLAlchemy; future schema changes should use migrations, not rely on `create_all` to alter existing tables.

## API overview

Interactive OpenAPI documentation is available at `/docs` while the backend runs.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register`, `/api/auth/login` | Create account / create session |
| POST | `/api/auth/logout` | Revoke current session |
| GET | `/api/auth/me` | Current account |
| GET / POST | `/api/documents` | List / upload owned PDFs |
| GET | `/api/documents/{id}/file` | Authorized PDF preview |
| POST | `/api/documents/{id}/reindex` | Create/replace semantic embeddings |
| DELETE | `/api/documents/{id}` | Delete PDF, chunks, related saved turns |
| POST | `/api/ask` | Retrieve evidence and return a cited answer |
| GET | `/api/conversations` | Latest 100 conversations |
| GET / DELETE | `/api/conversations/{id}` | Restore / delete a conversation |
| GET | `/api/health` | Application readiness and configured mode |
