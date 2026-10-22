# Studio integration gates V1

Source baseline: `419d01ccace83d871277b2fcfc487d1b61ff7d81`.

This is a separate source extension. Existing FINAL, engines, shaders, camera,
Scenes, original videos, claims and images are unchanged. Nothing is deployed.

The original 65422 source input is rejected by the prior Studio contracts before
draw: `STUDIO_DURATION_UNSUPPORTED` / `STUDIO_OVERNIGHT_PROFILE_REQUIRED`.
The new strict `WORLD_ENGINE_STUDIO_EXACT_REFERENCE_V1` family selects only its
pinned original source capsule. It does not convert historical ownership data.
The existing Studio HTTP handler, password login, Host/Origin/CSRF checks and
private storage remain in use. The added opt-in branch admits only a bounded
free SwiftShader regression. It never creates a GPU authorization or calls a GPU
launcher. Production input and budget checks delegate to the existing controller.

## Reproduce G1 without deployment

Reuse `exact-65422-reproduction-v1/tools/restore_capsule.py` and its immutable
source manifest to restore the original source checkout if absent. Read that
tool's CLI before use. Original report SHA is
`550c1d7db502b91dc94548284ddfb10ff27f8e52cdf7efac7e7df68bfa768656`.
Node 24.19.0, Playwright 1.62.1, Chromium 154.0.8037.57 and FFmpeg are required.

Run `python tools/run_actual_studio.py --private-root /workspace/<new-private-run>`
from this directory. That tool starts the preserved loopback-only test service,
logs in through its actual mobile Chromium login form, submits and starts the
strict JSON request, disconnects the browser and HTTP server, and monitors the
detached worker. It never reads old render caches. Output uses `captures/<job>/`;
the separately reviewed public files and reports are copied out for persistence.
The prior image digest in the harness is metadata of an existing image, **not**
an assertion that this new source extension is already present in that image.

No GPU or historical preview is authorized by this profile. A missing original
capsule fails closed. No private owner code, cookies or auth state are published.

## Gates

G1 must newly draw all 150 original frames and compare original raw/PNG hashes.
G2 requires actual same-date bilateral ownership evidence before a historical
transition can be admitted. Unknown source areas remain unknown.
G3 historical rendering is prohibited unless G1 and G2 both pass. Technical,
render and user visual approval are separate states. User approval is pending.
