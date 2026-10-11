# World Engine permanent development Gate

`generic_scope: ALL_WORLD_ENGINE_DEVELOPMENT_GATES`

Every development Gate requires all seven conditions below to be `PASS` before `GATE_COMPLETE`. Any `FAIL`, `NOT_RUN`, `UNKNOWN`, missing evidence, or unverified candidate means `GATE_INCOMPLETE` and blocks the next development Gate or Camera V5. MP4/PNG review files alone cannot complete a development Gate. Authorized source/asset repairs and reproduction phases within this Gate remain allowed when their specific preceding phase prerequisites pass; they do not require the future reproduction result to exist already.

This development branch applies the policy through the read-only command below. The command validates evidence; it does not render, build containers, install dependencies, or execute engine code. Run it to diagnose this Gate and before advancing to the next development Gate, preserving its JSON and exit status. Exit 1 prohibits claiming completion or advancing to the next Gate; it permits authorized repairs and phase-specific checks within the current Gate. This is a documented development procedure with an actual CLI, not automatic enforcement across every GitHub branch, CI job, or server.

```sh
python3 -B tools/validate_permanent_gate.py --repo . \
  --manifest world-simulation-shorts-engine/recovery/v4/PERMANENT_GATE_MANIFEST.json
```

| Condition | Required evidence |
|---|---|
| `SOURCE_PERSISTED` | Required source bytes are committed, match their manifest SHA/size, and their source contracts are confirmed. Unknown roles and substitutes cannot silently count as original recovery. |
| `ASSETS_PERSISTED` | All required runtime assets and their inventory are committed and match expected SHA/size. Proof media does not replace terrain, DEM, GIS, texture or font inputs. |
| `HASH_MANIFEST_PASS` | The complete required-file manifest is itself committed. Every required record has an exact expected SHA/size and matches actual bytes, the index and HEAD. |
| `DEPENDENCY_MANIFEST_PASS` | Exact dependency versions appear in verified committed lockfiles. Declared artifacts and verified runtime routes resolve to verified committed files. Dependency closure is confirmed. |
| `IMPORT_MANIFEST_PASS` | Actual source import inventory matches verified declared imports. JS targets are verified inventoried source modules whose own imports are checked; relative paths and browser routes agree; statically named/default bindings are exported. Import closure is confirmed. |
| `NO_REQUIRED_TEMP_FILES` | Complete runtime closure is verified and all required source, assets, inputs, procedures, locks and route targets are committed regular files under the repository. No required original exists only in an old `/tmp`, cache, symlink or external session. |
| `CLEAN_ENV_REPRODUCIBLE` | A separate clean checkout actually reproduces the Gate's approved result. A fresh receipt matches current HEAD, the full Gate-manifest SHA and input-manifest SHA; actual checkout inputs, command log, output SHA and session times are verified. |

The small validator supports JS/MJS ES-module static imports and literal dynamic imports, common named/default exports, JSON npm locks or exact `name==version` locks. Versions must be exact numeric release pins; ranges, tags and unsupported formats fail closed. Unsupported syntax or unconfirmed closure also fails closed. Its manifest is a reviewed inventory, not an automatic proof that arbitrary dynamic code has no hidden inputs. Confirm completeness against original input records and the actual runtime graph, preserving the known required-original inventory rather than omitting missing records. A `verified: true` or `status: PASS` declaration alone never replaces file, hash and graph checks. Unknown/unverified provenance remains incomplete even when bytes are present.

## Persistence validation procedure

1. Freeze and review the required-file, dependency, import and runtime-route inventory. Confirm source roles and original versus explicitly approved minimum-rebuild provenance. Run the CLI for all seven diagnostic results. An unknown role or missing prerequisite prevents the phase that requires it; independent read-only diagnostics may still report all seven conditions.

2. Preserve approved source and required asset bytes in the development branch. Keep original preserved files immutable. A rebuild is new code and must not be described as recovered original bytes or assigned an original SHA it does not have.

3. Commit a complete SHA/size inventory and input manifests. Keep public MP4/PNG Proof separate from development source, shaders, diagnostics, internal plans and paths. Do not copy development source into a public Proof branch or Release to provide media downloads.

4. Preserve the exact dependency locks and resolve actual imports and runtime routes. A served URL such as `/height.f32` is different from a development file path. Unknown mapping remains incomplete; do not rewrite original paths to conceal the gap.

5. Verify required-file closure and that no original is available only through old temporary files, cache or manual session state. Normal newly generated scratch files are allowed; mandatory originals must come from the preserved checkout.

6. Define this Gate's approved reproduction result, committed procedure, approved invocation and acceptance criterion before execution. An absent criterion or invocation is `UNKNOWN`. The current V4 criterion is a newly reproduced Final Hold SHA of `fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673`; future Gates use their own approved criteria.

7. After the current Gate's source/asset/dependency/import/input prerequisites pass and the task authorizes execution, reproduce in a separate clean checkout using the committed procedure and inputs. Preserve actual command, working directory, log, environment and output evidence. A fresh receipt is produced by this phase, so all-seven completion is not a prerequisite for starting it. If the task forbids rendering, reproduction remains `NOT_RUN`.

