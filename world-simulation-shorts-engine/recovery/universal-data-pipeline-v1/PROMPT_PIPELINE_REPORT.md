# Additive prompt-data and Scene adapter

CPU contract checks: **109/109 Node tests and14/14 JSON Schema tests passed**, no skips. Commands, complete logs, file hashes and scope are in `reports/PROMPT_PIPELINE_TEST_RESULTS.json`. Independent adversarial review is recorded separately by its reviewer. These results do not certify rendered pixels, NVIDIA execution, historical fact accuracy or final visual quality.

The new adapter reuses the protected Planner's `validateFactDataset`, `compileScenePlan`, `validateScenePlan`, and existing `compileExistingEnginePlan`; it changes none of those modules. Existing standard Scene JSON is validated unchanged through `validateLegacyScene`. The input contract and explicit limitations are in `PROMPT_CONTRACT.md` and `PROMPT_INPUT.schema.json`.

Implemented behavior:

- A single structured prompt (JSON or fenced JSON) supplies subject, simulation mode, dates, locations, source notes, geometry, state/route data, camera references and rendering profile. Arbitrary natural-language interpretation is explicitly unsupported.
- Historical/observed data requires server-reviewed exact source identity, canonical facts hash, geometry hashes, date applicability and claim scope. Fictional and declared illustrative general networks do not require military or historical data. A client `VERIFIED` label never unlocks history rendering.
- Missing feature data returns `NEEDS_INPUT`, contradictory time/source/reference data `CONFLICT`, unsupported connected capabilities `UNSUPPORTED`, malformed data `INVALID`. Each issue includes a field, reason and correction example. Unimplemented settings are rejected rather than silently ignored.
- Scenes retain original half-open frame ranges and source traces. Supplied dated states are sorted; their original input indices remain traceable. An unrelated qualified scene survives when another scene is blocked. Explicit dependencies propagate blocks; cycles and global range gaps/overlaps are rejected.
- Standard Scene and existing Area/Flow plans are emitted with deterministic input/geometry/scene digests. Renderer code/version digests are recorded. Region-native asset coverage, actual projected pixels and GPU execution remain independently verified by the real runtime.
- Raw JSON duplicate keys, nonfinite numbers, circular or non-JSON objects, prototype keys, unknown nested settings and malformed record arrays are rejected. CLI outputs use0600/exclusive create and refuse to overwrite old sources or results.

The five subject fixtures deliberately do not all claim historical completeness. Fictional Namibia, illustrative German aviation and illustrative Chilean trade inputs compile. Korean War full-control data and Roman Empire extent data remain blocked with precise missing-evidence/geometry reasons. A retained partial-front line does not qualify a complete occupation polygon. An in-memory mock in the unit suite exercises positive evidence-gate logic only and is explicitly not a historical source or rendered historical scene.

Changed/additional files owned by this adapter are `prompt_pipeline.mjs`, `PROMPT_INPUT.schema.json`, `PROMPT_CONTRACT.md`, `tests/test_prompt_pipeline.mjs`, `tests/test_prompt_schema.py`, and their reports. All are under the new recovery namespace. G1/G2 source, protected renderers, FINAL, original Scene/assets/caches and existing historical data remain unchanged.
