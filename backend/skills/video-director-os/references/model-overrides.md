# Model Overrides

Manual engine selection is authoritative unless the selected phase lacks the
required inputs or the engine cannot perform that operation.

Model overrides affect execution route, not prompt craft. Always use the
vendored upstream Seedance prompt-construction corpus for cinematic grammar,
reference discipline, motion language, continuity, and retakes, then translate
the finished prompt to the selected Loki engine.

- `prompt-only`: never invoke generation, editing, post, or assembly skills.
- `seedance-openrouter`: use `openrouter-seedance-video`.
- `wan-flf2v`: use `comfy-videogen` with first/last-frame mode.
- `wan-i2v`: use `comfy-videogen` with image-to-video mode.
- `ltx-i2v`: use `comfy-videogen` with an LTX profile and image-to-video mode.
- `ltx-flf2v`: use `comfy-videogen` with an LTX profile and first/last-frame
  mode only when supported locally.
- `grok-video`: use `grok-imagine-video`.
- `s2v-audio-driven`: use `comfy-s2vidgen` for image+audio or
  `comfy-videoedit` for video+audio edits.
- `bernini-v2v-edit`: use `comfy-videoedit` with `editMode=bernini` and
  `modelProfile=wan22-bernini`.

If incompatible, ask for the missing card type or propose the closest valid
engine. Do not silently switch engines.
