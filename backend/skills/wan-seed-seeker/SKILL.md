---
name: wan-seed-seeker
description: Explore WAN 2.2 image-to-video and first/last-frame seeds, returning three low-resolution candidate video cards, then rerender a selected candidate at higher resolution with the same prompt and seed.
metadata:
  loki:
    visibility: user
    capabilities: [video-generation, image-to-video, first-last-frame-video, seed-exploration, comfy]
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
            description: Regenerate the selected WAN preview at 720p or 1080p.
      - id: modelProfile
        label: WAN profile
        description: Choose the local WAN 2.2 model profile for previews.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          runMode: preview
        order: 20
        options:
          - value: wan22-i2v
            label: WAN 2.2 FP8
            description: Local GPU-backed WAN 2.2 profile with 10 high-noise and 10 low-noise steps.
          - value: wan22-dasiwa-tastysin-i2v
            label: WAN 2.2 Dasiwa TastySin
            description: Local Dasiwa TastySin WAN profile with 2 high-noise and 2 low-noise steps.
          - value: wan22-dasiwa-boundbite-i2v
            label: WAN 2.2 Dasiwa BoundBite
            description: Local Dasiwa BoundBite WAN profile with 2 high-noise and 2 low-noise steps.
      - id: videoMode
        label: Video mode
        description: Choose how selected images become the seed candidates.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          runMode: preview
        order: 30
        options:
          - value: i2v
            label: Image to video
            description: Use the first selected image as the source frame.
          - value: flf2v
            label: First/last frame
            description: Use the first selected image as the first frame and the last selected image as the last frame.
      - id: aspectRatio
        label: Aspect ratio
        description: Choose the preview and final video frame.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          runMode: preview
        order: 40
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
            description: Maximum standard clip duration.
      - id: targetResolution
        label: Final resolution
        description: Choose the rerender resolution for the selected seed preview.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          runMode: rerender
        order: 60
        options:
          - value: 720p
            label: 720p
            description: Higher detail final render.
          - value: 1080p
            label: 1080p
            description: Maximum final render detail.
      - id: extraLora
        label: WAN LoRA
        description: Optional WAN 2.2 LoRA name or path, with optional strength like relight:0.7. Use only when the user explicitly asks for a LoRA.
        type: text
        required: false
        askWhen: missing
        dependsOn:
          runMode: preview
        order: 70
        options: []
      - id: extraLoraHigh
        label: WAN high LoRA
        description: Optional WAN 2.2 high-noise UNet LoRA name or path. Use only when the user asks for a high-noise-specific LoRA.
        type: text
        required: false
        askWhen: missing
        dependsOn:
          runMode: preview
        order: 80
        options: []
      - id: extraLoraLow
        label: WAN low LoRA
        description: Optional WAN 2.2 low-noise UNet LoRA name or path. Use only when the user asks for a low-noise-specific LoRA.
        type: text
        required: false
        askWhen: missing
        dependsOn:
          runMode: preview
        order: 90
        options: []
    action:
      type: cli-local
      command: [python3, scripts/wan_seed_seeker_action.py]
      timeoutSeconds: 900
    output:
      packager: auto
      kind: video
---

# WAN Seed Seeker

Use this skill when the user wants to explore WAN 2.2 video seeds from selected
image inputs, then choose one candidate for a higher-resolution rerender.

## Modes

- `preview`: generate exactly three 360p MP4 cards from the same selected image
  inputs, prompt, profile, video mode, aspect ratio, and duration. Each
  candidate uses a different seed.
- `rerender`: require a selected WAN Seed Seeker preview card. The action reuses
  the selected card's stored prompt, seed, profile, video mode, aspect ratio,
  source images, duration, and WAN step counts. Only `targetResolution` changes.

## Video Modes

- `i2v`: use the first selected image as the source image for all three seed
  candidates.
- `flf2v`: use the first selected image as the first frame and the last selected
  image as the last frame. If only one image is selected, duplicate it as both
  endpoints.

WAN 2.2 does not use the LTX 2x upscale workflow, so the CLI receives the direct
target dimensions for `360p`, `720p`, and `1080p`.

## LoRAs

If the user asks to explore seeds with a WAN LoRA, use `comfy-lora-onboarding`
to resolve the file from `loras/wan22/` and pass it as `params.extraLora`.
Optional high/low specific WAN LoRAs can be passed as `params.extraLoraHigh` and
`params.extraLoraLow`. Preview metadata stores the resolved LoRA paths, and
`rerender` reuses them automatically with the selected seed.

## Prompt Guidance

Write a single-shot WAN motion prompt that describes the transition or image
animation, subject motion, camera movement, atmosphere, and what should remain
anchored to the selected image inputs. Do not ask for collages or merged
candidates; previews return three separate video cards.
