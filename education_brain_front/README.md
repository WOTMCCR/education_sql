# Frontend

React/Vite frontend for the Education Analytics Assistant.

The current product surface is a chat workspace with two modes:

- **Data Introduction**: metadata explanations, available tables, metric definitions, supported questions, and operating insights.
- **Data Analysis**: concrete numeric answers, trend charts, rankings, tables, SQL, metric lineage, and execution trace.

## Development

```bash
npm install
VITE_API_BASE_URL=http://127.0.0.1:8000 VITE_USE_MOCK=false npm run dev -- --host 127.0.0.1 --port 5173
```

## Build

```bash
npm test
npm run build
```

See the repository root `README.md` for screenshots and the full project overview.
