# Version and update policy

## Validity

This is a read-only audit snapshot of source `c0f2868e9cab8a269c2bd8552dc09920e5e53863` and operating immutable image `sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da`. Audit-branch publication commits contain documentation only. Image source identity, source-audit identity, publication identity and observed job identity are separate fields; never infer one from a tag prefix.

All evidence paths are repository-root relative at the source commit, including historical receipts cited as reused evidence. The listed legacy FINAL gate results are historical receipts, not newly executed Permanent Gates. Current image membership is declared closure plus immutable pull evidence and fresh manifest reads, not a new filesystem inspection of a running GPU.

## Future update procedure

1. Pin new source commit, accepted Scene/input identity, image digest and audit timestamp. Preserve the previous audit snapshot.
2. Diff changed parser/profile/schema/adapter/import-map/image manifest paths before selecting focused tests. Do not rerun unrelated historic suites.
3. Regenerate feature records, per-axis state and source evidence. Recheck aliases and actual selected factories; never equate source existence, image inclusion, parser acceptance and output verification.
4. Run actual CPU normalizer/backend examples and structural schema checks separately. Document runtime-only constraints JSON Schema cannot express. Unsupported keys must remain rejected until a validated path consumes them.
5. Hash-match source body to pinned Git blob and packaged manifest. Mark unreadable source NOT_VERIFIED rather than extrapolating.
6. Actual output verification requires the full matching MP4, decode/probe, capture/Scene/source identity and permitted artifact delivery. No render is authorized by this audit/update procedure.
7. Scan the new public documents for secrets, private state contents, personal data and accidental asset copies. Publish only the docs branch.
8. Hash every bundle member; build deterministic ZIP, publish under a commit-pinned URL, fetch with HTTP 200 and compare original/downloaded SHA-256. Store download verification separately to avoid circular hashes.

This procedure is documented, **not a newly installed CI auto-regeneration implementation**. Future schema/profile changes require an explicit audit update. `SOURCE_TREE_INVENTORY.csv` metadata coverage does not imply all listed files have been semantically audited.

## Bundle and integrity rules

`MANIFEST_SHA256SUMS.txt` covers all handoff members except itself, the ZIP, download checksums and subsequent download verification receipts. `DOWNLOAD_SHA256SUMS.txt` separately hashes the ZIP and member manifest. The ZIP includes only handoff documents/JSON/CSV (plus its internal member manifest), no original code, videos, imagery, raster samples, credentials or private runtime state. Receipt files may be committed after the artifact commit; phone download URLs remain pinned to the artifact commit.

Status of this snapshot: `USER_REVIEW_REQUIRED`. No FINAL promotion, image replacement, paid GPU, deployment or rendering is part of this work.
