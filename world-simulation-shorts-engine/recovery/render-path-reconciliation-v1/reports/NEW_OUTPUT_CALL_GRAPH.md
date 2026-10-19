# 새 5초 출력의 실제 제작 경로

이 문서는 새 조사 보고서이다. 기존 Scene·엔진·영상은 수정하지 않았다. 경로는 `world-simulation-shorts-engine/` 기준이며 아래 줄 번호는 보존된 소스의 실제 위치다.

## 출력 식별과 증명 범위

- 사용자가 부르는 `66461.mp4` 파일 자체와 SHA 대응표는 현재 입력에서 확보되지 않았다. 그 파일의 작업 ID·배포·컨테이너 digest·원본 명령행은 **UNKNOWN**이다.
- 실제 존재·해시 확인한 직전 공개 산출물은 `recovery/universal-overnight-v3/public-review/WORLD_ENGINE_OVERNIGHT_PREVIEW_5S.mp4`, SHA `3899d87cbacfbb54f9a094ac0a37755b7a3dd5ba941634e37f4555d01de83f66`, 2,053,810바이트다. 두 파일이 같다고 추측하지 않는다.
- 이 알려진 산출물은 로컬 소스 체크아웃 `e23613195c356ad53874030f983a30a0e30d639f`, 소스 manifest `ceca8be224e0b7e8ca73a429c7a36217d371fe09308d3829e9ff5b0d67a35fa7`의 실제 Chromium/SwiftShader draw/readPixels로 생성됐다. Studio 작업이나 gCube 배포에서 생성한 것이 아니다.
- 실제 캡처 UTC `2026-10-19T15:20:34.727Z`→`2026-10-19T15:27:18.201Z`, 403.474946초다. 한국 시각으로 10월 20일 00:20:34→00:27:18이다.
- `proof-final/CHECKOUT_PROVENANCE.json:2`와 `:6`은 체크아웃 실행을 명시한다. `proof-final/FINAL_DELIVERY_RECEIPT.json:89`의 `candidateImageExecutionVerified`는 false다.
- `sha256:a956…4886`은 원본 계획의 이미지 바인딩/이전 기반 이미지다. 추후 CI에서 빌드·독립 pull한 `sha256:7d45…a645`는 실행 후보 이미지다. 둘 중 하나에서 이 로컬 MP4를 렌더했다고 주장할 근거는 없다.
- 원본 80초 Plan raw SHA는 `33596c97b433887afb7ced6847d4ef63d099a9b6633546d541890a45c9c6289e`, legacy Scene SHA는 `1b2301864058d3ec4109259057ba17baa44ea165f60467bcbfd7756757cdf4b9`다. `scene-0007` 원본 전체 장면 SHA는 `dd13a3a52395ea329431d0c8d59cfb4fec82cd18c74b5ac2774ee5a970e36a06`다. 원본 2,400프레임 중 **[1400,1550)**만 캡처했다.

## 실제 실행 그래프

