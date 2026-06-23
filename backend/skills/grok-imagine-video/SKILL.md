---
name: grok-imagine-video
description: Generate videos with Grok Imagine through the xAI Imagine API. Use when the user explicitly asks for Grok, xAI, Imagine, text-to-video, or image-to-video with Grok. Do not use for image-only generation, local LTX/ComfyUI video, Seedance, audio, or non-Grok video models.
metadata:
  loki:
    visibility: internal
    capabilities: [video-generation, image-to-video, raster-card-output, grok, xai]
    arguments:
      - id: aspectRatio
        label: Aspect ratio
        description: Choose the video frame.
        type: choice
        required: true
        askWhen: always
        order: 10
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
        description: Choose the Grok Imagine video resolution.
        type: choice
        required: true
        askWhen: always
        order: 20
        options:
          - value: "720p"
            label: 720p
            description: Higher-quality video output.
          - value: "480p"
            label: 480p
            description: Faster lower-resolution output.
      - id: duration
        label: Duration
        description: Choose the target video duration.
        type: choice
        required: true
        askWhen: always
        order: 30
        options:
          - value: "5"
            label: 5 seconds
            description: Short clip for quick preview.
          - value: "10"
            label: 10 seconds
            description: Longer clip.
          - value: "15"
            label: 15 seconds
            description: Maximum standard clip duration.
    action:
      type: cli-local
      command: [python3, ../_grok_runtime/grok_imagine_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: video
---

# grok-imagine-video

Use this skill for Grok Imagine text-to-video and image-to-video generation
through the documented xAI video endpoints. If the user has selected an image
card or attached an image, the action sends it as image-to-video input;
otherwise it runs text-to-video.

Auth resolution follows Grok Build media tooling:

- `XAI_API_KEY`
- `GROK_CODE_XAI_API_KEY`
- valid `https://auth.x.ai` access token in `~/.grok/auth.json`

The action never logs token values.

## Parameters

Loki asks for `aspectRatio`, `resolution`, and `duration` before invocation.
The action uses `grok-imagine-video` unless a `model` param is passed.

Supported optional params:

- `model`: override the xAI video model.
- `image`, `imageUrl`, or `imageDataUrl`: explicit image-to-video source.
- `poll`: set to `false` to return a pending request id instead of waiting.
- `pollIntervalMs`: polling interval, default `5000`.
- `pollTimeoutMs`: polling timeout, default `600000`.

## Prompt Guidance

Write prompts as shot direction: subject, action, motion, camera behavior,
lighting, and mood. For selected image cards, describe how the still image
should move rather than restating only its contents.
