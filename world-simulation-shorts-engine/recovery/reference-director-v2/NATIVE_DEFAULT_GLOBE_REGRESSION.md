# Observed default globe exact-comparison failure; patch cause unconfirmed

Actual original and candidate04 native factory draws used the same source input, shared WebGL renderer and free SwiftShader backend. Flat Namibia/Nepal comparisons had passed bit-exactly. The subsequent WORLD default pair differs at **12 / 2,073,600 pixels**, maximum RGB channel difference5 (9pixels differ by more than1), absolute mean channel error9.8058127572e-6. The exact-equality test **failed**; it was not relaxed.

These are actual native engine frames, not the supplied reference video or Studio production. Raw readPixels hashes, output PNG hashes, source renderer hashes and full coordinates are in `reports/NATIVE_GLOBE_DEFAULT_REGRESSION.json`. The two actual PNGs are retained under `evidence/globe-default-regression-candidate04/`. All earlier failures and successes remain private as recorded by `reports/NATIVE_PIXEL_ATTEMPTS.json`.

The suspected added inactive GLSL branch is a hypothesis until the minimal default-shader isolation change is retested. PHASE1 has not passed at this point; active rotation and PHASE3 production stopped. No paid GPU/API, source replacement, threshold change or original reference media publication occurred.

Source credits: Solar System Scope/NASA-derived Earth day image, CC BY4.0 (https://www.solarsystemscope.com/textures/; https://creativecommons.org/licenses/by/4.0/), Natural Earth vectors Public Domain, Noto Sans CJK KR SIL OFL1.1. This is a rendered technical comparison, not survey/geographical accuracy evidence.


## Original-only control and corrected attribution

The candidate05 default WORLD pair also differed (14 pixels, maximum channel delta6). An independent unchanged-original control then observed different raw pixel hashes on repeated draws **within the same original factory**, with GL error0. This establishes an original-path determinism failure in the tested software environment, not a confirmed patch-caused regression. The earlier exact-comparison failure and its metrics are preserved above; the heading and root-cause interpretation are corrected.

Candidate05 restores byte-exact default fragment source. That code/source check is real; a pixel-restoration fix is UNVERIFIED. Native render-pass isolation must identify whether the variation comes from source sampling, boundary/coverage passes, shared driver state, readback or another tested cause. No failure threshold was relaxed and no underlying backend cause is asserted. See the native pixel agent’s retained original-only frames and receipts for execution evidence.

Native mode 5 source-only control also varies within the unchanged original factory (original-first: 24 different pixels, maximum delta 2), with graphics, boundaries and glow disabled. This narrows the failure to the original globe/source-output path in this backend and excludes those later compositing layers as necessary causes. The precise sampling/driver cause remains unconfirmed. See `reports/NATIVE_GLOBE_BASELINE_NONDETERMINISM.json`. Independent flat/rotation unit validation does not waive this unresolved exact WORLD baseline requirement.
