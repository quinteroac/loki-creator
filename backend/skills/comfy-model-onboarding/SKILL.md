---
name: comfy-model-onboarding
description: Configure local comfy-agent-tools model profiles and defaults. Use when the user has no .comfy-agent-tools.json config, wants to set models_dir, change a default capability profile, add a new checkpoint or fine-tune of a supported architecture, or diagnose profile/config errors such as unknown_profile, unsupported_capability, architecture_mismatch, config_error, missing_model_file, or unsupported_architecture.
metadata:
  loki:
    visibility: internal
    capabilities: [model-configuration, diagnostics, comfy]
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: diagnostic
---

# comfy-model-onboarding

Use this skill to help configure model profiles for the Comfy image skills,
`comfy-videogen`, and `comfy-musicgen`. Profiles are selected by capability, not
by an entire skill or CLI. A profile is not an architecture: for example `ltx23`
is the architecture/adapter, while `ltx23-10eros` is one profile of that architecture.

For loose LoRAs, naming, moving, or selecting ad hoc LoRAs, use
`comfy-lora-onboarding`. Do not add one-off style LoRAs to model profiles unless
the user wants that LoRA to become a persistent default.

If `comfy-models` is not available, use `comfy-tools-setup` first. In this
repository, prefer `uv run comfy-models`; outside the repo, let
`comfy-tools-setup` install the CLIs with `uv tool`.

## Setup

If `.comfy-agent-tools.json` is missing, ask the user where they want to store
or use ComfyUI model files, then initialize and validate the local config:

```bash
uv run comfy-models init
uv run comfy-models set-models-dir <models_dir>
uv run comfy-models validate
uv run comfy-models show
```

If config already exists, respect its `models_dir` unless the user asks to
change it.

## Supported Architectures

Only configure these architectures in v1:

- `qwen-image-edit`: base profile `qwen-edit2511`, capabilities `imagegen.generate`, `imagegen.edit`.
- `anima`: base profile `anima-base`, capability `imagegen.generate`.
- `flux-klein`: base profile `flux-klein-9b-snofs`, capabilities `imagegen.generate`, `imagegen.edit`.
- `krea2`: base profiles `krea2-turbo` and `krea2-turbo-int4-fast`, capability
  `imagegen.krea2-generate`.
- `upscale-model`: base profile `clear-reality`, capability `imagegen.upscale`.
- `rtx-vsr`: base profile `rtx-vsr`, capabilities `imagegen.rtx-upscale`, `videogen.rtx-upscale`; no model files.
- `ltx23`: base profile `ltx23-10eros`, capabilities `videogen.t2v`, `videogen.i2v`, `videogen.flf2v`, `videogen.ia2av`.
- `minimax-h3`: local MiniMax H3 profile, capabilities `videogen.minimax-h3-t2v`, `videogen.minimax-h3-i2v`, and `videogen.minimax-h3-r2v`, with native synchronized audio.
- `ace-step-1.5`: base profile `ace15-base`, capability `musicgen.generate`.
- `seedance2-api`: remote profile `seedance2-api`, capabilities `videogen.seedance2-t2v`, `videogen.seedance2-r2v`, `videogen.seedance2-flf2v`.
- `grok-imagine-api`: remote profile `grok-imagine-api`, capabilities `imagegen.grok-generate`, `imagegen.grok-edit`.

If a model is SDXL, Wan, a new audio architecture, or any Flux variant other than
the built-in `flux-klein` adapter, do not
pretend it is supported. Explain that a new architecture adapter is required.

Seedance 2.0 is not a local checkpoint or fine-tune architecture. Do not create
local profiles for it, do not route it through `models_dir`, and do not use
`comfy-model-downloader`. It requires `COMFY_ORG_API_KEY` and a
`comfy-diffusion` version that vendors the ByteDance Seedance 2.0 API nodes.

Grok Imagine is also remote-only. Do not create local checkpoint profiles for
`grok-imagine-api`, do not route it through `models_dir`, and do not use
`comfy-model-downloader`. It requires `COMFY_ORG_API_KEY` and a
`comfy-diffusion` version that vendors the Grok API nodes.

NVIDIA RTX VSR is also not a checkpoint architecture. Do not download or
validate model files for `rtx-vsr`; image RTX upscale uses
`imagegen.rtx-upscale` and video RTX upscale uses `videogen.rtx-upscale` with
local NVIDIA RTX/CUDA runtime dependencies.

## Onboarding Flow

1. Inspect the user-provided path and current models dir with non-destructive
   shell commands such as `ls`, `find`, or safetensors metadata reads.
2. Identify architecture first, then choose a base profile.
3. For fine-tunes, prefer `extends` and override only changed model paths.
4. Validate the profile before making it a default.
5. Set defaults per capability only where the profile supports that capability.
6. Recommend a small smoke test.

