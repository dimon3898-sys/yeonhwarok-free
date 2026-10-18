# Dropbox offline token implementation

Branch: `development/dropbox-offline-token-v1-20261018`.
Protected parent: `165a3489eede6e6f66c20f2d6ca1d70fd8c79560`.
Design checkpoint: `23996e675dbf36422664095496ca4317390f79c9` (remote saved).

## Implemented

`renewal.py` adds the fixed Dropbox OAuth token endpoint, bounded requests/responses, no redirects, private credential-file reader reuse, serialized in-memory token cache, pre-expiry refresh and one explicit 401 refresh/replay. There is no fallback to the old static token and no unbounded retry.

`offline_runtime.py` uses exactly the original DropboxStore class and Vault. The only authentication change is an opener supplying the current bearer token to the existing fixed file API routes. Receipt publication inherits the same opener. The old backend's factory and four module-local child-process entry seams are adapted; GPU/FFmpeg commands, detach, UID, timeout, preflight, crypto, checkpoint and cache implementation remain unchanged. The existing initialized-backend case is also covered.

`offline_entry.py`, `offline_frozen.py`, `offline_manifest.py`, `PARENT_SOURCES.json`, `OFFLINE_FILES.json` implement the independent entry, SHA-pinned parent loader and explicit payload verification. Original paths and APIs are not overwritten. Source aliases used by the old HTTPS extension remain separate.

`consent.py` is an optional one-time official offline consent helper. Hidden input and an exclusive private 0600 output file prevent enrollment secrets from entering command arguments, stdout, Git or backup. It does not perform consent without the account holder.

`Dockerfile`, `.dockerignore`, `ci.py` and the isolated workflow reuse the immutable durability image and isolated cryptography environment. There are no dependency installs or inherited-file modifications. Standard free public runners, disk-space guard, new tag guard, source/dependency comparison, Secret Scan and independent immutable pull are mandatory. Optional real Dropbox proof is BLOCKED if any required Secret is unavailable.

## Focused validation

- New runtime/auth/enrollment suite: 49 CPU mock tests PASS locally.
- New host packaging suite: 12 tests PASS locally.
- Existing actual FFmpeg partial-cache fresh restore: PASS.
- Existing frozen coordinator reuses completed cache and renders only the missing scene: PASS.
- All new Python syntax PASS; source-only explicit hash verification PASS.
- Read-only independent review found a test fixture's host-only parent path; corrected to the shared immutable-parent resolver before CI.
- Default gitleaks scanner found only SHA records whose former module names matched its generic credential heuristic. New modules were named `renewal.py` and `consent.py`; rules/thresholds/allowlists were not weakened. Re-scan: zero findings.

The two inherited recovery regressions use synthetic CPU media and an in-memory encrypted-object transport, not a real Dropbox account. The 49 tests use explicit mock OAuth/network/hardware I/O. They do not prove NVIDIA rendering, Dropbox external synchronization, or actual container-restart recovery.

The local sparse checkout lacks a parent's recursively referenced proxy manifest. Local full recursive manifest verification is therefore NOT EXECUTED; this is required against the complete immutable parent in Docker build and independent pull CI. The locally available 14 parent files are byte-identical. No missing parent file is fabricated or replaced.

The current GitHub integration cannot list Repository Secret metadata (HTTP 403). No Secret value was requested, read or printed. Availability is evaluated inside the existing authorized Actions Secret binding. Missing credentials do not prevent independent CPU implementation/build verification and do prevent real-provider proof.

## Failure and recovery

Refresh failure is a safe coded BackupError. The unchanged initial checkpoint barrier stops spawn; a failed per-scene backup raises before the next scene. Failed checkpoints are not published as successful. Existing completed cache, manifests, receipts and claims are not deleted or reset. Restore uses the existing last validated checkpoint; it never restores execution authority and requires a new valid operator approval.

## Remaining user configuration

Follow `README.md` for Dropbox Permissions, official offline consent, the four exact Repository Secret names, free workflow execution and later gCube Secret mapping. Preserve the original backup key. App Folder prefix remains `/WORLD_ENGINE_STUDIO_BACKUPS_V1`. Actual account-backed backup/restore must PASS before any paid GPU execution.

## Final evidence

Actual remote commit, image tag/digest, CI result, protected-file report and actual-provider status will be recorded in `RESULT.md` and `runs/`. Required temp-only implementation files: **0**. Enrollment Secret files belong only in the user's approved Secret storage. No GPU/gCube deployment, paid operation or FINAL promotion is authorized by this change.
