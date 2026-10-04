# Published checkout setup verification

Commit: `a6f3fc0f2281740f8446ede5fc4ce50590a21871` (verified against GitHub main before checkout).

Result: **PASS**. The exact full Git archive was installed using unchanged `bash tools/setup_cloud.sh`. All **130 tests passed** in 154.126 seconds; setup took 187.935 seconds.

- Fresh checkout: `/tmp/world-engine-published-checkout-20261004T185835Z`. Existing app runtime, venv and node_modules were absent before setup.
- Python packages were loaded from the new checkout's independent virtual environment, with system site packages disabled. Pinned fonttools 4.61.1 was installed there.
- Three.js 0.170.0 and Playwright 1.62.1 resolve inside the checkout's own node_modules. NODE_PATH and Python override variables were removed only for child processes.
- All five downloaded Korean eSpeak runtime packages match their declared SHA-256 hashes; copyright files are preserved, and unchanged bootstrap ran its real Korean WAV validation.
- All 380 tracked checkout files and original workspace tracked files retained their before/after hashes and modes.
- Existing proxy and CA settings were preserved. Evidence records variable names and presence only; public setup logs redact URL/auth content. The raw log remains private with mode 0600.

This verifies fresh dependency installation on the **same provided Linux system executables**. It does not verify a newly provisioned OS/cloud, a physical phone, a full video render, or a 4K graphics benchmark. No server, original sources, Git stage or current rendering job was modified.

Files: `REPORT.json` and source hash manifests contain the original orchestration record. `PROBE_VERIFICATION.json` contains correct fresh dependency resolution proof. The original two post-setup harness probes had Python syntax / package export lookup mistakes; correcting those read-only probes required no project source change or setup rerun.
