---
name: comfy-image-edit
description: Edit existing raster images with comfy-diffusion, including Qwen Image Edit 2511, FLUX.2 Klein 9B SNOFS, and remote Grok Imagine edit API nodes. Use when the user selects or provides an image and wants visual changes saved into the workspace. Do not use for new text-to-image generation without an input image, upscaling, video, music, voice, model downloads, custom node installation, or ComfyUI server workflows.
metadata:
  loki:
    visibility: user
    capabilities: [image-editing, raster-card-output, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    arguments:
      - id: modelProfile
        label: Edit model
        description: Choose the Comfy image editing model profile.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: qwen-edit2511
            label: Qwen Image Edit
            description: Qwen Image Edit 2511 for local image editing.
          - value: flux-klein-9b-snofs
            label: FLUX Klein SNOFS
            description: FLUX.2 Klein 9B FP8 + SNOFS LoRA for single-reference editing.
          - value: grok-imagine-api
            label: Grok Imagine API
            description: Remote Grok Imagine editing when COMFY_ORG_API_KEY is configured.
      - id: aspectRatio
        label: Aspect ratio
        description: Choose whether to preserve the input image frame or change it for the edited result.
        type: choice
        required: true
        askWhen: always
        order: 20
        options:
          - value: original
            label: Keep original
            description: Preserve the selected card or attachment aspect ratio.
          - value: "1:1"
            label: Square 1:1
            description: Change the edited output to a square frame.
          - value: "4:3"
            label: Landscape 4:3
            description: Change the edited output to a classic landscape frame.
          - value: "16:9"
            label: Widescreen 16:9
            description: Change the edited output to a cinematic widescreen frame.
          - value: "9:16"
            label: Vertical 9:16
            description: Change the edited output to a vertical portrait frame.
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 900
    output:
      packager: auto
      kind: image
---

# comfy-image-edit

Use this skill only for editing an existing image through the `comfy-imagegen`
CLI. The input image should come from selected card snapshots first:
`metadata.artifactUrl` or `mediaAssets` image artifact URLs are required.
Rendered previews and inline `dataUrl` payloads are UI-only and are not valid
skill inputs.

Local modes use the models directory declared in this skill's Loki metadata.
If a supported built-in edit model is missing, use `comfy-model-downloader` with
`imagegen.edit` for the active edit profile before running inference.

If `comfy-imagegen` or `comfy-models` is not available, use
`comfy-tools-setup` first. In this repository, prefer `uv run comfy-imagegen`;
outside the repo, let `comfy-tools-setup` install the CLIs with `uv tool`.

## Required Arguments

Loki declares `modelProfile` and `aspectRatio` as required skill arguments.
The bridge asks for the model first, then asks whether to preserve the original
frame or change to another aspect ratio before the agent invokes this skill.

Do not silently fall back to a default profile. The action rejects editing
without `modelProfile` and an input image.

Common edit profiles:

- `qwen-edit2511`: Qwen Image Edit 2511 for direct visual edits.
- `flux-klein-9b-snofs`: FLUX.2 Klein 9B FP8 + SNOFS LoRA for single-reference editing.
- `grok-imagine-api`: remote Grok Imagine editing, only when the API key is configured.

Aspect ratio choices:

- `original`: preserve the selected card or attachment frame.
- `1:1`, `4:3`, `16:9`, `9:16`: request a changed edit frame. FLUX and Grok
  edit modes can use changed frames; Qwen Image Edit should normally use
  `original`.

## Commands

Local edit:

```bash
uv run comfy-imagegen edit \
  --input path/to/input.png \
  --prompt "Transform this photo into a polished animated film still style while preserving the main subject and composition" \
  --seed 43 \
  --out outputs
```

For FLUX.2 Klein edit profiles, pass `--width` and/or `--height` only when the
user explicitly wants a changed canvas size. Any omitted dimension defaults to
the input image dimension.

Grok Imagine edit:

```bash
COMFY_ORG_API_KEY=... uv run comfy-imagegen grok-edit \
  --input path/to/input.png \
  --prompt "Keep the subject and composition, change the background to a clean moonlit studio" \
  --resolution 1K \
  --out outputs
```

## Edit Guidance

Write an instruction that names what should change and what should stay fixed.
Preserve identity, layout, pose, and important object details unless the user
explicitly asks to change them.

Qwen Image Edit may rescale internally, so read `outputs[].width` and
`outputs[].height` from the final JSON instead of assuming requested or input
dimensions match the saved PNG.

Grok Imagine uses remote Comfy API nodes and is separate from local model
profiles. Do not route `grok-imagine-api` through `models_dir`,
`comfy-model-downloader`, local LoRAs, or checkpoint onboarding. Supported image
models are `grok-imagine-image-pro`, `grok-imagine-image`, and
`grok-imagine-image-beta`; supported resolutions are `1K` and `2K`.

FLUX.2 Klein 9B SNOFS uses natural-language prompts, supports single-reference
editing, and is step-distilled for `steps=4`, `cfg=1.0`. Keep dimensions
divisible by 16 when changing canvas size. For edits, Flux Klein follows the
official distilled image-edit workflow: reference-image VAE encoding, reference
latents on both positive and negative conditioning, `Flux2Scheduler`,
`CFGGuider`, and `SamplerCustomAdvanced`.

## Defaults

- Models directory: declared in Loki metadata as `.loki/models/comfyui`
- Edit profile: `qwen-edit2511`
- Qwen diffusion model: `diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors`
- Qwen text encoder: `text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors`
- Qwen LoRA: `loras/qwen-image-edit/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors`
- Qwen params: `steps=4`, `cfg=3.0`, `seed=0`
- FLUX profile: `flux-klein-9b-snofs`
- FLUX architecture: `flux-klein`
- FLUX diffusion model: `diffusion_models/flux-2-klein-9b-fp8.safetensors`
- FLUX text encoder: `text_encoders/qwen_3_8b_fp8mixed.safetensors`
- FLUX VAE: `vae/flux2-vae.safetensors`
- SNOFS LoRA: `loras/flux-klein/klein_snofs_v1_1.safetensors`
- Grok profile: `grok-imagine-api`
- Dependency: `comfy-diffusion[comfyui,video]`
