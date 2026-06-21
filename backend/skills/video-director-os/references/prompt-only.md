# Prompt Only

Prompt-only mode is a valid production mode. It creates no image, video, audio,
ffmpeg, HyperFrames, Seedance, Grok, Comfy, or post-production skill calls.

Use the vendored Seedance Skill OS as the prompt-construction source:

- `../vendor/seedance-2.0/SKILL.md`
- `../vendor/seedance-2.0/skills/seedance-prompt/SKILL.md`
- `../vendor/seedance-2.0/skills/seedance-prompt-short/SKILL.md`
- `../vendor/seedance-2.0/references/prompt-examples.md`
- `../vendor/seedance-2.0/references/cinematography-shot-language.md`
- `../vendor/seedance-2.0/references/anti-slop-lexicon.md`
- `../vendor/seedance-2.0/references/filter-vocab.md`
- `../vendor/seedance-2.0/references/first-last-frame-guide.md`
- `../vendor/seedance-2.0/references/i2v-guide.md`
- `../vendor/seedance-2.0/references/shot-list-continuity.md`

Return copyable production material, not generic advice:

- workflow and phase,
- reference role map,
- final prompt or prompt batch,
- shot list and continuity notes,
- camera/motion/lighting/style clauses,
- anti-slop and negative guidance when useful,
- recommended engine/platform,
- duration, aspect ratio, resolution, FPS, or other relevant settings,
- first/last frame instructions when relevant,
- retake instructions if the user is iterating,
- approval or next-step question.

When targeting an external platform, keep the prompt self-contained. Do not
mention Loki cards, local filesystem paths, or internal skill names unless the
user explicitly asks for a Loki execution plan.
