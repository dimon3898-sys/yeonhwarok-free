# World Engine permanent development Gate

`generic_scope: ALL_WORLD_ENGINE_DEVELOPMENT_GATES`

Every development Gate requires all seven conditions below to be actual `PASS` before completion. These are mandatory technical/persistence conditions; global V4 completion also requires acceptance of the complete V4 output. `FAIL`, `NOT_RUN`, `UNKNOWN`, absent evidence, an unverified candidate or `USER_VISUAL_REVIEW_REQUIRED` means global `GATE_INCOMPLETE` and blocks the next development Gate and Camera V5. An authorized repair or reproduction phase within the current Gate may proceed after its own prerequisites pass; the future reproduction receipt is not a prerequisite for producing that receipt.

The current V4 work is an equivalent recovery with actual Static Final Hold `BIT_EXACT`, 375 newly rendered frames and all checked Camera/Reveal contracts PASS. Full V4 acceptance remains `USER_VISUAL_REVIEW_REQUIRED`: 6/7 checkpoint PNGs matched exactly; Context has 43 changed pixels with maximum channel difference 200, and decoded MP4 comparison found differences in 214 frames despite matching encoder SEI settings. Therefore global `GATE_INCOMPLETE` remains in force even if all seven technical/persistence flags later PASS. A completed render, exact Static, clean Static reproduction or source-file count cannot override these unaccepted V4 differences.

## Seven mandatory conditions

| Condition | Required evidence |
|---|---|
| `SOURCE_PERSISTED` | The actual runtime and declared build-source closure is inventoried, committed in the development branch and verified against actual SHA/size. Source contracts and provenance distinguish preserved originals from explicitly approved rebuilds. |
| `ASSETS_PERSISTED` | Every active runtime asset and required build input is preserved with verified SHA/size. Large-file pointers alone, cloud-local bytes and public Proof media do not establish durable asset availability. |
| `HASH_MANIFEST_PASS` | Complete required-file and input inventories are committed; every expected SHA/size matches hydrated bytes, index and HEAD. Historical expected hashes remain unchanged. |
| `DEPENDENCY_MANIFEST_PASS` | Exact versions and verified lockfiles cover the actual browser, JS and CPU-raster workflow. Runtime dependency artifacts and URL mappings resolve to the admitted files. |
| `IMPORT_MANIFEST_PASS` | AST-derived actual static/literal dynamic imports match the committed inventory. Targets, named/default bindings, browser routes and transitive import closure are verified. Unsupported or nonliteral unresolved imports fail closed. |
| `NO_REQUIRED_TEMP_FILES` | Mandatory runtime files, inputs, build sources, procedures, locks and routes resolve to committed repository files or admitted hydrated large-file bodies. No required original exists only in `/tmp`, a cache, a symlink or an external session. |
| `CLEAN_ENV_REPRODUCIBLE` | A separate clean checkout of the committed revision actually reproduces the approved result with full input bindings, actual command/log, session times, output bytes and validated comparison evidence. |

Use the current seven-condition diagnostic, from the repository root:

```sh
python3 -B tools/v4_recovery_gate.py --repo . \
  --manifest world-simulation-shorts-engine/recovery/v4/runtime/DEPENDENCY_MANIFEST.json \
  --imports world-simulation-shorts-engine/recovery/v4/runtime/IMPORT_MANIFEST.json
```

Preserve its JSON and exit status. Exit 0 requires all seven PASS; exit 1 blocks completion and next-Gate advancement. An exit-0/all-seven result concerns the technical/persistence conditions and does not authorize global V4 completion while visual review remains required. Missing manifests, required assets, temporary-only inputs, import targets or a fresh receipt must not be replaced by PASS placeholders. This is an actual development CLI and documented endpoint procedure; it is not automatic enforcement on every remote branch, CI job or server. Reduced legacy checks and historical 42/43-file counts cannot authorize an automatic rebuild or complete the Gate.

## V4 execution and comparison order

