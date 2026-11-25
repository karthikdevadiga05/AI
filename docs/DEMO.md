# Demo and interview guide

## Five-minute walkthrough

1. Create an account and upload both PDFs from `samples/`.
2. Ask: **What is the HDFS replication factor?** Open the source to show page 2.
3. Ask: **What is the monthly downtime budget?** Explain that citations use the physical PDF page number, not printed page labels.
4. Select both PDFs, enable Compare, and ask: **Compare metadata management and replication.** Excerpt mode retrieves passages from each; Ollama mode writes a comparison.
5. Ask an unrelated question: **Who won Wimbledon?** Show the insufficient-evidence state.
6. Restore an earlier conversation, export it, and explain the difference between chat history and conversational model context.
7. Sign into another account to demonstrate document isolation.

For an AI demonstration, enable Ollama, download both models, and reindex before the demo. If model setup is incomplete, demonstrate excerpt mode honestly.

## Questions worth preparing

- Why use RAG instead of asking an LLM directly? Retrieval supplies document-specific evidence and source references; it does not eliminate hallucination.
- Why combine keyword and vector search? Keyword search helps exact terms and acronyms; embeddings help semantic similarity. Rank fusion combines them without treating raw scores as comparable.
- Why preserve page boundaries? It makes citation navigation unambiguous, at the cost of sometimes splitting context across pages.
- What does citation validation guarantee? The identifier belongs to the retrieved evidence set. It does not verify that the claim is true or fully supported.
- What happens if a model fails? Keyword retrieval and clearly labelled excerpts remain available; failed embeddings can be reindexed.
- How is another user's PDF protected? Session authentication, owner-scoped queries, explicit ownership checks, and randomized storage names.
- What would change at scale? Queue ingestion, isolate PDF parsing, cache/index lexical statistics, add ANN indexing and distributed limits, and evaluate retrieval on real questions.

## Resume wording after reviewing and running the project

**CiteWise — Document Search & Question Answering** | Python, FastAPI, React, TypeScript, PostgreSQL/pgvector, Ollama

- Built a full-stack PDF question-answering workspace with page-level citations, document comparison, saved conversations, and user-isolated document access.
- Implemented page-aware chunking, BM25 and vector retrieval with reciprocal rank fusion, and structured AI responses with citation validation and an explicit excerpt fallback.

Only describe the parts you have run and can explain. Do not describe the six-question synthetic benchmark as general model accuracy. Add measured scale, latency, or quality figures only after a representative evaluation.
