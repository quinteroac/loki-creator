# Phase Contracts

For every phase, use the vendored upstream Seedance Skill OS as the prompt
construction grammar, then apply Loki's runtime routes only when execution is
approved.

## idea
Return a mini-treatment and the assumptions that matter.
Use `vendor/seedance-2.0/skills/seedance-interview/SKILL.md` and
`vendor/seedance-2.0/references/storytelling-framework.md` for the interview
shape.

## plan
Return duration, aspect ratio, shot list, intended engine, and approval request.
Use `vendor/seedance-2.0/references/shot-list-continuity.md` and
`vendor/seedance-2.0/references/multishot-grammar.md`.

## reference_frames
Generate or revise first/last frames, storyboard frames, or visual references.
Use `vendor/seedance-2.0/references/reference-workflow.md`,
`vendor/seedance-2.0/references/first-last-frame-guide.md`, and
`vendor/seedance-2.0/references/i2v-guide.md` to define what each frame must
carry.

## frame_approval
Ask the user to approve, reject, or revise the frame set.

## video_generation
Generate clips from approved prompts/references with the selected engine.
Use `vendor/seedance-2.0/skills/seedance-prompt/SKILL.md`,
`vendor/seedance-2.0/references/cinematography-shot-language.md`, and
`vendor/seedance-2.0/references/model-mechanics.md` to craft final prompts.

## clip_review
Classify each clip as keep, fix in post, edit, reroll, or rewrite.
Use `vendor/seedance-2.0/references/retake-protocol.md` and
`vendor/seedance-2.0/references/delivery-qc.md`.

## video_edit
Edit selected clips while preserving what is already approved.
Use Bernini only when visual content should change while preserving a useful
source take. For prompt construction, still use the upstream camera, motion,
style, and anti-slop files.

## assembly
Join approved clips in approved order.

## post
Add titles, subtitles, audio, trim, mux, cleanup, or overlays.

## delivery
Return final card notes, version notes, and remaining optional improvements.
