# v017 — Second event + adaptive wide camera QA

24초, 30fps, 720프레임. 실제 gcube Workload는 실행하지 않았습니다.

## 휴대폰 입력

이미지: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v017-second-event`

기존 입력 화면에서 수에즈 주제, **24초**, HIGH, 기존 기본 REFERENCE_MASTER를 사용합니다. **QA 체크는 해제**합니다. 기존 UI의 QA 12~15초 제한 및 화면 디자인을 수정하지 않기 위한 입력 방식입니다. 이 이미지의 정확히 24초 요청만 서버에서 `SECOND_EVENT_ADAPTIVE_WIDE_TEST`, `qa_mode=true`로 명시적으로 생성합니다. 기존 FAST_PLUS_LEGACY/LEGACY 요청, 12초/15초 프리셋은 기존 동작을 유지합니다.

## Camera timeline (end exclusive)

| State | Frames | Seconds |
|---|---|---|
| EVENT1_WIDE | 0–60 | 0–2 |
| EVENT1_LOCATION | 60–90 | 2–3 |
| EVENT1_ZOOM_IN | 90–150 | 3–5 |
| EVENT1_VIEW | 150–180 | 5–6 |
| EVENT1_HOLD | 180–330 | 6–11 |
| EVENT1_RESOLVED | 330–360 | 11–12 |
| ZOOM_OUT | 360–420 | 12–14 |
| ADAPTIVE_WIDE | 420–450 | 14–15 |
| EVENT2_LOCATION | 450–495 | 15–16.5 |
| EVENT2_ZOOM_IN | 495–585 | 16.5–19.5 |
| EVENT2_VIEW | 585–615 | 19.5–20.5 |
| EVENT2_HOLD | 615–720 | 20.5–24 |
| END | 720 | 24 |

첫 360프레임 카메라 위치·quaternion·FOV는 v016과 정확히 동일합니다. Suez CLOSED 6초, OPEN 11초의 기존 표시와 기존 사운드 2/6초를 유지합니다. 축소 도착 구도만 두 위치의 지리 관계를 담는 최소 안전영역 구도로 교체했습니다. 둘째 사건 해결·둘째 축소는 없습니다.

## Adaptive framing

기존 실제 계획의 Suez GIS(32.382202E,30.318359N)와 검증된 Singapore GIS(103.853875E,1.294979N) 사용. 두 지점과 연결 great-circle 33표본의 구면 지평선 가시성 및 실제 9:16 perspective projection을 검사한 후 이분 탐색으로 가장 가까운 north-up midpoint framing을 선택합니다. 단순 거리 threshold로 카메라 거리를 선택하지 않습니다.

CONTINENT_WIDE, 위치간 거리 8,161.966km. 카메라 거리 중심에서 2.879272259R, 지표 높이 1.879272259R, FOV64°. 목표 71.136069217E,19.202159088N. 화면좌표는 좌상단(0,0), 우하단(1,1): Suez(0.130000002,0.401666860), Singapore(0.869999998,0.598333140). 안전영역 x[.13,.87], y[.12,.82]에 모두 들어옵니다. 지구 원반 폭은 화면폭 1.054배로 일부 잘리며, 지구 전체 고정 구도가 아닙니다.

서울→도쿄와 프랑스→독일은 REGIONAL_WIDE; London→Sydney는 WORLD_WIDE로 계산했습니다. 서로 같은 거리라도 수평/수직 geographic span에 따라 필요한 framing 거리가 달라지는 검증도 포함합니다.

## Scope and evidence

카메라 전용 preset, native adapter, scoped camera QC만 추가했습니다. 기존 technical QC의 black frame, decode, texture, WebGL, clipping, format, audio 실패는 계속 차단합니다. 의도된 단일/두 사건 HOLD에 맞지 않는 기존 narrative retention 실패만 이 정확한 테스트 preset에서 적용하지 않습니다. `production_policy_not_applicable`에 원래 결과를 보존합니다.

기존 GPU/proxy/ZIP/checkpoint/asset/JPEG/FFmpeg/audio/redaction 소스 및 v015/v016 카메라는 byte/hash 동일합니다. 새 Singapore 라벨 때문에 기존 shader city-focus 슬롯이 바뀌지 않도록 원래 Suez/CLOSED/OPEN 순서를 유지합니다. 텍스트·조명 디자인을 새로 변경하지 않았습니다. 웹 UI/PWA는 수정하지 않았습니다.

SCENE_PLAN.json은 검증에 실제 사용한 계획이고 CAMERA_PREFLIGHT.json은 실제 Three.js camera math 및 production collect-all 결과입니다. SYNTHETIC_QC.json은 CPU test-pattern media의 encoder/concat/audio/QC 결과입니다. 이 결과들은 실제 GPU geographic pixels 검증을 뜻하지 않습니다. 다음 승인된 RTX4080S 실행에서만 자연스러운 축소, Singapore 확대, 라벨 판독과 확대 후 고정을 최종 확인할 수 있습니다.

실제 실행의 기존 Diagnostic ZIP에 전체 Scene JSON과 매 프레임 cameraState/cameraFrame/position/quaternion/FOV가 그대로 보존됩니다. 결과 MP4와 ZIP 다운로드 후 Workload를 중지합니다. 이번 개발에서 실제 Workload의 실행·설정 변경·결제는 하지 않았습니다.

## Final published validation

Source revision: `d654c61397a68abc37de15ed005ea0b5ae36b3ff`. GHCR digest: `sha256:088a6fd11b1d4677e884a50f09b84f453ca875e9637481b634de24fc269be3dc`.

[CI run](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37752955269): core643 + proxy/GPU206 + diagnostic31 =880 PASS,0 FAIL,0 SKIP. Installed packages/assets69, old12/15camera admission, new24camera/codec/audio/QC, old direction/reference/media/checkpoint retry, owner login/health/61-second persistence, GPU-required fail-closed boot and anonymous public pull PASS. Anonymous registry revision/config/digest independently verified. Actual GPU render remains NOT_RUN; no gcube actions performed.
