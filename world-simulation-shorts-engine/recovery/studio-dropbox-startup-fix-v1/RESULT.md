# Actual Dropbox CPU backup and recovery: PASS

## Confirmed causes and minimal correction

1. Original run `39110576350` recorded `DURABILITY_OFFLINE_STARTUP_FAILED`. Its Python `-c` / `runpy.run_path` command did not expose the offline module directory to imports. The exact immutable container reproduced exit 2 before correction and CLI import success, exit 0, after adding only the fixed working directory.
2. Run `39111545470` passed that startup check, then recorded `DURABILITY_KEY_32_BYTES_REQUIRED`. The mobile enrollment encoded the key using standard Base64; the frozen reader accepts canonical URL-safe Base64. The new input adapter changes only the process-local text representation and verifies that all 32 decoded key bytes remain identical. The existing Repository Secret and backup key were not changed.
3. Default Secret Scan initially classified source-manifest hashes beside filenames containing `key` as generic credentials. Explicit separate `path` and `sha256` fields preserve the same verification while allowing the unchanged default scanner to classify the manifest correctly. No rule or source file was excluded.

## Actual external proof

- Run: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39112133539
- Source: `5248d31220e63d3504fcd6b07dbe43ce6fe7549c`
- Profile: `development/dropbox-startup-fix-20261018`
- Safe result: `runs/39112133539-1/proof.json`
- Result-file SHA-256: `ee557ece7aa237754a82a1259f0a9e50011ab89e8cdec104666efc7b69b512d8`
- proofId: `08398705cd4ffb90a7f68a26ee6f65a121c5efa62ad4f854c1aa50ea371b55a7`
- checkpointId: `9fa8bdd8b3c4489409dc82c568c17e8a1e9646cb605d14eda5be534fc9d29796`
- Safe proof persistence commit: `5202b78`.

Actual existing OAuth refresh, Dropbox metadata access, encrypted upload, HTTPS download, decryption, SHA comparison and fresh-root checkpoint recovery passed. Actual FFmpeg synthetic media was used, not mock provider responses. The recovered cache correctly contained the two completed scenes and the one remaining scene. Recovered MP4 files were fully decoded and checked by the existing implementation.

## Focused validation and protection

- 23 focused tests: PASS; actual CPU container startup before/after: PASS.
- Default pinned Secret Scan: PASS, 0 findings.
- Immutable image source and parent manifests: PASS.
- Protected source changes: 0. Original FINAL, Candidate, renderer and backup engines remain unchanged.
- Existing GitHub Secrets, encryption-key bytes and existing Dropbox objects: preserved. Only additive synthetic proof objects were created; no existing backup deletion or overwrite.
- Temporary Secret files created by this invocation: removed by the frozen helper; required temp-only source files: 0.
- No new image build, GPU deployment, NVIDIA execution, production rendering or FINAL promotion.

This proves actual CPU external backup and fresh-root recovery in the same CLI process. It does not prove a container restart, an 80-second production video, NVIDIA rendering, or video quality. Key normalization currently applies to this proof profile; production startup must reuse the byte-preserving input adapter before claiming that separate path is verified. Existing production images were not modified.

The external proof was not repeated after PASS. No owner login, token reissue or Secret change is required for this result. Stop here for user review; paid GPU remains prohibited.
