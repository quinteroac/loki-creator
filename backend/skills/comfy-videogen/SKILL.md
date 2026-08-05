---
name: comfy-videogen
description: Generate MP4 videos with comfy-diffusion using local LTX 2.3, WAN 2.2, MiniMax H3 T2V/I2V/R2V, or remote ByteDance Seedance 2.0 API nodes. Use when the user wants local GPU-backed video generation saved into the workspace. Do not use for WAN audio-driven clips, image-only generation, music-only generation, voice generation, model downloads, ComfyUI server workflows, UI work, custom node installation, or non-Seedance hosted video APIs.
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
          - value: ltx23-dasiwa-golden-lace-v3
            label: LTX 2.3 Dasiwa Golden Lace
            description: Local GPU-backed Dasiwa Golden Lace v3 profile for LTX 2.3 workflows.
          - value: wan22-i2v
            label: WAN 2.2 FP8
            description: Local GPU-backed WAN 2.2 image-to-video and first/last-frame workflows. Default 10 high-noise steps and 10 low-noise steps.
          - value: wan22-t2v
            label: WAN 2.2 T2V
            description: Local GPU-backed WAN 2.2 text-to-video workflow. Use for reference-guided text-to-video after describing the selected image.
          - value: wan22-dasiwa-tastysin-i2v
            label: WAN 2.2 Dasiwa TastySin
            description: Local Dasiwa WAN 2.2 TastySin profile. Default 2 high-noise steps and 2 low-noise steps.
          - value: wan22-dasiwa-boundbite-i2v
            label: WAN 2.2 Dasiwa BoundBite
            description: Local Dasiwa WAN 2.2 BoundBite profile. Default 2 high-noise steps and 2 low-noise steps.
          - value: seedance2-api
            label: Seedance 2.0 API
            description: Remote ByteDance Seedance 2.0 API nodes through ComfyUI API Nodes.
          - value: minimax-h3
            label: MiniMax H3 Local
            description: Local MiniMax H3 video with synchronized native audio.
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
          - value: r2v
            label: Reference to video
            description: Read one selected reference image, describe it in the prompt, then create a text-to-video clip.
          - value: flf2v
            label: First/last frame
            description: Use selected images as storyboard pairs. One image duplicates as first and last; two images create one transition; three or four images create two transitions.
          - value: minimax-h3-t2v
            label: MiniMax text to video
            description: Generate a local MiniMax H3 clip from text with synchronized native audio.
          - value: minimax-h3-i2v
            label: MiniMax image to video
            description: Animate one selected image with local MiniMax H3 and synchronized native audio.
          - value: minimax-h3-r2v
            label: MiniMax reference to video
            description: Generate from one or more selected reference images with local MiniMax H3.
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
        order: 70
        options: []
      - id: lowNoiseSteps
        label: WAN low-noise steps
        description: Optional WAN 2.2 low-noise model steps. More low steps usually means more detail/refinement.
        type: text
        required: false
        askWhen: missing
        order: 80
        options: []
      - id: fps
        label: WAN FPS
        description: Optional WAN 2.2 frame rate. Default is 16 FPS; choose 24 FPS only when the user explicitly asks for smoother WAN motion.
        type: choice
        required: false
        askWhen: missing
        order: 60
        options:
          - value: "16"
            label: 16 FPS
            description: Compatible default for WAN 2.2.
          - value: "24"
            label: 24 FPS
            description: Smoother WAN 2.2 output with more frames.
      - id: extraLora
        label: Extra LoRA
        description: Optional compatible LoRA name or path, with optional strength like relight:0.7. Use only when the user explicitly asks for a LoRA.
        type: text
        required: false
        askWhen: missing
        order: 90
        options: []
      - id: extraLoraHigh
        label: WAN high LoRA
        description: Optional WAN 2.2 high-noise UNet LoRA name or path. Use only when the user asks for a high-noise-specific LoRA.
        type: text
        required: false
        askWhen: missing
        order: 100
        options: []
      - id: extraLoraLow
        label: WAN low LoRA
        description: Optional WAN 2.2 low-noise UNet LoRA name or path. Use only when the user asks for a low-noise-specific LoRA.
        type: text
        required: false
        askWhen: missing
        order: 110
        options: []
      - id: sageAttention
        label: SageAttention
        description: Enable SageAttention for MiniMax H3. Requires the sageattention package.
        type: choice
        required: false
        askWhen: missing
        order: 120
        options:
          - value: "false"
            label: "Off"
          - value: "true"
            label: "On"
      - id: easycache
        label: EasyCache
        description: Enable EasyCache for MiniMax H3 to reduce render time, with some possible quality loss.
        type: choice
        required: false
        askWhen: missing
        order: 130
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
  text-to-video, reference-guided text-to-video, image-to-video,
  image+audio-to-video, first/last-frame, and motion-track workflows.
