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
