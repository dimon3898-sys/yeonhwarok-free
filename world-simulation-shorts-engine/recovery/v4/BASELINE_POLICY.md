# V4 recovered equivalent baseline — active policy

The official development and regression reference is
`V4_RECOVERED_EQUIVALENT_BASELINE`, defined by [BASELINE_MANIFEST.json](BASELINE_MANIFEST.json).
Its immutable source revision is `786521b87b5edd65dfd7ff507d2f0fbaa08f0152` on
`development/v4-minimum-rebuild-20261012`. The commit containing this policy and
manifest is a documentation-only successor; it does not change that source revision.

## Acceptance and historical evidence

The user explicitly selected this recovered state as the official baseline after
reporting that visual review found no structural recovery error. This accepts the
recovered equivalent baseline and resolves its pending user review. It does not
approve `ORIGINAL_V4_BIT_EXACT` or change the historical comparisons: Static Final
Hold and clean Static are BIT_EXACT; Camera/Reveal pass for 375 frames; 6/7
checkpoints are BIT_EXACT; Context differs by 43 pixels; decoded MP4 differs in
214/375 frames. The existing MP4 and all approved reference PNGs remain unchanged.

This policy supersedes only the pending visual-review disposition and old-reference
selection in the source revision's `docs/PERMANENT_GATE_POLICY.md`,
`REBUILD_REPRODUCTION.md` and recovery reports. Those files, their hashes and their
historical verdicts remain intact. The baseline's seven-condition V4 validator was
run read-only against the pinned source revision and all seven conditions passed.
Its historical overall `GATE_INCOMPLETE`/exit 1 is preserved because that revision
predates this user acceptance; it is not relabeled as a strict original-video PASS.

## Mandatory Permanent Gate before the next development Gate

The seven-condition policy in `docs/PERMANENT_GATE_POLICY.md` remains ACTIVE for
every World Engine development Gate. Run the applicable Permanent Gate validator
with the actual Gate's committed runtime/build closure and evidence before starting
the next Gate. All of the following must be actual PASS:

- `SOURCE_PERSISTED`
- `ASSETS_PERSISTED`
- `HASH_MANIFEST_PASS`
- `DEPENDENCY_MANIFEST_PASS`
- `IMPORT_MANIFEST_PASS`
- `NO_REQUIRED_TEMP_FILES`
- `CLEAN_ENV_REPRODUCIBLE`

Missing, stale, unverified or failing evidence means `GATE_INCOMPLETE`. Creating
MP4/PNG or writing a PASS declaration does not complete a Gate. The preserved
validator is `tools/v4_recovery_gate.py`; its JSON conditions and exit status must
both be retained. `tools/validate_permanent_gate.py` also remains preserved.
Neither this freeze nor an old all-seven report replaces execution of the validator
for a later Gate. An unexplained validator failure blocks progression.

The retained clean Static receipt validates source revision `786521b`, not the new
metadata-only commit or a later revision with changed inputs. Future source, asset,
Plan, dependency or procedure changes require current-commit manifests, validated
remote storage and appropriate fresh clean-environment reproduction evidence.
This is a mandatory development procedure with executable validation, not a claim
that every remote branch is automatically protected by CI.

## Future comparison and storage rules

Use this recovered baseline's pinned source, assets, Plans, MP4 and PNGs for future
regressions, including Camera V5 when separately instructed. Preserve historical
proof as provenance; do not restart searches for lost temporary V4 originals or
hold development waiting for them. Equivalent Plans remain explicitly identified
as `RECOVERED_EQUIVALENT_V4_PLAN`, not historical original Plans.

Keep Source + Runtime Assets + Build Inputs + Manifests in development storage.
Public review contains MP4/PNG, optional SHA256SUMS and a minimal README. Never
copy development source, shaders, internal Plans or diagnostics to public Proof.

The freeze modifies no Renderer, Camera, Reveal, Terrain, visual algorithm, asset
or media file and starts no Camera V5 work. Any later development action requires
a separate instruction and its Permanent Gate checks.