```text
PREVIEW_PROFILE.json
  preset VERIFIED_FRONT_V4_80S / V4_ARCHIVAL_80S
  completion camera V5_EVENT_TRACKING + frontier AUTHORED_FRONT_MOTION_V2
  eventFlow events/flows/areas = []
  overnight scalarTerritory/nationalUnits = null
        │
prepare_source_preview.py.prepare
  → 기존 Studio parser/Scene 검증 계약
  → 기존 역사 Plan 선택·검증 (자유 자연어 AI 기획을 새로 실행하지 않음)
  → SUBMISSION / PLAN / INTEGRATION_REQUEST / OVERNIGHT_REQUEST / PREVIEW_REQUEST
        │
free_preview_runner.mjs CLI → runFreePreview
  → capturePreviewWithRuntime (softwareProbe=true)
  → loadOvernightSoftwarePlan
     → native.loadLongRuntimePlan (원본 full plan/scene/native payload/ASTRA 검증)
     → production.extendProductionServerPlan
     → fronts.extendFrontServerPlan
     → extendCompletionServerPlan
        → extendIntegrationServerPlan (기존 Area/Camera factory alias)
     → extendLoadedOvernightPlan (추가 요청/소스 권위 검증)
        │
loopback serve_long.py + Chromium --use-angle=swiftshader
  /universal/long_adapter.mjs → overnight/browser_adapter.mjs
    → /overnight-v3/parent_adapter.mjs → completion/browser_adapter.mjs
      → /completion-v2/parent_adapter.mjs → front-v4/front_adapter.mjs
        ├ createAreaNativeBridge → 기존 V5 native camera/GIS/factory
        ├ createProductionNativeCamera (completion alias)
        │    → createCompletionNativeCamera → 기존 V5 evaluator/layout/redraw API
        ├ ASTRA upload → createReferenceTerrainMaterialPassV4
        ├ createProductionAreaPass (completion/integration aliases)
        │    → 보존된 Area V3 GPU owner + supplied-front motion wrapper
        └ 기존 foreground marker/label owners
      → completion optional Event/Flow/Area owner: empty, no additional pass
    → overnight optional scalar/frontier/national owners: null, no additional pass
        │
각 original globalFrame 1400..1549
  window.longVideoProof.capture(globalFrame)
    → native/GIS coverage + 실제 source-bound camera
    → ASTRA source texture/DEM/bathymetry (valid masks and fallback)
    → source-bound supplied schematic area/front
    → 날짜/출처 qualifier + 기존 native markers/labels
    → completion/overnight wrappers
    → gl.finish → readPixels → RGBA SHA + PNG SHA
        │
captureLongFrames (한 프레임씩) → PNG 000000..000149
  → 기존 longEncodingArgs/originalEncodingArgs → FFmpeg H.264
  → FFprobe + 전체 decode
        │
기존 CC0 SFX mixer → 원본 global audio 구간 정확히 clip
  → 기존 mux/decode/pixel·PTS 비교
  → 최종 5초 MP4 + 체크포인트 + receipts
```

원본 셸의 정확한 argv 문자열은 저장되지 않았다. 실제 엔트리포인트와 재현 인자 계약은 `free_preview_runner.mjs:161–166`, 원본 입력과 SHA는 `PREPARED.json` 및 `PREVIEW_RECEIPT.json`으로 확인했다. 재현할 때는 새 비어 있는 private output 디렉터리에서 동일 `--plan-file`, `--plan-sha256`, `--request-file`, `--overnight-request-file`, `--submission-file`, `--activation-file`, `--activation-sha256`, `--scene-id scene-0007`를 사용해야 한다. 과거 결과 디렉터리를 다시 사용하거나 초기화하면 안 된다.

## 코드 근거

