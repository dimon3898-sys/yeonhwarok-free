# Independent scope and contract review

Reviewed source: the original5cc9b98 renderer backup, candidate04/candidate05
diffs, the actual candidate05 renderer, `director_program.mjs`,
`director_graphic_pass.mjs`, font-coverage validation, and their directly reused
Event/Area/measurement interfaces. This is a read-only source review by the
protection/regression task owner. Actual native pixel controls and component
draw evidence have separate owners and receipts.

## Authorized renderer change

The original307 contract was acquired before any edit. The sole authorized old
path is `web/map_infographic_v1/renderer.mjs`. Original SHA is
`e4c80a478fe7b849c9f260eaffa436bea32af78596673dd2e046e25412363b38`;
actual candidate05 SHA is
`9f60a7e4a6299b23b6c9070be4b830a3bbad25f5e1b321e5eff383ce35fb4995`.
The original immutable backup and manifest were not rewritten.

Candidate04 exposed an actual default-globe pixel difference, even though its
adjacent CPU contracts passed. Candidate05 restores the original
`terrainFragment` declaration/literal byte-for-byte and compiles the extended
variant only for the explicit opt-in. Its source substitutions require unique
anchors and fail if the preserved source shape changes. The current04→05 and
original→05 exact diffs were recorded before apply; root saved remote checkpoint
`bb0d8ec781949e2c765f178019ff44cc588c2154` before authorizing apply.
Source equality alone does not settle native readback variability. Subsequent
unchanged-original controls also varied within one factory; the old/new mismatch
therefore does not establish that the patch caused the difference. The original
baseline itself is nondeterministic in the tested software environment. The
actual pixel gate must decide that independently; no thresholds were relaxed.

Opt-in source review retains a paired geographic forward/inverse transform,
frozen initial basis, actual four-corner source-envelope checks, original and
layout minimum-span admission, and explicit float-position precision rejection.
Relative source UV sampling avoids subtracting large absolute values in the
fragment path. The original GIS UV and material/lighting order remain separate
from source sampling. This review does not establish visual quality or source
detail availability.

## Generic program and consumer

Previously identified contract issues were resolved in the additive module:

- Required visibility intervals must lie inside the event's actual lifetime.
- Each LABEL's bound PIN must remain active for the entire LABEL interval.
- Unsupported LINE context-cull and AREA/LINE required-range behavior is
  rejected before draw, rather than accepted and silently ignored.
- Per-type fields are strict; an irrelevant event/style field is rejected.
- Authored pin dimensions retain uniform aspect, preserving the circular hole.
- Accepted text codepoints are checked against the actual retained font's cmap;
  font-byte identity is tested. General Unicode shaping is not claimed.

The source registry and factual/license admission remain external to this
program. A provenance string or `VERIFIED` field is not an independent factual
check. Geographic line reveal is evaluated on source arclength before screen
projection. Full-word text reservation, source-bound metric placement and
viewport clipping are distinct behaviors. The source wrapper does not claim
that an admitted Studio production job or native map video was generated.

The composition owner's final25 CPU tests and five synthetic component draws
are separate receipts. The latter test a solid background and projection stub;
they cannot prove the whole native-map/Studio integration or the reference scene.

## Preservation and regression results

`reports/PROTECTION_AFTER_RENDERER05.json` confirms306 original protected files
unchanged plus1 explicitly authorized renderer modification;6,876 of6,877
baseline tracked files unchanged; four old worktrees unchanged; five cache roots
and1,135 metadata entries unchanged. Cache contents were not rehashed.

The exact same68 unchanged adjacent tests passed on candidate04 and candidate05,
with separate retained run directories. They do not constitute a new run of all
historical503 tests or an image-quality PASS. The old V1 sealed preflight still
pins the old renderer hash and must reject a changed renderer; its original
expectations and the original307 manifest were not weakened for the new path.

No protected file was edited by this independent review. No paid service, GPU
deployment, production video, cache deletion or FINAL promotion was performed.
