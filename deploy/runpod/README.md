# RunPod Deployment

This folder contains the RunPod image and deployment helpers for Loki Creator.
The image is CLI-ready: it installs the Loki runtime plus `pi`, `codex`, `grok`,
`agy`, lightweight Comfy wrappers, and `runpodctl`. The heavy Comfy/PyTorch CUDA
runtime is installed on demand into `/workspace/.loki/runtime/comfy-agent-tools`.
It does not bake provider credentials into the image.

For the end-to-end operator guide, see `docs/RUNPOD.md`.

## Build The Image

Copy the example config and set your image repository:

```bash
cp deploy/runpod/runpod.config.example.env deploy/runpod/runpod.config.env
$EDITOR deploy/runpod/runpod.config.env
```

Build and push to GHCR:

```bash
scripts/runpod/build-image.sh
```

Useful overrides:

```bash
IMAGE_TAG=$(git rev-parse --short HEAD) TAG_LATEST=1 scripts/runpod/build-image.sh
PUSH=0 scripts/runpod/build-image.sh
```

Provider secrets are intentionally not accepted by the build script.

## Deploy A Pod

Configure your local RunPod CLI first:

```bash
runpodctl doctor
```

Then deploy:

```bash
scripts/runpod/deploy-pod.sh
```

The script creates a persistent Pod, mounts `/workspace`, exposes port `3000`
for Loki, and prints the RunPod proxy URL:

```text
https://<pod-id>-3000.proxy.runpod.net
```

## Authenticate After Deployment

Authentication is done remotely over SSH, after the Pod exists. The wrapper uses
`runpodctl ssh info <pod-id>` and runs the command with an interactive TTY.

```bash
scripts/runpod/auth.sh <pod-id> codex
scripts/runpod/auth.sh <pod-id> pi
scripts/runpod/auth.sh <pod-id> grok
scripts/runpod/auth.sh <pod-id> agy
```

For API-only providers, store runtime secrets after deployment:

```bash
scripts/runpod/auth.sh <pod-id> provider openrouter
scripts/runpod/auth.sh <pod-id> provider comfy
scripts/runpod/auth.sh <pod-id> provider hf
scripts/runpod/auth.sh <pod-id> provider civitai
```

Runtime secrets are written to `/workspace/.loki/runpod/runtime-secrets.env`
with `0600` permissions. Restart the Pod after adding a runtime secret so Loki
services inherit the new environment.

## Models

Models are downloaded on demand into `/workspace/.loki/models/comfyui`.

```bash
scripts/runpod/models.sh <pod-id> list
scripts/runpod/models.sh <pod-id> download imagegen.generate
scripts/runpod/models.sh <pod-id> download imagegen.krea2-generate
scripts/runpod/models.sh <pod-id> download videogen.i2v
scripts/runpod/models.sh <pod-id> validate
```

You can also set `LOKI_MODEL_CAPABILITIES` in `runpod.config.env` for first
boot, for example:

```env
LOKI_MODEL_CAPABILITIES=imagegen.generate,imagegen.krea2-generate,videogen.i2v
```

`comfy-imagedescribe` expects the HuggingFace model directory
`LLM/Qwen-VL/Qwen3-VL-2B-Instruct` under `/workspace/.loki/models/comfyui`.
This Qwen3-VL directory is not auto-downloaded by `comfy-models`.

Krea2 INT4 Fast uses the `krea2-turbo-int4-fast` profile. Its optimized UNet is
local-only, so place `diffusion_models/krea2_turbo_convrot_int4_fast.safetensors`
under the models directory before selecting it in Loki. `comfy-models` can still
download the shared Krea2 text encoder and VAE.

NVIDIA RTX image/video upscaling uses the `rtx-vsr` profile and does not
download model files. It requires the Comfy tool runtime to include the NVIDIA
RTX/CUDA dependencies, including `nvidia-vfx`.

## Health Check

Run:

```bash
scripts/runpod/doctor.sh <pod-id>
```

Inside the Pod this calls `loki-doctor`, which verifies installed CLIs, Comfy
bootstrap wrappers, GPU visibility, persistent stores, backend health, agent
bridge health, and the frontend proxy.

## Persistent Paths

The image links runtime state to the mounted `/workspace` volume:

- `/root/.pi -> /workspace/.pi`
- `/root/.codex -> /workspace/.codex`
- `/root/.grok -> /workspace/.grok`
- `/root/.gemini -> /workspace/.gemini`
- `/opt/loki-creator/.loki -> /workspace/.loki`
- `/opt/loki-creator/.comfy-agent-tools.json -> /workspace/.comfy-agent-tools.json`
- `/workspace/.loki/runtime/comfy-agent-tools` stores the on-demand Comfy CLI
  environment.

Stopping or restarting the Pod preserves auth, projects, artifacts, model
config, the Comfy runtime, and downloaded models.
