---
name: grok-imagine-image
description: Generate raster images with Grok Imagine through the xAI Imagine API. Use when the user explicitly asks for Grok, xAI, Imagine, or Grok image generation. Do not use for video, image editing, local ComfyUI generation, or non-Grok image models.
metadata:
  loki:
    visibility: user
    capabilities: [image-generation, raster-card-output, grok, xai]
    arguments:
      - id: aspectRatio
        label: Aspect ratio
        description: Choose the image frame before generation.
        type: choice
        required: true
        askWhen: always
        order: 10
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
      - id: resolution
        label: Resolution
        description: Choose the Grok Imagine output resolution.
        type: choice
        required: true
        askWhen: always
        order: 20
        options:
          - value: "1k"
            label: 1K
            description: Fast standard output.
          - value: "2k"
            label: 2K
            description: Higher-detail output.
    action:
      type: cli-local
      command: [python3, ../_grok_runtime/grok_imagine_action.py]
      timeoutSeconds: 900
    output:
      packager: auto
      kind: image
---

# grok-imagine-image

Use this skill for text-to-image generation through Grok Imagine / xAI Imagine.
It calls the documented xAI image generation endpoint and returns materialized
image artifacts for Loki cards.

Auth resolution follows Grok Build media tooling:

- `XAI_API_KEY`
- `GROK_CODE_XAI_API_KEY`
- valid `https://auth.x.ai` access token in `~/.grok/auth.json`

The action never logs token values.

## Parameters

Loki asks for `aspectRatio` and `resolution` before invoking this skill.
The action uses `grok-imagine-image-quality` unless a `model` param is passed.

Supported optional params:

- `model`: override the xAI image model.
- `n`: number of images.
- `responseFormat` or `response_format`: `b64_json` or `url`; defaults to `b64_json`.

## Prompt Guidance

Write a concrete visual prompt with subject, setting, composition, lighting,
style, and any important text constraints. Avoid asking for transparent output;
Grok Imagine is treated here as an opaque raster generator.
