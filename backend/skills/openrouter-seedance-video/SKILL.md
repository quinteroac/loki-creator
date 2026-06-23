---
name: openrouter-seedance-video
description: Generate Seedance 2.0 videos through Loki's direct OpenRouter route. Use for Video Director Seedance generation, reference-to-video, and approved Seedance clips. Do not route through ComfyUI.
metadata:
  loki:
    visibility: internal
    capabilities: [video-generation, image-to-video, seedance, openrouter, raster-card-output]
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
          - value: "9:16"
            label: Vertical 9:16
      - id: duration
        label: Duration
        description: Choose the target video duration.
        type: choice
        required: true
        askWhen: always
        order: 20
        options:
          - value: "5"
            label: 5 seconds
          - value: "7"
            label: 7 seconds
          - value: "10"
            label: 10 seconds
          - value: "15"
            label: 15 seconds
    action:
      type: cli-local
      command: [python3, scripts/seedance_openrouter_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: video
---

# openrouter-seedance-video

Use this skill for Seedance 2.0 generation through Loki's direct OpenRouter
service. It requires one selected or attached local image artifact. The action
uses `SeedanceVideoGenerationService` and returns the packaged video card from
that direct route.

Do not use ComfyUI Seedance modes for Video Director's `Seedance via
OpenRouter` engine.
