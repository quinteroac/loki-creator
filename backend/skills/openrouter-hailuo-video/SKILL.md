---
name: openrouter-hailuo-video
description: Generate MiniMax H3 (Hailuo 3) videos through OpenRouter. Use for Video Director text-to-video, image-to-video, or first/last-frame clips with H3. Do not route through ComfyUI.
metadata:
  loki:
    visibility: internal
    capabilities: [video-generation, text-to-video, image-to-video, first-last-frame, audio-generation, minimax, hailuo, openrouter, video-card-output]
    arguments:
      - id: aspectRatio
        label: Aspect ratio
        description: Choose the H3 video frame.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: "21:9"
            label: Ultrawide 21:9
          - value: "16:9"
            label: Widescreen 16:9
          - value: "4:3"
            label: Landscape 4:3
          - value: "1:1"
            label: Square 1:1
          - value: "3:4"
            label: Portrait 3:4
          - value: "9:16"
            label: Vertical 9:16
      - id: duration
        label: Duration
        description: Choose a duration supported by MiniMax H3.
        type: choice
        required: true
        askWhen: always
        order: 20
        options:
          - value: "5"
            label: 5 seconds
          - value: "6"
            label: 6 seconds
          - value: "7"
            label: 7 seconds
          - value: "8"
            label: 8 seconds
          - value: "9"
            label: 9 seconds
          - value: "10"
            label: 10 seconds
          - value: "11"
            label: 11 seconds
          - value: "12"
            label: 12 seconds
          - value: "13"
            label: 13 seconds
          - value: "14"
            label: 14 seconds
          - value: "15"
            label: 15 seconds
    action:
      type: cli-local
      command: [python3, scripts/hailuo_openrouter_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: video
---

# openrouter-hailuo-video

Generate MiniMax H3 video through Loki's OpenRouter service. Use no selected
image for text-to-video, one local image for image-to-video, or two local images
for first/last-frame control. Preserve selected-card order when assigning the
first and last frames.

The action fixes resolution to H3's supported `2K` tier and enables generated
audio. Pass only local Loki artifact-backed images; preview-only and inline
data URL inputs are not executable references.
