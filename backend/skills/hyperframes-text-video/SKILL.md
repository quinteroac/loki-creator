---
name: hyperframes-text-video
description: Create an MP4 video with animated titles, subtitles, lower thirds, quotes, captions, or CTAs over one selected Loki image or video using HyperFrames. Use when the user wants editorial/social text animation, title cards, subtitle overlays, caption stacks, or branded text motion over existing media. Do not use for generating new imagery, changing the underlying image/video content, audio generation, transcription, or transparent overlay delivery.
metadata:
  loki:
    visibility: user
    capabilities: [video-composition, title-animation, subtitle-animation, text-overlay, hyperframes]
    arguments:
      - id: videoResolution
        label: Video resolution
        description: Choose the output video resolution.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: 480p
            label: 480p
            description: Faster render for drafts and social previews.
          - value: 720p
            label: 720p
            description: Higher detail with a heavier render.
      - id: aspectRatio
        label: Aspect ratio
        description: Choose the output video frame.
        type: choice
        required: true
        askWhen: always
        order: 20
        options:
          - value: "16:9"
            label: Widescreen 16:9
            description: Standard landscape video.
          - value: "9:16"
            label: Vertical 9:16
            description: Reels, shorts, stories, and mobile-first video.
          - value: "1:1"
            label: Square 1:1
            description: Square social feed video.
    action:
      type: cli-local
      command: [python3, scripts/hyperframes_text_video_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: video
---

# hyperframes-text-video

Use this skill to create a final MP4 with animated text over exactly one
selected Loki image or video card. The user can describe the desired titles or
subtitles in natural language, but the action contract is structured: before
invoking the skill, build `params.scriptJson`.

Loki asks for `videoResolution` (`480p` or `720p`) and `aspectRatio` (`16:9`,
`9:16`, or `1:1`) before invocation. Include those answers in `params` as
top-level values, not inside `scriptJson`.

## Input Contract

The selected background must be one local Loki artifact: one image or one video.
Do not pass inline previews, `dataUrl`, pasted base64, remote URLs, or inferred
filesystem paths. If the selected card does not resolve to a local artifact,
invoke the skill anyway only when `context.localMediaReferences` contains one
valid image/video path. Otherwise the run must fail.

## `params.scriptJson`

Pass `scriptJson` as a JSON object or JSON string:

```json
{
  "durationSeconds": 6,
  "fps": 30,
  "backgroundFit": "cover",
  "blocks": [
    {
      "kind": "title",
      "text": "Launch Night",
      "start": 0.2,
      "duration": 2.4,
      "preset": "title-card",
      "position": "center"
    },
    {
      "kind": "subtitle",
      "text": "A short line timed like a caption.",
      "start": 3.0,
      "duration": 1.8,
      "preset": "karaoke-subtitle",
      "position": "bottom"
    }
  ]
}
```

Required:

- `durationSeconds`: required for images. Optional for videos; when omitted, the
  action uses the source video duration.
- `blocks`: one or more text blocks. Every block must include non-empty `text`,
  `start`, and `duration`.

Defaults:

- `fps`: `30`.
- `backgroundFit`: `cover`.
- `preset`: based on `kind`.
- `position`: based on `preset`.

Valid `kind`: `title`, `subtitle`, `lowerThird`, `quote`, `cta`.

Valid `preset`: `title-card`, `lower-third`, `karaoke-subtitle`, `quote`,
`caption-stack`, `cta`.

Valid `position`: `center`, `top`, `bottom`, `lower-left`, `lower-right`.

## Prompting Guidance

Convert the user request into concise, timed text blocks. Prefer fewer blocks
with good rhythm over many simultaneous overlays. Titles should be short and
legible. Subtitles should be one readable phrase per block, not paragraphs.

For image backgrounds, choose a duration that fits the requested animation. For
video backgrounds, keep all block timing inside the source video duration.

Use the collected `videoResolution` and `aspectRatio` arguments instead of
inventing raw dimensions. The action maps `480p`/`720p` plus the selected frame
to deterministic HyperFrames dimensions.

## Rendering Contract

The action creates a deterministic HyperFrames project under the skill run
folder, runs `hyperframes lint`, `hyperframes inspect`, then renders an MP4 to a
known output path. If any validation/render step fails, read the action error.
Do not look for alternate render files or generate a replacement by another
tool.