- `ltx23-dasiwa-golden-lace-v3`: local GPU-backed Dasiwa Golden Lace v3 profile
  for LTX 2.3 workflows. Use this when the user asks for Dasiwa/Golden Lace with
  local LTX text-to-video, reference-guided text-to-video, image-to-video,
  image+audio-to-video, or first/last-frame generation.
- `wan22-t2v`: local GPU-backed WAN 2.2 text-to-video workflow. Use this for WAN
  reference-guided text-to-video after describing the selected reference image.
- `wan22-i2v`: local GPU-backed WAN 2.2 workflows. Use this for image-to-video
  and first/last-frame video when the user explicitly asks for WAN/Wan 2.2 or
  wants the standard WAN local model. For `r2v`, the runtime uses `wan22-t2v`
  instead. Defaults: `highNoiseSteps=10`, `lowNoiseSteps=10`.
- `wan22-dasiwa-tastysin-i2v`: local Dasiwa WAN 2.2 TastySin profile. Use when
  the user asks for Dasiwa/TastySin image-to-video or first/last-frame
  generation. For `r2v`, the runtime uses `wan22-dasiwa-tastysin-t2v` instead.
  Defaults: `highNoiseSteps=2`, `lowNoiseSteps=2`.
- `wan22-dasiwa-boundbite-i2v`: local Dasiwa WAN 2.2 BoundBite profile. Use when
  the user asks for Dasiwa/BoundBite image-to-video or first/last-frame
  generation. For `r2v`, the runtime uses `wan22-dasiwa-boundbite-t2v` instead.
  Defaults: `highNoiseSteps=2`, `lowNoiseSteps=2`.
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
- `r2v`: reference-guided text-to-video. Requires one selected or attached image.
  In agent mode with a vision-capable PI model, use `read_loki_visual` on the
  selected local image, write a concrete visual description into the
  generation prompt, then run text-to-video from that prompt. The runtime
  validates that a reference image exists, but does not pass it to the Comfy
  video CLI as `--input`. Supported profiles are `ltx23-10eros`,
  `ltx23-dasiwa-golden-lace-v3`, `wan22-t2v`, `wan22-i2v`,
  `wan22-dasiwa-tastysin-i2v`, and `wan22-dasiwa-boundbite-i2v`; WAN image
  profiles are converted to their matching T2V profile for execution, preserving
  Dasiwa TastySin/BoundBite when selected.
  Seedance remains out of scope for this Loki skill mode.
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

Selected-card inputs are handled by Loki. When the user has selected image,
audio, or video cards, do not ask the user for filesystem paths and do not try to
invent local paths from `/api/artifacts/...` URLs. Invoke this skill with the
chosen `modelProfile`, `videoMode`, duration, resolution, and aspect ratio; the
runtime resolves selected card `metadata.artifactUrl`, `mediaAssets`, and
validated local media references into local files for `--input`, `--audio`,
`--first`, `--last`, or `--control-video`. Inline `dataUrl` values and rendered
previews are UI-only and are not valid skill inputs.

For `r2v`, use the selected image as visual context for the agent, not as a
Comfy image-conditioning input. Before invoking the skill action, describe the
reference image in the final generation prompt: subject identity, composition,
style, lighting, materials, palette, and any details the video should preserve.
Then add the intended motion, camera behavior, temporal change, and audio cues.
Use `read_loki_visual` on the selected local image and fold its concrete
subject, composition, style, lighting, materials, palette, and identity traits
into the final prompt. If visual reading is unavailable because the selected
agent model does not have vision, ask for the missing visual details instead of inventing
them.

