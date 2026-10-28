WORLD ENGINE — isolated diagnostic derivative

Predecessor source commit bc76bbfacc9b8fab40e89c3eb8d85b94b3ae8dbb passed GitHub Actions run 40620811966: eleven remote file SHA256 checks and fourteen production-image CPU diagnostic cases, UID/GID1000, no GPU.

This pipeline packages only that pinned source delta into a new runtime root; preserves the original root and manifests; changes the copied cold-start bootstrap's runtime hash pin only; retains all authentication and source validation logic. Image packaging checks are necessary because source paths and manifest pins change, not repeated renderer tests.

CPU startup verification reuses only affected existing default-entrypoint/setup/plan/TERM and missing-owner cases, plus installed diagnostic source binding. No GPU devices, render-start requests, gCube changes or operational secrets. GHCR publication is restricted to a new unique tag after CPU PASS. No deployment is authorized by a CI success.

Original GPU root cause is still unknown. Remote Dropbox write/readback and a separately approved real GPU run remain required. An uppercase code outside the fixed allowlist is omitted; classification is not a guaranteed root-cause diagnosis.