1. Freeze the candidate scene, REGIONAL/CONTINENT bindings and actual runtime dependency/import/asset inventories. Preserve the 43 original files and their original inventory byte-for-byte. Label new Plan data `RECOVERED_EQUIVALENT_V4_PLAN_CANDIDATE`; equal rendered output does not make that data the recovered historical original.
2. Verify module contracts and imports, admitted asset bytes and served routes. Run `tools/setup_v4_recovery.sh` for the pinned installed toolchain and frozen npm locks. Missing prerequisites stop the phase that needs them; the endpoint never silently recreates missing originals from old temporary paths or legacy recipes.
3. Use `world-simulation-shorts-engine/tools/v4_recovery_terrain.py` only for the admitted native terrain recipe. The pinned exact NE1 master and four exact COGs are build inputs; context RGB and height.f32 are separate runtime derivatives. Preserve their source and output SHA/size evidence.
4. Render a fresh Static Final Hold into a new private directory with `recovery/v4/runtime/render.mjs`. Compare the complete 1080×1920 decoded RGBA image against the approved reference using `tools/compare_v4_png.py`, without masks, tolerance or excluded regions. `BIT_EXACT` or `PIXEL_EXACT` with zero changed pixels is required. `RENDERED` alone is not Static PASS. A mismatch stops V4 initialization and later phases.
5. Bind the successful Static receipt and comparison to the same source revision and required inputs. Only then initialize V4 and run approved checkpoint frames, followed by all 375 integer frames 0–374 at 30 fps. Any input change invalidates the prior Static prerequisite and requires affected revalidation. Preserve camera/reveal/layout diagnostics and decoded comparisons; a few passing checkpoints do not prove all frames.
6. Preserve Source+Assets+Manifest+procedure in the development branch. Commit only the reviewed candidate accepted by the actual comparisons. Produce a fresh receipt from a separate clean checkout using the committed invocation; a local development diagnostic is not that receipt.
7. Run the seven-condition endpoint with explicit clean-checkout and private receipt paths. All-seven PASS is necessary for the next Gate; accepted complete V4 output is also required. `USER_VISUAL_REVIEW_REQUIRED` keeps the global Gate incomplete and prohibits automatic Camera V5 progression. Encode or publish MP4/PNG only after its required frame checks and authorization; keep public Proof media separate from development source, plans, shaders, internal diagnostics and build inputs.

Failure stops dependent phases. The user-set limit is three V4 visual/reproduction correction iterations; after the third unresolved result, stop and report the unresolved decision. The additional REG242 geometry candidate produced 56 changed Context pixels and was rejected. The bounded search is stopped; do not select that rejected candidate or restart a broader bounds search automatically. Necessary read-only diagnostics, persistence checks and bounded dependency repair do not fabricate a new visual success.

## Active runtime and source closure

The live adapter loads six data assets plus one Three.js bootstrap module. The complete mapping, input files and procedure are listed in `world-simulation-shorts-engine/recovery/v4/REBUILD_REPRODUCTION.md`. The active texture is `context-native.png`; unused `continent-native.png` is historical provenance and must not be added as a mandatory runtime input solely because its old hash exists. NE1 master and COG4 are build-only sources, not browser fetches. GIS geometry arrays used by the candidate plans are required input data; they are not additional HTTP asset files.

Required closure also includes the actual imported modules, the pinned font, candidate JSON inputs, saved V4 camera/input records, runtime harness/server/CLI, manifests, dependency locks and setup/build/comparison procedures. Confirm this graph against actual loads; declarations of `verified: true` do not establish completeness by themselves.

## Large files and durable availability

The NE1 source is 699,969,932 bytes and height.f32 is 207,360,000 bytes. Their current exact local files establish byte correctness, not permanent storage or clean reproducibility. Git LFS attributes have been selected for exactly the canonical NE1 master and height.f32 paths. The owner handles development-branch commit/push and approved remote/clean-checkout verification; this document does not assert their final availability from local bytes or create an upload automatically.

For these two Git LFS paths, commit reviewed `.gitattributes` entries and exact SHA256/size pointers in the development branch, retain verified hydrated bodies locally, and obtain the bodies in a separate clean checkout from the approved durable remote. Verify each fetched body against its pointer and full manifest. Preserve a current-commit `lfs_clean_clone_verification` receipt and the actual authorized remote-fetch/availability evidence. A local clone, copied cache, uploaded-but-unretrieved object, or cloud snapshot alone is insufficient evidence of remote availability.

