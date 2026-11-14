# Three 6-second clips — GPU-gated plan (2026-11-14)

## Status
DESIGN_ONLY / BLOCKED_GPU_WEBGL2. No MP4 generated, no GPU run, no build, no prior PASS rerun.

## Preserved baseline
- Branch fix/reference-6s-formal-admission-20261113; baseline checkpoint remains BLOCKED_ROOT_CAUSE_UNKNOWN.
- Original 20s / 600-frame plan, 106 territory geometries, and existing source data are unchanged.
- Previously observed 10s/300-frame capture does **not** guarantee 6s capture on current gCube; latest manual WebGL2 test returned false.
- User requested three **6-second** deliverables (total 18 seconds), not three 20-second videos.

## Segment contract (provisional until source shot timing is mapped)
| Deliverable | Global source interval | 30fps frames | Output |
|---|---|---:|---|
| 01 | [0.000s, 6.000s) | 0–179 | 1080×1920 MP4, 6s |
| 02 | [6.000s, 12.000s) | 180–359 | 1080×1920 MP4, 6s |
| 03 | [12.000s, 18.000s) | 360–539 | 1080×1920 MP4, 6s |

- Original global frames 540–599 (18–20s) are **not assigned**. Do not silently discard: requires explicit content decision before locking creative continuity.
- Use original global timeline, not independent resets; ensure camera position, territory state, label state, effects and pacing match at 180/360 frame boundaries.
- Do not compress 20s into 18s or accelerate reference motion without user authorization.
- No assumption that arbitrary 6s slice is supported by the formal history renderer. Confirm mapping of existing six-shot timing, input contract and existing formal 6s path before emitting inputs.
- Retain the original 20s artifact unchanged; this is an alternative delivery plan.

## Execution gates
1. Read original shot/timeline files and exact 6s formal generator contract; reuse valid prior PASS.
2. Produce three scene JSON inputs only if contracts and state continuity can be established from source.
3. Check each new JSON with free, changed-scope validations only.
4. STOP before GPU: WEBGL2 initialization is still blocked. Paid GPU and build need separate preconditions and explicit user approval.
5. Never label MP4 PASS without actual files, frame counts and decode evidence.

## Existing evidence
- gpu-failure-recovery/CHECKPOINT.json
- gpu-failure-recovery/RECURRENCE_COMPARISON.json
- gpu-failure-recovery/EGL_RUNTIME_PATH_AUDIT.md
- production/capture-json-size-fix-v13/evidence/CAPTURE_DIAGNOSTIC.json
