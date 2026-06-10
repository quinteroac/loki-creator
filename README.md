# Loki Creator

Creative workspace with a React frontend on Bun and a Python backend on uv.

## Development

```bash
bun run dev
```

This command starts the frontend and backend at the same time.

## Frontend

```bash
cd frontend
bun install
bun run dev
```

## Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8001
```

The frontend expects the API at `http://localhost:8001`. You can change it with `VITE_API_URL`.
