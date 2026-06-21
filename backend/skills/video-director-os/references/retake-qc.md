# Retake And QC

Use `vendor/seedance-2.0/references/retake-protocol.md` and
`vendor/seedance-2.0/references/delivery-qc.md` as the upstream source for
retake logic. The local verdicts below are Loki's operational labels.

Classify every generated clip with one verdict:

- `keep`: primary goal is achieved.
- `fix in post`: flaw is trim, color, text, sound, or edge-frame cleanup.
- `edit`: timing/composition are good; one visual layer should change.
- `reroll`: prompt is right; sample was unlucky.
- `rewrite`: same flaw repeats or shot is overloaded.

Change one variable per retake: prompt clause, seed, mode, reference, or edit
operation. If a shot fails repeatedly, simplify it or split it.
