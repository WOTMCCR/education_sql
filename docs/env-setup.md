# Environment Setup

Last checked: 2026-05-18

## Stack Summary

- Backend: FastAPI package under `education_brain/knowledge`
- Frontend: Vite/React under `education_brain_front`
- Data generator: Python project under `data_ge/edu-data`
- Data QA dependencies: MySQL, Elasticsearch + IK, Kibana, Qdrant, TEI embedding

## Checks

| Check | Result | Notes |
|---|---|---|
| Required Iteration 01 docs | PASS | `edu.sql`, `edu-data/README.md`, and `standard/insight.md` exist |
| Docker Compose | PASS | `docker compose version` returns v2.40.3 |
| Python / uv | PASS | Python 3.12.3, `uv 0.9.18` |
| Node / npm | PASS | Node v20.19.6, npm 10.8.2 |
| Network | PASS | PyPI and npm registry reachable |
| Docker services | PASS | MySQL, ES, Kibana, Qdrant, and embedding containers start |
| Business data | PASS | `uv run init_db.py` and `uv run -m generate.main --profile smoke` completed |
| Meta build | PASS | 66 tables, 738 columns, 14 metrics, 21 joins, 17 dimensions |
| HTTP smoke | PASS | `SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh` passed 5 checks |

## Commands

```bash
cd infra/education-data-qa
docker compose up -d

cd ../../data_ge/edu-data
uv run init_db.py
uv run -m generate.main --profile smoke

cd ../../education_brain
PYTHONPATH=. knowledge/.venv/bin/python -m knowledge.analytics.build_meta --config ../data_ge/edu-data/meta/education_meta.yaml --recreate
PYTHONPATH=. knowledge/.venv/bin/uvicorn knowledge.api.app:app --host 0.0.0.0 --port 8000
SMOKE_STAGE=meta ./knowledge/tests/smoke_test_data_qa.sh
```

## Known Limitations

- `education_brain` currently relies on `education_brain/knowledge/.venv` for verified execution. Running plain `uv run` from `education_brain` is not the verified path unless a root project file is added later.
- TEI `cpu-1.8` with the mounted `bge-large-zh-v1.5` model can start but may panic on real `/embed` requests on this WSL host. The project-local compose uses `cpu-1.9`, verified with a 1024-dimensional `/embed` response.