The diagnostic accepts explicit `--lfs-checkout` and `--lfs-receipt` paths for hydrated-body/clean-checkout validation. These checks do not independently attest durable remote availability; that evidence must also be reviewed and retained. Unsupported storage or missing retrieval evidence leaves persistence incomplete. Do not describe a local-only LFS object as a completed durable recovery.

## Receipt and endpoint contract

`runtime-diagnostic.json` is generated by the actual renderer CLI and records mode, source commit, required input SHA/size, invocation, times, outputs and runtime errors. It explicitly does not prove a clean environment or all seven conditions. Preserve `static-final-hold.png`, `static-final-hold.comparison.json` and `runtime-diagnostic.json` together. The CLI records `static_comparison` with its path, report, passed state and actual comparator command; a mismatch retains evidence and exits 1 with status ERROR. The approved PNG baseline has SHA256 `fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673` and decoded top-down RGBA SHA256 `cee0e480f1a0941f13d7bbe675952abe5a3bef53dd0bcc44c001f856982e7376`. The V4 guard verifies the baseline and re-decodes the actual output against it, requiring zero pixel/channel differences and the approved decoded hash. It also verifies current source commit and every shared Static input SHA/size; only V4-specific scene/camera inputs may be added. It must verify the real files before admitting a Static receipt; copying the approved PNG or editing status fields is not reproduction.

The committed `fresh_reproduction.acceptance` records `mode: PIXEL_EXACT`, the fixed `expected_png_sha256` and `expected_rgba_sha256`, and the inventoried `comparator_path`. The current endpoint independently decodes the actual fresh PNG and approved PNG, verifies 1080×1920 PNG format and the approved full RGBA hash, and records BIT_EXACT or PIXEL_EXACT from actual bytes. It does not rely on a receipt's claimed pixel result.

A clean Gate receipt is separate, with `schema: 1`, `kind: fresh_clean_environment_reproduction`, current `source_commit`, `manifest_sha256` bindings for the dependency/import manifests, full `required_inputs`, UTC start/end times, `clean_environment` identity and clean baseline, exact approved `command` argv/cwd/exit/log SHA, and actual output and comparison evidence. The approved invocation and procedure must be committed before this execution. Paths for logs, output and comparisons remain regular files under the explicit private receipt directory and must be tied to the actual session. Do not record credential values.

Validate the final receipt explicitly:

```sh
python3 -B tools/v4_recovery_gate.py --repo . \
  --manifest world-simulation-shorts-engine/recovery/v4/runtime/DEPENDENCY_MANIFEST.json \
  --imports world-simulation-shorts-engine/recovery/v4/runtime/IMPORT_MANIFEST.json \
  --receipt /absolute/private/fresh-reproduction.json \
  --clean-checkout /absolute/separate-clean-checkout
```

Add the explicit LFS receipt/checkout arguments when LFS inputs are used. The endpoint must reject absent or stale receipts, temp-only mandatory inputs, changed manifests, a different HEAD or input inventory, dirty/aliased checkouts, missing logs and unverified output/comparison bytes. An old approved PNG SHA MATCH is preservation evidence; `BIT_EXACT`/`PIXEL_EXACT` requires an actual new comparison. Receipt checking is not cryptographic execution attestation, and JSON PASS declarations cannot replace the checks.

## Current V4 disposition

The successful Static and Camera/Reveal contracts are recorded independently from complete video acceptance. The Context and decoded MP4 differences require user visual review of the actual review media and comparisons. Encoder-setting/SEI agreement does not establish decoded frame equality. Retain `USER_VISUAL_REVIEW_REQUIRED` and global `GATE_INCOMPLETE` until the remaining result is explicitly accepted or a newly authorized correction satisfies the full criterion. Do not replace this decision with all-seven storage PASS, an exact clean Static or a public media upload. Camera V5 remains blocked.
