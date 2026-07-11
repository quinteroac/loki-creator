---
name: comfy-krea2-image
description: Generate local Krea2 Turbo raster images through comfy-agent-tools. Use for high-fidelity text-to-image or reference-informed image prompt construction with Krea2 Turbo saved into the Loki workspace. Do not use for editing existing images, upscaling, video, music, voice, LoRAs, model downloads, custom node installation, or ComfyUI server workflows.
metadata:
  loki:
    visibility: user
    capabilities: [image-generation, raster-card-output, comfy, krea2]
    runtime:
      modelsDir: .loki/models/comfyui
    arguments:
      - id: mode
        label: Mode
        description: Choose whether to generate from text only or interpret selected image references first.
        type: choice
        required: true
        askWhen: always
        order: 5
        options:
          - value: t2i
            label: Text to image
            description: Expand the user's text into one Krea2 prompt.
          - value: r2i
            label: Reference to image
            description: Read selected or attached images as visual references, then write one standalone Krea2 prompt.
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
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: image
---

# comfy-krea2-image

Use this skill only for Krea2 Turbo local image generation through
`comfy-imagegen krea2-generate`. Loki fixes the model profile to
`krea2-turbo`; do not ask for `modelProfile` and do not route Krea2 through
`comfy-image-generate`.

If `comfy-imagegen`, `comfy-models`, or the `krea2-generate` subcommand is not
available, use `comfy-tools-setup` first. If Krea2 model files are missing, use
`comfy-model-downloader` with `imagegen.krea2-generate`.

## Modes

- `t2i`: expand the user's text into the final Krea2 prompt.
- `r2i`: requires at least one selected or attached local image artifact. In
  agent mode with a vision-capable PI model, use `read_loki_visual` on the
  selected local image before writing the final prompt. The Krea2 CLI does not
  receive the image as `--input`; it receives only your standalone prompt.

For `r2i`, never invoke this skill with placeholder wording such as `reference
image`, `selected image`, `based on the image`, `imagen de referencia`, `imagen
seleccionada`, `recrear la referencia`, or `mantener la referencia`. Replace
those placeholders with concrete visible traits.

## Prompt Template

You are an expert prompt engineer for text-to-image models. Your task is to
expand the user's prompt into a highly effective image-generation prompt.

Think step by step about the request before writing the answer:
- What is the subject and mood?
- What visual styles, mediums, and lighting options would fit? Consider two or
  three alternatives and pick the one that best serves the caption.
- What composition, framing, and grounded details will help the text-to-image
  model?

Then output a single expanded prompt paragraph.

Follow these rules strictly:

1. **Faithfulness First:** Preserve all original subjects, actions, colors, and
   spatial relationships. Do not add new objects, props, characters, or animals
   unless the user clearly implies them.
2. **Practical T2I Structure:** Write a prompt that a text-to-image model can
   parse cleanly. Group subjects with their own attributes and actions. Use
   grounded phrasing for poses, interactions, and spatial layout.
3. **Style Planning Stays Internal:** Use your internal reasoning to choose
   style, medium, framing, and lighting. Do not emit planning tags or wrappers
   in the visible answer body or skill prompt.
4. **Text Rendering:** If the user requests visible text, quotes, labels, or
   typography, specify the exact text clearly and wrap requested words in
   quotes.
5. **Avoid Over-Specification:** Do not invent highly specific clothing, colors,
   materials, or scene details unless the input supports them.
6. **Structure:** Write one cohesive paragraph after internal thinking. No
   bullets, JSON, or markdown in the final skill prompt.
7. **Respect Existing Detail:** If the user's prompt is already detailed,
   lightly polish and finalize rather than heavily expanding; preserve their
   phrasing and direction.
8. **Respect the Human Form:** Treat depictions of people with dignity. Assume
   clothing covers genitals and intimate anatomy.
9. **Preserve User Medium:** When the user explicitly requests a medium such as
   photo, photograph, illustration, painting, sketch, or 3D render, honor it.
   Do not pivot to a different medium to avoid difficulty.

For `r2i`, treat the concrete visual traits from `read_loki_visual` as part of
the user's input, while still preserving the user's requested change or desired
new image. Do not mention the image-reading mechanism in the final prompt.

## Required paramsJson

Pass:

- `mode`: `t2i` or `r2i`.
- `aspectRatio`: `1:1`, `4:3`, `16:9`, or `9:16`.
- Optional `seed`.

Do not pass `modelProfile`; Loki sets `krea2-turbo`. Do not pass LoRA params;
upstream `krea2-generate` does not expose LoRA flags in this integration.

## Runtime Contract

The action builds:

```bash
uv run comfy-imagegen krea2-generate \
  --models-dir .loki/models/comfyui \
  --prompt "<final one-paragraph prompt>" \
  --width <derived from aspectRatio> \
  --height <derived from aspectRatio> \
  --seed <optional seed> \
  --out outputs
```

The runtime writes `.comfy-agent-tools.json` with capability
`imagegen.krea2-generate` and profile `krea2-turbo`.

## Preflight Checklist

- `params.mode` is `t2i` or `r2i`.
- `params.aspectRatio` is present.
- For `r2i`, at least one selected or attached local image artifact is
  available and the final prompt contains concrete visible traits.
- The prompt is exactly one cohesive paragraph, not JSON, markdown, a bullet
  list, or a copy of the template.
- The prompt does not mention reference/selected images or Loki tools.
