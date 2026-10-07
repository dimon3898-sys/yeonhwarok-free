# Developer-only validation guide

This guide is for the managed Codex/build environment. The mobile owner should not run these commands. It does not authorize a gcube workload, GPU test or image publication.

## Repository and source protection

Use branch `fix/v010-pipeline-preflight`. Existing main is `7f882ce970feb051700bf76e828dd81fe374f1d2`. Compare the 28 approved source hashes in `PRESERVED_APPROVED_SOURCES.json` before and after validation. Keep all historical project, cache, checkpoint, video and image files. Never add the entire untracked workspace to Git.

## Local prerequisites

Python 3.12, Node 24, FFmpeg/ffprobe, Pillow, NumPy and fontTools. Existing `cinematic-world-map/node_modules` supplies Three/Playwright. Offline speech uses the existing licensed local runtime; no paid AI API is required. Local layout testing constructs native camera/route/entity geometry, not a software WebGL renderer.

Run from `world-simulation-shorts-engine`:

```sh
python -m unittest discover -s tests
python -m unittest discover -s deployment/gcube -p 'test_*.py'
python -m deployment.gcube.asset_audit
python -m deployment.gcube.gateway_preflight
```

Run the existing diagnostic tests separately from `deployment/gcube-proxy-diag` with its `run_checks.py` launcher. A non-root local process skips the one descriptor permission test; root container tests execute it. No skip is considered proof of hardware readiness.

## Native and media fixtures

`tests/fixtures/suez_qa12/v009_reconstructed_plan.json` comes from the v009 QA planner, not from recovered gcube project storage. `actual_s002_excerpt.json` holds only the user's supplied partial failure evidence. Do not label the former as an exact captured Scene JSON.

The native `tools/collect_all_preflight.mjs` replays every frame without creating WebGL. The container workflow then runs `pipeline_media_preflight.py` and `pipeline_retry_preflight.py`. These use valid HIGH-resolution synthetic JPEG test patterns and actual encoders/mixers/QC. They are transport/media checks, not map graphics or GPU acceptance footage.

## Complete validation image

`.github/workflows/gcube-pipeline-checks.yml` builds `deployment/gcube/Dockerfile.pipeline-check` on branch pushes touching code. It derives from immutable public v009 digest `sha256:5f8250473de90076bfb7d2a357881523a1e4555ff3a5b970bb8e598fd4acfb9a`. Build runs on the GitHub runner because the local execution workspace lacks room for the complete image. It does not push an image tag.

The workflow first tests assets inside the image, installed graphics/browser/FFmpeg dependencies and UID1000 write paths. Historical JSON/devcontainer/upload regression fixtures are mounted readonly only afterwards. The calibrated optional TTS stage downloads exact official SHA256-pinned Ubuntu packages and retains their source/copyright notices. Its library path is confined to the speech subprocess. System/GPU libraries are never replaced.

After all regression groups, gateway login must preserve Secure cookies and block forged Origin. The actual production entrypoint must persist over61seconds with `GPU_HARDWARE_UNAVAILABLE` and `engine_ready=false` on the no-GPU runner. Health200 proves liveness, not GPU readiness. No CPU/SwiftShader frame render is allowed.

## Release barrier

Do not merge/publish `gcube-v010` as an S002 root-cause fix until the actual missing failed audit fields are obtained and the same failure is reproduced before correction. Obtain only existing audit/checkpoint fields: `webglError`, `textClipped`, `entityClipped`, `missingTextures`, `fontReady`, frame index. Exclude owner code, cookies, authorization and URLs. Do not start a paid GPU to recover lost ephemeral evidence.
