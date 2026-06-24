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
            description: Build the prompt from the user's text.
          - value: r2i
            label: Reference to image
            description: Use selected or attached images as visual references interpreted by the agent.
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
            description: Anime and illustration generation with Anima Base v1.0 + Turbo LoRA.
          - value: anima-preview3-turbo
            label: Anima Preview3
            description: Anime and illustration generation with Anima Preview3 + Turbo LoRA.
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
      timeoutSeconds: 0
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

If `.comfy-agent-tools.json` is missing or the user wants to configure a new
checkpoint/fine-tune/default, use `comfy-model-onboarding` first.

## Modes

- `t2i`: transform the user's text into the final model prompt.
- `r2i`: inspect selected or attached image artifacts, describe visible
  subjects, style, layout, colors, pose, crop, background, and lighting, then
  combine that with the user's prompt. The CLI has no image-conditioning flag in
  this mode; the selected image is interpreted by the agent before invoking the
  skill.

For `r2i`, require at least one selected or attached local image artifact. Do
not use inline previews, data URLs, or vague placeholders.
If the agent does not already have a trusted visual description, call
`describe_loki_image` before composing the final prompt.

## Required Arguments

Loki declares `mode`, `modelProfile`, and `aspectRatio` as required skill
arguments. The bridge asks these one at a time before the agent invokes this
skill, then passes the collected values to the action params.

Do not silently fall back to a default mode or profile. The action rejects
generation without `mode`, `modelProfile`, and `aspectRatio`.

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
  --prompt "masterpiece, best quality, anime illustration, 1girl, solo, samurai, katana, forest, rain, cinematic lighting, dramatic shadows" \
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

Treat the user's request as the source of truth. Prompt improvements are allowed
only when they are additive and compatible with what the user asked for. Preserve
the requested subject, count, identity details, style, medium, composition,
clothing, expression, pose, lighting, camera, background, colors, mood, text, and
constraints.

For local Comfy generation profiles, Loki does not add an NSFW filter and does
not rewrite adult prompts into softer substitutes. Preserve adult/NSFW user
intent when converting the request into model-friendly prose or tags. Remote
profiles such as `grok-imagine-api` may still fail according to provider-side
rules outside Loki's control.

Do not swap the subject, setting, style, camera, mood, language, or constraints.
Do not drop unusual details because they are hard to tag. Do not translate,
summarize, or convert the request into a shorter tag list if that loses any
meaning.

Good improvements: clarify ambiguous lighting, add compatible rendering terms,
make composition/camera wording more concrete, or add model-friendly descriptors
that reinforce the user request.

Bad improvements: replacing the requested character or object, changing the
scene, forcing anime/photorealism when the user asked for another style, adding
unrequested clothing or props, removing text/logo constraints, or reducing a rich
request to generic tags like `1girl, anime style, detailed background`.

For `modelProfile` values `anima-base` and `anima-preview3-turbo`, the action
`prompt` must use anime booru/Danbooru-style tag nomenclature. Do not pass prose
such as `Generate a full-body anime-style illustration...`. Rewrite the user's
request into a comma-separated tag prompt before invoking the action.

Anima tag prompt rules:

- Use comma-separated tags and short tag phrases, not sentences.
- Prefer lowercase visual tags such as `1girl`, `solo`, `full body`, `standing`,
  `singing`, `microphone`, `long hair`, `orange eyes`, `school uniform`,
  `simple background`, `clean lineart`, `anime coloring`.
- Include quality/style tags up front when useful: `masterpiece`, `best quality`,
  `anime illustration`, `clean lineart`, `vibrant colors`.
- Preserve every important requested subject, count, pose, clothing, prop,
  composition, expression, background, color, and constraint as tags.
- Do not include imperative words like `generate`, `create`, `make`, `draw`, or
  `from the selected image`.
- Do not add contradictory tags, extra characters, extra panels, frames, logos,
  or text unless the user requested them.

Bad Anima prompt:

```text
Generate a full-body anime-style illustration of a girl singing on stage holding
a microphone. She has long flowing hair, expressive eyes, and a cute performance
outfit.
```

Better Anima prompt:

```text
masterpiece, best quality, anime illustration, 1girl, solo, full body, singing,
open mouth, holding microphone, long flowing hair, expressive eyes, performance
outfit, standing, stage, vibrant colors, clean lineart, simple background
```

The runtime passes the received prompt to `comfy-imagegen` unchanged. Any prompt
editing must happen deliberately before invoking the action and must preserve the
user's intent.

For reference-informed prompts:

- Describe what is visibly present in the selected images: subject count, pose,
  clothing, materials, style, palette, camera angle, layout, text, background,
  linework, and lighting.
- If those traits are not already trusted context, call `describe_loki_image`
  and use its description as the visual grounding source.
- Write the final image prompt as a standalone visual description or, for Anima,
  as standalone visual tags.
- Do not include phrases such as `reference image`, `selected image`, `based on
  the image`, `imagen de referencia`, `imagen seleccionada`, `recrear la
  referencia`, or `mantener la referencia` in the prompt. The CLI never sees the
  image for `r2i`, only your final prompt.

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

## Preflight Checklist

Before invoking the Loki action, verify:

- The required user choices are present: `modelProfile` and `aspectRatio`.
- `params.mode` is `t2i` or `r2i`.
- If `params.mode` is `r2i`, at least one selected or attached local image
  artifact is available.
- The action `prompt` is the final model prompt, not a copy of the user request,
  UI text, or card description boilerplate.
- For `r2i`, the prompt is standalone and does not mention reference/selected
  images.
- If `modelProfile` is `anima-base` or `anima-preview3-turbo`, the prompt is a
  comma-separated booru/Danbooru-style tag list.
- For Anima prompts, there are no imperative prose phrases such as `Generate`,
  `Create`, `Make`, `Draw`, or `from the selected image`.
- For Anima prompts, important requested details are represented as tags:
  subject count, identity, framing, pose, expression, clothing, props,
  background, colors, style, and constraints.
- For Anima prompts, quality/style tags appear near the front when useful, such
  as `masterpiece`, `best quality`, `anime illustration`, `clean lineart`, and
  `vibrant colors`.
- For non-Anima profiles, the prompt follows that profile's guidance: natural
  language for FLUX.2 Klein SNOFS, Qwen Image Edit generation, and Grok Imagine.
- `paramsJson` contains the chosen `modelProfile` and `aspectRatio`, plus only
  intentional generation options such as seed or LoRA.
