---
name: comfy-image-edit
description: Edit existing raster images with comfy-diffusion, including Qwen Image Edit 2511, FLUX.2 Klein 9B SNOFS, and remote Grok Imagine edit API nodes. Use when the user selects or provides an image and wants visual changes saved into the workspace. Do not use for new text-to-image generation without an input image, upscaling, video, music, voice, model downloads, custom node installation, or ComfyUI server workflows.
metadata:
  loki:
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
`mediaAssets` images are preferred, and `preview` is the fallback when the card
is an HTML/CSS/canvas composition.

Local modes use the models directory declared in this skill's Loki metadata.
If a supported built-in edit model is missing, use `comfy-model-downloader` with
`imagegen.edit` for the active edit profile before running inference.

If `comfy-imagegen` or `comfy-models` is not available, use
`comfy-tools-setup` first. In this repository, prefer `uv run comfy-imagegen`;
outside the repo, let `comfy-tools-setup` install the CLIs with `uv tool`.

## Required Arguments

Loki declares `modelProfile` as a required skill argument. The bridge asks it
before the agent invokes this skill, then passes it to the action params.

Do not silently fall back to a default profile. The action rejects editing
without `modelProfile` and an input image.

Common edit profiles:

- `qwen-edit2511`: Qwen Image Edit 2511 for direct visual edits.
- `flux-klein-9b-snofs`: FLUX.2 Klein 9B FP8 + SNOFS LoRA for single-reference editing.
- `grok-imagine-api`: remote Grok Imagine editing, only when the API key is configured.

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
