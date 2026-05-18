# Education Data QA Local Environment

This directory contains the project-local Docker environment for Iteration 01.

## Services

| Service | URL / port | Purpose |
|---|---|---|
| MySQL | `127.0.0.1:3306` | `edu` business tables and `meta_*` tables |
| Elasticsearch | `http://127.0.0.1:9200` | Dimension value retrieval |
| Kibana | `http://127.0.0.1:5601` | Elasticsearch debugging |
| Qdrant | `http://127.0.0.1:6333` | Column and metric vector retrieval |
| Embedding | `http://127.0.0.1:8081` | Text embedding API |

## Start

```bash
cd infra/education-data-qa
docker compose up -d
docker compose ps
```

The default MySQL credentials match `data_ge/edu-data/.env.example`:

```text
host=127.0.0.1
port=3306
user=root
password=123321
database=edu
```

## Local Overrides

Copy `.env.example` to `.env` if ports or the local BGE model path need to be
changed. Do not commit `.env`.

```bash
cp .env.example .env
```

`BGE_MODEL_DIR` must point to a local `bge-large-zh-v1.5` model directory. The
model weights are intentionally not stored in this repository.

The embedding service uses TEI `cpu-1.9`. TEI `cpu-1.8` could start with this
local BGE model on this WSL host, but real `/embed` requests triggered an
internal queue panic.

## Probes

```bash
mysqladmin ping -h 127.0.0.1 -P 3306 -uroot -p123321
curl -fsS http://127.0.0.1:9200
curl -fsS http://127.0.0.1:6333/healthz
curl -fsS http://127.0.0.1:8081/health
curl -fsS http://127.0.0.1:8081/embed \
  -H 'Content-Type: application/json' \
  -d '{"inputs":["教育问数"]}'
```

## Full Iteration 01 Flow

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
