# GCUBE RTX4080 Super production preparation — v008

Based on the user-supplied gcube support confirmation: RTX4080 Super and RTX4090 support NVIDIA graphics; RTX3070 and T4 do not. This is provider evidence, not a GPU measurement in Codex.

The immutable operating v005 base is preserved. The v008 overlay checks the actual dpkg installation of libegl1, libvulkan1, libx11-6 and libxext6, installing only missing packages. It does not install a kernel driver or bake in NVIDIA_DRIVER_CAPABILITIES=all. Inject that setting in gcube.

Unspecified GPU startup tries Vulkan first with the existing wrapper's --use-gl=angle and --use-angle=vulkan; only failed bounded GPU admission can try --use-angle=gl-egl. Both paths use the same unchanged NVIDIA identity and actual WebGL2 shader/draw/readPixels admission. Software renderer rejection, no automatic CPU switch and READY gating are unchanged. An explicit backend override is honored as one attempt; leave WORLD_ENGINE_GPU_PROFILE unset to use automatic ordering.

The user-confirmed v007 request structure is replayed with substituted hostname/IPs. Before: X_FORWARDED_PROTO_NOT_HTTPS, HTTP 403. After: all static Host/forwarding/Origin preconditions and owner session tests pass. Upstream HTTP is admitted only for a verified .service.gcube.ai authority, unchanged trusted TCP peer, two IPv4 XFF entries (public then private), private IPv4 Envoy address, and consistent strictly parsed forwarding values. HTTPS compatibility remains. Forwarding values never authenticate an owner.

**External HTTPS remains required for public login.** The capture contains no browser transport or Origin proof. Secure cookies and mutation Origin checks remain; the public login fields stay disabled until the browser itself reports HTTPS and a secure context. Never send an owner-code to a plain HTTP service URL. A forwarded http value is not converted into evidence of browser TLS.

Existing MASTER/FLAT renderer, Scene JSON, FAST_PLUS, audio/rhythm, cache and checkpoint files are hash-preserved. No gcube operation or video render was performed. The CPU-only CI profile is explicit, isolated boot testing, never a production GPU fallback or a claim of RTX4080S success.

## gcube settings

- Image: ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v008 (publication proof is recorded separately after CI)
- Port: 8000
- Container Command: blank; existing foreground ENTRYPOINT starts automatically.
- GPU: Tier2 RTX4080 Super; RTX4090 only if separately approved after a failed RTX4080S hardware test.
- Environment: NVIDIA_DRIVER_CAPABILITIES=all; WORLD_ENGINE_OWNER_CODE=<new secret, 16+ characters>; WORLD_ENGINE_STORAGE_MODE=ephemeral; WORLD_ENGINE_STORAGE_PATH=/data; WORLD_ENGINE_RENDER_MODE=gpu-required.
- Leave WORLD_ENGINE_GPU_PROFILE unset; do not set CPU mode or insecure local mode.
- Keep Istio ON and 1GB shared memory. Ephemeral is for this admission-only test; results will not survive workload deletion. Existing persistent-storage mode remains available for production.
- Open the verified HTTPS service URL. Check NVIDIA visible, nvidia-smi, selected Vulkan or EGL, WebGL2, NVIDIA renderer and GPU test frame before READY. Merely receiving /healthz is not GPU READY.
- Do not start a 12s/75s/80s render. This stage only prepares and checks GPU admission; real RTX4080S validation is NOT_RUN until gcube is explicitly tested.

## Publication and final verification

The operating image is public and anonymously pulled by the successful GitHub Actions run. See CI_PROOF.json and PUBLIC_IMAGE_PROOF.json. The image revision is 3a68236c54d7f8d58efaf64989ebbc250aa2e8ec. Image source bytes for proxy/server/GPU ordering/fixtures were compared with the checkout. All previous v001–v005 and v006-diag/v007-diag digests were checked unchanged; the v005 base layers are identical. No owner code, forced all capability or automatic CPU fallback is baked in.

The actual image passed dependency queries, official backend flags, root and UID1000 boot/login/health, GPU-required-without-hardware fail-closed behavior, 270 operating/diagnostic tests (1 skipped, no failures), and the captured internal-HTTP proxy/secure owner login plus at least 61 seconds foreground persistence. Explicit CPU mode was used only for isolated no-GPU CI startup tests, not a production fallback.

Real RTX4080 Super WebGL2 remains NOT_RUN. The next gcube test should only inspect NVIDIA identity and a real GPU draw; no QA video is authorized yet. The supplied capture does not establish the externally accessible HTTPS service URL. The HTTPS-only login guard and Secure session cookies are retained.
