# Project Operating Notes

## Environment

- Runtime verified on 2026-05-18: Python 3.12.3, `uv 0.9.18`, Node.js v20.19.6, npm 10.8.2, Docker 29.1.3, Docker Compose v2.40.3.
- Project-local data QA services live in `infra/education-data-qa/` and expose MySQL `3306`, MongoDB `27017`, Elasticsearch `9200`, Kibana `5601`, Qdrant `6333/6334`, and TEI embedding `8081`; these were running and health-checked on 2026-05-18.
- The repo-root Docker Compose file path is `infra/education-data-qa/docker-compose.yaml`.
- MySQL defaults for Iteration 01 are `root/123321`, database `edu`, matching `data_ge/edu-data/.env.example`.
- The backend package is importable from `education_brain` with `PYTHONPATH=.`. The verified local environment is `education_brain/knowledge/.venv`.
- Verified build command: `cd education_brain && PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta --config ../data_ge/edu-data/meta/education_meta.yaml --recreate`.
- Verified API command: `cd education_brain && PYTHONPATH=. knowledge/.venv/bin/uvicorn knowledge.api.app:app --host 0.0.0.0 --port 8000`.
- HTTP smoke scripts require the API to be running first; if `/health` is unreachable, start uvicorn instead of rerunning smoke blindly.
- Iteration 03 gate is `cd education_brain && SMOKE_STAGE=llm ./knowledge/tests/smoke_test_data_qa.sh`; do not use `SMOKE_STAGE=all` as Iteration 03 acceptance because it includes chat/history/frontend later-stage dependencies.
- Iteration 04 chat/history work uses MongoDB on `27017`; `infra/education-data-qa` now includes a `mongodb` service using the local `mongo:7.0` image.
- Global `/health` defaults to `HEALTH_REQUIRED_DEPENDENCIES=mongodb`; Milvus `19530` and MinIO `9000` are old document/RAG dependencies scheduled for deletion in Iteration 04 and should not be required for current analytics + chat history integration.
- Verified test commands: `cd education_brain && PYTHONPATH=. knowledge/.venv/bin/python -m pytest knowledge/tests/test_data_qa_pipeline.py knowledge/tests/test_llm_nl2sql_pipeline.py -q`; `cd education_brain_front && npm test && npm run build`.
- Iteration 05A preflight on 2026-05-18 verified `SMOKE_STAGE=meta` against the running stack before destructive bootstrap rebuilds.
- Iteration 05B preflight on 2026-05-18 verified `SMOKE_STAGE=e2e` after the 05A bootstrap rebuild.
- TEI CPU `cpu-1.9` with the local `bge-large-zh-v1.5` Candle backend is the verified analytics embedding path. `cpu-1.8` could start but panicked on real `/embed` requests on this WSL host.
- Full environment notes and incident log: `docs/env-setup.md`.
