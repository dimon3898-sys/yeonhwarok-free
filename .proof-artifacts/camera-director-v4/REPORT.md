[REFERENCE RULES IMPLEMENTED]

주인공 인식 → 공간 관계 확보 → 연속 접근 → 이동 중 위치 안내 → 감속 → 안정된 제목 → 고정 읽기. 실제 64306과 완성 MP4를 비교했습니다.

[MOTION ARC]

PRIMARY_RECOGNITION → CONTEXT_EXPANSION → RELATION_HOLD → EVENT_APPROACH → GUIDED_REVEAL → DECELERATE → EVENT_FRAMING → SETTLE → LOCK → EVENT_TITLE → PERCEPTION_HOLD → NEXT

[CONTEXT EXPANSION]

Geometry/Safe Area 자동 판정: REQUIRED. 1.07s (f32) → 2.70s (f81). Relation Hold 후 접근.

[PAN / ZOOM]

동일 geographic 공간. Geometry-derived pan_weight=0.067687, zoom_weight=0.932313; Camera center/log-extent를 한 Plan에서 연속 평가.

[ACCELERATION / DECELERATION]

C2 가속·이동·안내 감속·미세 접근. Reveal은 CameraPlan을 변경하지 않으며, 제목 전 Settle/Lock 유지.

[MOVING PRIMARY LABEL]

0.00s (f0)부터 읽기 조건 충족. 실제 Primary 내부 geographic anchor와 측정된 글자 크기 유지; 이동 중 후보 변경 0.

[MOVING MARKER]

6.10s (f183). REGIONAL 도착 전 실제 event anchor에 표시; 속도/크기/안전영역 조건으로 결정.

[LOCATION LABEL]

6.40s (f192). Marker 이후 등장하며 측정된 Universal Layout 후보를 유지.

[EVENT TITLE]

9.00s (f270). Camera 정착·Lock 이후에만 등장.

[PERCEPTION WINDOWS]

Primary ≥0.70s; Location ≥1.20s; Title ≥2.60s. Full-title Hold 9.70s (f291) → 12.30s (f369); drift 0.

[LOD CONTINUITY]

PASS. 동일 NE1 원본의 native geographic window만 확장. Resampling/새 DEM/Visual 수정 없음. 승인 CONTINENT/REGIONAL overlap pixel 차이 0; 최종 actual MP4의 source edge 문제 해소.

[LOCAL ADMISSION]

LOCAL_NOT_ADMITTED respected. 승인 REGIONAL Safe Closest에서 정지.

[GENERALIZATION]

Suez-specific hardcode: NO

Synthetic Fixture A: PASS
Synthetic Fixture B: PASS
Synthetic Fixture C: PASS

[VISUAL PROTECTION]

PASS. 기존 Source14/Shader14/GPU Graphic Shader4 보존. 최종 PNG SHA-256 `fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673`로 승인본과 동일.

[TECHNICAL VALIDATION]

PASS: 333
FAIL: 0
ERROR: 0
SKIP: 1

SKIP: RTX4080S 미실행. 전체 Legacy 회귀 미실행.

[DECISION]

REFERENCE_CAMERA_REVEAL_PASS

[VIDEO]

SUEZ_CAMERA_DIRECTOR_V4.mp4

1080×1920 · 30fps · 375frames · 12.5초 · 무음 · Software WebGL2

[CHECKPOINTS]

PRIMARY_START: 01_PRIMARY_START.png
CONTEXT: 02_CONTEXT.png
EVENT_APPROACH: 03_EVENT_APPROACH.png
MARKER_GUIDE: 04_MARKER_GUIDE.png
REGIONAL_LOCK: 05_REGIONAL_LOCK.png
EVENT_TITLE: 06_EVENT_TITLE.png
FINAL_HOLD: 07_FINAL_HOLD.png

[NEXT]

USER VIDEO REVIEW REQUIRED

반복: 2회. Iteration1에서 native context edge 확인, Iteration2에서 동일 원본의 geographic coverage window 보완. Camera/Reveal/Layout Plan은 두 반복 간 byte 동일합니다. 초기 숫자 비교 Harness4FAIL 및 첫 Visual FAIL 기록은 삭제하지 않았습니다. Container/gCube/RTX4080S/Event/TTS 실행 없음.
