# Education Analytics Assistant

An AI-assisted analytics workspace for education operations. The application lets operators, academic affairs staff, and managers ask natural-language questions about enrollment, revenue, refunds, completion, attendance, service tickets, and other operational data. It returns structured answers with charts, tables, metric definitions, generated SQL, and execution trace details.

The project is organized as a full-stack prototype:

- **Backend**: FastAPI service for chat, natural-language-to-SQL analytics, metadata retrieval, and conversation history.
- **Frontend**: React + Vite chat interface with chart rendering, table fallback, metric explanations, and mobile-friendly layout.
- **Analytics metadata**: configurable business metrics, dimensions, table relationships, and semantic retrieval support.
- **Demo data generator**: synthetic education-operations data used for local development and product demos.

## Screenshots

### Data Analysis

Ask a concrete business question and receive a visual result with supporting table data. This example asks for current-month enrollment.

![Data analysis result](assets/readme/data-analysis-result.png)

### Revenue Trend

Trend questions render as line charts with the result table preserved below the chart.

![Revenue trend](assets/readme/revenue-trend.png)

### Campus Ranking

Dimension and ranking questions render as bar charts with sorted rows.

![Campus ranking](assets/readme/campus-ranking.png)

### Completion Trend

Teaching and learning metrics, such as completion rate, use the same traceable analysis flow.

![Completion trend](assets/readme/completion-trend.png)

### Refund Metric

Refund-related metrics are returned as structured metric cards and tables.

![Refund metric](assets/readme/refund-stat.png)

### Data Introduction

Ask what data exists, what metrics mean, or which questions are supported. The system answers from metadata without running SQL.

![Data introduction result](assets/readme/data-introduction-result.png)

### Automatic Routing

Discovery questions such as "what tables are available?" are routed to data introduction even if the user is currently in analysis mode.

![Automatic routing to data introduction](assets/readme/auto-route-data-introduction.png)

### Multi-turn History

Analysis and introduction answers share the same conversation history and can be restored after refresh.

![Multi-turn history](assets/readme/multi-turn-history.png)

### Trace Panel

Every analysis result keeps SQL, metric lineage, table relationships, assumptions, and execution stages available for inspection.

![Trace panel](assets/readme/trace-panel.png)

### Mobile Layout

The chat interface remains usable on narrow screens.

![Mobile chat](assets/readme/mobile-chat.png)

## What It Can Do

- Answer operational questions such as:
  - "What is this month's enrollment?"
  - "What is this month's revenue?"
  - "What is this month's refund amount?"
  - "How has completion rate changed over the last three months?"
  - "How has revenue changed over the last 30 days?"
  - "Which campus has the highest enrollment?"
  - "What metrics should a campus manager review every day?"
  - "What tables and fields are available?"
- Render multiple result types:
  - single metric cards
  - line charts
  - bar charts
  - tables
  - structured error states
- Explain metric definitions, dimensions, fields, and table relationships.
- Keep generated SQL, metric lineage, joins, assumptions, and trace steps available in an expandable debug panel.
- Preserve conversation history with structured blocks, so charts and metadata citations can be restored after reload.
- Block unsafe SQL-style user input before execution.

## Architecture

```text
education_brain_fullstack/
├── education_brain/          # FastAPI backend and analytics pipeline
├── education_brain_front/    # React/Vite frontend
├── data_ge/edu-data/         # synthetic demo data and metadata definitions
├── infra/                    # optional local service templates
└── assets/readme/            # public README screenshots
```

Backend flow:

```text
Chat request
  ├─ data-analysis question -> metadata recall -> SQL generation -> SQL validation -> query execution -> chart/table response
  └─ data-introduction question -> metadata retrieval -> LLM explanation -> citations
```

Frontend flow:

```text
Chat page
  ├─ Data Analysis mode: renders DataQaResult blocks as charts, tables, SQL, metric definitions, and trace
  └─ Data Introduction mode: renders markdown explanations and metadata citations
```

