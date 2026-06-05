---
name: ffmpeg-video-audio-mux
description: Put one selected Loki canvas audio card onto one selected Loki canvas video card using ffmpeg. Use when the user wants to add, replace, mux, attach, or put audio/music/voice/sound onto an existing video without generating new video. Do not use for audio-driven video generation, image-to-video, joining multiple videos, or audio-only work.
metadata:
  loki:
    visibility: user
    capabilities: [video-editing, audio-editing, video-composition, audio-composition, ffmpeg]
    action:
      type: cli-local
      command: [python3, scripts/mux_audio_video.py]
      timeoutSeconds: 900
    output:
      packager: auto
      kind: video
---

# ffmpeg-video-audio-mux

Use this skill to put one selected audio card onto one selected video card and
return a new MP4 video artifact.

The action reads the first resolvable selected video and the first resolvable
selected audio from Loki selected cards. It replaces the video's audio track
with the selected audio. Do not use this skill to generate new video content.

## Behavior

The output is normalized as:

- MP4 container.
- H.264 video, `yuv420p`.
- AAC stereo audio at 48 kHz.

Audio is always fit to the video duration:

- If the selected audio is longer than the video, the audio is cut at the video
  end.
- If the selected video is longer than the audio, silence is added after the
  audio ends until the video ends.

On success, the action returns one MP4 artifact for Loki to package as a video
card. On failure, read the action error; do not run any ComfyUI workflow.
