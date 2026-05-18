# Environment Setup

> Updated by env-preflight skill. Last updated: 2026-05-18 17:58:02 CST.

## Tech Stack

Python 3.12 backend and data generator, Vite/React frontend, Docker Compose data QA services.

| Component | Version | Manager | Notes |
|-----------|---------|---------|-------|
| Python | 3.12.3 | system + project `.venv` | Backend uses `education_brain/knowledge/.venv`; data generator uses `data_ge/edu-data/.venv`. |
| uv | 0.9.18 | system | Use the verified `.venv` commands for backend tests and API. |
| Node.js | v20.19.6 | system | Frontend package is `education_brain_front`. |
| npm | 10.8.2 | system | `node_modules` and Vite binary are present. |
| Docker | 29.1.3 | Docker Desktop | Data QA services run from `infra/education-data-qa`. |
| Docker Compose | v2.40.3-desktop.1 | Docker Desktop | Use `docker compose`, not legacy `docker-compose`. |

## Environment Constraints

- Iteration 03 validation is `POST /analytics/query` plus `SMOKE_STAGE=llm`; do not use `SMOKE_STAGE=all` as the Iteration 03 gate.
- Smoke scripts require the FastAPI server to be running first. If `/health` is unreachable, start the API instead of rerunning the smoke script blindly.
- Current compose stack provides MySQL, MongoDB, Elasticsearch, Kibana, Qdrant, and TEI embedding.
- The compose file is `infra/education-data-qa/docker-compose.yaml`; use that path if invoking Docker Compose from the repo root.
- MongoDB is required for chat history in Iteration 04/05. It is part of `infra/education-data-qa/docker-compose.yaml` as `mongodb` using the local `mongo:7.0` image.
- Milvus and MinIO appear only in old document/search code scheduled for deletion in Iteration 04; they are not part of the education data QA path.
- Global `/health` defaults to required dependency `mongodb` only via `HEALTH_REQUIRED_DEPENDENCIES=mongodb`; do not add Milvus/MinIO for the current Iteration 04/05 path.
- TEI `cpu-1.9` on port `8081` is the verified embedding service. Prior `cpu-1.8` panicked on real WSL CPU `/embed` requests.
- Elasticsearch single-node health is expected to be `yellow` because replicas are unassigned; this is acceptable for local smoke.
- Do not parse TEI output with `curl | python3 - <<'PY'`; that feeds the script through stdin and makes Python treat JSON as code. Use Python `urllib`/`requests` or save/pipe through a separate script.

## Iteration Environment Matrix

| Iteration | Required services | Required app process | Main verification |
|-----------|-------------------|----------------------|-------------------|
| 03 LLM NL2SQL | MySQL `3306`, ES `9200`, Qdrant `6333`, TEI `8081`, OpenAI-compatible LLM key | FastAPI on `8000` only for smoke | `cd education_brain && SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh` |
| 04 chat + visual integration | Iteration 03 services + MongoDB `27017` for chat history | FastAPI `8000`; frontend dev server only for browser QA | `SMOKE_STAGE=chat`, `SMOKE_STAGE=visual`, then `SMOKE_STAGE=e2e` after Mongo/history is implemented |
| 05A data bootstrap | Iteration 03 services + MongoDB for history environment consistency | Data generator commands + FastAPI for meta smoke | `generate.main --profile smoke`, `build_meta --recreate`, `SMOKE_STAGE=bootstrap` once implemented |
| 05B Meta QA | Iteration 03 services + MongoDB `27017` for chat history | FastAPI for Meta QA smoke | `SMOKE_STAGE=meta_qa` once implemented |

## Check Results

### Latest Preflight: 2026-05-18 17:58:02 CST

