---
name: ltx-seed-seeker
description: Explore LTX 2.3 image-to-video seeds, returning three low-resolution candidate video cards, then rerender a selected candidate at higher resolution with the same prompt and seed.
metadata:
  loki:
    visibility: user
    capabilities: [video-generation, image-to-video, seed-exploration, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    arguments:
      - id: runMode
        label: Mode
        description: Choose whether to generate seed previews or rerender a selected preview.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: preview
            label: Generate previews
            description: Create three 360p seed candidate video cards.
          - value: rerender
            label: Rerender selected seed
            description: Regenerate the selected i2v preview at 720p or 1080p.
      - id: modelProfile
        label: LTX profile
        description: Choose the local LTX 2.3 model profile for previews.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          runMode: preview
        order: 20
        options:
          - value: ltx23-10eros
            label: LTX 2.3 Local
            description: Local GPU-backed LTX 2.3 10Eros workflow.
          - value: ltx23-dasiwa-golden-lace-v3
            label: LTX 2.3 Dasiwa Golden Lace
            description: Local GPU-backed Dasiwa Golden Lace v3 profile for LTX 2.3.
      - id: aspectRatio
        label: Aspect ratio
        description: Choose the preview and final video frame.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          runMode: preview
        order: 30
        options:
          - value: "9:16"
            label: Vertical 9:16
            description: Portrait frame for reels and mobile video.
          - value: "16:9"
            label: Widescreen 16:9
            description: Standard cinematic landscape frame.
          - value: "4:3"
            label: Classic 4:3
            description: Classic landscape frame.
      - id: duration
        label: Duration
        description: Choose the preview and final video duration.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          runMode: preview
        order: 40
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
            description: Maximum standard clip duration.
      - id: targetResolution
        label: Final resolution
        description: Choose the rerender resolution for the selected seed preview.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          runMode: rerender
        order: 50
        options:
          - value: 720p
            label: 720p
            description: Higher detail final render.
          - value: 1080p
            label: 1080p
            description: Maximum final render detail.
    action:
      type: cli-local
      command: [python3, scripts/ltx_seed_seeker_action.py]
      timeoutSeconds: 900
    output:
      packager: auto
      kind: video
---

# LTX Seed Seeker

Use this skill when the user wants to explore LTX 2.3 video seeds from selected
image inputs, then choose one candidate for a higher-resolution rerender.

## Modes

- `preview`: generate exactly three 360p MP4 i2v cards from the same selected
  image input, prompt, profile, aspect ratio, and duration. Each candidate uses a
  different seed.
- `rerender`: require a selected LTX Seed Seeker preview card. The action reuses
  the selected card's stored prompt, seed, profile, aspect ratio, source
  images, and duration. Only `targetResolution` changes.

## Prompt Guidance

Write a single-shot LTX 2.3 motion prompt that describes the selected image as
the starting visual anchor and then directs what happens next. LTX 2.3 responds
best to specific shot direction, so write one flowing present-tense paragraph
with subject motion, camera movement, spatial layout, lighting, material detail,
and atmosphere. Match the amount of detail to the selected duration; longer
clips need enough action beats to fill the time.

For image-to-video seed exploration, prioritize verbs and motion over static
description:

- Say who moves, what moves, how it moves, and how quickly.
- Describe the camera relative to the subject: slow push-in, pull-back, tracking
  move, pan, tilt, handheld drift, or static hold.
- Preserve the selected image identity and composition, but do not repeat every
  visible static detail unless it must stay anchored.
- Add texture/material cues when they affect motion: hair strands, fabric,
  glossy surfaces, dust, rain, reflections, smoke, particles, or edge light.
- For portrait previews, compose vertically on purpose with clear headroom,
  hands/body placement, and foreground/background spacing.

Avoid prompts that read like still images, vague phrases such as `the scene
comes alive`, abstract emotion labels without visible acting cues, readable text
or logos, chaotic physics, overloaded scenes, and conflicting lighting.

Good seed prompt:

```text
The camera slowly pushes toward the subject while their hair lifts in a soft
side wind and their coat fabric ripples. They turn their head toward the light,
blink once, and take a small step forward. Warm rim light catches the edge of
the face, fine fabric texture stays visible, and the background drifts into
soft motion blur.
```

Do not ask for collages or merged candidates; previews return three separate
video cards.

Select one image card or attach one image. If multiple images are selected, only
the first image is used for seed exploration.