## Fine-Tune Examples

LTX 2.3 checkpoint/fine-tune:

```bash
uv run comfy-models add-profile my-ltx23-finetune \
  --extends ltx23-10eros \
  --checkpoint checkpoints/my_ltx23_finetune.safetensors

uv run comfy-models validate-profile my-ltx23-finetune
uv run comfy-models set-default videogen.t2v my-ltx23-finetune
```

Qwen Image Edit fine-tune:

```bash
uv run comfy-models add-profile my-qwen-edit \
  --extends qwen-edit2511 \
  --unet diffusion_models/my_qwen_edit.safetensors

uv run comfy-models validate-profile my-qwen-edit
uv run comfy-models set-default imagegen.generate my-qwen-edit
uv run comfy-models set-default imagegen.edit my-qwen-edit
```

Anima fine-tune or compatible LoRA:

```bash
uv run comfy-models add-profile my-anima \
  --extends anima-base \
  --unet diffusion_models/my_anima.safetensors \
  --lora loras/my_anima_turbo_lora.safetensors

uv run comfy-models validate-profile my-anima
uv run comfy-models set-default imagegen.generate my-anima
```

Anima profiles generate images only. They do not support `imagegen.edit`. Keep
turbo Anima profiles at `steps=8` and `cfg=1.0` unless the user explicitly wants
to test a slower non-turbo profile.

FLUX.2 Klein 9B SNOFS:

```bash
uv run comfy-models download-profile flux-klein-9b-snofs --dry-run
uv run comfy-models download-profile flux-klein-9b-snofs --yes
uv run comfy-models validate-profile flux-klein-9b-snofs
uv run comfy-models set-default imagegen.generate flux-klein-9b-snofs
uv run comfy-models set-default imagegen.edit flux-klein-9b-snofs
```

This profile uses gated Black Forest Labs FLUX.2 Klein 9B FP8 weights plus the
SNOFS LoRA. Use `HF_TOKEN` after the user accepts the FLUX license terms. Do not
redistribute the weights, and do not use this profile for a public/commercial
generation service without separate licensing. Flux Klein edits follow the
official distilled image-edit workflow from `comfy-diffusion`.

Krea2 Turbo:

```bash
uv run comfy-models download-profile krea2-turbo --dry-run
uv run comfy-models download-profile krea2-turbo --yes
uv run comfy-models validate-profile krea2-turbo
uv run comfy-models set-default imagegen.krea2-generate krea2-turbo
```

This profile uses `diffusion_models/krea2_turbo_fp8_scaled.safetensors`,
`text_encoders/qwen3vl_4b_fp8_scaled.safetensors`, and
`vae/qwen_image_vae.safetensors`. It is image generation only and does not
support `imagegen.edit` or ad hoc `--extra-lora` arguments.

Krea2 Turbo INT4 Fast:

```bash
uv run comfy-models download-profile krea2-turbo-int4-fast --yes
uv run comfy-models validate-profile krea2-turbo-int4-fast
```

This profile requires the locally supplied
`diffusion_models/krea2_turbo_convrot_int4_fast.safetensors`. The downloader
can fetch the shared Krea2 text encoder and VAE but cannot retrieve that INT4
UNet. Use it per invocation through Loki's Krea2 profile picker; do not make it
the persistent default unless the user asks.

NVIDIA RTX VSR:

```bash
uv run comfy-imagegen rtx-upscale --input path/to/input.png --resolution 1080p --quality ULTRA --out outputs
uv run comfy-models set-default imagegen.rtx-upscale rtx-vsr
```

This profile has no model files. Missing NVIDIA RTX/CUDA or `nvidia-vfx`
dependencies must be fixed through the Comfy tool runtime, not the model
downloader.

ACE-Step 1.5 variant:

```bash
uv run comfy-models add-profile my-ace15 \
  --extends ace15-base \
  --unet diffusion_models/my_ace15.safetensors

uv run comfy-models validate-profile my-ace15
uv run comfy-models set-default musicgen.generate my-ace15
```

## Smoke Tests

- Image generate: `uv run comfy-imagegen generate --prompt "simple cinematic portrait" --width 512 --height 512`
- Krea2 generate: `uv run comfy-imagegen krea2-generate --prompt "simple cinematic portrait" --width 512 --height 512`
- Image edit: use a small existing PNG and a simple prompt.
- Upscale: use a small existing PNG.
- RTX image upscale: use a small existing PNG with `rtx-upscale --resolution 1080p --quality ULTRA`.
- Video: use `--length 49 --fps 24`.
- Music: use `--duration 30 --steps 8 --cfg 1`.

Do not install custom nodes or add unsupported adapters in this skill. For
missing files in supported built-in profiles, use `comfy-model-downloader`.
Keep changes scoped to `.comfy-agent-tools.json` and validated profile defaults.
