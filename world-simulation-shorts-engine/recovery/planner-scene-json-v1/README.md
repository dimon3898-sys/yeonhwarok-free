# Planner Scene JSON V1 Candidate

PART A is complete and immutable: `EVENT_FEATURE_BUNDLE_V3_AREA_FINAL_BASELINE`, commit `7da699c07cddf618f5e8a93ca735db51d31bbb39`, Final Manifest SHA-256 `672aa536a65c5f36d5e3f2b96a70c548897872093b9d602772fe75d96d14bc45`. Its user approval, Permanent Gate 7/7 and remote BIT_EXACT reproduction are retained. The Planner Candidate does not rerun or promote that Final.

The new layer compiles TopicIntent and supplied facts into declarative Scene JSON: beats, feature selection, camera/scale intents and deterministic timing. Existing geographic Event, Flow, Area and Camera engines evaluate those plans. No renderer, projection, camera, physics or Layout Core is recreated. FACT_BASED_VISUAL_GRADE permits visually faithful approximations while preserving historical location, sequence and direction. Authored historical fronts and areas are infographic approximations, not exact military control boundaries or tactical simulation.

Storage order follows the authorized instruction: B. Planner Core plus Synthetic A/B/C PASS; C. real fixture plus validated Scene JSON and existing-engine integration PASS before long rendering; D. original proof and Candidate manifests. Only new files are added. Every path already tracked at the parent Final is checked for unchanged bytes. Runtime inputs are permanent repository-relative files; required temp-only inputs are zero.

Public review contains exactly one original MP4, eight native Checkpoint PNGs, the canonical executed `SCENE_PLAN.json` and `SHA256SUMS`. Source code, diagnostic reports, internal runtime configuration and planning procedures remain outside `public-review/`. The public Scene JSON is the expressly requested declarative product artifact. It must pass the same schema validator as the executed scene and contain no runtime file paths, credentials or diagnostic payloads.

This is `PLANNER_SCENE_JSON_V1_CANDIDATE`. Stop at `USER_VIDEO_REVIEW_REQUIRED`. The Planner Permanent Gate and clean Final reproduction are deferred until user video approval.

## Pinned environment

Use Node 24.19.0, `/usr/bin/python3` 3.13.5, Chromium 154.0.8037.57, FFmpeg 7.1.5, Three 0.170.0 and Playwright/Playwright Core 1.62.1. The unchanged baseline Python lock retains NumPy 2.2.4, Pillow 11.1.0 and GDAL 3.10.3. The existing `/usr/bin/python3` jsonschema 4.19.2 and its installed dependency closure are pinned in `planner-validation-requirements.lock` for schema audits and tests only. No new runtime dependency is added. The saved dependency manifest verifies actual interpreter/package versions and lock hashes.

From the repository root, install the locked Node environment if needed:

```sh
npm --prefix cinematic-world-map ci --ignore-scripts --no-audit --no-fund --strict-ssl=true
```

The schema audit environment additionally requires the exact versions in `planner-validation-requirements.lock`. The managed image already supplies them for `/usr/bin/python3`; use that interpreter rather than an unrelated user Python. If reproducing outside this pinned image, install the lock in an isolated Python 3.13.5 audit environment and record that environment in the local reproduction receipt.

Run the new focused Planner tests; their repository fixtures preserve exact semantic feature selection:

```sh
node --test world-simulation-shorts-engine/tests/planner_scene_v1.test.mjs
```

Run any additional `planner_*.test.mjs` named in `REPRODUCTION_MANIFEST.json` before generating the implementation inventory. The frozen AST parser resolves actual imports and export bindings; no new parser dependency is introduced.

## Inventory and persistence

At B, after the saved `evidence/SYNTHETIC.json` reports PASS:

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/planner-scene-json-v1/build_candidate_manifest.py --stage implementation --write-manifests
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/planner-scene-json-v1/scan_candidate.py --repo . --scanner /workspace/.onboarding/event-v1-tools/gitleaks --output world-simulation-shorts-engine/recovery/planner-scene-json-v1/evidence/SECRET_SCAN_IMPLEMENTATION.json
```

At C, after the real fixture, canonical `fixtures/SCENE_PLAN.json` and `evidence/INTEGRATION.json` report PASS, use `--stage fixture --write-manifests`. Commit and push those original implementation inputs before rendering. At D, after the encoded proof and inspected decoded-frame `evidence/VISUAL_AUDIT.json` report PASS, use `--stage candidate --write-manifests`. Scan and commit all original media, source, fixtures, data and manifests, then use `--stage candidate --require-persisted` to verify exact HEAD and index bytes. These inventory commands never render or run the approval-only Permanent Gate.

## Deterministic source reproduction

Use the pre-render source revision named in the saved Candidate `REPRODUCTION_MANIFEST.json`; `public-review/` and `evidence/proof/` are absent at that revision. Retain the committed prerequisite evidence and install the pinned dependencies above. The real fixture build procedure and its fact/source records are included in `BUILD_INPUT_MANIFEST.json`; native assets and URL routes are enumerated in `RUNTIME_ASSET_MANIFEST.json`.

Create the original proof once from those saved inputs:

```sh
node world-simulation-shorts-engine/recovery/planner-scene-json-v1/render_proof.mjs
```

The renderer captures native 1080×1920 frames, checks protected graphics and encodes a single 30fps silent MP4. Checkpoints are the exact PNG frames fed into that original encoding. Public delivery never re-encodes the MP4 or regenerates the PNGs. Inspect actual decoded video frames for front/area/time readability, purposeful camera rhythm, mobile text and visual hierarchy before recording technical Candidate PASS. That review does not grant user approval.

After pushing the Candidate media commit:

```sh
/usr/bin/python3 -B world-simulation-shorts-engine/recovery/planner-scene-json-v1/verify_public_downloads.py --commit ORIGINAL_MEDIA_COMMIT
```

The verifier makes eleven real HTTP GETs, requires HTTP 200 and compares each downloaded body with both the original file and immutable Git commit. It verifies all ten entries in `SHA256SUMS` and checks the public Scene JSON schema, safety and exact equality to the executed production scene. Temporary downloaded copies are verification outputs, never required runtime inputs.
