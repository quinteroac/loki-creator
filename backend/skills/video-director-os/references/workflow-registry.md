# Workflow Registry

Video Director workflows are phase templates. The user may select a workflow
manually, or `auto` may infer one from the request.

## auto-director

Use when the request is open ended. Start in `idea`, pick the workflow after the
first brief, and state the chosen path.

## short-film-sequence

Use for narrative shorts, scenes, trailers, and multi-shot story pieces.
Default path: `idea -> plan -> reference_frames -> frame_approval ->
video_generation -> clip_review -> assembly -> post -> delivery`.

## first-last-frame-sequence

Use when endpoint control matters. Generate first/last image cards first, then
video clips from approved pairs.

## image-to-video-sequence

Use when the user already has approved images or wants stills animated.

## product-ad

Use for product, brand, packshot, demo, proof, CTA, campaign variants, and
social cutdowns.

## music-performance

Use for singing, dancing, dialogue, lip sync, S2V, music video, audio timing,
or performance clips.

## retake-and-repair

Use when clips already exist and the user wants to improve, reroll, edit, or
triage them.

## video-edit

Use when selected video cards should be transformed rather than regenerated.

## post-production

Use for joining clips, trims, titles, subtitles, audio mux, cleanup, captions,
or final delivery cards.
