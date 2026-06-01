# Loki Creator

Workspace creativo con frontend React sobre Bun y backend Python sobre uv.

## Desarrollo

```bash
bun run dev
```

Este comando levanta el frontend y el backend al mismo tiempo.

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

El frontend espera la API en `http://localhost:8001`. Puedes cambiarlo con `VITE_API_URL`.
