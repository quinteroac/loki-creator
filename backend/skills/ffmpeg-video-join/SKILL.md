---
name: ffmpeg-video-join
description: Join two or more selected Loki canvas video cards into one MP4 using ffmpeg. Use when the user wants to concatenate, stitch, merge, combine, or transition between existing selected videos. Do not use for generating new video, image-only work, audio-only work, or ComfyUI workflows.
metadata:
  loki:
    visibility: user
    capabilities: [video-editing, video-composition, ffmpeg]
    arguments:
      - id: joinMode
        label: Join mode
        description: Choose how the selected videos should be joined.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: direct
            label: Direct cut
            description: Join clips one after another with hard cuts.
          - value: trim-last-frame
            label: Trim last frame
            description: Remove the final frame from each clip except the last and soften color jumps.
          - value: crossfade
            label: Crossfade
            description: Blend video and audio between clips.
          - value: fade-black
            label: Fade through black
            description: Transition between clips through black.
          - value: dissolve
            label: Dissolve
            description: Use a dissolve transition between clips.
    action:
      type: cli-local
      command: [python3, scripts/join_videos.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: video
---

# ffmpeg-video-join

Use this skill to join two or more selected Loki canvas video cards into one
MP4 artifact using `ffmpeg`.

The action reads videos only from selected cards. By default it uses the first
resolvable video asset from each selected card, preserving the selected card
order. If the user asks for a specific clip order, inspect the selected card
names/ids/media assets and pass `paramsJson.videoOrder` with every selected
video in the requested order. Do not use this skill when the user wants to
generate new video content.

## Parameters

Loki asks for `joinMode` before invocation.

Supported modes:

- `direct`: hard cuts, no transition.
- `trim-last-frame`: removes one frame from the end of each clip except the
  last, color-matches each incoming clip to the previous cut, then uses hard
  cuts.
- `crossfade`: blends clips together with a fade transition.
- `fade-black`: fades through black between clips.
- `dissolve`: dissolves between clips.

Optional params may be passed through `paramsJson`:

- `fadeDurationSeconds`: transition duration for transition modes. Default
  `0.5`. The action reduces it when clips are too short, or fails when the clips
  cannot support a transition.
- `videoOrder`: array containing every selected video in the requested order.
  Entries may be selected card ids, card names/display titles, filenames,
  artifact URLs, or local artifact paths. The action fails if any entry cannot
  be matched or if the order omits selected videos.
- `title`: output card title. Default `Joined video`.

## Behavior

The action normalizes all inputs before joining:

- MP4 container.
- H.264 video, `yuv420p`.
- AAC stereo audio at 48 kHz.
- Resolution and FPS matched to the first selected video.
- Aspect ratio preserved with black padding.
- Silent audio inserted for clips without audio.

On success, the action returns one MP4 artifact for Loki to package as a video
card. On failure, read the action error; do not run any ComfyUI workflow.
