# T4 proxy recovery v005 — validation evidence

Image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v005`

Source revision: `1770b3a8a99b9423a076b0a91441d572d6751415`

Image digest: `sha256:aca64542277a971c6ce1c616308d8a263f7aca8ff94874971e298c88a4e38567`

[Passing fresh-image Actions run](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37569476532).

- Local regression: 231 tests, 230 PASS, 1 GPU-dependent skip, 0 failures.
- A–K proxy/owner/security cases pass. The new health-forwarding test prevents the internal health exception from rejecting or bypassing the public HTTPS envelope.
- Full image: root and UID1000 boot, 0.0.0.0:8000, owner login, Pod-IP health probes, explicit CPU-comparison Chromium WebGL2 draw, and foreground lifetime pass.
- Fresh image with a test-only same-Pod TCP relay: HTTPS external authority + HTTP localhost:8000, one/two/three XFF entries, secure owner cookie and 48 malicious mutation requests checked. Server remains alive for at least 61 seconds after READY. The step completed in 65 seconds; that step duration is not a video-render benchmark.
- GPU-required containers without NVIDIA remain blocked. Software renderer rejection contracts pass. No video render was requested, and no real GPU or T4 deployment was performed.
- Anonymous Docker pull passes in CI using an empty Docker credential configuration. Separately, an anonymous registry token verifies manifest/config and every actual layer. This workspace did not download all layers into its small VFS daemon; fresh full-image execution and the Docker pull occurred on the Actions CPU runner.
- v001–v004 registry digests are unchanged; 130 protected engine/render/asset/security/runtime files are byte-identical to the pre-task snapshot.
- No actual T4 raw header capture is available. Passing reproduced Istio envelopes does not prove live T4 WebGL capability.

## Existing VM constraint

The current official CLI guide permits workload updates only after stopping. The official stop guide says data/environment without storage backup are deleted on stop. Neither guarantees preservation of the same Tier1 VM or a hot image swap. Existing-VM retention is UNVERIFIED. No deployment/stop request was sent.

## Next one-shot actual test

Inspect real EGL/Vulkan backend results (unexecuted backends correctly display NOT_RUN), WebGL2, actual NVIDIA T4 renderer and stage F draw proof. Use a fresh private owner code of at least 16 characters. A 12-second QA video requires separate user approval after GPU PASS. CPU fallback and forced GPU PASS are not introduced.
