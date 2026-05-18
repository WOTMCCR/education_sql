# Project Operating Notes

## Environment

- Runtime verified on 2026-05-18: Python 3.12.3, `uv 0.9.18`, Node.js v20.19.6, npm 10.8.2, Docker Compose v2.40.3.
- Project-local data QA services live in `infra/education-data-qa/` and expose MySQL `3306`, Elasticsearch `9200`, Kibana `5601`, Qdrant `6333/6334`, and TEI embedding `8081`.
- MySQL defaults for Iteration 01 are `root/123321`, database `edu`, matching `data_ge/edu-data/.env.example`.
- The backend package is importable from `education_brain` with `PYTHONPATH=.`. The verified local environment is `education_brain/knowledge/.venv`.
- Verified build command: `cd education_brain && PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta --config ../data_ge/edu-data/meta/education_meta.yaml --recreate`.
- Verified API command: `cd education_brain && PYTHONPATH=. knowledge/.venv/bin/uvicorn knowledge.api.app:app --host 0.0.0.0 --port 8000`.
- TEI CPU `cpu-1.9` with the local `bge-large-zh-v1.5` Candle backend is the verified analytics embedding path. `cpu-1.8` could start but panicked on real `/embed` requests on this WSL host.
- Iteration 01 smoke passed with `cd education_brain && SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh`.
