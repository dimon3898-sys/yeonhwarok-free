# Dropbox GPU production preparation V1

Independent candidate based on `00cae13`, preserving the approved Studio/FINAL,
Camera, Area, Flow, Event, Planner, ASTRA, renderer, GPU admission and cache.

This adds no backup engine. The unchanged immutable offline parent already
provides Scene checkpoints, per-scene encrypted backup, offline token renewal,
failure admission, restore and detached process management. Only the verified
key text-input adapter is now connected to every fixed production child.

## Runtime

`production_entry.py` verifies the exact additive payload, SHA-pins and verifies
the offline parent, then selects only the original fixed production stages.
`production_runtime.py` strictly reads the original private Secret file, uses
the byte-identical normalizer from the successful CPU proof, and calls the
original key consumer on a new UID1000/0600 private scratch copy. The original
file, GitHub Secret and all 32 key bytes stay unchanged. Scratch is removed on
success and failure. Four fixed offline child paths are redirected through the
same adapter, preserving process options and native renderer commands.

The Dockerfile only adds `/opt/world-engine-studio-dropbox-gpu-production` on
immutable parent digest `6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0`.
No dependency install or inherited source write occurs. Parent layer prefix,
source manifests, dependencies, entrypoint and inherited healthcheck are checked.

## Free validation

- Focused UID1000 tests: key bytes, strict Secret paths/permissions, scratch
  failure cleanup, fixed child redirection, denied test-stage entry and actual
  frozen 240-minute/cost/expiry/retry validators.
- The existing approved external proof is authenticated, not republished.
- `restart_probe.py` is a developer-only CPU driver, not a production stage. It
  can read only the fixed approved synthetic checkpoint. Dropbox mutations are
  denied. A fresh local volume is restored in container A, then container B
  rechecks identical cached media/claim/metadata. Distinct container IDs and
  hostnames, full MP4 checks and no execution-authority restoration are required.
- Production `startup_restore.ensure_restore()` still rejects synthetic data.
  CPU fixtures cannot be selected as production checkpoints or GPU evidence.
- Default pinned Secret Scan; free public Ubuntu runner only; new unique tag,
  GHCR publication and independent digest pull. Existing tags are never replaced.

See `GCUBE_SETUP.md` for exact supported settings, real cost-approval fields,
Secret delivery limitations, proof expiry and production recovery binding.
Do not deploy or render a paid GPU before owner cost approval and safe Secret
delivery are established. The application time limit does not stop gCube billing.

## Developer continuation

The workflow is `.github/workflows/studio-dropbox-gpu-production-v1.yml` on
`development/dropbox-gpu-production-20261018`. The build/pull jobs only touch the
additive namespace. Existing four Repository Secrets are read only for the final
read-only Dropbox recovery job. Nothing uses gCube credentials or deploys GPUs.

Generated manifests preserve source commit and payload hashes; safe run records
and SHA256SUMS persist remotely. Required temp-only source files: 0. No 80-second
runtime, performance, NVIDIA, gCube restart or visual-quality PASS is inferred.
