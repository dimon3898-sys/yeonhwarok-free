# Provenance-hardened isolated atlas generation

Candidate only. Production/runtime admission, rendering, GPU use and deployment remain disabled. The prior82 and86 atlas directories are unchanged.

## Outputs and verification

`generation1/` is a complete new generation published by atomic directory rename only after all captured input file hashes and input inventories were rechecked. Its `GENERATION_INDEX.json` binds every generated artifact. Treat this directory as immutable; verification detects later changes. `VALIDATION_RESULTS.json` lives outside it to avoid modifying the completed generation.

All86 optical source tiles were checked. Each paired classification mask was independently reconstructed from the exact hashed parent classification array at optical sample centers, then compared with the stored masks. `source_snapshot.py` enforces EPSG:4326, axis alignment, decoded affine consistency, dimensions and tile edges. Unknown or altered categorical classes and mismatched paired masks fail closed.

The1.4MiB `SOURCE_ARRAY_EVIDENCE.json` binds original source URLs/range hashes/licensing/grids, decoded arrays and resampling evidence, mask parent hashes and exact sampling method, baseline materialization/crop evidence and every input file's captured hash. Every product derivation receipt carries its hash; the receipt itself remains hashed in the candidate manifest. `verify_generation.mjs` verifies these transitive bindings, upstream-source equality, baseline original/crop linkage, generation hashes and the ordinary candidate validator. No source authenticity or correct original COG resampling is inferred merely from these locally consistent hashes.

## Results

- Four new focused tests passed: file mutation, inventory mutation, affine shear/shift rejection and exact classification pairing/tamper rejection.
- All four real candidate manifests and generation/evidence bindings verified.
- All45 raw atlas files are byte-identical to the preserved86-source candidate. See `PRESERVED_PIXEL_EQUIVALENCE.json`.
- Source-grid unresolved invalid optical known-land count remains40. Five atlas layer counts remain8,5,8,6,2. Sampling cannot waive the source-grid blocker.
- No DSM is included and no2020 alternate source was applied.

## Execution and limitations

`python build_atlases.py` requires a fresh output generation name: it refuses to overwrite `generation1` or an existing staging directory. Source data is captured and hashed, loaded from those captured bytes, then rechecked immediately before publication. Concurrent source changes cause rejection, not mixed-generation acceptance. Failed staging output is not published. The acquisition session may add DSM files independently because DSM is not an input to this optical-only generation.

Run `python -m unittest -v test_source_snapshot` for the new unit checks and `node verify_generation.mjs` for actual artifact verification. The latter performs no rendering/network and writes its report outside the generation. No historical project PASS suites were run.

These changes close local provenance/grid/snapshot integrity gaps, not source qualification. Acquisition authenticity, native contributing-sample validity, clouds, shoreline suitability, epoch limits, visual color/seams, safe runtime LOD/material treatment and deployment remain pending. The40 unresolved optical known-land source samples remain an explicit admission blocker. BMNG fallback remains truthful display context, never certified optical or invented elevation.

## Portable CLI revision and producer history

The current helpers were revised after generation1 was created. They did NOT produce that existing generation. Exact earlier builder/verifier/snapshot bytes and their hashes are retained in `producer_history/generation1/`; the generation index hash remains unchanged. Do not use the new helper hashes as historical producer hashes.

Builder options: `--source-root PATH`, `--output-root NEW_GENERATION_PATH`, `--baseline-receipt PATH`, and `--check-paths`. Defaults are the source-qualification parent directory, a generation1 directory beside the builder, and BASELINE_MATERIALIZATION_RECEIPT.json under the source root. Environment equivalents for roots are WORLD_ENGINE_SOURCE_ROOT and WORLD_ENGINE_OUTPUT_ROOT. Explicit overrides allow other layouts. Existing output/staging directories are never overwritten.

Verifier options: `--output-root GENERATION_PATH`, `--validator MODULE_PATH`, `--report EXTERNAL_PATH`, and `--check-paths`. The validator default is `../../../source-candidate-contract/derived_source_manifest.mjs`, resolved from the helper directory. From the planned repository placement `production/reference-reproduction-v18/evidence/source-qualification/atlas-hardened/`, this resolves to `production/reference-reproduction-v18/source-candidate-contract/derived_source_manifest.mjs`. WORLD_ENGINE_CANDIDATE_VALIDATOR overrides the default. Reports inside the immutable generation are rejected.

Five CLI tests passed with no source reads or generation writes. The later shared-validator revision independently requires a hashed sourceEvidenceSha256 receipt; its actual-byte verification results are separate in EVIDENCE_REVISION_VALIDATION_RESULTS.json. Original generation files remain untouched. Acquisition authenticity is still pending.
