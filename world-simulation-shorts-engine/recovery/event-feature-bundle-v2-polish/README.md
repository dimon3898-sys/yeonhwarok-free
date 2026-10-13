# Flow / Movement Visual Polish V2 Candidate

Status: USER_VIDEO_REVIEW_REQUIRED. This Candidate grants no FINAL status and executes no Permanent Gate.

Parent V1 FINAL: `f79f3d55d945ef0e53b03ac2ed666f48f28b5881`.
Accepted Flow structure/source: `12715730f0d93cecf450bd51099be9e99fbdb71c`.
Development branch: `development/event-flow-polish-v2-20261013`.

## Four approved presentation changes

- TRANSPORT_MOBILE profile scales the approved 52×30 graphic by 1.20 to 62.4×36 pixels. Four native size candidates were compared. Fixture/profile data selects the scale; the engine has no location or object-name branch. The existing front/back silhouette and route-tangent heading are retained.
- The existing V1 arc-length reveal evaluator draws a modest lead ahead of the unchanged object trajectory. Route completion moves from global frame 92 to 157, making progress visible through travel. The existing single directional chevron follows ahead of the bow. No new line engine or motion simulation.
- The new proof fixture empties its existing watermark data field. This removes “이동 예시” through the original layout's optional-text behavior. The route title and real location labels retain their style and positions.
- A faster, asymmetric rise and restrained wider ring emphasize the existing single 18-frame arrival pulse. The approved object deceleration and settle are unchanged. Final hold remains 34 frames.

All original route coordinates, object arc-length fractions/positions/headings, camera states, Detail Approach, style shaders, occlusion, markers and protected V1 source files remain unchanged. The sole modification to the accepted Flow GPU adapter is an optional presentation hook; callers without a profile retain the original branch.

## Focused reproduction

Use the inherited pinned setup recipe and Git/LFS assets from the Candidate manifests. No new dependency or source-data download is required.

```bash
node world-simulation-shorts-engine/recovery/event-feature-bundle-v2-polish/build_polish_fixture.mjs --verify
node --test world-simulation-shorts-engine/tests/flow_visual_profile_v2.test.mjs
node world-simulation-shorts-engine/recovery/event-feature-bundle-v2-polish/focused_validation.mjs
node world-simulation-shorts-engine/recovery/event-feature-bundle-v2-polish/render_proof.mjs
```

Render from a fresh checkout of the original source commit recorded in the proof report / reproduction manifest. That revision has no `public-review` or `evidence/proof` output directories; original outputs are created exclusively. At the media revision, preserve the production media and use a disposable checkout for reproduction.

Output: 240 native frames / 8 seconds, 1080×1920, 30fps, silent H.264. One original encode. Checkpoint PNGs are the exact native frames supplied to that encode. Every frame checks camera/core-motion equality and protected pixel masks.

Public review is restricted to one MP4, six PNG checkpoints, and SHA256SUMS. Diagnostic comparisons, source, fixture data and manifests remain outside that directory. Phone downloads use immutable media-commit raw URLs with HTTP 200 and downloaded-body SHA verification.

Required temporary-only runtime files: 0. Historical inactive provenance descriptors remain explicitly non-runtime. User approval is required before the deferred final Permanent Gate.