8. Validate the actual fresh evidence using the same CLI with explicit private receipt and checkout paths:

```sh
python3 -B tools/validate_permanent_gate.py --repo . \
  --manifest world-simulation-shorts-engine/recovery/v4/PERMANENT_GATE_MANIFEST.json \
  --receipt /absolute/private-evidence/fresh-reproduction.json \
  --clean-checkout /absolute/separate-clean-checkout
```

9. Record `GATE_COMPLETE` only for seven actual PASS results and exit 0. Otherwise record `GATE_INCOMPLETE` and the missing evidence. The next development Gate stays blocked. Authorized within-Gate repair follows the phase order below; the user-set three-iteration limit applies to V4 visual/reproduction correction, not maintenance of this read-only diagnostic tool.

## User's V4 minimum-rebuild A–I phase order

| Phase | Required work | Advancement rule |
|---|---|---|
| A | Four missing modules, with verified roles/contracts | If A fails or an unknown role remains, B–I are `NOT_RUN`/`SKIP`. Do not invent unknown module behavior. |
| B | Import graph | Start only after A passes. |
| C | Four terrain inputs/provenance | Start only after B passes. A missing upstream master remains a documented gap. |
| D | Renderer startup | Start only after C passes and execution is authorized. |
| E | CameraPlan compile | Start only after D passes. |
| F | RevealPlan compile | Start only after E passes; saved frame-contract checks do not claim fresh measured-plan compilation. |
| G | Static Final Hold reproduction | Start only after F passes; compare newly generated output with the approved V4 criterion. |
| H | Checkpoint | Start only after G passes and preserve source/assets/manifests/procedure/evidence. |
| I | MP4 | Start only after H passes and MP4 generation is explicitly authorized. |

At each phase, failure stops later phases. Maximum V4 visual/reproduction correction iterations: three; after the third unresolved result, stop and report the decision required. Read-only Gate diagnostics may run independently to explain missing prerequisites. The seven-condition `GATE_COMPLETE` check is mandatory before moving to another development Gate or Camera V5, not before the within-Gate repair that makes a condition pass. This task's validator generates no render or MP4.

## Manifest and receipt contract

`PERMANENT_GATE_MANIFEST.json` uses schema 1 and these fields:

- `required_files`: records with repository-relative `path`, `kind` (`source`, `asset`, `input`, `procedure`, `dependency_lock`), `expected_sha256`, and `expected_size`. Optional `historical_original_sha256` and provenance `status` describe rebuilt material; they never assert actual original SHA equality.
- `dependencies`: exact `name`, `version`, verified `lock_path`, optional verified `artifact_path`, and explicit `verified: true`.
- `imports`: `importer`, actual `specifier`, `resolved_path`, and explicit `verified: true`.
- `runtime_routes`: served `url`, repository-relative `file`, and explicit `verified: true`.
- `completeness`: explicit confirmations for `source_contracts_confirmed`, `runtime_inputs_complete`, `dependency_graph_complete`, `import_graph_complete`, and `required_file_inventory_complete`, each backed by actual review and evidence.
- `fresh_reproduction`: `receipt_path`, `expected_output_sha256`, `input_manifest_path`, committed `procedure_path`, approved `approved_command` argv template, and optional `source_commit`. The only path placeholders expanded are `{checkout}` and `{evidence}`. The command must include a preserved source/procedure entrypoint. Until production execution, omit the receipt or leave it null; do not fill a PASS placeholder.

A fresh receipt has `schema: 1`, `kind: fresh_clean_environment_reproduction`, `source_commit`, `gate_manifest_sha256`, `input_manifest_sha256`, UTC `started_at_utc`/`completed_at_utc`, `clean_environment` (`checkout_path`, matching `source_commit`, `baseline_clean: true`), `command` (exact approved `argv`, `cwd` equal to the separate checkout, actual `exit_code: 0`, relative `log_path`, `log_sha256`), and `output` (relative `path`, `sha256`). Log and output paths remain under the explicit receipt directory and must be regular files. Do not include secret values in receipts or logs.

The validator verifies canonical separate-checkout identity and Git top-level, clean status, HEAD and required input bytes, the current manifest/input SHA, exact approved invocation and working directory, actual log/output bytes, and output modification time within the recorded command session. Path aliases of the original checkout and nested Git subdirectories are rejected. Receipt source HEAD must exactly match current HEAD; later commits require revalidation. External receipts are accepted only with explicit CLI paths; manifest-relative `..` traversal is rejected. A preserved `07_FINAL_HOLD.png` is rejected as the fresh output, and any existing approved PNG MATCH is only preservation evidence. JSON status alone is not successful reproduction, and these checks do not provide cryptographic execution attestation.

Required files, manifests and procedures must be committed before persistence PASS is possible. Receipt evidence may be private outside the source checkout; it is not a required runtime input and avoids embedding a circular current-commit reference in a tracked receipt. The current task has no clean reproduction receipt and cannot complete the Gate.
