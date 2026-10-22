# Re-running the preserved 143 G2 checks

The unchanged command list is from
`recovery/g2-final-recovery-v1/tools/run_cpu_regressions.py`. That old runner
itself is **not executed** because its finalizer overwrites the protected
`g2-final-recovery-v1/reports/CPU_REGRESSION_RESULTS.json`. The additive
`tools/run_g2_regressions.py` executes the same test commands, same ordering,
same strict case counts and zero-SKIP condition. It writes each command's
stdout, stderr, exit status and duration only in this task's new
`reports/regressions/<attempt>/` directory. No old test or assertion is edited.

## Fresh-environment fixture restoration

Three missing old private inputs were identified by actual test code:

1. `test_native_preparation.mjs` and `test_geometry_alignment.py` require the
   original `REGIONAL-plan.json` at an old absolute capsule path. Its bytes
   are already tracked and have the exact SHA and Git blob attested in
   `exact-65422-reproduction-v1/reports/SOURCE_CAPSULE_MANIFEST.json`:
   SHA-256 `e5940e0f258001e2f3273d441694a8b4f0fbcd1d51d74e4d38685c64c2944ee6`,
   7,984,189 bytes. Only this needed inert file is materialized at the
   previously absent alias. The full old capsule is not reconstructed.
2. The 48 neutral Namibia/Nepal probe fixture files are restored from the
   committed, SHA-pinned `g2-renderer-recovery-v1/fixtures/GENERIC_PROBE_INPUTS.zip`
   to a fresh private probe directory. `G2_GENERIC_PROBE_ROOT` selects it;
   no old capture cache is overwritten or used as a new rendered frame.
3. One source-position test otherwise skips without the original official
   GovInfo PDF. It is only 918,062 bytes. The already documented original URL
   is fetched using the supported network permission path, inherited proxy
   and TLS verification. Actual HTTP 200 and exact SHA-256
   `34d1bf77b29304711cef0ca41a9fcbddec0f04bc14ec11d3088f6373b238f41b`
   were checked before a previously absent legacy test alias was created.
   This does not create new historical coordinates or change source facts.

`tools/setup_regressions.py` accepts only byte-identical existing files or
creates absent files exclusively; symlinks and mismatches fail. Archive
paths are checked for traversal. Restore receipts list all files and hashes.

```sh
PYTHONDONTWRITEBYTECODE=1 python -B \
  world-simulation-shorts-engine/recovery/universal-data-pipeline-v1/tools/setup_regressions.py \
  --source-pdf /workspace/universal-data-pipeline-v1-private-20261022/GOVINFO_UN_OFFENSIVE_1950.pdf

PYTHONDONTWRITEBYTECODE=1 python -B \
  world-simulation-shorts-engine/recovery/universal-data-pipeline-v1/tools/run_g2_regressions.py \
  --attempt <new-unique-attempt-id>
```

The existing source-fixture-store code may additionally restore its own
SHA-pinned neutral ZIP into `/tmp/world-engine-source-6d90f2132cf8c496`, as it
did in the preserved original tests. That operation validates every byte and
does not replace repository source or an old cache.

## Free browser dependency shared with the new runtime

Playwright was installed only into a new private dependency prefix:

```sh
npm install --prefix /workspace/universal-data-pipeline-v1-private-20261022/node-deps \
  --cache /workspace/universal-data-pipeline-v1-private-20261022/npm-cache \
  --ignore-scripts --no-audit --no-fund playwright@1.62.1
```

Actual versions: Node `v24.19.0`, Playwright `1.62.1`, system Chromium
`154.0.8037.57`, Python `3.12.14`, PyMuPDF `1.26.6`, Pillow `12.3.0`.
The new runtime can use
`WORLD_ENGINE_NODE_DEPS=/workspace/universal-data-pipeline-v1-private-20261022/node-deps`
and `/usr/bin/chromium`. No tracked `node_modules` directory is changed.

The first default-sandbox network attempts returned local OS `EPERM` before
reaching the proxy. The supported permission escalation then succeeded with
the same inherited proxy and TLS. No destination-policy bypass, direct route,
fake credential, paid service, GPU job or deployment was used. Access receipts
retain the failed and successful distinction.

These CPU checks and browser dependencies establish regression/development
readiness only. They do not establish NVIDIA hardware or video-quality PASS.
