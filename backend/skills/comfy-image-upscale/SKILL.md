---
name: comfy-image-upscale
description: Upscale existing raster images with comfy-diffusion ClearReality or NVIDIA RTX VSR. Use when the user selects or provides an image and wants a higher-resolution version saved into the workspace. Do not use for new image generation, semantic editing, video, music, voice, model downloads, custom node installation, or ComfyUI server workflows.
metadata:
  loki:
    visibility: user
    capabilities: [image-upscaling, raster-card-output, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    arguments:
      - id: engine
        label: Engine
        description: Choose the image upscaling engine.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: clear-reality
            label: ClearReality
            description: Local ClearReality model upscale using imagegen.upscale.
          - value: rtx-vsr
            label: RTX VSR
            description: NVIDIA RTX VSR image upscale without local model files.
      - id: resolution
        label: RTX resolution
        description: Choose the target RTX VSR output bounds. The input aspect ratio is preserved.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          engine: rtx-vsr
        order: 20
        options:
          - value: 1080p
            label: 1080p
            description: HD delivery target with moderate output size.
          - value: 1440p
            label: 1440p
            description: Higher-detail delivery target between HD and 4K.
          - value: 4k
            label: 4K
            description: UHD delivery target for final upscale.
          - value: 720p
            label: 720p
            description: Light upscale for previews or smaller source images.
          - value: 480p
            label: 480p
            description: Small output target for very low-resolution images.
          - value: 8k
            label: 8K
            description: Very large output target; use only when explicitly requested.
      - id: quality
        label: Quality
        description: Choose the RTX VSR quality level.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          engine: rtx-vsr
        order: 30
        options:
          - value: ULTRA
            label: Ultra
            description: Highest RTX VSR quality.
          - value: HIGH
            label: High
            description: Strong quality with less cost than Ultra.
          - value: MEDIUM
            label: Medium
            description: Balanced quality and speed.
          - value: LOW
            label: Low
            description: Fastest quality preset.
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: image
---

# comfy-image-upscale

Use this skill only for upscaling an existing image. ClearReality is the
default engine and uses `comfy-imagegen upscale`. NVIDIA RTX VSR uses
`comfy-imagegen rtx-upscale` when the user explicitly asks for RTX, NVIDIA VSR,
hardware/video-super-resolution style upscale, or passes `engine: rtx-vsr`.

The input image should come from selected card snapshots first:
`metadata.artifactUrl` or `mediaAssets` image artifact URLs are required.
Rendered previews and inline `dataUrl` payloads are UI-only and are not valid
skill inputs.

ClearReality uses the models directory declared in this skill's Loki metadata.
If the ClearReality upscale model is missing, use `comfy-model-downloader` with
`imagegen.upscale` before running inference. RTX VSR does not use
`models_dir`, does not use the model downloader, and does not accept LoRAs.
Report RTX/CUDA/NVIDIA hardware or `nvidia-vfx` dependency errors explicitly.

If `comfy-imagegen` or `comfy-models` is not available, use
`comfy-tools-setup` first. In this repository, prefer `uv run comfy-imagegen`;
outside the repo, let `comfy-tools-setup` install the CLIs with `uv tool`.

## Command

ClearReality:

```bash
uv run comfy-imagegen upscale \
  --input path/to/input.png \
  --out outputs
```

NVIDIA RTX VSR:

```bash
uv run comfy-imagegen rtx-upscale \
  --input path/to/input.png \
  --resolution 1080p \
  --quality ULTRA \
  --out outputs
```

## Upscale Guidance

Do not add prompt text. Use the input image only. Preserve the visual content
and improve resolution/detail through the selected upscaler.

Optional params:

- `engine`: `clear-reality` or `rtx-vsr`; default `clear-reality`.
- RTX `resolution`: `480p`, `720p`, `1080p`, `1440p`, `4k`, or `8k`; default
  `1080p`.
- RTX `quality`: `LOW`, `MEDIUM`, `HIGH`, or `ULTRA`; default `ULTRA`.
- RTX advanced params: `scale` or `width` plus `height` are allowed only when
  explicitly provided, and should not be combined with `resolution`.

## Defaults

- Models directory: declared in Loki metadata as `.loki/models/comfyui`
- ClearReality upscaler: `upscale_models/4x-ClearRealityV1.pth`
- RTX profile: `rtx-vsr`, capability `imagegen.rtx-upscale`
- Dependency: `comfy-diffusion[comfyui,video]`
