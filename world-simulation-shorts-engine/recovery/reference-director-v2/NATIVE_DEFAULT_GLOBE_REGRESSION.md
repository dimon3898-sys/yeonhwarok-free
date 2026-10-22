# Confirmed default globe pixel regression in candidate04

Actual original and candidate04 native factory draws used the same source input, shared WebGL renderer and free SwiftShader backend. Flat Namibia/Nepal comparisons had passed bit-exactly. The subsequent WORLD default pair differs at **12 / 2,073,600 pixels**, maximum RGB channel difference5 (9pixels differ by more than1), absolute mean channel error9.8058127572e-6. The exact-equality test **failed**; it was not relaxed.

These are actual native engine frames, not the supplied reference video or Studio production. Raw readPixels hashes, output PNG hashes, source renderer hashes and full coordinates are in `reports/NATIVE_GLOBE_DEFAULT_REGRESSION.json`. The two actual PNGs are retained under `evidence/globe-default-regression-candidate04/`. All earlier failures and successes remain private as recorded by `reports/NATIVE_PIXEL_ATTEMPTS.json`.

The suspected added inactive GLSL branch is a hypothesis until the minimal default-shader isolation change is retested. PHASE1 has not passed at this point; active rotation and PHASE3 production stopped. No paid GPU/API, source replacement, threshold change or original reference media publication occurred.

Source credits: Solar System Scope/NASA-derived Earth day image, CC BY4.0 (https://www.solarsystemscope.com/textures/; https://creativecommons.org/licenses/by/4.0/), Natural Earth vectors Public Domain, Noto Sans CJK KR SIL OFL1.1. This is a rendered technical comparison, not survey/geographical accuracy evidence.
