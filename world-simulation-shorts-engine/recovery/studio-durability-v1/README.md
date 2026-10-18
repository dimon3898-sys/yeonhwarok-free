# Studio durability V1 — CPU candidate

This additive entry point preserves the private Studio tree and the frozen
renderer. It does not make `/world-storage` a private state directory and does
not start, stop, or deploy a GPU. The parent image is pinned by digest in
`Dockerfile`; existing files are not overwritten.

## Storage layout

| Purpose | Location | Trust |
|---|---|---|
| Live Scene, audio, job records, cache | `/var/lib/world-engine-private/engine/production-studio-mvp-v1/production` | Existing UID/GID 1000, directories 0700 and files 0600 |
| Existing media exports | `/world-storage` | Shared mount; original readback rules retained |
| Recoverable encrypted backups | Opaque object IDs directly in Dropbox API folder `/WORLD_ENGINE_STUDIO_BACKUPS_V1` | AES-GCM authentication and separate retained key |
| Discoverable backup receipts | Dropbox API folder `/WORLD_ENGINE_STUDIO_BACKUPS_V1/receipts` | Append-only encrypted manifest pointers |
| Backup credentials inside a running container | Private Studio root, `durability-secrets` | UID/GID 1000, mode 0600; never exported |

The Dropbox API folder is a path within the approved Dropbox app's access
scope. It is independent of the `/world-storage` mount and is not a public
review folder. An existing Dropbox account can be reused; an additional PVC
is not required by this design. Access to the API and retention of the recovery
key outside the container are required. No credential is generated silently.

## Automatic barriers

1. Read-only preflight validates configured storage and fresh external recovery
   evidence. It creates no substitute Scene or audio checkpoint.
2. The actual Scene JSON and actual SFX settings are encrypted, uploaded,
   downloaded, authenticated, and catalogued before the detached worker starts.
3. After each completed scene, the existing verified MP4 export runs first.
   The extension then preserves only completed, verified native cache artifacts:
   segment MP4, frame ledger, scene receipt, completion receipt and hashes.
4. Every referenced chunk and the final manifest are verified by remote
   readback. Catalog publication is also required before success is returned.
5. Any storage, authentication, quota, timeout, corruption, or catalog error
   prevents the next scene. There are no unbounded network retries.

Content-addressed encrypted chunks avoid duplicate uploads. No raw frame dump,
active approval, operator policy, owner code, session, PID or live claim is
backed up as executable authority. Existing claims and files are never reset.

## gCube settings after external proof succeeds

Use the new candidate image by immutable digest from `IMAGE.json` when one has
been built and independently pulled. Keep command empty and port 8080. Keep
the existing owner, HTTPS, image-digest, GPU and operator-policy settings.
Keep the Dropbox mount at `/world-storage`.

| Setting | Exact value |
|---|---|
| `WORLD_ENGINE_STUDIO_BACKUP_MODE` | `dropbox-api` |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_PREFIX` | `/WORLD_ENGINE_STUDIO_BACKUPS_V1` |
| `WORLD_ENGINE_STUDIO_BACKUP_PROOF_ID` | Actual 64-character proof ID from successful `external-check` |
| `WORLD_ENGINE_STUDIO_BACKUP_KEY` | Approved Secret: canonical URL-safe base64 of 32 random bytes, retained outside the container |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN` | Approved Secret: valid Dropbox API credential for this folder |

Secret values must be entered through an approved Secret store, never chat,
GitHub source, Docker build arguments or reports. The same recovery key is
needed on a replacement container. A replacement token may be used with the
same key and account/folder. A lost key cannot be reconstructed from Dropbox.
Dropbox token lifetime must cover the job; expiry stops progression safely.

Do not set `WORLD_ENGINE_STUDIO_STATE_ROOT=/world-storage`. Leave the existing
private default in place. `WORLD_ENGINE_STORAGE_MODE` and
`WORLD_ENGINE_STORAGE_PATH` are legacy launcher settings, not controls for this
Studio private tree; they cannot provide the new durability guarantee.

