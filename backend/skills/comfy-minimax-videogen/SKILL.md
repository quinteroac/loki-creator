---
name: comfy-minimax-videogen
description: Generate local MiniMax H3 text-to-video, image-to-video, or reference-to-video clips with synchronized native audio using comfy-videogen. Use this skill for MiniMax H3 local video generation; do not merge it with comfy-videogen or use it for hosted MiniMax APIs.
metadata:
  loki:
    visibility: user
    capabilities: [video-generation, text-to-video, image-to-video, reference-to-video, raster-card-output, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    arguments:
      - id: mode
        label: H3 mode
        description: Choose text-to-video, first-image-to-video, or multimodal reference-to-video.
        type: choice
        required: true
        askWhen: always
        order: 5
        options:
          - value: minimax-h3-t2v
            label: Text to video
          - value: minimax-h3-i2v
            label: Image to video
          - value: minimax-h3-r2v
            label: Reference to video
      - id: megapixels
        label: Megapixels
        description: H3 output size preset. Dimensions are calculated from megapixels, aspect ratio, and a multiple of 32.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: "0.2"
          - value: "0.3"
          - value: "0.4"
          - value: "0.5"
          - value: "0.6"
          - value: "0.7"
          - value: "0.8"
          - value: "0.9"
          - value: "0.98"
          - value: "1.0"
          - value: "1.2"
          - value: "1.5"
          - value: "1.8"
          - value: "2.0"
      - id: aspectRatio
        label: Aspect ratio
        description: H3 output aspect ratio.
        type: choice
        required: true
        askWhen: always
        order: 20
        options:
          - value: "1:1"
          - value: "2:3"
          - value: "3:2"
          - value: "3:4"
          - value: "4:3"
          - value: "9:16"
          - value: "16:9"
          - value: "21:9"
      - id: duration
        label: Duration
        description: H3 duration in seconds at 24 fps. The frame count is snapped to the 17k+5 grid.
        type: choice
        required: true
        askWhen: always
        order: 30
        options:
          - value: "3"
          - value: "5"
          - value: "7"
          - value: "10"
          - value: "15"
      - id: refImageSize
        label: Reference image size
        description: How aggressively to preserve reference detail.
        type: choice
        required: false
        askWhen: missing
        order: 40
        options:
          - value: match
          - value: max
      - id: quality
        label: Quality
        description: Sampling quality preset. Low uses 8 steps, medium 12, and high 20.
        type: choice
        required: true
        askWhen: always
        order: 35
        options:
          - value: low
          - value: medium
          - value: high
      - id: sageAttention
        label: SageAttention
        description: Enable SageAttention for faster H3 attention. Requires the sageattention package.
        type: choice
        required: true
        askWhen: always
        order: 45
        options:
          - value: "false"
            label: "Off"
          - value: "true"
            label: "On"
      - id: easycache
        label: EasyCache
        description: Enable EasyCache to reduce render time, with some possible quality loss.
        type: choice
        required: true
        askWhen: always
        order: 50
        options:
          - value: "false"
            label: "Off"
          - value: "true"
            label: "On"
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: video
---

# comfy-minimax-videogen

Use this skill for local MiniMax H3 T2V, I2V, and R2V generation. All modes
produce an MP4 with synchronized native stereo audio. Use `minimax-h3-t2v`
without image inputs, `minimax-h3-i2v` with one first-frame image, or
`minimax-h3-r2v` with one or more reference images. R2V references are passed
in order and should be named in the prompt as `<Picture 1>`, `<Picture 2>`, and
so on.

The H3 model is local and uses these files under `.loki/models/comfyui`:

- `diffusion_models/minimax/minimax_h3_ref2va_pruned_int8_convrot.safetensors`
- `diffusion_models/minimax/minimax_h3_fl2va_pruned_int8_convrot.safetensors`
- `text_encoders/minimax/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
- `vae/minimax/minimax_h3_audio_vae_fp32.safetensors`
- `vae/minimax/minimax_h3_video_vae_fp16.safetensors`

If the files are missing, use `comfy-model-downloader` for the exact capability:
`videogen.minimax-h3-t2v`, `videogen.minimax-h3-i2v`, or
`videogen.minimax-h3-r2v`. If the CLI is missing, use `comfy-tools-setup`.
This skill supports 0.2–2.0 megapixel presets, the aspect ratios listed above,
and 3, 5, 7, 10, or 15 seconds. It does not use `COMFY_ORG_API_KEY`.
Quality presets are low (8 steps), medium (12 steps), and high (20 steps).
SageAttention and EasyCache are explicit generation options and are asked before
each run; both default to off when invoking the CLI directly.
The runner keeps ComfyUI's normal VRAM mode. For 16 GB GPUs, its R2V pipeline
must release the Qwen3-VL conditioning models before loading the H3 UNet; do
not solve this by forcing `lowvram` globally.

## Prompting

Follow the official MiniMax H3 prompt format. T2V and I2V use these three
fields in English and in this order:

```text
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...
```

The value passed to `--prompt` is sent directly to H3. It must be the final
model-facing prompt, not an agent brief or an execution handoff. Do not add
prefaces such as `Create a ... clip`, explanations of what the agent is doing,
workflow/parameter notes, JSON, Markdown fences, or phrases such as `using the
supplied image`. Do not explain the three field names; keep only the field
labels and their content. For reference inputs, use `<Picture N>` and
`<Subject N>` only as the H3 labels required to bind the visual reference, then
describe the visual directly.

R2V uses MiniMax H3's full-reference format from
`VIDEO_PROMPT_WRITING_GUIDE_ref_en.md`, not the short T2V/I2V format. Write
these six sections in English and in this order:

```text
subject_definitions: ...
summary: ...
retention_analysis: ...
detailed_description: ...
overall_soundscape: ...
non_diegetic_music: ...
```

In R2V, define each reusable `<Subject N>` and reference asset, then describe
the target video in `detailed_description`. Keep the guide's stable subject and
speaker IDs, shot numbering, cut-time rules, dialogue `<d>` blocks, and
reference relationship markers. Do not collapse these sections into
`integrated_multimodal_description`.

For T2V/I2V, the `integrated_multimodal_description` field describes the
timeline, subject actions, camera movement, dialogue, visible text, and
diegetic sound. Use sequential `[Shot N]` blocks;
do not timestamp Shot 1, and use increasing cut times for later shots. Keep
speaker IDs stable, preserve user-provided dialogue verbatim inside `<d>` tags,
and specify camera motion as type plus meaningful amplitude/speed.

For I2V, begin with exactly: `For the target video, at 0.00 seconds into the
target video, <Picture 1> (from [Shot 1]) is fully referenced.` Then anchor the
first shot to the supplied image before describing forward motion. For R2V,
define referenced subjects and assets with `<Subject N>`, `<Picture N>`,
`<Video N>`, and `<Audio N>` when applicable, and preserve their labels. Use
`N/A` for either audio field only when that sound layer is intentionally absent.
Consult the official H3 base and full-reference prompt guides for the complete
specification.
