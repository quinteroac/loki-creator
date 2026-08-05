# Model Router

Use these defaults only when the user selected `Auto` for the video engine.
The router chooses execution; prompt construction still comes from the vendored
Seedance Skill OS.

- `imagegen`: first frames, last frames, storyboards, product frames, character
  references, visual development, and promptable image edits.
- `openrouter-seedance-video`: Seedance through OpenRouter. Use only for the
  Video Director Seedance route; do not route Seedance through ComfyUI here.
- `openrouter-hailuo-video`: MiniMax H3 through OpenRouter. Use for 2K
  text-to-video, one-image I2V, or selected first/last-frame clips with generated
  audio. Preserve selected-card order for the first and last frames.
- `comfy-videogen` WAN FLF2V: first/last-frame clips with local endpoint
  control and multi-segment storyboard generation.
- `comfy-videogen` WAN I2V: animate selected images locally with WAN.
- `comfy-videogen` LTX I2V: expressive local motion and cinematic camera from
  one selected image.
- `ltx-seed-seeker`: three LTX I2V preview candidates before final rerender.
- `wan-seed-seeker`: three WAN I2V or FLF2V preview candidates.
- `grok-imagine-video`: Grok text-to-video or image-to-video.
- `comfy-s2vidgen`: image plus audio-driven performance, singing, speech, or
  music-timed video.
- `comfy-videoedit`: lip sync, audio-driven video edits, and Bernini V2V/Edit.
- `ffmpeg-video-join`: assembly from approved video cards.
- `hyperframes-text-video`: titles, subtitles, lower thirds, quotes, captions,
  and CTA overlays.
- `ffmpeg-video-audio-mux`: attach or replace final audio.

Explain the engine choice in one sentence before expensive generation.
