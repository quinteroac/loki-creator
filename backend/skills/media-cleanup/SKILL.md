---
name: media-cleanup
description: Clean selected Loki image or video cards by blurring, covering, or cropping user-specified regions with ffmpeg. Use for privacy redaction, framing cleanup, and non-attribution blemish cleanup on media the user owns. 
metadata:
  loki:
    visibility: user
    capabilities: [image-editing, video-editing, privacy-redaction, media-cleanup, ffmpeg]
    arguments:
      - id: operation
        label: Cleanup operation
        description: Choose the deterministic cleanup to apply to the selected image or video.
        type: choice
        required: true
        askWhen: always
        order: 10
        options:
          - value: blur-regions
            label: Blur regions
            description: Blur one or more rectangular regions.
          - value: cover-regions
            label: Cover regions
            description: Fill one or more rectangular regions with a solid color.
          - value: crop
            label: Crop
            description: Crop the media to one rectangular region.
      - id: regionsJson
        label: Regions JSON
        description: Rectangles to edit. Use relative coordinates from 0 to 1, e.g. [{"x":0.1,"y":0.2,"width":0.3,"height":0.2}], or add "unit":"pixels" for pixel values. Crop accepts one rectangle object or a one-item list.
        type: text
        required: true
        askWhen: always
        order: 20
    action:
      type: cli-local
      command: [python3, scripts/media_cleanup_action.py]
      timeoutSeconds: 0
    output:
      packager: auto
      kind: auto
---

# Media Cleanup

Use this skill to create a cleaned copy of one selected image or video card.
The original card is never replaced.

## Parameters

Loki asks for:

- `operation`: `blur-regions`, `cover-regions`, or `crop`.
- `regionsJson`: JSON rectangle data.

For `blur-regions` and `cover-regions`, pass a list of rectangles:

```json
[
  { "x": 0.12, "y": 0.18, "width": 0.22, "height": 0.16 },
  { "x": 420, "y": 80, "width": 180, "height": 90, "unit": "pixels" }
]
```

For `crop`, pass one rectangle object or a one-item list:

```json
{ "x": 0.08, "y": 0.0, "width": 0.84, "height": 1.0 }
```

Optional params may be passed through `paramsJson`:

- `blurRadius`: positive number, default `18`.
- `coverColor`: ffmpeg color or hex color, default `black`.
- `title`: output card title.

Use selected canvas cards or attachments as inputs. Prefer a selected card when
both are present.
