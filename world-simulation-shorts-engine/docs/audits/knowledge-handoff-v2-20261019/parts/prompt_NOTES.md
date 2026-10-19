# Prompt audit synthesis notes

- Current Studio is a structured input adapter, not an unrestricted instruction interpreter. Outer schema differs from inner prompt and normalized output.
- Eight requested keys renderIntent/map/territory/camera/militaryUnits/events/timeline/qualityGate fail both actual inner and envelope contract tests with distinct exact errors.
- Existing 5-second advanced runtime features cannot be activated by naming them in this prompt. V4 exact-parent equality and V3 source-derived metadata prohibit arbitrary profile edits.
- UI always sends outer SFX(enabled,gain), overriding all inner SFX, including authored cues/WAV. UI70% and normalizer65% differ. This is an exact observed request-flow detail, not a visual guess.
- Minimum API prompt needs integer durationSeconds80; current frozen parent has80.0. Bare2-field preset accepted only when UIouterduration supplies80.
- 33 existing focused tests PASS:32stubBackend parser/revision tests,1realfrozenbackend integration.42additionalactualbackend contract casesPASS; nojobstart/preflight/GPU/FFmpeg/Dropbox invoked.
- Audio revision only; camera/territory/frontier interval edits are not implemented. Preserve all source; audit only, no fixes made.
- Image inclusion uses prior independent digest pull evidence, separate from actual 80s output. Current80s output unavailable, so OUTPUT_VERIFIED=NOT_VERIFIED.