| 단계 | 코드 위치 | 확인한 동작 |
|---|---|---|
| 프리셋 선택 | `recovery/universal-overnight-v3/PREVIEW_PROFILE.json:3`, `:18`, `:34`, `:45` | V4 역사 프리셋, V5 이벤트 추적/기존 전선, 추가 Event/Flow 없음, scalar/national 없음 |
| parser/기존 Scene 재사용 | `recovery/universal-overnight-v3/prepare_source_preview.py:31–44`, `contract_v3.py:66–81` | 기존 Studio 정규화 → parent 계약, 새로운 5초용 Scene 재작성 없음 |
| 실제 소스 합성 | `recovery/universal-overnight-v3/free_preview_runner.mjs:67–95` | 원본 native→production→front→completion 순서, byte hash 확인 |
| 추가 sealed binding | `recovery/universal-overnight-v3/capture_runtime.mjs:24–40`, `runtime_binding.mjs:39–63` | parent를 별칭으로 보존하고 추가 browser adapter만 선택 |
| 실제 software 브라우저 | `recovery/universal-overnight-v3/free_preview_runner.mjs:115–137` | loopback 한정, 실제 Chromium SwiftShader, 실제 diagnostic 검증 |
| parent 호출 | `recovery/universal-overnight-v3/browser_adapter.mjs:18–38` | bootParent 및 원본 draw 이후 선택된 추가 owner만 호출 |
| 추가 Event/Flow | `recovery/universal-integration-completion-v2/browser_adapter.mjs:16–33` | 데이터가 없는 경우 pass 미생성 및 명시적인 empty reason 반환 |
| 실제 native/ASTRA | `recovery/verified-front-data-v4-recovery/front_adapter.mjs:46–71` | 실제 ASTRA bundle, 기존 native bridge, 실제 material factory/area/foreground 생성 |
| 실제 합성 순서 | `recovery/verified-front-data-v4-recovery/front_adapter.mjs:92–142` | native→ASTRA→실제 선택된 전선/영역→출처/날짜→marker; 원본 source 불변 |
| V5 카메라 실행 | `recovery/universal-integration-completion-v2/production_camera_bridge.mjs:16–26`, `camera_extension.mjs:134–176` | 기존 V5 평가기와 native layout/render API 호출; parent-floor와 전 타임라인 안전 범위 유지 |
| 전선 motion | `recovery/universal-integration-completion-v2/frontier_extension.mjs:29–73`, `:94–108` | 동일 ID의 실제 supplied coordinates 변화만 측정, 카메라 이동 제외 |
| 빈 고급 owner | `recovery/universal-overnight-v3/visual_extensions.mjs:125–159` | scalar/national null은 empty pass; 임의 geometry/군대 생성 없음 |
| global time 보호 | `recovery/universal-overnight-v3/preview_capture.mjs:69–86`, `:105–125` | 원본 Plan/Scene equality, 원본 frame을 그대로 capture, 파일 번호만 local 변환 |
| 실제 draw/readback | `recovery/verified-front-data-v4-recovery/front_adapter.mjs:150–151` | drawFrame(globalFrame)→readPixels→RGBA/PNG SHA |
| bounded capture/encode | `recovery/universal-auto-video-v2/long_capture.mjs:63–90`, `recovery/universal-overnight-v3/preview_capture.mjs:139–150` | 프레임 하나씩 저장, 기존 encoder·해상도·fps 유지, FFprobe/전체 decode |
| SFX | `recovery/universal-overnight-v3/preview_audio.py:92–129` | 기존 mixer→원본 global clip→기존 mux. 영상 Scene/timing 변경 없음 |

## 실제 150프레임에서 확인한 활성화

이 표는 모의 factory 테스트가 아니라 보존된 actual `FRAMES.ndjson` 150행을 다시 읽어 집계했다. 공개 보고서에는 원본 로그 전체 대신 안전한 수치·픽셀/소스 해시만 남겼다. `NEW_OUTPUT_PROVENANCE.json`에 프레임별 요약과 원본 로그 해시가 있다.

