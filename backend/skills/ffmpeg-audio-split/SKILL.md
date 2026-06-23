---
name: ffmpeg-audio-split
description: Split one selected Loki canvas audio card into multiple shorter audio clip cards using ffmpeg. Use when the user wants to cut, segment, chop, split, or divide an existing selected audio file into 3, 5, 7, 10, or 15 second clips. Do not use for generating new audio, video work, image work, or ComfyUI workflows.
metadata:
  loki:
    visibility: user
    capabilities: [audio-editing, audio-composition, ffmpeg]
    arguments:
      - id: clipDurationSeconds
        label: Clip duration
        description: Choose the duration for each generated audio clip.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: "3"
            label: 3 seconds
            description: Split the audio into 3-second clips.
          - value: "5"
            label: 5 seconds
            description: Split the audio into 5-second clips.
          - value: "7"
            label: 7 seconds
            description: Split the audio into 7-second clips.
          - value: "10"
            label: 10 seconds
            description: Split the audio into 10-second clips.
          - value: "15"
            label: 15 seconds
            description: Split the audio into 15-second clips.
    action:
      type: cli-local
      command: [python3, scripts/split_audio.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: audio
---

# ffmpeg-audio-split

Use this skill to split one selected Loki canvas audio card into multiple audio
clip cards using `ffmpeg`.

The action reads audio only from selected cards. It uses the first resolvable
audio asset in selected-card order. Do not use this skill when the user wants
to generate new audio content.

## Parameters

Loki asks for `clipDurationSeconds` before invocation.

Supported clip durations match the short video duration presets:

- `3`
- `5`
- `7`
- `10`
- `15`

Optional params may be passed through `paramsJson`:

- `title`: base title for generated clips. Default `Audio clip`.

## Behavior

The action creates consecutive clips from the selected audio. The final clip is
included even when it is shorter than the selected duration.

Each output clip is normalized as:

- M4A container.
- AAC stereo audio at 48 kHz.

On success, the action returns one audio artifact per generated clip for Loki to
package as separate audio cards. On failure, read the action error; do not run
any ComfyUI workflow.
