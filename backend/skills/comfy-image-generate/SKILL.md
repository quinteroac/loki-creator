---
name: comfy-image-generate
description: Generate new raster images with comfy-diffusion, including local Anima Base v1.0 with turbo LoRA, FLUX.2 Klein 9B SNOFS, Qwen Image Edit 2511 generation, and remote Grok Imagine API nodes. Use for text-to-image generation from the current machine with outputs saved into the workspace. Do not use for editing existing images, upscaling, video, music, voice, model downloads, custom node installation, or ComfyUI server workflows.
metadata:
  loki:
    visibility: user
    capabilities: [image-generation, raster-card-output, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    arguments:
      - id: modelProfile
        label: Image model
        description: Choose the Comfy generation model profile.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: anima-base
            label: Anima Base
            description: Anime and illustration generation with Anima Base v1.0 + Turbo LoRA. Requires Danbooru-style tag prompts.
          - value: anima-preview3-turbo
            label: Anima Preview3
            description: Anime and illustration generation with Anima Preview3 + Turbo LoRA. Requires Danbooru-style tag prompts.
          - value: flux-klein-9b-snofs
            label: FLUX Klein SNOFS
            description: FLUX.2 Klein 9B FP8 + SNOFS LoRA for local image generation.
          - value: qwen-edit2511
            label: Qwen Image Edit
            description: Qwen Image Edit 2511 used as a generation profile.
          - value: grok-imagine-api
            label: Grok Imagine API
            description: Remote Grok Imagine generation when COMFY_ORG_API_KEY is configured.
      - id: aspectRatio
        label: Aspect ratio
        description: Choose the image frame before generation.
        type: choice
        required: true
        askWhen: always
        order: 20
        options:
          - value: "1:1"
            label: Square
            description: Balanced square image.
          - value: "4:3"
            label: Landscape 4:3
            description: Classic horizontal frame.
          - value: "16:9"
            label: Widescreen
            description: Wide cinematic frame.
          - value: "9:16"
            label: Portrait
            description: Vertical mobile frame.
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 900
    output:
      packager: auto
      kind: image
---

# comfy-image-generate

Use this skill only for creating new images through the `comfy-imagegen` CLI.
Local modes use the models directory declared in this skill's Loki metadata.
If a supported built-in model is missing, use `comfy-model-downloader` to fetch
only the requested capability before running inference.

The CLI is quiet by default and prints only final JSON. Use `--verbose` only when
debugging ComfyUI runtime output, warnings, or progress bars.

If `comfy-imagegen` or `comfy-models` is not available, use
`comfy-tools-setup` first. In this repository, prefer `uv run comfy-imagegen`;
outside the repo, let `comfy-tools-setup` install the CLIs with `uv tool`.

At the start of every image workflow, start or reuse the local Comfy Media
gallery for the active output directory:

```bash
uv run comfy-media gallery --out outputs --host 127.0.0.1 --port 8765
```

Use `comfy-media --help` only if the CLI is missing or behaves unexpectedly; do
not skip the gallery just because generation can run headless.

If `.comfy-agent-tools.json` is missing or the user wants to configure a new
checkpoint/fine-tune/default, use `comfy-model-onboarding` first.

## Required Arguments

Loki declares `modelProfile` and `aspectRatio` as required skill arguments. The
bridge asks these one at a time before the agent invokes this skill, then passes
the collected values to the action params.

Do not silently fall back to a default profile. The action rejects generation
without both `modelProfile` and `aspectRatio`.

Common generation profiles:

- `anima-base`: Anima Base v1.0 + Turbo LoRA, anime/illustration generation.
- `anima-preview3-turbo`: Anima Preview3 + Turbo LoRA, anime/illustration generation.
- `flux-klein-9b-snofs`: FLUX.2 Klein 9B FP8 + SNOFS LoRA, image generation.
- `qwen-edit2511`: Qwen Image Edit 2511, image generation.
- `grok-imagine-api`: remote Grok Imagine generation, only when the API key is configured.

If model validation fails with `missing_model_file`, use
`comfy-model-downloader` with `imagegen.generate` for the active generation
profile.

If the user asks to use or organize a LoRA by name or purpose, use
`comfy-lora-onboarding` to search `loras/<architecture>/` first and pass the
chosen file with `--extra-lora`.

## Commands

Local generation:

```bash
uv run comfy-imagegen generate \
  --prompt "masterpiece, best quality, score_7, safe, 1girl, anime style, cinematic lighting, detailed background" \
  --width 1024 \
  --height 1024 \
  --seed 42 \
  --extra-lora .loki/models/comfyui/loras/anima/realism-portrait.safetensors:0.8:0.0 \
  --out outputs
```

Grok Imagine generation:

```bash
COMFY_ORG_API_KEY=... uv run comfy-imagegen grok-generate \
  --prompt "A cinematic product photo of a translucent orange cassette player on wet asphalt" \
  --model grok-imagine-image \
  --resolution 1K \
  --aspect-ratio 1:1 \
  --out outputs
```

## Prompt Guidance

For `modelProfile` values `anima-base` and `anima-preview3-turbo`, the action
input prompt must be Danbooru-style tags. Never pass the user's natural-language
request directly to `--prompt` and never use a sentence for Anima. Rewrite the
request before invoking the Loki action.

Use a comma-separated tag list with lowercase tags and spaces instead of
underscores except score tags. Recommended positive prefix:
`masterpiece, best quality, score_7, safe, ...`. Put subject, count,
composition, clothing, expression, pose, lighting, camera, background, and style
as compact tags.

Example: user asks "una chica samurai en un bosque lluvioso con luz
cinematica"; Anima prompt should be:

```text
masterpiece, best quality, score_7, safe, 1girl, samurai, katana, forest, rain, cinematic lighting, dramatic shadows, detailed background, anime style
```

It must not be:

```text
Una chica samurai en un bosque lluvioso con luz cinematica
```

The Loki action rejects Anima generation when the prompt still looks like
natural language. Recommended negative guidance when adapting prompts:
`worst quality, low quality, score_1, score_2, score_3, artist name`.

Anima is not a realism model. It is intended for anime, illustration, and art.
Keep generation around 1MP, such as 1024x1024, 896x1152, or 1152x896.

Grok Imagine uses remote Comfy API nodes and is separate from local model
profiles. Do not route `grok-imagine-api` through `models_dir`,
`comfy-model-downloader`, local LoRAs, or checkpoint onboarding. Supported image
models are `grok-imagine-image-pro`, `grok-imagine-image`, and
`grok-imagine-image-beta`; supported resolutions are `1K` and `2K`.

FLUX.2 Klein 9B SNOFS uses natural-language prompts and is step-distilled for
`steps=4`, `cfg=1.0`. Keep dimensions divisible by 16. It requires gated Black
Forest Labs weights and SNOFS has a separate personal-use license: local image
generation is allowed, generated images may be sold, but public/commercial
generation services, derivative model creation, and weight redistribution are
not allowed without a separate license.

## Defaults

- Models directory: declared in Loki metadata as `.loki/models/comfyui`
- Anima diffusion model: `diffusion_models/anima-base-v1.0.safetensors`
- Anima text encoder: `text_encoders/qwen_3_06b_base.safetensors`
- VAE: `vae/qwen_image_vae.safetensors`
- Anima turbo LoRA: `loras/anima/anima-turbo-lora-v0.1.safetensors`
- Anima params: `steps=8`, `cfg=1.0`, `seed=0`
- FLUX profile: `flux-klein-9b-snofs`
- FLUX params: `steps=4`, `cfg=1.0`, `sampler=euler`, `seed=0`
- Grok profile: `grok-imagine-api`
- Grok provider: `comfy-api`
- Grok model: `grok-imagine-image`
- Grok params: `resolution=1K`, `aspect_ratio=1:1`, `number_of_images=1`, `seed=0`
- Dependency: `comfy-diffusion[comfyui,video]`

The Anima turbo LoRA expects `cfg=1.0`; increasing CFG can degrade or break the
expected turbo behavior.