Duration, WAN FPS, and WAN step choices:

- `3`, `5`, `7`, `10`, or `15` seconds. Local LTX converts duration to `length` frames
  using `fps=24` unless another fps is explicitly provided. Seedance receives
  the same value as `--duration`.
- WAN 2.2 uses `fps=16` by default and also accepts `fps=24` when the user
  explicitly asks for smoother WAN motion. WAN length is always
  `duration * fps + 1`, so 5 seconds at 16 FPS is `81` frames and 5 seconds at
  24 FPS is `121` frames. Do not cut WAN clips to `duration * fps` frames such
  as `80` at 16 FPS, because it weakens motion and first/last-frame adherence.
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
`comfy-lora-onboarding` to search the architecture folder first (`loras/ltx23/`
for LTX, `loras/wan22/` for WAN) and pass the chosen file only to modes that
support ad hoc LoRA insertion.

## Modes

- `t2v`: text prompt to MP4 with audio.
- `r2v`: selected reference image plus prompt to MP4. The agent reads the
  selected image, folds a visual description into the prompt, and the runtime
  maps the request to the matching text-to-video CLI workflow (`t2v` for LTX,
  `wan22-t2v` for WAN). The selected image is required for agent context and
  validation, but is not passed to the CLI as `--input`.
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
  --length 121 \
  --fps 24 \
  --high-steps 10 \
  --low-steps 10 \
  --extra-lora .loki/models/comfyui/loras/wan22/blue-motion.safetensors:0.7 \
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
  --extra-lora-high .loki/models/comfyui/loras/wan22/high-noise-detail.safetensors:0.6 \
  --extra-lora-low .loki/models/comfyui/loras/wan22/low-noise-color.safetensors:0.4 \
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

MiniMax H3 T2V and I2V prompts use the official three-field structure:
`integrated_multimodal_description`, `overall_soundscape`, and
`non_diegetic_music`. I2V prompts begin with the exact first-frame instruction.
MiniMax H3 R2V prompts use the official full-reference six-section structure:
`subject_definitions`, `summary`, `retention_analysis`,
`detailed_description`, `overall_soundscape`, and `non_diegetic_music`.
R2V keeps `<Picture N>`/`<Subject N>` labels stable. Describe shots, camera
motion, actions, dialogue, visible text, and diegetic sound concretely; keep
dialogue verbatim inside `<d>` tags. Consult the official MiniMax H3 base and
full-reference prompt guides when constructing these prompts.

The prompt sent to the selected video model must be final model-facing text.
Do not write it as a request to an agent, a workflow handoff, or an explanation
of the prompt. Avoid `Create a ... clip`, `using the supplied image`, execution
notes, parameter notes, JSON, Markdown fences, and explanations of H3 field
names. For H3, retain only the required field labels and their content; use the
three-field format for T2V/I2V and the six-section full-reference format for
R2V. Use `<Picture N>`/`<Subject N>` only where the model needs those reference
labels.

For local Comfy video profiles, Loki does not add an NSFW filter and does not
rewrite adult prompts into softer substitutes. Preserve adult/NSFW user intent
while still writing a clear model-friendly shot prompt with concrete motion,
camera behavior, and duration-appropriate action. Remote profiles such as
`seedance2-api` may still fail according to provider-side rules outside Loki's
control.

For LTX 2.3 profiles, write the action prompt like a compact shot direction for
a cinematographer. LTX 2.3 handles more detail than earlier LTX workflows, so do
not reduce the prompt to a vague mood tag. Use one flowing paragraph in present
tense, with enough detail to fill the selected duration.

For every LTX prompt, include:

- Shot setup: shot scale, composition, spatial layout, and whether the frame is
  vertical, widescreen, square, or classic 4:3.
- Subject and action: who moves, what moves, how it moves, and what changes from
  the first moment to the final moment.
- Camera behavior: push in, pull back, track, pan, tilt, handheld drift, static
  hold, or another concrete movement relative to the subject.
