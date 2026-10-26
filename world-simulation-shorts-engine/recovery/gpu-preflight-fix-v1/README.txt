WORLD ENGINE — two GPU preflight blockers, configuration-only repair

BASE
Commit 1811f3c52fc8fc1e4d2de716f2b91f851be1cf12.
Image digest sha256:32c677d1dbeec3908b6790484b34905ad6818f8e5a9127106579f7dfd233342e.
Main, recovery branches, frozen runtime manifest and existing images are preserved.

DEPENDENCY ROOT
The original dependency_facts rejects a missing/invalid WORLD_ENGINE_NODE_DEPS
before Playwright module resolution. The runtime expects a package root, not
node_modules itself. The candidate adds only:
WORLD_ENGINE_NODE_DEPS=/opt/world-engine/cinematic-world-map
The CPU baseline gate must first prove that this root and the pinned Playwright
files already exist in the real original OCI filesystem. No install occurs.
If that evidence fails, CI stops before the build/publication. No guessed PASS.
The config-only derivative has identical root filesystem, entrypoint, command,
user, auth, renderer, controller, Scene and UI. Image config comparison enforces
this before publication; only the one environment entry may differ.

SHARED MEMORY
Original nvidia_backend.py reserve() requires /dev/shm total capacity >=
2 * 1024**3 = 2,147,483,648 bytes. The reported exact error means this capacity
was below the threshold. It does not mean a permission or free-byte check failed.
gCube UI labels its runtime option GB but does not document exact byte conversion.
Set Workload #5373 Other Options -> Shared Memory to 3 GB and save without Deploy.
The actual next container must still report >=2GiB and pass the original guard.
Do not lower the guard or remount /dev/shm from inside the image.
A new image alone does not alter the provider's runtime shared-memory mount.

FOCUSED FREE CPU VERIFICATION
Public ubuntu-24.04, attempt1 only; no GPU, render, auth or full preflight.
Original dependency_facts runs with missing root (exact expected failure) and
existing root (pinned Node/Playwright metadata success). Candidate uses its actual
inherited ENV; the test must not inject the value it is supposed to verify.
Actual CPU Docker /dev/shm sizes 2,000,000,000 / 2,147,483,648 / 3,000,000,000
exercise the unchanged reserve() body: BLOCKED / PASS / PASS. Decimal requested
sizes may round to page boundaries, which the test records. Mount facts and a
UID1000-owned small write/read probe distinguish capacity from access problems.
No old NVIDIA, HTTPS, Dropbox, Owner or complete runtime/OCI PASS test is repeated.

PUBLICATION
Only after the focused gates pass, publish a new unique preflight-fix-v1 tag.
Refuse existing tags; compare tag/digest readback and tested image config digest.
Any failure stops the workflow. No automatic retry, render, or gCube deployment.

NEXT SINGLE GPU SESSION (NOT AUTHORIZED BY THIS REPAIR TASK)
1. Use the new verified tag. Keep Container Command blank and port8080.
2. Set both existing image-digest environment fields to the verified new digest;
   do not alter Owner values, source manifests, storage or other runtime settings.
3. Confirm Shared Memory 3GB is saved; record actual /dev/shm bytes after startup.
4. Refresh execution-specific expiry/Stop timing under a separate deployment task.
5. Existing Studio preflight must show RENDER_DEPENDENCIES and
   DISK_AND_SHARED_MEMORY PASS. Do not bypass other normal execution gates.
6. Only in the approved single session, render AVIATION_EUROPE_NL.json once:
   6s,180frames,1080x1920,30fps,silent. Inspect and remotely preserve the MP4.
7. Stop on any failure, never retry; confirm Finished and billing cessation.
CPU repair READY is not GPU or MP4 quality PASS.

Official shared-memory option documentation:
https://data-alliance.github.io/gai-platform-docs/en/user-guide/gcube-cli/cli-workload/
https://data-alliance.github.io/gai-platform-docs/en/user-guide/workload/register-workload/
