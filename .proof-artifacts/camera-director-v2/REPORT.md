# Camera Director V2 — continuous continent zoom

[CAMERA PATH]
단일 MAP_INFOGRAPHIC_RENDERER_V1 Factory, 하나의 평면 지도 좌표계와 실제 Camera trajectory입니다. Globe, Hard Cut, Dissolve, 완성 화면 교체를 사용하지 않습니다.

[ZOOM / PAN]
실제 GIS 기반 CONTINENT bounds에서 승인 REGIONAL bounds까지 geographic center와 log extent를 연속 계산합니다. Quintic C2 easing으로 출발·가속·이동·감속을 한 곡선으로 처리합니다. Suez 전용 카메라 수치는 없습니다.

[STATE TIMELINE]
0–1.5s WIDE HOLD; 1.5–3.1s ACCELERATE; 3.1–4.933s TRAVEL; 4.933–6.8s DECELERATE; 6.8–7.4s SETTLE; 7.4–7.6s LOCK; 7.6–9.6s V1 REVEAL; 9.6–12.6s HOLD; 12.6–12.8s NEXT ready, camera fixed.

[LOD TRANSITION]
카메라 시간표와 독립적으로 실제 texel density와 viewport/source coverage를 검사합니다. 같은 Natural Earth 원본의 두 native pixel window를 동일 geographic coordinate에서 material 이전에만 샘플합니다. 겹치는 2,419,200 source pixels RGB는 정확히 동일합니다. 91 partial-weight frames, maximum weight step 0.0474848313; frame189에서 regional source 1.0. 완성 RGB frame 합성이 없습니다. Terrain/DEM/Normal/Material/Lighting/Output Transfer 계산과 데이터는 변경하지 않았습니다.

[DECELERATION]
한 곡선을 유지하며 final endpoint의 center/log extent velocity는 0입니다. 구간 경계에서 easing을 재시작하지 않습니다.

[REGIONAL ARRIVAL]
Frame203에서 승인 범위에 정확히 도착합니다. 이후 카메라 drift 없음. 최종 HOLD PNG는 V1 및 승인된 REGIONAL PNG와 파일 SHA-256·전체 2,073,600 RGB pixels가 정확히 일치합니다. Changed pixels0, max channel difference0.
Final PNG SHA-256: `fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673`.

[V1 REVEAL/HOLD PRESERVED]
YES. SETTLE/LOCK부터 후반 모든 정수 프레임의 상대 상태·Reveal timing·읽는 시간을 V1과 비교했습니다. Primary → Marker → 한글 Location/Country → Event Title. Layout/Font/Boundary/Glow/Marker 보호.

[LOCAL LIMIT]
RESPECTED. LOCAL_NOT_ADMITTED, no LOCAL frames, no zoom closer than approved REGIONAL fallback. Data-admission safe closest certification is not newly claimed.

[TECHNICAL VALIDATION]
PASS: 188
FAIL: 0
ERROR: 0
SKIP: 1 (RTX4080S, user prohibition)
All384frames decoded. Actual backend Chromium151 / ANGLE SwiftShader WebGL2, not NVIDIA. No black/blank frame or full-frame cut/flash during approach. Geographic-warp-aligned LOD signed luminance residual −0.159..+0.182/255. Compressed HOLD max adjacent mean RGB difference0.00367/255. Compression/resampling/AA/DEM footprint affect these auxiliary metrics; visual contact-sheet inspection is also recorded.

Initial harness reports are preserved: an initial assertion incorrectly froze user-allowed settle timing; a runtime comparison initially required bit-exact floating layout coordinates. Maximum coordinate difference2.27e-13px; only screen x/y coordinates use explicit1e-10 tolerance. Widths/heights, text style, font hashes, GIS anchors and strings remain exact. The final PNG pixel check is exact, with no tolerance. No Renderer/image changes or re-render were used to resolve these checks.

[DECISION]
CONTINUOUS_CAMERA_PASS (Software proof; final user video review pending). One visual iteration.

[OUTPUT]
SUEZ_CAMERA_DIRECTOR_V2.mp4 — 1080×1920, 30fps, 384frames /12.8seconds, silent.
01_WIDE_START.png, 02_APPROACH.png, 03_DECELERATE.png, 04_REGIONAL_LOCK.png, 05_FINAL_HOLD.png — lossless1080×1920.
MP4 SHA-256: `927d6944fa21bcbd41b71c3dce2582fc8062c2047d5e3282f478b30035a69cf8`.

[EXECUTION LIMIT]
No Container build/push, gCube, RTX4080S, Event Engine, TTS or next stage. GitHub publication only transfers these existing bytes; no rendering in CI.

[NEXT]
USER VIDEO REVIEW REQUIRED
