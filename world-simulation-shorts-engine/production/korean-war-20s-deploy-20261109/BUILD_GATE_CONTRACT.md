The parent integrates the public files below at:
`world-simulation-shorts-engine/production/korean-war-20s-deploy-20261109/` (PKG).

- `package/build_once.py`, `package/probe_installed.py`, `package/verify_backup.py` → PKG root.
- Manifest agent `final-context/**` → `PKG/final-context/**`, with no extra files.
- Manifest agent `PUBLIC_SOURCE_CLOSURE.json` → `PKG/PUBLIC_SOURCE_CLOSURE.json`.
- Public private-package receipt (hashes and contract only) → a chosen public PKG path.
- Private installer `private_bundle.py` and its new focused verifier `verify_private_bundle.py` → `PKG/private-package/`. Workflow executes only the synthetic seven-check fixture as root/uid1000 on the free runner. This step must write `RUNNER_TEMP/korean-war-20s-private-fixture-result.json`; the builder requires all seven PASS and the exact installer SHA before any build.
- CPU acceptance receipts and already-public PART01/PART02 strict JSON files can remain at their existing repository paths; gate file receipts reference those exact paths. No raw private source, bundle ZIP, GeoJSON, binary windows, or raster data is permitted in this package or image context.
- This contract is a builder interface, not evidence of completed qualification.

Every file receipt is exactly `{ "path": "repo/relative/file", "bytes": 123, "sha256": "64 lowercase hex" }` (additional descriptive keys are allowed). Source closure paths are relative to the installed image repository ROOT, unlike gate file receipt paths, which are relative to the Git checkout. The full closure includes all internal runtime rows plus the startup manifest/bootstrap/worker, runtime manifest itself, and every overlay file. Keep external and conditional inherited files in separate arrays.

```json
{
  "schema": "WORLD_ENGINE_KOREAN_WAR_20S_BUILD_GATE_V1",
  "status": "PASS",
  "sourceCommit": "accepted CPU source 40-hex SHA",
  "parentImage": "ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:1ab43dd68e5ccdd364b6ec97d61d2f877070213cc42101412f45e17c54871e4b",
  "cpuEvidence": {
    "status": "PASS",
    "sourceCommit": "same accepted CPU source SHA",
    "oldPASSReruns": 0,
    "gpuStarts": 0,
    "evidence": ["file receipts binding A12 acceptance and preserved valid evidence"]
  },
  "privateAssets": {
    "status": "PASS",
    "sourceBackupAvailable": true,
    "rawAssetsExcludedFromPublicContext": true,
    "installationPath": "/workspace/shared",
    "receipt": "sealed public private-package receipt file receipt",
    "archiveVerification": "public local private ZIP/member verification file receipt",
    "backupEvidence": "public private backup download verification file receipt"
  },
  "studioInputs": {
    "status": "PASS",
    "officialPipeline": true,
    "inputs": ["PART01 file receipt", "PART02 file receipt"]
  },
  "sourceClosure": "PKG/PUBLIC_SOURCE_CLOSURE.json file receipt",
  "contextManifest": "PKG/final-context/CONTEXT.json file receipt",
  "contextFiles": ["exact recursive final-context file receipts, including CONTEXT.json and Dockerfile"]
}
```

Optional `parentBackupRecovery` is a file receipt for an already-valid published v16 recovery PASS with `status:PASS`, `archiveRootDigest` equal to the pinned parent and `dockerLoadVerified:true`. If present, it is reused; otherwise the old backup receives its first one-time download/hash/load check. Old backup release assets and old tag are preserved regardless.

`privateAssets.receipt` stays immutable even if its creation-time status says LOCAL_PREPARED. Separate `archiveVerification` must have schema `WORLD_ENGINE_PRIVATE_ARCHIVE_VERIFICATION_V1`, status PASS, rawAssetsExcludedFromPublicContext true. Separate `backupEvidence` must have status PASS and downloadVerified true. Both must match the immutable package receipt's `archiveSHA256` and `archiveBytes` exactly; `installationPath` must also match. The backup proof must contain no signed/private capability URL or raw source bytes. The root finalizes BUILD_GATE only after this proof exists.

CONTEXT fields consumed: `parentImage`, `overlay:[{path,bytes,sha256}]`, `runtimeManifestSHA256`, `startupManifestSHA256`, `entrypoint`, optional `precreatedDirectories`. The exact accepted private-directory list is:

```json
[
  {"path":"/workspace","uid":0,"gid":0,"mode":"0755"},
  {"path":"/workspace/shared","uid":1000,"gid":1000,"mode":"0700"}
]
```

The allowlisted Dockerfile has exactly these ordered statements, no blank lines/comments, ending with a newline. Omit RUN only if directories list is absent/empty. JSON uses Python default `json.dumps` spacing:

```dockerfile
FROM ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:1ab43dd68e5ccdd364b6ec97d61d2f877070213cc42101412f45e17c54871e4b
COPY --chown=0:0 ["overlay/", "/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo/"]
RUN install -d -o 0 -g 0 -m 0755 /workspace && install -d -o 1000 -g 1000 -m 0700 /workspace/shared
ENTRYPOINT ["the existing tini/python bootstrap argv with final two manifest SHA pins"]
```

Activation is a separate CAS commit changing ONLY `.github/workflows/world-engine-korean-war-20s-image-once.yml`, commit message exactly `WORLD_ENGINE_KOREAN_WAR_20S_IMAGE_A1`, on `deploy/korean-war-20s-20261109`. Preparation may have merge parents; activation must have the preparation commit as first parent. Fill both `REQUIRED_PREPARATION_HEAD` placeholders with that known first parent and `REQUIRED_64_HEX_GATE_SHA256` with SHA256 of the final gate bytes. Do not include the activation workflow in the preparation commit with live guards. The checked-out Git SHA is reported separately from the accepted A12 source SHA.

Publication tag is unique `korean-war-20s-v17-${GITHUB_RUN_ID}`. Backup release is `korean-war-20s-image-backup-${GITHUB_RUN_ID}`. Public proof files are uploaded both to the backup release (when reserved) and to Actions artifact `korean-war-20s-image-evidence-${GITHUB_RUN_ID}`:

- `BUILD_GATE_ACCEPTED.json`, `PLAN.json`
- `PARENT_BACKUP_VERIFICATION.json`
- `PRIVATE_INSTALLER_QUALIFICATION.json` (also separate raw fixture artifact if it blocks before the builder)
- `INSTALLED_PROBE.json`, `ENTRYPOINT_PROBE.json`
- `BACKUP_DOWNLOAD_RESTORE.json`
- `RESULT.json`

The release also holds inherited helper `RESERVATION.json` and `RETENTION_RESULT.json` plus numbered image archive parts. Root `RESULT.status=PASS` means image, entrypoint CPU boundary, GHCR digest and downloadable backup verified; it does not mean gCube save or GPU compatibility. A probe failure retains the exact candidate before blocking publication. No step retries. A failed activation is diagnosed before any new separately-authorized candidate is considered.
