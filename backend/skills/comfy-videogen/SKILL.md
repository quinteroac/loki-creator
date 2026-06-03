---
name: comfy-videogen
description: Generate MP4 videos with comfy-diffusion using local LTX 2.3 10Eros, local WAN 2.2 image/first-last-frame workflows, or remote ByteDance Seedance 2.0 API nodes. Use when the user wants local GPU-backed text-to-video, image-to-video, image+audio-to-video, first/last-frame video generation, LTX motion-track IC-LoRA control, WAN 2.2 image-guided video, or Seedance 2.0 API text/reference/first-last-frame video saved into the workspace. Do not use for image-only generation, music-only generation, voice generation, model downloads, ComfyUI server workflows, UI work, custom node installation, or non-Seedance hosted video APIs.
metadata:
  loki:
    visibility: user
    capabilities: [video-generation, image-to-video, raster-card-output, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    arguments:
      - id: modelProfile
        label: Video model
        description: Choose the video generation model/runtime.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: ltx23-10eros
            label: LTX 2.3 Local
            description: Local GPU-backed LTX 2.3 10Eros workflows.
          - value: wan22-i2v
            label: WAN 2.2 FP8
            description: Local GPU-backed WAN 2.2 image-to-video and first/last-frame workflows. Default 10 high-noise steps and 10 low-noise steps.
          - value: wan22-dasiwa-tastysin-i2v
            label: WAN 2.2 Dasiwa TastySin
            description: Local Dasiwa WAN 2.2 TastySin profile. Default 2 high-noise steps and 2 low-noise steps.
          - value: wan22-dasiwa-boundbite-i2v
            label: WAN 2.2 Dasiwa BoundBite
            description: Local Dasiwa WAN 2.2 BoundBite profile. Default 2 high-noise steps and 2 low-noise steps.
          - value: seedance2-api
            label: Seedance 2.0 API
            description: Remote ByteDance Seedance 2.0 API nodes through ComfyUI API Nodes.
      - id: aspectRatio
        label: Aspect ratio
        description: Choose the video frame.
        type: choice
        required: true
        askWhen: always
        order: 20
        options:
          - value: "16:9"
            label: Widescreen 16:9
            description: Standard cinematic landscape frame.
          - value: "9:16"
            label: Vertical 9:16
            description: Portrait frame for reels and mobile video.
          - value: "1:1"
            label: Square 1:1
            description: Square social video frame.
          - value: "4:3"
            label: Classic 4:3
            description: Classic landscape frame.
      - id: resolution
        label: Resolution
        description: Choose the target video resolution. Use 480p for fast previews and 720p when the extra detail is worth the heavier run.
        type: choice
        required: true
        askWhen: always
        order: 30
        options:
          - value: 480p
            label: 480p
            description: Faster, lighter generation for previews and iteration.
          - value: 720p
            label: 720p
            description: Higher detail with a heavier generation cost.
      - id: videoMode
        label: Video mode
        description: Choose how selected images become video segments.
        type: choice
        required: true
        askWhen: always
        order: 40
        options:
          - value: i2v
            label: Image to video
            description: Create one video per selected image.
          - value: flf2v
            label: First/last frame
            description: Use selected images as storyboard pairs. One image duplicates as first and last; two images create one transition; three or four images create two transitions.
      - id: duration
        label: Duration
        description: Choose the target video duration.
        type: choice
        required: true
        askWhen: always
        order: 50
        options:
          - value: "3"
            label: 3 seconds
            description: Short, fast preview clip.
          - value: "5"
            label: 5 seconds
            description: Short clip for quick preview.
          - value: "7"
            label: 7 seconds
            description: Balanced default duration.
          - value: "10"
            label: 10 seconds
            description: Longer shot with more motion time.
          - value: "15"
            label: 15 seconds
            description: Maximum standard clip duration for LTX 2.3 and Seedance 2.0.
      - id: highNoiseSteps
        label: WAN high-noise steps
        description: Optional WAN 2.2 high-noise model steps. More high steps usually means more motion.
        type: text
        required: false
        askWhen: missing
        order: 60
        options: []
      - id: lowNoiseSteps
        label: WAN low-noise steps
        description: Optional WAN 2.2 low-noise model steps. More low steps usually means more detail/refinement.
        type: text
        required: false
        askWhen: missing
        order: 70
        options: []
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 900
    output:
      packager: auto
      kind: video
---

# comfy-videogen

Use this skill for video generation through the `comfy-videogen` CLI. Local LTX
2.3 and WAN 2.2 modes use model files under `.loki/models/comfyui`.
Remote Seedance 2.0 modes use ComfyUI API Nodes vendored by `comfy-diffusion` and require
`COMFY_ORG_API_KEY`.

If a built-in LTX 2.3 or WAN 2.2 profile is missing files, use
`comfy-model-downloader` for the requested local `videogen.<mode>` capability
before running inference. Do not use the downloader for Seedance 2.0;
`seedance2-api` has no local model files.

The CLI is quiet by default and prints only final JSON. Use `--verbose` only when
debugging ComfyUI runtime output, warnings, or progress bars.

If `comfy-videogen` or `comfy-models` is not available, use
`comfy-tools-setup` first. In this repository, prefer `uv run comfy-videogen`;
outside the repo, let `comfy-tools-setup` install the CLIs with `uv tool`.

## Required Arguments

Loki declares `modelProfile`, `aspectRatio`, `resolution`, `videoMode`, and
`duration` as required skill arguments. The bridge asks which video model/runtime
to use first, then asks for the frame, resolution, image/storyboard mode, and
target duration before the agent invokes this skill.

Available model profiles:

- `ltx23-10eros`: local GPU-backed LTX 2.3 10Eros workflows. Use this for local
  text-to-video, image-to-video, image+audio-to-video, first/last-frame, and
  motion-track workflows.
- `wan22-i2v`: local GPU-backed WAN 2.2 workflows. Use this for image-to-video
  and first/last-frame video when the user explicitly asks for WAN/Wan 2.2 or
  wants the standard WAN local model. Defaults: `highNoiseSteps=10`,
  `lowNoiseSteps=10`.
- `wan22-dasiwa-tastysin-i2v`: local Dasiwa WAN 2.2 TastySin profile. Use when
  the user asks for Dasiwa/TastySin. Defaults: `highNoiseSteps=2`,
  `lowNoiseSteps=2`.
- `wan22-dasiwa-boundbite-i2v`: local Dasiwa WAN 2.2 BoundBite profile. Use when
  the user asks for Dasiwa/BoundBite. Defaults: `highNoiseSteps=2`,
  `lowNoiseSteps=2`.
- `seedance2-api`: remote ByteDance Seedance 2.0 API workflows. Use this for
  text-to-video, reference-image-to-video, and first/last-frame video when
  `COMFY_ORG_API_KEY` is configured.

Aspect ratio choices:

- `16:9`: widescreen landscape.
- `9:16`: vertical portrait.
- `1:1`: square.
- `4:3`: classic landscape.

Resolution choices:

- `480p`: lighter preview/iteration resolution. Local dimensions are `848x480`
  for `16:9`, `480x848` for `9:16`, `480x480` for `1:1`, and `640x480` for
  `4:3`.
- `720p`: higher-detail resolution. Local dimensions are `1280x720` for `16:9`,
  `720x1280` for `9:16`, `720x720` for `1:1`, and `960x720` for `4:3`.
- Seedance 2.0 receives this value directly as `--resolution`.

Video mode choices:

- `i2v`: image-to-video. Each selected image becomes one video segment/card.
- `flf2v`: first/last-frame storyboard. Selected images are consumed in order as
  pairs: one image duplicates as both first and last frame for one video; two
  images create one transition; three images create two videos using `(1,2)` and
  `(3,3)`; four images create two videos using `(1,2)` and `(3,4)`.
- Treat multiple generated videos as connected storyboard beats in the same
  story. Keep prompts coherent across segments while respecting each image pair.
- Local video generation is GPU-exclusive and must run sequentially. Do not try
  to parallelize storyboard segments, spawn multiple local video jobs at once, or
  ask the user to run concurrent local generations. Loki publishes each segment
  to the canvas as it completes.

Duration and WAN step choices:

- `3`, `5`, `7`, `10`, or `15` seconds. Local LTX converts duration to `length` frames
  using `fps=24` unless another fps is explicitly provided. Seedance receives
  the same value as `--duration`.
- WAN 2.2 uses `fps=16` by default and should use full-second frame counts with
  one terminal frame: `49` frames for 3 seconds, `81` for 5 seconds, `113` for
  7 seconds, `161` for 10 seconds, and `241` for 15 seconds. Do not cut WAN
  clips to `duration * fps` frames such as `80` at 16 FPS, because it weakens
  motion and first/last-frame adherence.
- WAN 2.2 accepts optional `highNoiseSteps` and `lowNoiseSteps` params. More
  high-noise steps usually means more motion; more low-noise steps usually means
  more detail/refinement. If both are omitted, the selected profile defaults are
  used. If only one is provided, the CLI derives the other from total `steps`
  when available.

If `.comfy-agent-tools.json` is missing or the user wants to configure a new
checkpoint/fine-tune/default such as an LTX 2.3 variant, use
`comfy-model-onboarding` first.

If model validation fails with `missing_model_file`, use `comfy-model-downloader`
for the exact mode: `videogen.t2v`, `videogen.i2v`, `videogen.flf2v`,
`videogen.ia2av`, `videogen.motion-track`, `videogen.wan22-i2v`, or
`videogen.wan22-flf2v`.

If the user asks to use or organize a LoRA by name or purpose, use
`comfy-lora-onboarding` to search `loras/ltx23/` first and pass the chosen file
with `--extra-lora` only to modes that support ad hoc LoRA insertion.

## Modes

- `t2v`: text prompt to MP4 with audio.
- `i2v`: input image plus prompt to MP4 with audio.
- `ia2av`: input image plus input audio plus prompt to MP4 with audio. Use this
  to animate a still image in relation to an existing WAV/MP3/FLAC, including
  WAV files created by `comfy-musicgen`.
- `flf2v`: first image plus last image plus prompt to MP4 with audio. This mode
  uses the experimental 10Eros first/last-frame adaptation with latent
  upscaling/refinement.
- `motion-track`: input image plus motion-track control video plus prompt to MP4
  with audio. Use `comfy-motion-track-control` for IC-LoRA setup and control
  video preparation.
- `wan22-i2v`: WAN 2.2 input image plus prompt to MP4.
- `wan22-flf2v`: WAN 2.2 first image plus last image plus prompt to MP4.
- `seedance2-t2v`: remote Seedance 2.0 text prompt to MP4.
- `seedance2-r2v`: remote Seedance 2.0 reference image plus prompt to MP4.
- `seedance2-flf2v`: remote Seedance 2.0 first image plus last image plus
  prompt to MP4.

## Commands

Text to video:

```bash
uv run comfy-videogen t2v \
  --prompt "a slow cinematic camera push through a warm coffee shop, soft ambient room tone" \
  --out outputs
```

Image to video:

```bash
uv run comfy-videogen i2v \
  --input path/to/image.png \
  --prompt "steam rises gently while the camera slowly pushes in, warm cinematic ambience" \
  --out outputs
```

Image plus audio to audiovisual video:

```bash
uv run comfy-videogen ia2av \
  --input path/to/image.png \
  --audio path/to/song.wav \
  --prompt "a slow expressive portrait animation, subtle head movement and lighting pulses synchronized with the song, cinematic shallow depth of field" \
  --length 97 \
  --fps 24 \
  --out outputs
```

First/last frame:

```bash
uv run comfy-videogen flf2v \
  --first path/to/start.png \
  --last path/to/end.png \
  --prompt "a smooth transition between the two frames with subtle camera motion and ambient sound" \
  --width 540 \
  --height 360 \
  --extra-lora .loki/models/comfyui/loras/ltx23/detailer.safetensors:0.7:0.0 \
  --out outputs
```

HDR IC-LoRA:

```bash
uv run comfy-videogen motion-track \
  --input path/to/start.png \
  --control-video path/to/motion-reference.mp4 \
  --prompt "cinematic portrait, hair and camera follow the drawn motion paths, natural motion" \
  --attention-strength 1.0 \
  --out outputs
```

WAN 2.2 image to video:

```bash
uv run comfy-videogen wan22-i2v \
  --input path/to/image.png \
  --prompt "cinematic camera drift, subtle subject motion, natural lighting" \
  --length 81 \
  --fps 16 \
  --high-steps 10 \
  --low-steps 10 \
  --out outputs
```

WAN 2.2 first/last frame:

```bash
uv run comfy-videogen wan22-flf2v \
  --first path/to/start.png \
  --last path/to/end.png \
  --prompt "smooth cinematic transition between both frames, coherent motion" \
  --length 81 \
  --fps 16 \
  --high-steps 2 \
  --low-steps 2 \
  --out outputs
```

Seedance 2.0 text to video:

```bash
COMFY_ORG_API_KEY=... uv run comfy-videogen seedance2-t2v \
  --prompt "cinematic shot of a futuristic city at sunset, slow camera drift" \
  --out outputs
```

Seedance 2.0 reference image to video:

```bash
COMFY_ORG_API_KEY=... uv run comfy-videogen seedance2-r2v \
  --input path/to/image.png \
  --prompt "slow expressive portrait animation, subtle head movement and soft lighting changes" \
  --out outputs
```

Seedance 2.0 first/last frame:

```bash
COMFY_ORG_API_KEY=... uv run comfy-videogen seedance2-flf2v \
  --first path/to/start.png \
  --last path/to/end.png \
  --prompt "smooth cinematic transition between both frames" \
  --out outputs
```

## Prompt Guidance

Describe visual motion, camera movement, subject action, scene mood, and audio
texture. Keep prompts concrete and short enough for a single shot. For `i2v`,
`ia2av`, and `flf2v`, name what should remain anchored to the input image or
guide frames.

For `ia2av`, the prompt should describe how the image should move in relation to
the audio: tempo-synced lighting pulses, breathing portrait motion, subtle camera
drift, dance movement, performance gestures, or environmental reaction. The
video duration is controlled by `--length / --fps`; long songs are trimmed to
that window unless `--audio-start-time` or `--audio-duration` is passed.

Use the collected `resolution` and `aspectRatio` arguments instead of inventing
raw dimensions. Loki translates `480p`/`720p` plus the selected frame into
managed `--width`/`--height` values for local modes, and passes `--resolution`
directly to Seedance 2.0.

## Defaults

### LTX 2.3 Local

- Models directory: `.loki/models/comfyui`
- Checkpoint: `checkpoints/10Eros_v1-fp8mixed_learned.safetensors`
- Text encoder: `text_encoders/gemma_3_12B_it_fp4_mixed.safetensors`
- Distilled LoRA: `loras/ltx23/ltx-2.3-22b-distilled-lora-384.safetensors`
- Text-encoder LoRA: `loras/ltx23/gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors`
- Upscaler: `latent_upscale_models/ltx-2.3-spatial-upscaler-x2-1.1.safetensors`
- HDR IC-LoRA: `loras/ltx23/ltx-2.3-22b-ic-lora-hdr-0.9.safetensors`
- Video params: `width=512`, `height=320`, `length=49`, `fps=24`, `cfg=1.0`, `seed=0`
- Motion-track params: `attention_strength=1.0`, `reference_downscale=1.0`
- IA2AV audio params: `audio_start_time=0.0`, `audio_duration=length/fps` by default
- Dependency: `comfy-diffusion[comfyui,video,audio]` v2.2.0 or newer for HDR IC-LoRA

### WAN 2.2 Local

- Models directory: `.loki/models/comfyui`
- Profile: `wan22-i2v`
- Dasiwa profiles: `wan22-dasiwa-tastysin-i2v`, `wan22-dasiwa-boundbite-i2v`
- Supported modes: `wan22-i2v`, `wan22-flf2v`
- Video params: `fps=16`; recommended frame counts are `49` for 3 seconds,
  `81` for 5 seconds, `113` for 7 seconds, `161` for 10 seconds, and `241` for
  15 seconds.
- Standard default steps: `highNoiseSteps=10`, `lowNoiseSteps=10`
- Dasiwa default steps: `highNoiseSteps=2`, `lowNoiseSteps=2`
- Required local files include WAN 2.2 high/low-noise diffusion models, text encoder, and VAE as reported by `comfy-models validate-profile <profile>`.

Extra LoRAs are optional and ad hoc. Use repeatable
`--extra-lora PATH[:MODEL_STRENGTH[:CLIP_STRENGTH]]` after resolving the file
through `loras/ltx23/` or the loose `loras/` fallback. In this cut, extra LoRAs
are supported for `flf2v`; `t2v`, `i2v`, and `ia2av` return clean JSON errors if
an extra LoRA is supplied because those modes still use upstream wrappers without
a safe insertion point.

### Seedance 2.0 Remote API

- Auth: `COMFY_ORG_API_KEY`
- Profile: `seedance2-api`
- Provider: `comfy-api`
- Model: `Seedance 2.0`
- Params: `resolution=480p`, `ratio=16:9`, `duration=7`, `generate_audio=true`, `watermark=false`, `seed=0`
- No local weights, no `models_dir`, no downloader, no LoRAs, no ComfyUI server.
- Requires a `comfy-diffusion` version that vendors ComfyUI API Nodes with
  `ByteDance Seedance 2.0`. If missing, the CLI returns `missing_dependency`.
- Do not use Seedance 1.x/1.5, OAuth, or token auth in this skill.

## Output Handling

The CLI prints JSON to stdout. On success, read `artifacts` for the saved MP4 path.
On failure, read `error` and `error_type`; do not parse logs for control flow.

After every successful video command, immediately index the same output directory
so the new artifact appears in Comfy Media:

```bash
uv run comfy-media index --out outputs
```

Audio is required in v1. If MP4 audio muxing fails, the command fails instead of
silently saving a no-audio video.