| Category | Check | Status | Notes |
|----------|-------|--------|-------|
| Sandbox | Project dir writable | PASS | `test -w .` succeeded. |
| Sandbox | `/tmp` writable | PASS | `test -w /tmp` succeeded. |
| Sandbox | Subprocess creation | PASS | `zsh -lc 'echo subprocess-ok'` succeeded. |
| Network | npm registry | PASS | `curl -I https://registry.npmjs.org/` returned HTTP 200. |
| Network | PyPI | PASS | `curl -I https://pypi.org/simple/` returned HTTP 200. |
| Runtime | Python | PASS | Python 3.12.3. |
| Runtime | uv | PASS | uv 0.9.18. |
| Runtime | Node.js/npm | PASS | Node v20.19.6, npm 10.8.2. |
| Runtime | Docker Compose | PASS | Docker 29.1.3, Compose v2.40.3-desktop.1. |
| Deps | Backend venv | PASS | `education_brain/knowledge/.venv/bin/python` present. |
| Deps | Data generator venv | PASS | `data_ge/edu-data/.venv/bin/python` present. |
| Deps | Frontend deps | PASS | `education_brain_front/node_modules` and `node_modules/.bin/vite` present. |
| Services | MySQL | PASS | `mysqladmin ping` reports `mysqld is alive`. |
| Services | Elasticsearch | PASS | `_cluster/health` reachable; local status `yellow`. |
| Services | Qdrant | PASS | `/healthz` reports `healthz check passed`. |
| Services | TEI embedding | PASS | `/embed` returns 1024-dimensional vectors. |
| Services | FastAPI `8000` | INFO | Not expected to run persistently; start before smoke tests. |
| Services | MongoDB `27017` | PASS | `mongo:7.0` container is running; `admin.command('ping')` returned `ok: 1.0`. |
| Services | Milvus/MinIO | INFO | Not running and not required; old document/RAG code is scheduled for deletion in Iteration 04. |
| Workflow | Global health | PASS | `/health` returned `healthy` with required component `mongodb`. |
| Workflow | Analytics health | PASS | `/analytics/health` returned `healthy`; counts: 66 tables, 738 columns, 14 metrics, 21 joins, 17 dimensions. |
| Workflow | Backend focused tests | PASS | `12 passed, 1 warning`. |
| Workflow | Frontend tests | PASS | `4 passed`. |
| Workflow | Frontend build | PASS | `vite build` succeeded with current split chunks; no large chunk warning. |
| Workflow | Backend import | PASS | `PYTHONPATH=. knowledge/.venv/bin/python -c "from knowledge.api.app import app"` succeeded. |
| Workflow | Git state | INFO | Branch `main`; worktree was clean before Iteration 04 preflight documentation updates. |

## Verified Commands

### Start Data QA Services

```bash
cd infra/education-data-qa
docker compose up -d
docker compose ps
```

### Rebuild Smoke Data And Meta

These commands rewrite the local `edu` database and meta indexes. Run them only when intentionally refreshing smoke data.

```bash
cd data_ge/edu-data
uv run init_db.py
uv run -m generate.main --profile smoke

cd ../../education_brain
PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta \
  --config ../data_ge/edu-data/meta/education_meta.yaml \
  --recreate
```

### Start API Before HTTP Smoke

```bash
cd education_brain
PYTHONPATH=. knowledge/.venv/bin/uvicorn knowledge.api.app:app --host 0.0.0.0 --port 8000
```

### Iteration 03 Gate

```bash
cd education_brain
PYTHONPATH=. knowledge/.venv/bin/python -m pytest \
  knowledge/tests/test_data_qa_pipeline.py \
  knowledge/tests/test_llm_nl2sql_pipeline.py -q

SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh
```

### Frontend Gate

```bash
cd education_brain_front
npm test
npm run build
```

## Actions Taken

1. Inspected toolchain versions, write access, subprocess creation, network reachability, dependency presence, Docker Compose status, and service ports.
2. Verified MySQL, Elasticsearch, Qdrant, and TEI embedding health.
3. Verified backend focused NL2SQL tests: `12 passed, 1 warning`.
4. Verified frontend tests: `4 passed`.
5. Verified frontend build: `vite build` succeeded.
6. Added MongoDB to `infra/education-data-qa/docker-compose.yaml` and `.env.example`.
7. Started MongoDB from the local `mongo:7.0` image and verified `mongodb://localhost:27017`.
8. Updated global `/health` to check only configured required dependencies by default, so missing Milvus/MinIO does not mark the current integration environment degraded.

## User Actions Required

None for Iteration 03/04 environment setup. Iteration 04 implementation still needs the `/chat/query mode=data_qa` and history persistence code changes.

Milvus/MinIO are intentionally not part of the current preparation. Iteration 04 is expected to delete old document ingestion/RAG/file-storage code instead of validating it.

## Incident Log

### 2026-05-18 — Smoke Failed Because API Was Not Running

- **Error:** `服务未启动或不可达: http://localhost:8000/health`.
- **Category:** workflow.
- **Resolution:** Start FastAPI with the verified uvicorn command before running `SMOKE_STAGE=llm`.
- **New constraint:** Smoke scripts are HTTP-level checks; they do not start the API themselves.

### 2026-05-18 — TEI Output Parse Mistake

- **Error:** Python `SyntaxError` after `curl ... | python3 - <<'PY'`.
- **Category:** workflow.
- **Resolution:** Use Python `urllib`/`requests` to call `/embed` and parse JSON in the same process.
- **New constraint:** Avoid stdin heredoc plus piped JSON for service health parsing.