| 기능 | 실제 결과 | 해석 |
|---|---|---|
| Global time/원본 Scene | 150/150 정확한 1400..1549, reset false | preview 초기화 원인 아님 |
| ASTRA | 150/150, 3개 역할·6개 텍스처, 실제 source grade ON | ASTRA 미호출 아님. DEM 약 0.5°×0.5°, GEBCO 약 2°×2°의 제한된 원본 지원 범위이며 밖은 기존 재질 |
| Area V3 | 150/150 supplied held-core 영역/전선 | 한쪽 allied cyan 계열만 제공. 적대 점령 complement 생성 금지 |
| V5 camera | 150/150 completion V5 실행 | actualV5Turn=false 150개, extent 폭 고정. 48개 수치적 bounds 변화의 순변위는 약 **0.602px**에 불과 |
| archival official-front 선택 | 0/150 | 현재 구간에서는 명시적인 `PRESERVED_SCHEMATIC_CONTEXT` 정책. basic renderer로 조용히 fallback한 것이 아님 |
| moving supplied-front response | wrapper는 실제 실행, 모든 strength=1 | supplied 각 front의 좌표 자체는 고정, 다른 ID snapshot 사이 alpha 전환. 연속 scalar 전선의 이동·정지 감쇠가 아님 |
| terrain-coupled frontier lighting | 0/150 | diagnostic blocker `SCALAR_TERRITORY_AND_CURRENT_TERRAIN_TEXTURE_CONTRACT_REQUIRED` |
| 추가 Event/Flow/Area | 0/150 | 실제 입력 arrays=[], 명시적으로 추가 이벤트 요청 없음 |
| scalar control/frontier V3 | 0/150 | scalarTerritory=null; 코드 import는 실행/픽셀 적용 증거가 아님 |
| 국가별 군대 badge | 0/150 | nationalUnits=null, 검증된 unitPositions=[], 실제 화면은 native 서울 marker/labels |
| Native text/protection | 그대로 실행 | 큰 title/date/qualifier와 보호 마스크가 남아 원형/사각 빈 공간을 만들 수 있음. 공개 문구 제거용 새 profile은 선택되지 않음 |
| SFX | 원본 cue 1개, 유효 48kHz 240,000 samples | 레퍼런스 음원 복제 안 함. 다중 기계식 리듬 데이터가 제공된 것이 아님 |
| NVIDIA/후보 image execution | 미실행 | local SwiftShader 기술 증거이며 NVIDIA 품질 PASS 아님 |

## 확인된 차이와 안전한 수정 지점

1. 고급 기능 파일이 사라진 것이 아니라 **다른 Scene/자료 계약과 소비자 계열을 선택**했다. `REFERENCE_VISUAL_MASTER_V2_F`라는 assetClosure 이름은 reference source 일부를 재사용한다는 뜻이며 scalar 영토·국가 군대·presentation camera가 모두 활성화됐다는 증거가 아니다.
2. `camera_activity.py:177–180`은 임의의 float bounds 변경을 `OBSERVED_MOVING`으로 분류한다. `preview_contract.py:183–195`는 그 pair 수를 최우선 점수로 사용한다. 실제 영상은 0.602px 순이동·실질 확대/회전 없음이므로, **수치 변화와 눈에 보이는 카메라 연출을 혼동하는 선택/보고 결함**이 확인된다. 최소 수정은 새 계층에 pixel-equivalent displacement/zoom/실제 turn 판정을 기록하고 품질 게이트를 엄격히 하는 것이며, 기존 카메라를 다시 설계할 이유는 없다.
3. [1400,1450)는 chapter-08 남하 제목 아래 이전 BUSAN→NORTH_ADVANCE 자료 전환을 보여준다. 이는 원본 source schedule의 carry-in이며 preview reset이 아니다. 새 후보 Scene/구간에서 기존 검증된 올바른 시점만 선택할 수 있지만 과거 Scene을 덮어쓰거나 일별 전선을 만들어 해결하면 안 된다.
4. 양측 점령 영역·국가별 군대·이동 경로가 없는 상태에서 null/empty를 임의 생성으로 채우면 안 된다. 이전 고급 가상 Candidate는 별도의 정확한 Scene/source-bound 실행 경로로 보존·재연결하고, 실제 역사 영상 자료 계약과 분리해야 한다.
5. old-image 미사용·GPU 문제·MP4 encode가 고급 표현 손실의 원인이라는 증거는 없다. 실제 150프레임과 hash는 기존 초기 software run과 bit exact였다. 인코딩/SFX 단계가 효과를 제거했다는 가설도 해당 비교 결과와 맞지 않는다.

이 조사로 새로운 GPU 실행이나 영상 렌더링을 수행하지 않았다. 새 보고서 2개만 작성했다. 정확한 `66461.mp4` 파일 대응이 없으므로 해당 이름의 제작 이력을 확정한 것으로 보고하지 않는다.
