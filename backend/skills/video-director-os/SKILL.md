---
name: video-director-os
description: Governs Loki Video Director planning, workflow phases, model routing, approvals, retakes, video editing, assembly, post-production, and prompt-only handoff across supported video engines, using the vendored Emily2040/seedance-2.0 prompt-construction Skill OS as its primary prompting corpus.
metadata:
  loki:
    visibility: internal
    capabilities: [video-direction, workflow-orchestration, prompt-planning, production-memory, prompt-construction]
    output:
      packager: auto
      kind: text
---

# video-director-os

Use this skill as the operating system for Loki's Video Director. It is not a
generation engine. It is the director/planner/prompt-construction layer that
turns a user's idea into phased production decisions, reference roles, prompts,
retakes, edits, assembly, and post-production actions.

## Vendored Prompt OS

This skill vendors the upstream Seedance 2.0 Skill OS text literally under:

- `vendor/seedance-2.0/SKILL.md`
- `vendor/seedance-2.0/skills/*/SKILL.md`
- `vendor/seedance-2.0/references/*.md`
- `vendor/seedance-2.0/data/*.json`
- `vendor/seedance-2.0/LICENSE`

The vendored source is MIT licensed. Keep the included `LICENSE` file with this
vendored corpus.

Before constructing serious video prompts, read the relevant upstream files.
Use the upstream text as the primary prompt-construction and filmmaking grammar.
Use Loki's local references as the execution/runtime override layer.

## Required Reading By Task

Always read:

- `vendor/seedance-2.0/SKILL.md`
- `vendor/seedance-2.0/references/quick-ref.md`
- `vendor/seedance-2.0/references/capability-map.md`
- `references/model-overrides.md`
- `references/model-router.md`
- `references/phase-contracts.md`

For prompt construction:

- `vendor/seedance-2.0/skills/seedance-prompt/SKILL.md`
- `vendor/seedance-2.0/skills/seedance-prompt-short/SKILL.md`
- `vendor/seedance-2.0/references/prompt-examples.md`
- `vendor/seedance-2.0/references/cinematography-shot-language.md`
- `vendor/seedance-2.0/references/anti-slop-lexicon.md`
- `vendor/seedance-2.0/references/filter-vocab.md`
- `vendor/seedance-2.0/references/pro-filmmaking-standards.md`

For interviews and idea refinement:

- `vendor/seedance-2.0/skills/seedance-interview/SKILL.md`
- `vendor/seedance-2.0/skills/seedance-interview-short/SKILL.md`
- `vendor/seedance-2.0/references/progressive-disclosure.md`
- `vendor/seedance-2.0/references/intent-vs-precision.md`
- `vendor/seedance-2.0/references/storytelling-framework.md`

For reference, I2V, and first/last frame work:

- `vendor/seedance-2.0/references/reference-workflow.md`
- `vendor/seedance-2.0/references/i2v-guide.md`
- `vendor/seedance-2.0/references/first-last-frame-guide.md`
- `vendor/seedance-2.0/references/shot-list-continuity.md`
- `vendor/seedance-2.0/references/multishot-grammar.md`
- `references/reference-role-map.md`

For specialist craft:

- `vendor/seedance-2.0/skills/seedance-camera/SKILL.md`
- `vendor/seedance-2.0/skills/seedance-lighting/SKILL.md`
- `vendor/seedance-2.0/skills/seedance-motion/SKILL.md`
- `vendor/seedance-2.0/skills/seedance-style/SKILL.md`
- `vendor/seedance-2.0/skills/seedance-characters/SKILL.md`
- `vendor/seedance-2.0/skills/seedance-vfx/SKILL.md`
- `vendor/seedance-2.0/skills/seedance-audio/SKILL.md`

For retakes, QC, and delivery:

- `vendor/seedance-2.0/references/retake-protocol.md`
- `vendor/seedance-2.0/references/delivery-qc.md`
- `vendor/seedance-2.0/references/audio-post-delivery.md`
- `vendor/seedance-2.0/references/subtitles-localization.md`
- `references/retake-qc.md`
- `references/video-editing-bernini.md`

For non-English prompt surfaces:

- `vendor/seedance-2.0/references/multilingual-community-examples.md`
- `vendor/seedance-2.0/references/vocab/en.md`
- `vendor/seedance-2.0/references/vocab/es.md`
- `vendor/seedance-2.0/references/vocab/ja.md`
- `vendor/seedance-2.0/references/vocab/ko.md`
- `vendor/seedance-2.0/references/vocab/ru.md`
- `vendor/seedance-2.0/references/vocab/zh.md`

## Loki Override Layer

The upstream corpus is Seedance-oriented. In Loki, apply it as a prompt and
filmmaking OS across multiple engines:

- Seedance via OpenRouter: `openrouter-seedance-video`
- WAN/LTX generation: `comfy-videogen`
- WAN/LTX seed exploration: `wan-seed-seeker`, `ltx-seed-seeker`
- Grok video: `grok-imagine-video`
- S2V/audio-driven: `comfy-s2vidgen`, `comfy-videoedit`
- Bernini V2V/Edit: `comfy-videoedit`
- Assembly: `ffmpeg-video-join`
- Audio mux: `ffmpeg-video-audio-mux`
- Titles/subtitles/post: `hyperframes-text-video`
- Image/storyboard/reference frames: `imagegen`

When upstream instructions mention Seedance-specific API surfaces, translate the
prompt-construction idea to the selected Loki engine unless the selected engine
is explicitly `seedance-openrouter`.

## Operating Loop

1. Intake: identify creative goal, audience, duration, aspect ratio, references,
   audio needs, delivery target, approval needs, and constraints.
2. Read the relevant vendored upstream files for the task.
3. Workflow route: choose or honor the selected workflow.
4. Phase route: identify the current phase and what must be produced next.
5. Reference role map: assign each selected or attached asset one primary role.
6. Engine route: honor the user's manual engine unless incompatible; otherwise
   choose from the model router.
7. Prompt construction: use the vendored Seedance prompt grammar, anti-slop
   rules, camera language, continuity rules, and retake protocol.
8. Approval gate: ask for approval before expensive generation unless the user
   explicitly approved that exact phase.
9. Execute: invoke the smallest suitable Loki skill for the current phase.
10. Review: classify results as keep, fix in post, edit, reroll, or rewrite.
11. Continue: update memory and move to the next phase only when approved.

## Output Contract

For planning phases, return concise production objects: mini-treatment, shot
list, reference role map, engine recommendation, prompt batch, or approval
question. For prompt-only phases, return copyable prompts and platform settings.
For execution phases, use the selected Loki skill and keep the final UI response
short.
