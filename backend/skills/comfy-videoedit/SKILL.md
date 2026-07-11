---
name: comfy-videoedit
description: Edit MP4 videos with comfy-diffusion video-edit capabilities exposed by comfy-agent-tools. Use for WAN 2.2 video+audio audio-driven edits, lip sync over an existing video, or WAN 2.2 Bernini reference-guided video edits saved into the Loki workspace. Do not use for plain text-to-video, image-to-video, first/last-frame generation, audio-only work, image-only work, model downloads, ComfyUI server workflows, or non-Comfy video APIs.
metadata:
  loki:
    visibility: user
    capabilities: [video-editing, video-to-video, lip-sync, audio-driven-video, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    arguments:
      - id: editMode
        label: Edit mode
        description: Choose the Comfy video-edit capability.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: audio-driven
            label: Audio-driven edit
            description: Reprocess one selected video with one selected audio clip using WAN 2.2 S2V video-to-video presets.
          - value: lipsync
            label: Lip sync
            description: Lip-sync one selected video to one selected audio clip.
          - value: bernini
            label: Bernini edit
            description: Edit or generate a reference-guided WAN 2.2 Bernini video from a prompt, selected video, and optional selected reference images.
      - id: modelProfile
        label: Video edit model
        description: Choose the underlying WAN 2.2 edit profile.
        type: choice
        required: true
        askWhen: always
        order: 20
        options:
          - value: wan22-dasiwa-littledemon-v2-video-audio
            label: LittleDemon video+audio
            description: Default WAN 2.2 video+audio profile for audio-driven and lip-sync edits.
          - value: wan22-bernini
            label: WAN 2.2 Bernini
            description: Reference-guided Bernini profile for video edits and prompt-guided video creation.
      - id: berniniMode
        label: Bernini mode
        description: Choose whether Bernini edits a video, edits a video with image references, or creates video from references only.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          editMode: bernini
        order: 30
        options:
          - value: v2v
            label: Video to video
            description: Edit one selected source video and inherit its frame size.
          - value: rv2v
            label: Reference video to video
            description: Edit one selected source video using selected reference images, inheriting the source video frame size.
          - value: r2v
            label: Reference to video
            description: Generate a Bernini video from selected reference images without a source video.
      - id: aspectRatio
        label: Aspect ratio
        description: Choose the Bernini R2V frame. V2V and RV2V inherit this from the selected video.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          editMode: bernini
          berniniMode: r2v
        order: 40
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
        description: Choose the standard Loki Bernini R2V size. V2V and RV2V inherit width and height from the selected video.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          editMode: bernini
          berniniMode: r2v
        order: 50
        options:
          - value: 480p
            label: 480p
            description: Faster, lighter edit for previews and iteration.
          - value: 720p
            label: 720p
            description: Higher-detail edit with a heavier generation cost.
      - id: fps
        label: FPS
        description: Choose the Bernini R2V frame rate.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          editMode: bernini
          berniniMode: r2v
        order: 60
        options:
          - value: "16"
            label: 16 FPS
            description: WAN-compatible default.
          - value: "24"
            label: 24 FPS
            description: Smoother output with more frames.
      - id: duration
        label: Duration
        description: Choose the Bernini output duration. Use a longer value when the edit should extend the selected video.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          editMode: bernini
        order: 70
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
            description: Extended clip for longer edits.
      - id: steps
        label: Steps
        description: Optional sampler steps. Use only when the user asks for quality/speed tuning.
        type: text
        required: false
        askWhen: missing
        order: 80
        options: []
      - id: denoise
        label: Denoise
        description: Optional video+audio denoise strength. Lower values preserve more of the original video.
        type: text
        required: false
        askWhen: missing
        order: 90
        options: []
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: video
---

# comfy-videoedit

Use this skill for the video-editing capabilities currently exposed by
`comfy-agent-tools`:

- `audio-driven`: wraps `comfy-videogen wan22-video-audio --mode audio-driven`.
- `lipsync`: wraps `comfy-videogen wan22-video-audio --mode lipsync`.
- `bernini`: wraps `comfy-videogen wan22-bernini`.

If `comfy-videogen`, `comfy-models`, or the local wrapper CLI is not available,
use `comfy-tools-setup` first. If model validation fails with
`missing_model_file`, use `comfy-model-downloader` for the requested capability:
`videogen.wan22-video-audio` or `videogen.wan22-bernini`.

## Required Inputs

For `audio-driven` and `lipsync`, require exactly one selected video and one
selected audio clip. Loki resolves selected cards to local `--input-video` and
`--audio` paths; do not ask the user for filesystem paths when cards are
selected.

For `bernini`, require a final prompt and `params.duration` for every mode. Use
`params.berniniMode` to choose:

- `v2v`: one selected source video and no required reference image. Inherit
  `width` and `height` from the source video; do not ask for aspect ratio or
  resolution.
- `rv2v`: one selected source video plus selected reference images. Inherit
  `width` and `height` from the source video; do not ask for aspect ratio or
  resolution.
- `r2v`: selected reference images without a source video. Ask for
  `aspectRatio`, standard Loki `resolution` (`480p` or `720p`), and `fps`
  (`16` or `24`) before invoking the action.

Use selected images as repeated `--reference-image` values when the user wants
reference-guided identity, style, character, object, or scene control.

## Prompt Guidance

For source-video edits, preserve the user's intent instead of enriching it.
Convert UI wording into a concise model prompt, but do not invent scene,
identity, style, motion, camera, lighting, wardrobe, background, or composition
details unless the user explicitly requested them. The prompt should name the
requested change first and then state that everything else from the source video
must be preserved.

For local edits such as recoloring, object changes, cleanup, or small visual
adjustments, use restrictive language such as `only`, `preserve`, `unchanged`,
and `do not change anything else`. Do not turn a narrow edit into a rich
descriptive generation prompt. Do not pass UI wording such as `edit this video`.

Examples:

- User: `cambia el color de pelo de la chica a rosa`
- Prompt: `Only change the girl's hair color to vivid pink. Preserve the source video exactly: same face, outfit, pose, motion, camera, background, lighting, framing, style, and timing. Do not change anything else.`

- User: `haz que el auto sea rojo`
- Prompt: `Only change the car color to red. Preserve every other visual detail, motion, camera, background, lighting, and timing from the source video.`

- User: `dale un look cyberpunk con lluvia y luces neon`
- Prompt: `Give the source video a cyberpunk look with rain and neon lights. Preserve the original subject identity, motion, framing, and timing unless they must change to apply the requested style.`

For lip sync and audio-driven edits, include a prompt only when visual behavior
matters beyond syncing to the selected audio. Mention mouth movement,
performance energy, camera stability, or framing only when the user requested
those qualities.

For Bernini, always pass a prompt and duration. Keep the prompt as one
present-tense paragraph. For `v2v` and `rv2v`, treat Bernini as a preservative
edit model: keep prompts minimal, change-focused, and explicit about preserving
the selected source video. If selected reference images are used, describe only
the reference details the user asked to transfer; do not add unrelated scene
detail. In agent mode with a vision-capable PI model, use `read_loki_visual` on
selected local images before writing those reference details. For selected video
references, call `read_loki_visual`; if it reports that video bytes cannot be
attached in this runtime, ask for the missing visual details instead of
inventing them. For `r2v`, there is no source video to preserve, so the prompt
may describe the target video, but it still must not add unrequested details.

## Params

Use `params.editMode` with one of `audio-driven`, `lipsync`, or `bernini`.
Optional tuning params are passed through when present:

- Video+audio: `steps`, `denoise`, `cfg`, `sampler`, `scheduler`, `shift`,
  `seed`, `negativePrompt`, `chunkLength`, `chunkOverlap`, `audioStartTime`,
  `maskVideoPath`, and `maskImagePath`.
- Bernini: `berniniMode`, `duration`, `fps`, `steps`, `splitStep`, `cfg`,
  `seed`, `negativePrompt`, `highLoraStrength`,
  `lowLoraStrength`, `sampler`, `scheduler`, and `refMaxSize`. For `r2v`, also
  pass `aspectRatio`, `resolution`, and `fps` (`16` or `24`); for `v2v` and
  `rv2v`, the runtime reads the selected source video dimensions with `ffprobe`
  and passes inherited `width` and `height` to Bernini. The Bernini LightX2V `lora`, `unetHigh`,
  `unetLow`, `textEncoder`, and `vae` paths are model-file overrides, not style
  LoRA controls; do not set them unless correcting model placement.

The local wrapper CLI is `backend/skills/_comfy_runtime/comfy_videoedit.py`.
It exposes `comfy-videoedit video-audio` and `comfy-videoedit bernini` and
delegates to the matching `comfy-videogen` subcommands while preserving the
final JSON output.