## Key Concepts

### Data Analysis

Use this mode for questions that need actual numbers, ranking, trends, or detailed records. It can generate and execute read-only SQL against the configured analytics database.

Examples:

- "What is this month's total revenue?"
- "What is this month's enrollment?"
- "What is this month's refund amount?"
- "Show revenue trend for the last 30 days."
- "Which campus has the highest revenue?"

### Data Introduction

Use this mode to understand the data catalog, metric definitions, supported dimensions, and recommended analysis directions. It does not execute SQL.

Examples:

- "What tables are available?"
- "What does paid revenue mean?"
- "Which metrics should I monitor every day?"
- "What revenue-related questions can I ask?"

### Automatic Routing

The backend automatically routes discovery-style questions to Data Introduction, including prompts such as:

- "What data is available?"
- "What tables are available?"
- "What can I ask?"
- "What insights should I focus on?"
- "Which metrics should I monitor?"

This keeps users from accidentally sending catalog or strategy questions into the SQL pipeline.

## Tech Stack

- Python 3.12
- FastAPI
- Pydantic
- MySQL-compatible analytics store
- MongoDB-compatible chat history store
- Qdrant-compatible vector retrieval
- Elasticsearch-compatible dimension-value retrieval
- OpenAI-compatible chat completion API
- React 18
- Vite
- Recharts
- Tailwind-style utility CSS

## Local Development

This repository does not include private credentials or production configuration. Create local environment files from the example files and fill in your own values.

### Backend

```bash
cd education_brain
PYTHONPATH=. knowledge/.venv/bin/uvicorn knowledge.api.app:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd education_brain_front
VITE_API_BASE_URL=http://127.0.0.1:8000 VITE_USE_MOCK=false npm run dev -- --host 127.0.0.1 --port 5173
```

### Frontend Build

```bash
cd education_brain_front
npm test
npm run build
```

## Configuration

The backend expects these groups of configuration values:

- chat history database connection
- analytics SQL database connection
- vector retrieval endpoint
- dimension-value search endpoint
- embedding endpoint
- OpenAI-compatible LLM endpoint and model

Do not commit real credentials. Keep local secrets in `.env` or deployment-specific secret managers.

## API Surface

Primary endpoints:

- `POST /chat/query`
- `GET /chat/history`
- `POST /analytics/query`
- `GET /analytics/health`
- `GET /analytics/meta/metrics`
- `GET /analytics/meta/columns`
- `GET /analytics/meta/values`

`/chat/query` supports two product modes:

- `data_qa`: data analysis, may generate and execute read-only SQL
- `meta_qa`: data introduction, explains metadata and supported questions

## Verification Snapshot

Recent local verification against the included `edu-data` demo domain covered:

- backend route tests for chat, data analysis, metadata introduction, history, and automatic routing
- frontend unit tests and production build
- browser-driven manual flows with Playwright:
  - enrollment, revenue, refund, and completion metrics
  - line, bar, stat, table, and trace rendering
  - metadata introduction
  - automatic routing from analysis to introduction
  - history restore
  - mobile viewport

Current demo-data acceptance notes:

- Supported successfully in the latest run: current-month enrollment, current-month revenue, current-month refund amount, 30-day revenue trend, campus enrollment ranking, three-month completion-rate trend, metadata discovery, and full "question -> parse -> execute -> result" UI flow.
- Known extension areas: some complex course-series refund-rate prompts and week-over-week renewal wording need stronger metric coverage and prompt routing. The framework returns structured errors instead of breaking the service.

## Security Notes

- Real API keys, database passwords, and internal service endpoints are not required in the repository.
- SQL execution is validated and unsafe user input is blocked.
- Metadata introduction does not execute SQL.
- LLM trace data is summarized and does not expose full prompts or raw responses to the frontend.

## Repository Hygiene

The public repository is intended to keep source code, sanitized examples, and product screenshots. Local verification artifacts, internal planning notes, environment files, generated databases, and private credentials should stay out of version control.
