# V3 visual failure intake — 2026-11-13

Status: **VISUAL_FAIL_CONFIRMED / ROOT_CAUSE_NOT_VERIFIED**. This is an additive read-only review, not a rerender or a repair PASS.

## Baseline
- Git HEAD at intake: `4ae94ece747e900c8c3a7b03528409e3691218be`.
- Existing CPU MP4: `cpu-a1/VIDEO.mp4`; existing checkpoint SHA256: `9d76ebf89d6dace3b362aefc1116b1151ef339e5726d32b7e7b790cca72f9431`.
- Existing compile, 14 delta checks, 180-frame CPU output and decode PASS remain intact. No existing test was rerun.

## New direct observation
- The user supplied a copy of the V3 video (`70368.mp4`) in the conversation. Frame indices 003,009,015,030,045,060,081,090,096,135,145,149 were decoded for read-only visual comparison (270x480 preview).
- Geography, city labels, route progress and camera movement are visible.
- The expected expanding rings, separated luminous halo and distinct moving-object echoes are **not clearly perceptible at mobile preview size**. Arrival emphasis is visually weak.
- This establishes a perceptual failure, **not** which renderer parameter or compositing stage caused it. No assertion that the uploaded copy has identical SHA to GitHub source is made.

## Focused code evidence
- `recovery/universal-presentation-v2/presentation_flow.mjs` has bounded flow style/trail/ring validation.
- `web/map_infographic_v1/flow_graphic_pass_v2.mjs` contains pulse/echo rendering primitives.
- These are implementation existence checks only; they do not establish visible effect intensity or causal attribution.

## First incomplete gate
**Identify confirmed cause per effect from the existing V3 runtime and rendered pixels**: pulse radius/alpha and projection, halo/core contrast and layer order, trail spacing/alpha and occlusion, camera motion, arrival timing. Separate CONFIRMED_CAUSE from PROBABLE_CAUSE and NOT_VERIFIED. Do not modify code or run full 180-frame capture until minimum representative-frame visual gate passes.

No GPU, image build, product code change, or old PASS rerun performed by this intake.
