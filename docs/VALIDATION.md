# Validation record

## Verified in the build workspace

- **22 Python tests passed** on SQLite, covering authentication/session handling, cross-origin rejection, user isolation, PDF extraction, filtering, page citations, comparison, history, deletion, malformed files, upload limits, embedding validation, structured-response validation, and provider-failure fallback.
- **2 Chromium browser tests passed**, exercising registration, PDF upload, question answering, source preview, history restoration, Markdown export, no-evidence response, deletion, and a 390px mobile layout without horizontal overflow.
- **TypeScript check and Vite production build passed.**
- **Six synthetic retrieval cases** returned the expected page at rank 1; an unrelated question returned insufficient evidence. Full inputs/results are in `evaluation.json`. These are smoke tests, not general accuracy measurements.

The workspace's standard Chromium launcher pointed to a missing binary, and Playwright's CDN download was unavailable. Browser tests were completed using a Chromium binary supplied through `@sparticuz/chromium`, with the `CHROMIUM_PATH` test override. This package is a local validation tool, not an application dependency.

## Not verified here

- Live Ollama model inference or answer quality. Provider tests use deterministic mocked responses that verify the API contract, validation, and fallback logic.
- Docker image build / Compose startup and PostgreSQL/pgvector execution. Docker and PostgreSQL services were not available in this workspace.
- GitHub Actions execution; local passing tests do not imply a remote CI run.
- Public deployment, multi-user load, adversarial PDF parsing, and large-corpus retrieval quality.

Run the documented Docker/Ollama setup on a suitable machine before presenting the local-AI or PostgreSQL paths as demonstrated. No latency, scale, or real-world accuracy claim is inferred from these checks.