The bootstrap supports private file inputs instead of raw Secret inputs:
`WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE` and
`WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN_FILE`. Files must be absolute,
non-symlink private regular files, mode 0600. Runtime copies are owned by
UID/GID 1000. File input takes priority; differing retained credentials are
never overwritten.

## Free external proof and explicit restore

`cli.py` has no production render command. Run it as UID/GID 1000 using the
candidate's isolated Python at
`/opt/world-engine-studio-durability-venv/bin/python`.

- `external-check --private-work-root <existing-private-0700-directory>` uses
  real Dropbox API upload/download, synthetic CPU-encoded media, deletion of
  only its new local test source, and fresh-root restore with full decode.
  It produces a seven-day proof ID only if all steps succeed. It never reports
  NVIDIA approval or changes a production claim.
- `list-checkpoints` authenticates the encrypted catalog and shows plan/audio
  hashes, image binding and completed-scene counts. Select the matching plan
  with the most complete verified cache, rather than trusting a timestamp.
- `restore --checkpoint-id <id> --state-root <fresh-private-root>
  --plan-sha256 <expected-sha> --image-digest <original-immutable-digest>`
  downloads and authenticates all referenced data, revalidates MP4s with
  FFprobe/full decode and reconstructs the original SceneCache entries.

Restore into a new local private root with a trusted writable parent, never
onto an existing root or shared mount. Original directories remain untouched.
Use the same immutable image. Recovered `production/PLAN.json` and
`production/AUDIO.json` provide the exact new Studio submission inputs.
Existing bootstrap and Studio setup create fresh authentication/HTTPS/policy
state. A new explicit operator cost/time approval and Start action are still
required. Valid completed cache entries are reused; incomplete scenes render
only after that approval. Container restart never automatically starts a job.

### Optional cold-container restore without a terminal command

For an explicitly selected backup, the additive bootstrap supports:

| Setting | Value |
|---|---|
| `WORLD_ENGINE_STUDIO_RESTORE_CHECKPOINT_ID` | Authenticated checkpoint ID selected from the backup catalog |
| `WORLD_ENGINE_STUDIO_RESTORE_PLAN_SHA256` | Matching original Scene plan SHA-256 |
| `WORLD_ENGINE_STUDIO_STATE_ROOT` | A new private local root, for example `/var/lib/world-engine-private/engine/production-studio-restored-v1` |
| `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST` | The same immutable image digest used by the backed-up Scene |

Keep the original backup key and a valid scoped Dropbox token. The bootstrap
restores as UID/GID 1000 before starting Studio; then the existing setup creates
fresh owner/HTTPS/policy state. On a repeated start it only verifies the matching
restored input and every retained cache artifact. It never replaces an existing
unrelated root, deletes claims, or starts a GPU render.

Cold restoration is bounded and can take time to download/verify media. The new
image allows a 20-minute Docker health start period. gCube's independent startup
probe/restart grace has **not** been confirmed here; do not assume Docker
metadata changes that platform policy. If its grace is shorter, resolve that
platform setting before attempting a long cold restore. The ordinary path with
no explicit restore ID does not perform a cold restore.

After the two approved backup Repository Secrets have been connected, the
existing successful CI run's `verify-pull` job can be rerun by itself to obtain
real external recovery evidence. Rebuilding the same image is unnecessary.

## Boundaries

CPU fixture recovery and mocked Dropbox tests are separate from actual external
persistence. Production remains blocked without a valid real external proof.
No paid GPU, NVIDIA validation, actual 80-second recovery or video-quality PASS
is implied by this package. Existing completed media and FINAL are unchanged.

Required temporary-only source/assets: **0**. Local test directories contain
only newly generated synthetic fixtures and are removed after each test.
