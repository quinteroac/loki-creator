# Loki Creator

Creative workspace with a React frontend on Bun and a Python backend on uv.

## Runtime Shape

Loki runs three local services:

- React frontend on Vite for development, or a static build in deployment.
- FastAPI backend on port `8001`.
- Agent bridge on port `8787`.

Local workspace data, projects, imports, generated artifacts, and model config
live under `.loki` by default.

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

## RunPod Deployment

Loki includes a RunPod-ready image and helper scripts. The image installs the
core CLIs during build (`pi`, `codex`, `grok`, `agy`, and `runpodctl`) but does
not include provider credentials. Comfy tools and their PyTorch CUDA runtime are
bootstrapped on demand into the persistent `/workspace` volume. Authentication
is performed after deployment through remote SSH commands.

Quick path:

```bash
cp deploy/runpod/runpod.config.example.env deploy/runpod/runpod.config.env
$EDITOR deploy/runpod/runpod.config.env
scripts/runpod/build-image.sh
runpodctl doctor
scripts/runpod/deploy-pod.sh
```

After deployment:

```bash
scripts/runpod/doctor.sh <pod-id>
scripts/runpod/auth.sh <pod-id> codex
scripts/runpod/auth.sh <pod-id> pi
scripts/runpod/auth.sh <pod-id> grok
scripts/runpod/auth.sh <pod-id> agy
scripts/runpod/models.sh <pod-id> download imagegen.generate
```

The Pod serves Loki at:

```text
https://<pod-id>-3000.proxy.runpod.net
```

RunPod deployment details live in [docs/RUNPOD.md](docs/RUNPOD.md). The image
implementation files live under [deploy/runpod](deploy/runpod).
