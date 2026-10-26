WORLD ENGINE: additive packaged Studio startup V2

Base: startup commit a27782c9d0d462ad271c58d0e0819c6c2964b5dd,
runtime commit 624b540cad6dcfbe44e7e5d98c2b3d2ae8694851.
The original renderer, Scene contract, controller, authentication, mobile UI,
runtime manifest and original OCI image are unchanged.

WHY THIS EXISTS
The original image entrypoint owns the old Studio supervisor. Overriding CMD
does not establish a safe latest-Studio startup. This derivative changes the
image's default entrypoint and adds frozen runtime files plus a new startup
adapter under /opt/world-engine-handoffs/studio-v2. It never kills an existing
Studio. A fresh container starts Tini -> bootstrap -> existing supervisor,
GPU admission child and exactly one latest Studio worker.

AUTHENTICATION AND HTTPS
The existing owner-code, policy validators, setup challenge, CSRF, same-origin
guards, authenticated origin registration and production login remain the
authority. If PUBLIC_ORIGIN is unset or empty, the existing SETUP mode is used.
The guarded root redirects to /setup. No URL is invented. A valid nonempty
origin is checked by the original canonical_origin function.
After deployment, obtain the actual provider HTTPS service origin, open its
/setup page, enter the owner code using the secure user input path, confirm
that exact origin, then log in again. The controller factory remains gated
until registration. This operation does not start a render.

REQUIRED DEPLOYMENT INPUTS
Use the newly published unique tag in gCube; retain its independently verified
GHCR manifest digest in both WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST and
WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST. Their equality is a contract guard, not
independent proof of the provider's actual image. Compare provider-selected
image evidence with GHCR before approving a GPU render.
GPU_BACKEND=vulkan; WORLD_ENGINE_STUDIO_PORT=8080.
WORLD_ENGINE_STUDIO_STATE_ROOT=/var/lib/world-engine-studio-v2/auth must not
already exist. It is private container storage, outside the Dropbox export.
The parent directory is created in the new image; startup creates the private
root using the existing initializer. Existing private roots are rejected.
WORLD_ENGINE_STUDIO_OWNER_CODE and WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON
must be supplied through official secure inputs, never through image layers,
repository files, commands or logs. No production credentials are generated.
The exact six policy fields are validUntil, maxWallSeconds, maxRetries,
maxCostAmount, currency and gpuHourlyRate. Use verified actual billing units
and rate. Currency conversion, if needed, requires verified evidence.
For this authorization: at most 1800 seconds, zero retries, target KRW 2000.
Set the absolute expiry immediately before the approved single deployment.

STORAGE AND STOP GATES
Preserve the existing Dropbox connection and /world-storage mount. The new
image includes no credentials, Dropbox data, private state or output files.
Before GPU deployment, establish a fresh output directory and prove remote
write/read access without overwriting an existing path. Private auth is not
automatically backed up to the public export. Exported MP4 SHA256 must match
an actual external download; local mount existence alone is insufficient.
Application expiry stops this container's service; it does NOT stop provider
billing. Verify the provider's one-time Stop schedule and manual Stop path,
leave time to confirm Finished within the approved 30 minutes, and do not
deploy when the deadline or KRW 2000 target cannot be respected.

CPU CI AND PUBLICATION
The new branch's public ubuntu-24.04 workflow runs once (run_attempt == 1).
It materializes the frozen manifest file set, stages a bounded build context,
pulls the original base by digest once, and builds without build-step network.
Actual disposable CPU containers use the candidate image's default entrypoint
and packaged source files; no target entrypoint override, source mount, GPU
device, render or deployment is permitted. Test credentials, HTTPS origin,
image identity and billing rate are explicitly synthetic fixtures.
Tests cover SETUP -> existing authenticated registration -> latest controller
and six-second CPU plan; termination/signals; worker failure without restart;
port collision; missing owner; application expiry. Existing unaffected tests
are not rerun. A failed suite stops publication; no automatic retry exists.
Only after CPU PASS, publish a never-existing unique GHCR tag using the scoped
Actions token, then verify manifest SHA256 and config identity via tag and
digest readback. Raw tokens, cookies and private configuration are not logged.
An image publication result is not GPU, real HTTPS, real Dropbox or MP4 PASS.

SINGLE GPU SESSION, ONLY AFTER ALL GATES
Use RTX 4080 SUPER x1, one deployment, one render, zero retries. Verify actual
NVIDIA/Vulkan readiness and latest controller. Reuse AVIATION_EUROPE_NL.json:
1080x1920, 30 fps, 180 frames, 6 seconds, audio disabled. Inspect the resulting
MP4 with metadata/frame-count checks and visual review, preserve and download
it externally, then Stop immediately and confirm Finished and final charges.
On an unexpected error stop immediately; do not redeploy or retry rendering.
Technical GPU execution and visual quality are separate judgments.
