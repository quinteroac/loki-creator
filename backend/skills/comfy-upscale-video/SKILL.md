---
name: comfy-upscale-video
description: Upscale existing MP4 videos with NVIDIA RTX Video Super Resolution or SeedVR2 through comfy-agent-tools. Use when the user selects or provides a local video and wants a higher-resolution MP4 saved into the workspace. Do not use for image upscaling, new video generation, semantic video editing, audio-only work, model downloads, custom node installation, LoRAs, ComfyUI server workflows, or non-Comfy video APIs.
metadata:
  loki:
    visibility: user
    capabilities: [video-upscaling, video-to-video, raster-card-output, comfy]
    runtime:
      modelsDir: .loki/models/comfyui
    arguments:
      - id: engine
        label: Engine
        description: Choose the video upscaling engine.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: rtx-vsr
            label: RTX VSR
            description: Fast NVIDIA RTX Video Super Resolution upscaling.
          - value: seedvr2
            label: SeedVR2
            description: Diffusion video upscaling with SeedVR2 restoration/detail.
      - id: resolution
        label: RTX resolution
        description: Choose the target RTX VSR output bounds. The input aspect ratio is preserved.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          engine: rtx-vsr
        order: 20
        options:
          - value: 1080p
            label: 1080p
            description: HD delivery target with moderate output size.
          - value: 1440p
            label: 1440p
            description: Higher-detail delivery target between HD and 4K.
          - value: 4k
            label: 4K
            description: UHD delivery target for final upscale.
          - value: 720p
            label: 720p
            description: Light upscale for previews or smaller source clips.
          - value: 480p
            label: 480p
            description: Small output target for very low-resolution clips.
          - value: 8k
            label: 8K
            description: Very large output target; use only when explicitly requested.
      - id: resolution
        label: SeedVR2 resolution
        description: Choose the target SeedVR2 short-edge preset. The input aspect ratio is preserved.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          engine: seedvr2
        order: 20
        options:
          - value: 1080p
            label: 1080p
            description: Default SeedVR2 delivery target.
          - value: 1440p
            label: 1440p
            description: Higher-detail delivery target between HD and 4K.
          - value: 4k
            label: 4K
            description: UHD SeedVR2 upscale target.
          - value: 720p
            label: 720p
            description: Lighter SeedVR2 target for previews or smaller source clips.
      - id: quality
        label: Quality
        description: Choose the RTX VSR quality level.
        type: choice
        required: true
        askWhen: always
        dependsOn:
          engine: rtx-vsr
        order: 30
        options:
          - value: ULTRA
            label: Ultra
            description: Highest RTX VSR quality.
          - value: HIGH
            label: High
            description: Strong quality with less cost than Ultra.
          - value: MEDIUM
            label: Medium
            description: Balanced quality and speed.
          - value: LOW
            label: Low
            description: Fastest quality preset.
      - id: processingMode
        label: Processing mode
        description: Choose whether to process the source as one clip or split long videos into 30 second chunks.
        type: choice
        required: true
        askWhen: always
        order: 40
        options:
          - value: single
            label: Single clip
            description: Process the selected video in one RTX VSR run.
          - value: long
            label: Long video
            description: Split videos longer than 30 seconds, upscale each part, then join the final MP4.
    action:
      type: cli-local
      command: [python3, ../_comfy_runtime/comfy_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: video
---

# comfy-upscale-video

Use this skill only for upscaling an existing local video through
`comfy-videogen rtx-upscale` or `comfy-videogen seedvr2-upscale`. The input
video should come from selected card snapshots first: `metadata.artifactUrl` or
`mediaAssets` video artifact URLs are required. Rendered previews and inline
data payloads are UI-only and are not valid skill inputs.

RTX Video Super Resolution is a faithful hardware video upscaler. SeedVR2 is a
diffusion video upscaler that can restore/detail video at a higher runtime cost.
Do not add prompt text, LoRAs, image references, or unrelated model files.
Preserve the source clip content and improve resolution through the selected
engine.

If `comfy-videogen` is not available, does not expose `rtx-upscale`, or fails
with `missing_dependency`, the agent must handle setup before giving up. Use
`comfy-tools-setup` or repair the local tool installation, then retry the same
upscale request once. For the RTX VSR `nvidia-vfx` dependency, reinstall the
tool with:

```bash
uv tool install --force --with nvidia-vfx git+https://github.com/quinteroac/comfy-agent-tools
```

The runtime also performs this repair attempt for RTX VSR dependency failures.

This mode requires NVIDIA RTX/CUDA support and the `nvidia-vfx` dependency
inside the comfy-agent-tools environment. Dependency failures are agent-owned;
hardware failures such as no CUDA-capable RTX GPU are user/environment issues
and should be reported clearly after the dependency repair attempt has been
made.

SeedVR2 uses `comfy-videogen seedvr2-upscale`. It fetches the pinned
`numz/ComfyUI-SeedVR2_VideoUpscaler` upstream repo on first use and auto-
downloads its DiT/VAE model files. Do not use `comfy-model-downloader` for
SeedVR2. Loki passes `--models-dir .loki/models/comfyui/seedvr2` so those files
stay in the workspace model tree.

## Commands

```bash
comfy-videogen rtx-upscale \
  --input-video path/to/input.mp4 \
  --resolution 1080p \
  --quality ULTRA \
  --out outputs
```

```bash
comfy-videogen seedvr2-upscale \
  --input-video path/to/input.mp4 \
  --resolution 1080p \
  --models-dir .loki/models/comfyui/seedvr2 \
  --out outputs
```

## Options

- `engine`: required. Use `rtx-vsr` or `seedvr2`.
- RTX `resolution`: required. Use one of `480p`, `720p`, `1080p`, `1440p`, `4k`, or `8k`.
- SeedVR2 `resolution`: required. Use one of `720p`, `1080p`, `1440p`, or `4k`.
- `quality`: required for RTX only. Use one of `LOW`, `MEDIUM`, `HIGH`, or `ULTRA`.
- `processingMode`: required. Use `single` for normal clips or `long` for videos longer than 30 seconds.

Do not pass `--width`, `--height`, `--scale`, `--chunk-size`, `--temporal-overlap`,
`--batch-size`, `--blocks-to-swap`, `--cuda-device`, `--video-backend`, or
`--verbose` in this Loki skill.

When `processingMode` is `long`, the runtime measures the source duration with
`ffprobe`. Videos longer than 30 seconds are split into exact 30 second MP4
segments, each segment is processed with the selected upscaling engine, and the
resulting MP4 segments are joined with the ffmpeg concat demuxer into one final
video artifact. Clips of 30 seconds or less use the normal single-clip flow.

## Defaults

- RTX profile: `rtx-vsr`
- RTX capability: `videogen.rtx-upscale`
- SeedVR2 profile: `seedvr2`
- SeedVR2 capability: `videogen.seedvr2-upscale`
- SeedVR2 models: `.loki/models/comfyui/seedvr2`
