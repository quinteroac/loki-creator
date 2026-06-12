# RunPod Deployment Guide

This guide explains how to build, deploy, authenticate, and operate the Loki
Creator RunPod image.

## Overview

The RunPod image is CLI-ready and credential-free:

- It installs Loki, Bun, uv, the FastAPI backend, the agent bridge, nginx, SSH,
  ffmpeg, lightweight Comfy wrappers, and the production frontend build.
- It installs the core CLIs during image build: `pi`, `codex`, `grok`, `agy`,
  and `runpodctl`.
- It installs `comfy-agent-tools` plus PyTorch CUDA 12.4 on demand into the
  persistent `/workspace/.loki/runtime/comfy-agent-tools` directory.
- It serves the frontend, backend, and agent bridge through one public HTTP
  port: `3000`.
- It stores all durable state on the RunPod volume mounted at `/workspace`.
- It does not bake provider API keys, OAuth tokens, or user credentials into
  the image.

The image entrypoint starts:

- nginx on `3000`
- FastAPI backend on `8001`
- agent bridge on `8787`
- `sshd` for remote commands through RunPod SSH

## Persistent Storage

The container links runtime state into `/workspace`:

- `/root/.pi -> /workspace/.pi`
- `/root/.codex -> /workspace/.codex`
- `/root/.grok -> /workspace/.grok`
- `/root/.gemini -> /workspace/.gemini`
- `/opt/loki-creator/.loki -> /workspace/.loki`
- `/opt/loki-creator/.comfy-agent-tools.json -> /workspace/.comfy-agent-tools.json`
- `/workspace/.loki/runtime/comfy-agent-tools` stores the on-demand Comfy CLI
  environment.

This means projects, imports, generated artifacts, CLI auth state, model config,
and downloaded models survive Pod restarts and stops as long as the RunPod
volume is preserved.

## Build The Image

Copy and edit the deployment config:

```bash
cp deploy/runpod/runpod.config.example.env deploy/runpod/runpod.config.env
$EDITOR deploy/runpod/runpod.config.env
```

Set at least:

```env
GHCR_IMAGE=ghcr.io/YOUR_GITHUB_OWNER/loki-creator
RUNPOD_GPU_ID=NVIDIA GeForce RTX 4090
```

Build and push:

```bash
scripts/runpod/build-image.sh
```

Useful build overrides:

```bash
IMAGE_TAG=$(git rev-parse --short HEAD) TAG_LATEST=1 scripts/runpod/build-image.sh
PUSH=0 scripts/runpod/build-image.sh
```

The build script intentionally does not accept provider secrets.

## Deploy A Pod

Configure the local RunPod CLI:

```bash
runpodctl doctor
```

Deploy:

```bash
scripts/runpod/deploy-pod.sh
```

The deploy script creates a persistent Pod from the configured GHCR image,
mounts `/workspace`, exposes `3000/http` and `22/tcp`, and prints the Loki URL:

```text
https://<pod-id>-3000.proxy.runpod.net
```

If your GHCR image is private, configure registry auth in RunPod and set
`RUNPOD_REGISTRY_AUTH_ID` in `deploy/runpod/runpod.config.env`.

## Remote Commands

All post-deployment actions use:

```bash
scripts/runpod/remote.sh <pod-id> <command...>
```

The wrapper calls `runpodctl ssh info <pod-id>`, extracts the SSH command, and
runs the command with an interactive TTY. Opening a shell is also supported:

```bash
scripts/runpod/remote.sh <pod-id>
```

## Health Check

Run:

```bash
scripts/runpod/doctor.sh <pod-id>
```

This executes `loki-doctor` inside the Pod. It checks:

- required CLI binaries and versions
- GPU visibility through `nvidia-smi`
- `sshd`
- persistent auth/config directories
- backend health
- agent bridge health
- frontend proxy health

## Authentication

Authenticate after deployment. The image contains the CLIs; credentials are
created remotely and persisted under `/workspace`.

```bash
scripts/runpod/auth.sh <pod-id> codex
scripts/runpod/auth.sh <pod-id> pi
scripts/runpod/auth.sh <pod-id> grok
scripts/runpod/auth.sh <pod-id> agy
```

Expected behavior:

- `codex`: starts the Codex login flow.
- `pi`: starts Pi; use `/login` inside Pi, then exit.
- `grok`: starts Grok Build login if available, otherwise first-run Grok auth.
- `agy`: starts Antigravity CLI auth; in SSH it should print the local
  authorization URL.

For API-only providers, store runtime secrets after deployment:

```bash
scripts/runpod/auth.sh <pod-id> provider openrouter
scripts/runpod/auth.sh <pod-id> provider comfy
scripts/runpod/auth.sh <pod-id> provider hf
scripts/runpod/auth.sh <pod-id> provider civitai
```

Runtime secrets are written to:

```text
/workspace/.loki/runpod/runtime-secrets.env
```

The file is written with `0600` permissions. Restart the Pod after adding a
runtime secret so the backend and bridge inherit the updated environment.

## Models

Comfy models are downloaded on demand into:

```text
/workspace/.loki/models/comfyui
```

Use:

```bash
scripts/runpod/models.sh <pod-id> list
scripts/runpod/models.sh <pod-id> show
scripts/runpod/models.sh <pod-id> download imagegen.generate
scripts/runpod/models.sh <pod-id> download videogen.i2v
scripts/runpod/models.sh <pod-id> validate
```

To request model downloads on first boot, set:

```env
LOKI_MODEL_CAPABILITIES=imagegen.generate,videogen.i2v
```

Keep model downloads selective. The default image does not bake models into the
container.

## Image Files

The RunPod implementation lives in:

- `deploy/runpod/Dockerfile`: image build.
- `deploy/runpod/bin/`: in-image commands.
- `deploy/runpod/nginx.conf`: public frontend/API/agent proxy.
- `scripts/runpod/`: local build, deploy, SSH, auth, model, and test wrappers.
- `.github/workflows/runpod-image.yml`: GHCR image build workflow.

## Troubleshooting

If Loki does not load, run:

```bash
scripts/runpod/doctor.sh <pod-id>
```

If remote commands cannot connect, confirm local RunPod SSH setup:

```bash
runpodctl doctor
runpodctl ssh info <pod-id>
```

If a CLI is installed but unauthenticated, rerun the matching auth wrapper. Auth
state should persist under `/workspace`.

If a model is missing, download only the required capability:

```bash
scripts/runpod/models.sh <pod-id> download <capability>
```

If runtime secrets were added with `loki-auth provider`, restart the Pod before
retrying the generation flow.
