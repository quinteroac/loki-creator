---
name: comfy-image-upscale
description: Upscale existing raster images with comfy-diffusion ClearReality. Use when the user selects or provides an image and wants a higher-resolution version saved into the workspace. Do not use for new image generation, semantic editing, video, music, voice, model downloads, custom node installation, or ComfyUI server workflows.
metadata:
  loki:
    visibility: user
    capabilities: [image-upscaling, raster-card-output, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 900
    output:
      packager: auto
      kind: image
---

# comfy-image-upscale

Use this skill only for upscaling an existing image through the
`comfy-imagegen upscale` CLI. The input image should come from selected card
snapshots first: `metadata.artifactUrl` or `mediaAssets` image artifact URLs
are required. Rendered previews and inline `dataUrl` payloads are UI-only and
are not valid skill inputs.

Local modes use the models directory declared in this skill's Loki metadata.
If the ClearReality upscale model is missing, use `comfy-model-downloader` with
`imagegen.upscale` before running inference.

If `comfy-imagegen` or `comfy-models` is not available, use
`comfy-tools-setup` first. In this repository, prefer `uv run comfy-imagegen`;
outside the repo, let `comfy-tools-setup` install the CLIs with `uv tool`.

## Command

```bash
uv run comfy-imagegen upscale \
  --input path/to/input.png \
  --out outputs
```

## Upscale Guidance

Do not add prompt text. Use the input image only. Preserve the visual content
and improve resolution/detail through the upscaler.

## Defaults

- Models directory: declared in Loki metadata as `.loki/models/comfyui`
- Upscaler: `upscale_models/4x-ClearRealityV1.pth`
- Dependency: `comfy-diffusion[comfyui,video]`
