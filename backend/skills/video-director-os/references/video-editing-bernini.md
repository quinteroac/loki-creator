# Bernini Video Editing

Use Bernini through `comfy-videoedit`, not `comfy-videogen`.

Required params:

- `editMode`: `bernini`
- `modelProfile`: `wan22-bernini`
- `berniniMode`: `v2v`, `rv2v`, or `r2v`

Modes:

- `v2v`: selected source video only; inherit frame size.
- `rv2v`: selected source video plus selected reference images; inherit frame
  size.
- `r2v`: selected reference images without a source video; requires aspect
  ratio, resolution, FPS, and duration.

Use Bernini for visual edits, style/lighting/background changes, repair of a
good take, reference-guided video-to-video, and reference-only video generation.
Do not use it for joining, audio mux, captions, or deterministic blur/crop.
