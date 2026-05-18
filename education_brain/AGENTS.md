## Project Background

- This project is an education knowledge base service centered on real teaching data rather than a generic RAG demo.
- The current backend lives under `knowledge/` and uses FastAPI as the service entry.
- The core external dependencies are MongoDB, Milvus, and MinIO:
  MongoDB stores structured business data, Milvus serves vector retrieval, and MinIO stores extracted assets.
- The near-term goal is to make the service start reliably, read configuration correctly, connect to those three dependencies, and expose a truthful `/health` endpoint.

## Current Requirements

- Treat `knowledge/core/config.py` as the single source of truth for runtime configuration.
- Treat `knowledge/core/clients.py` as the unified entry for dependency clients and dependency health probes.
- Milvus authentication must be configurable explicitly through settings and `.env`.
  Required fields may include `MILVUS_URI`, `MILVUS_USER`, `MILVUS_PASSWORD`, `MILVUS_TOKEN`, and `MILVUS_DB_NAME`.
- If Milvus auth is enabled, do not assume anonymous access.
  The common default admin pair is `root` / `milvus`, but the deployed environment may override it.
- `/health` should fail fast and return `degraded` with concrete component errors instead of hanging indefinitely.
- In the current phase, prioritize background clarification, config correctness, and dependency integration over writing new tests.
  Skip new test-first expansion unless the user explicitly asks to resume test work.

## Environment

- Runtime: Python 3.12.3 (`/usr/bin/python3`), `uv 0.9.18`
- Network: npm / PyPI / GitHub are reachable through the configured local proxy (`127.0.0.1:7890` / `127.0.0.1:7891`); `nslookup` is not installed, so prefer `curl` / `getent hosts`
- Sandbox: project dir, `/tmp`, and home dir are writable; Python/Node subprocess creation works; localhost HTTP bind/connect on `127.0.0.1` is currently verifiable
- Dependencies: `knowledge/pyproject.toml`, `knowledge/.venv`, and `knowledge/uv.lock` all exist
- Local venv: `knowledge/.venv` is active-capable and resolves `sys.prefix` to the local project env
- Verification: declared distributions are installed and core imports succeed; `knowledge/.venv/bin/python -m pytest --version` returns `pytest 9.0.3`
- Package management: prefer `uv`; this venv also exposes `python -m pip`
- Socket note: backend `uvicorn` startup and `curl http://127.0.0.1:8000/...` both succeed in the current snapshot
- Embedding verification: cached `BAAI/bge-m3` loads and encodes successfully in offline CPU mode
- Reranker verification: cached `BAAI/bge-reranker-v2-m3` snapshot exists but is incomplete; weights missing, so reranker is not verified usable yet
- CUDA note: `torch.cuda.is_available()` is `False` in this sandbox, so `.env` default `BGE_DEVICE=cuda` will not work here without fallback
- Frontend note: sibling project `../education_brain_front` now has `node_modules`; `npm run dev` and `npm run build` both pass, and the API layer can target the real backend with `VITE_USE_MOCK !== 'true'`
- Last preflight: 2026-04-19, details in `docs/env-setup.md`
