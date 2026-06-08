---
name: ideogram4-image
description: Generate local Ideogram 4 images through comfy-agent-tools with structured prompts, object/text bounding boxes, and optional selected-image reference interpretation. Use for Ideogram 4 text-to-image or reference-informed image generation in Loki agent mode. Do not use for Comfy direct mode, image editing, upscaling, video, music, or non-Ideogram models.
metadata:
  loki:
    visibility: user
    capabilities: [image-generation, reference-image-generation, raster-card-output, ideogram, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    arguments:
      - id: mode
        label: Mode
        description: Choose whether to generate from text only or interpret selected image references first.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: t2i
            label: Text to image
            description: Build the Ideogram prompt from the user's text.
          - value: r2i
            label: Reference to image
            description: Use selected or attached images as visual references interpreted by the agent.
      - id: qualityProfile
        label: Quality
        description: Choose the Ideogram 4 quality preset.
        type: choice
        required: true
        askWhen: always
        order: 20
        options:
          - value: Default
            label: Default
            description: 20 steps, balanced speed and quality.
          - value: Quality
            label: Quality
            description: 48 steps, highest quality.
          - value: Turbo
            label: Turbo
            description: 12 steps, fastest option.
      - id: aspectRatio
        label: Aspect ratio
        description: Choose the image frame.
        type: choice
        required: true
        askWhen: always
        order: 30
        options:
          - value: "1:1"
            label: 1:1 Square
            description: Square frame.
          - value: "3:2"
            label: 3:2 Photo
            description: Landscape photo frame.
          - value: "4:3"
            label: 4:3 Standard
            description: Classic landscape frame.
          - value: "16:9"
            label: 16:9 Widescreen
            description: Wide cinematic frame.
          - value: "21:9"
            label: 21:9 Ultrawide
            description: Extra-wide cinematic frame.
          - value: "2:3"
            label: 2:3 Portrait Photo
            description: Vertical photo frame.
          - value: "3:4"
            label: 3:4 Portrait Standard
            description: Classic vertical frame.
          - value: "9:16"
            label: 9:16 Portrait Widescreen
            description: Tall mobile frame.
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 900
    output:
      packager: auto
      kind: image
---

# Ideogram 4 Image

Use this skill only for local Ideogram 4 image generation through
`comfy-imagegen ideogram4-generate`. It is a Loki agent-mode skill, not a direct
Comfy composer mode.

If `comfy-imagegen` or `comfy-models` is missing, use `comfy-tools-setup`. If
the Ideogram 4 model files are missing, use `comfy-model-downloader` for
`imagegen.ideogram4-generate`.

## Modes

- `t2i`: transform the user's text into an Ideogram 4 structured prompt.
- `r2i`: inspect selected or attached image artifacts, describe visible
  subjects, style, layout, colors, text, and composition, then combine that with
  the user's prompt. The CLI has no image-conditioning flag; the selected image
  is interpreted by the agent before invoking the skill.

For `r2i`, require at least one selected or attached local image artifact. Do
not use inline previews, data URLs, or vague placeholders.

## Required paramsJson

Pass these fields in `paramsJson`:

- `mode`: `t2i` or `r2i`.
- `qualityProfile`: `Quality`, `Default`, or `Turbo`.
- `aspectRatio`: `1:1`, `3:2`, `4:3`, `16:9`, `21:9`, `2:3`, `3:4`, or `9:16`.
- `styleAesthetics`: concise style qualities.
- `styleLighting`: concrete lighting direction and mood.
- `styleMedium`: medium such as photograph, poster, illustration, logo, or 3D render.
- Exactly one of `stylePhoto` or `styleArtStyle`.
- `background`: the global background/setting.
- At least one `objects` or `texts` element.

Optional fields include `styleColors`, `seed`, `cfg`, `steps`, `mu`, and `std`.

Object element:

```json
{"bbox":[100,120,900,880],"description":"main subject, centered, detailed visual description"}
```

Text element:

```json
{"bbox":[80,160,220,840],"text":"BOLD TITLE","description":"large crisp headline text, centered"}
```

Bboxes use Ideogram coordinates `y_min,x_min,y_max,x_max` from `0` to `1000`.
Make boxes large enough for text and leave margins. Do not overlap text boxes
with key faces or important objects unless the user asks for overlay design.

## Prompt guidance

Set the action `prompt` to the high-level Ideogram description, not UI text or a
raw user command. Ideogram 4 responds best to structured captions: clear overall
description, style, background, and a compositional deconstruction with elements.

For text/logo/design requests:

- Put the exact requested text in `texts[].text`.
- Keep text short and quote-sensitive.
- Describe typography, placement, contrast, and surrounding negative space.
- Use bboxes to reserve enough space for readable text.

For reference-informed prompts:

- Describe what is visibly present in the selected images: subject count, pose,
  materials, style, palette, camera angle, layout, text, and background.
- Write the final image prompt as a standalone visual description.
- Do not include phrases such as `reference image`, `selected image`, `based on
  the image`, `imagen de referencia`, `imagen seleccionada`, `recrear la
  referencia`, or `mantener la referencia` in `prompt`, `background`, objects,
  or text descriptions. Ideogram never sees the image, only your final
  structured text.

Do not add a Loki-specific NSFW filter or rewrite adult prompts into softer
content. The skill passes the agent-authored prompt structure to Ideogram 4 and
lets the model, CLI, and invoking agent apply their own limits.

## Example paramsJson

```json
{
  "mode": "t2i",
  "qualityProfile": "Default",
  "aspectRatio": "16:9",
  "styleAesthetics": "premium cinematic product advertising, sharp composition, high detail",
  "styleLighting": "soft studio key light with cool rim light and controlled reflections",
  "styleMedium": "photograph",
  "stylePhoto": "commercial product photography",
  "styleColors": ["#0B0F14", "#F4D06F", "#FFFFFF"],
  "background": "dark glossy studio surface with subtle reflections",
  "objects": [
    {
      "bbox": [210, 270, 850, 730],
      "description": "translucent amber cassette player, centered hero object, crisp edges, premium materials"
    }
  ],
  "texts": [
    {
      "bbox": [80, 170, 190, 830],
      "text": "RETRO WAVE",
      "description": "large readable condensed sans-serif headline, warm cream color, centered above product"
    }
  ]
}
```
