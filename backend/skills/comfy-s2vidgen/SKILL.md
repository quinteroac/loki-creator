---
name: comfy-s2vidgen
description: Generate audio-driven MP4 videos with comfy-diffusion WAN 2.2 S2V from one selected image plus one selected audio clip. Use when the user wants WAN S2V, sound-to-video, audio-driven character motion, dialogue, singing, or performance video saved into the Loki workspace. Do not use for text-only video, image-to-video without audio, first/last-frame video, music generation, voice generation, image generation, model downloads, ComfyUI server workflows, or non-WAN video APIs.
metadata:
  loki:
    visibility: user
    capabilities: [video-generation, sound-to-video, raster-card-output, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    arguments:
      - id: modelProfile
        label: S2V model
        description: Choose the WAN sound-to-video model profile.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: wan22-s2v
            label: WAN 2.2 S2V FP8
            description: Standard local GPU-backed WAN 2.2 sound-to-video profile.
          - value: wan22-dasiwa-littledemon-v2-s2v
            label: Dasiwa LittleDemon S2V
            description: Dasiwa LittleDemon V2 WAN 2.2 sound-to-video profile.
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
        description: Choose the target video resolution.
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
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 900
    output:
      packager: auto
      kind: video
---

# comfy-s2vidgen

Use this skill for WAN 2.2 sound-to-video through the `comfy-videogen wan22-s2v`
CLI. It requires one selected image and one selected audio clip. Loki resolves
selected card artifacts into local `--input` and `--audio` paths, so do not ask
the user for filesystem paths when cards are already selected.

If `comfy-videogen` or `comfy-models` is not available, use `comfy-tools-setup`
first. If model validation fails with `missing_model_file`, use
`comfy-model-downloader` for `videogen.wan22-s2v`.

## Required Arguments

Loki declares `modelProfile`, `aspectRatio`, and `resolution` as required skill
arguments. The bridge asks only those three before invoking this skill.

Do not ask for duration. The runtime measures the selected audio with `ffprobe`
and sets `--length` to `ceil(audio_seconds * 16)` with `--fps 16`. For example,
14 seconds of audio generates 224 frames. Fractional durations round up so the
video does not cut off the audio.

Resolution choices:

- `480p`: `848x480` for `16:9`, `480x848` for `9:16`, `480x480` for `1:1`, and
  `640x480` for `4:3`.
- `720p`: `1280x720` for `16:9`, `720x1280` for `9:16`, `720x720` for `1:1`,
  and `960x720` for `4:3`.

## Prompt Guidance

WAN S2V prompts should describe a single audio-driven scene, not a generic
animation instruction. Follow the official WAN S2V examples:
https://humanaigc.github.io/wan-s2v-webpage/

Before invoking the Loki action, rewrite the user's request into the final WAN
S2V scene prompt. The action's `prompt` argument must be that final scene prompt,
because Loki stores it on the generated video card. Do not pass request wording,
tool instructions, UI copy, or selected-card boilerplate such as `Generate an
audio-driven video from the selected image and selected audio clip`.

Write prompts in this shape:

- Start with `In the video, ...` or `The video shows ...`.
- Name the subject and what they do with the audio: speaking, singing, dialogue,
  chanting, playing music, or reacting to rhythm.
- Include expression and performance details: emotional state, gaze, mouth
  motion, head movement, hands, body posture, or dance/performance gestures.
- Add camera and environment when useful: slow push-in, handheld movement,
  rooftop wind, rain, train motion, stage lighting, church interior, seaside,
  or other scene context.
- Preserve important visual identity from the selected image, but phrase it as
  scene content rather than as input mechanics.

Good prompt:

```text
In the video, a woman is singing on a rainy ship deck. Her expression is serious
and emotional, her wet hair moves in the wind, the camera sways slightly with
the storm, and waves splash around her.
```

Avoid vague prompts such as `animate this image to the audio`. Convert them into
a concrete performance scene while preserving the selected image identity.

Bad action prompt:

```text
Generate an audio-driven video from the selected anime-style image of a girl
singing on stage and the selected audio clip.
```

Better action prompt:

```text
In the video, an anime-style girl with long flowing hair sings into a handheld
microphone on a softly lit stage. Her mouth follows the vocals, her eyes look
expressive and focused, one hand lifts with the rhythm, and the camera holds a
steady medium shot with a gentle push-in.
```

## Command Shape

The runtime builds this command:

```bash
uv run comfy-videogen wan22-s2v \
  --models-dir .loki/models/comfyui \
  --input path/to/image.png \
  --audio path/to/audio.wav \
  --prompt "In the video, ..." \
  --width 848 \
  --height 480 \
  --length 224 \
  --fps 16 \
  --audio-duration 14 \
  --out outputs
```

The CLI prints JSON to stdout. On success, read `artifacts` for the saved MP4
path. On failure, read `error` and `error_type`; do not parse logs for control
flow.

## Preflight Checklist

Before invoking the Loki action, verify:

- The selected inputs include exactly what WAN S2V needs: one image and one
  audio clip.
- The only required user choices are present: `modelProfile`, `aspectRatio`, and
  `resolution`.
- No duration was requested from the user and no duration is passed in params;
  runtime derives frames from audio duration at 16 fps.
- The action `prompt` is the final WAN S2V scene prompt, not a copy of the user
  request, UI text, or selected-card boilerplate.
- The prompt starts with `In the video, ...` or `The video shows ...`.
- The prompt describes one coherent scene with subject identity, speech/singing
  or other audio-driven performance, mouth movement, expression, body movement,
  camera, and environment.
- Important visual details from the selected image are preserved as scene
  content.
- `paramsJson` contains the chosen `modelProfile`, `aspectRatio`, and
  `resolution`, and does not include `duration`, `highNoiseSteps`, or
  `lowNoiseSteps`.