- Environment and material detail: lighting, color palette, atmosphere, fabric,
  hair, surface finish, particles, reflections, wear, or edge detail.
- Audio when the mode produces or uses audio: ambient sound, voice quality,
  music, impact sounds, or the way the motion reacts to the audio.

For LTX `r2v`, describe the selected reference image first, then describe the
motion and shot. The model receives text only, so do not rely on the selected
image being passed to Comfy as conditioning.
For LTX `t2v`, describe the full scene because the model has no visual anchor.
For LTX `i2v`, `ia2av`, and `flf2v`, focus on motion and transformation: the
input image or guide frames already define the visual identity. Preserve
important visible identity and composition, but avoid spending the prompt on
static details that are already obvious from the selected card.

For LTX portrait output, compose vertically on purpose: subject placement,
headroom, hands, foreground/background spacing, and camera movement should make
sense in a tall frame, not a cropped landscape shot.

For `ia2av`, describe the visual interpretation of the audio: tempo-synced
lighting pulses, breathing portrait motion, mouth movement, performance
gestures, dance movement, or environmental reaction. The video duration is
controlled by `--length / --fps`; long songs are trimmed to that window unless
`--audio-start-time` or `--audio-duration` is passed.

Avoid LTX prompts that are static, contradictory, or overly numerical. Do not
write only `a cinematic portrait`, `make the scene come alive`, or abstract
emotional labels such as `sad`; translate emotion into visible acting cues such
as gaze, posture, breath, pauses, facial tension, or hand movement. Do not ask
for readable text/logos, chaotic physics, overloaded crowd scenes, or conflicting
lighting setups.

Good LTX i2v action prompt:

```text
The camera slowly pushes toward the woman in the red coat as rain runs down the
cafe window behind her. She lowers her eyes to the phone, stirs the coffee once,
then looks up toward the street. Warm tungsten light catches the wet glass,
soft reflections shimmer on the table, and faint cafe ambience plays under the
rain.
```

Good LTX flf2v action prompt:

```text
A continuous handheld tracking shot moves from the first frame into the final
pose. The character steps forward, coat fabric fluttering in the wind, hair
strands lifting around the face, while the background neon streaks into soft
motion blur and the camera settles into the final composition.
```

Use the collected `resolution` and `aspectRatio` arguments instead of inventing
raw dimensions. Loki translates `480p`/`720p` plus the selected frame into
managed `--width`/`--height` values for local modes, and passes `--resolution`
directly to Seedance 2.0.

## Defaults

### LTX 2.3 Local

- Models directory: `.loki/models/comfyui`
- Profiles: `ltx23-10eros`, `ltx23-dasiwa-golden-lace-v3`
- 10Eros checkpoint: `checkpoints/10Eros_v1-fp8mixed_learned.safetensors`
- Dasiwa Golden Lace v3 checkpoint: `checkpoints/DasiwaLTX23_goldenLaceV3.safetensors`
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
- Video params: `fps=16` by default, or `fps=24` when requested. Length is
  `duration * fps + 1`; at 16 FPS the standard frame counts are `49`, `81`,
  `113`, `161`, and `241`, while at 24 FPS they are `73`, `121`, `169`, `241`,
  and `361`.
- Standard default steps: `highNoiseSteps=10`, `lowNoiseSteps=10`
- Dasiwa default steps: `highNoiseSteps=2`, `lowNoiseSteps=2`
- Required local files include WAN 2.2 high/low-noise diffusion models, text
  encoder, and VAE as reported by `comfy-models validate-profile <profile>`.

Extra LoRAs are optional and ad hoc. Use repeatable
`--extra-lora PATH[:MODEL_STRENGTH[:CLIP_STRENGTH]]` after resolving the file
through `loras/wan22/` or the loose `loras/` fallback. `wan22-i2v` and
`wan22-flf2v` also support `--extra-lora-high` and `--extra-lora-low` when a LoRA
should affect only the high-noise or low-noise UNet. The Loki runtime accepts
`extraLora`, `extraLoraHigh`, and `extraLoraLow` params and resolves short names
against `loras/wan22/`.

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

Audio is required in v1. If MP4 audio muxing fails, the command fails instead of
silently saving a no-audio video.
