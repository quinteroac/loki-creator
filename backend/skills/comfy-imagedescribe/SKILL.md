---
name: comfy-imagedescribe
description: Describe or caption local images with the Qwen3-VL 2B Instruct vision-language model through comfy-agent-tools. Use as Loki's internal visual-grounding fallback when an agent needs concrete visible traits from a selected or attached image before reference generation, prompt writing, captioning, tagging, or visual QA. Do not use for image generation, editing, upscaling, video generation, music generation, model downloads, ComfyUI server workflows, UI work, or custom node installation.
metadata:
  loki:
    visibility: internal
    capabilities: [image-description, visual-grounding, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: text
---

# comfy-imagedescribe

Use this internal skill for local image description through the
`comfy-imagedescribe describe` CLI. It uses the Qwen3-VL 2B Instruct
vision-language model from the configured Comfy models directory.

The default model path is:

```text
LLM/Qwen-VL/Qwen3-VL-2B-Instruct
```

This must be a HuggingFace model directory. Do not point it at a single Qwen
diffusion text-encoder safetensors file.

## Required Input

Require one selected or attached local image artifact. Do not use inline
previews, data URLs, rendered previews, or placeholder reference-language as
inputs.

## Command Shape

The runtime builds this command:

```bash
comfy-imagedescribe describe \
  --models-dir .loki/models/comfyui \
  --input path/to/image.png \
  --prompt "Describe this image in detail, including subject, composition, style, lighting, colors, pose, clothing/materials, background, visible text, and camera angle." \
  --out outputs \
  --no-manifest
```

Optional params:

- `inputPath` or `imagePath`: explicit local image path.
- `maxLength`: maps to `--max-length`.
- `seed`: maps to `--seed`.
- `greedy`: maps to `--greedy` when true.

## Output

The CLI prints JSON to stdout. On success, read the `description` field. Loki
also stores that text in metadata as `imageDescription` so bridge tools can use
the description without treating it as a user-visible generated card.

## Failure Handling

If `comfy-imagedescribe` is missing, use `comfy-tools-setup`. If the Qwen3-VL
model directory is missing, fail explicitly and tell the user to place
`Qwen/Qwen3-VL-2B-Instruct` under `LLM/Qwen-VL/Qwen3-VL-2B-Instruct` in the
configured Comfy models directory. Do not auto-download this model.
