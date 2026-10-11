# CAMERA DIRECTOR V3 — USER VIDEO REVIEW REQUIRED

[FRAME 0 PRIMARY COLOR]
PASS. Egypt uses the approved Primary gold material from frame 0 through frame 383. Secondary/Neutral role colors remain unchanged.

[CAMERA V2 PRESERVED]
PASS. All 384 actual frames preserve V2 center, extent, velocity, easing/state timing and LOD values. One continuous flat-map Renderer Factory; no frame replacement, dissolve, LOCAL, camera tuning or projection change.

[COLOR CONTINUITY]
PASS. Original PNGs and the encoded MP4 were checked. Primary material factor is always 1; camera and LOD run independently. Boundary/Glow style and their V2 timing are preserved separately.

[REVEAL]
LOCK finishes at frame 227. First visible frames: Marker 229 → 수에즈 운하 241 → 이집트 256 → 수에즈 운하 폐쇄 268. All information is fully revealed by frame 288; HOLD timing remains identical to V2. Country color has no reveal stage. The existing 가정 시나리오 disclosure is retained.

[FINAL HOLD]
PASS. Lossless 05_FINAL_HOLD.png is byte-for-byte and pixel-for-pixel identical to the approved V2 hold PNG.
SHA-256: fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673

[TECHNICAL VALIDATION]
PASS: 207
FAIL: 0
ERROR: 0
SKIP: 1 (RTX4080S prohibited)
Completed renderer iterations: 1.
An initial unaligned whole-frame RGB difference check flagged normal fast pan/zoom at frame 129 (11.213/255). Its original failed evidence is retained in technical-validation.json. The corrected check removes the exact geographic camera motion and applies the existing V2 aligned-luminance criterion; no threshold loosening, renderer modification or rerender was used to resolve this test-method issue.

[DECISION]
CAMERA_DIRECTOR_V3_PASS — technical proof submitted for user approval.

[VIDEO]
SUEZ_CAMERA_DIRECTOR_V3.mp4: 1080×1920, 30fps, 384 frames, 12.8 seconds, silent H.264 MP4.

[CHECKPOINTS]
01_FRAME0.png: frame 0
02_MID_ZOOM.png: frame 120
03_REGIONAL_LOCK.png: frame 227
04_MARKER_REVEAL.png: frame 239
05_FINAL_HOLD.png: frame 333
All five PNGs are original 1080×1920 lossless Renderer exports.

[EXECUTION LIMITS]
Software WebGL2 / SwiftShader only. Container, gCube, RTX4080S, Event, TTS, audio and next-stage work: NOT RUN. Release automation only verifies and uploads these existing bytes; it does not render or build.

[NEXT]
USER VIDEO REVIEW REQUIRED.
