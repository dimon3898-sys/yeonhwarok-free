# 기존 고급 5초 Candidate의 실제 실행 경로

조사 범위: 기존 Git blob·코드·캡처 receipt의 읽기 전용 추적. 이 문서 자체는 영상을 새로 디코딩하거나 NVIDIA를 실행한 증거가 아니다. 실제 영상 비교는 별도 미디어 검증 보고서를 따른다.

## 무엇을 확인했는가

이전 `65416` 계열과 그 다음 전선 강조 수정본 `65422`는 원본 MP4와 150프레임 실행 receipt가 함께 존재한다. 단순히 파일명에 “고급”이 있다는 이유로 선택하지 않았다. `65422`는 그 계보에서 마지막으로 전체 150프레임이 기록된 고급 5초 Candidate다. 사용자가 이를 단일 최상급 영상으로 선정·최종 승인했다는 기계 검증 가능한 기록은 발견하지 못했다.

| 항목 | 65416 | 65422 / moving-frontier glow fix |
| --- | --- | --- |
| 실제 렌더 소스 | `61bdae3d16472d6926bf9cf3d20c78513d826579` | `2c097df2d02432a3f9ae4dae5d714dbc9eacd434` |
| 보존 보고서 스냅샷 | `8e2b994755330907ceed9b9bfcc922e9b113138d` | `45af879d7417abba58e9ebd59d8e6630a785ac28` |
| Scene SHA-256 | `73d5ab5bd41e91866227a9174af64c219c46dc001bd570bd7f854c153e1dc09b` | `aac147932d687f065469c224dbe2a02494f17c01a9be87383e771ada3f275159` |
| MP4 SHA-256 | `4f1b676baef6a4ba6fefbfd58a5d6b2e235fb57ada7d11cfd2baf827ec79f12e` | `f3de1bdf9244171a47c6e5eccca6aae1370f58d8bf4721a7658b6bca2eed2ef6` |
| 실제 backend | SwiftShader | SwiftShader |
| 실제 생성 컨테이너 digest | UNKNOWN: source checkout 실행 | UNKNOWN: source checkout 실행 |
| 판정 | 기술 PASS / 품질 NEEDS_REWORK | 기술 PASS / 전선 강조 IMPROVED |
| 사용자 영상 최종 승인 | receipt의 `false` | receipt의 `false` |

`45af879`는 저장된 원본 계보를 참조하는 패키징 기준 커밋이다. 실제 65422 렌더 소스 `2c097df`와 혼동하면 안 된다. 이후 GPU 이미지에 `45af879` 파일이 포함된 사실은 그 이미지가 이 MP4를 생성했다는 증거가 아니다.

## 65422 실행 그래프

```text
사전 작성·저장된 MAP_ENGINE_UNIT_SCENE_V4
  + REGIONAL/CONTINENT/native Scene/camera-plan/input-manifest
  + 기존 FACT_BASED_VISUAL_GRADE admission
→ Node render_proof.mjs --source-commit=2c097df…
→ 모든 렌더 입력의 Git 원본 byte·SHA 확인
→ openQualityRuntime(VISUAL_REFERENCE_STUDY)
→ 기존 V5 serve.py loopback 입력/모듈 서버
→ Chromium WebGL2, ANGLE SwiftShader
→ compileTerritoryControlPlan(controlIntent)
→ compileReferenceCameraTrack(base V5, frame176, authored 5s keyframes)
→ createMapEngineUnitGpuAdapterV4
    → 원본 createMapInfographicRenderer: GIS/coverage/projection
    → createReferenceTerrainMaterialPassV4: 원본 NE1 색·구운 지형 음영/바다 재질
    → createTerritoryControlPass: 상호 보완하는 두 세력 점령 색상
    → createControlFrontierLightPassV3: 실제 scalar 경계, 밝은 core/금빛 halo
    → createReferencePresentationPass: 화면·지도 좌표가 일치하는 roll/overscan
    → createNationalUnitBadgeOverlay: caller Scene의 기존 8개 국기 표식
→ frame 0…149 drawFrame / readPixels / PNG·카메라·제어 상태 hash
→ 기존 FFmpeg libx264, CRF16, 30fps, 150 frames, yuv420p, 무음
→ 원본 MP4·5개 체크포인트·receipt
```

이 캡처에서 Studio 프롬프트 parser와 Planner는 **실행 시작점이 아니다**. 미리 컴파일된 Planner 입력을 로드한다. 경로에 `planner_runtime.mjs`를 import하는 것은 경로·JSON·해시 도우미 재사용이며, 자유 프롬프트 기획을 실행했다는 뜻이 아니다. runtime module inventory에 Area/Flow/Event/Planner가 나열돼 있는 것 역시 각 기능의 실제 draw 증거가 아니다.

## 실행 단계별 정확한 코드 근거

아래 세 파일은 현재 보존본이 렌더 소스 `2c097df`의 Git bytes와 일치함을 확인했다. SHA 전체는 `OLD_CANDIDATE_PROVENANCE.json`에 있다.

| 단계 | 원본 코드 위치 | 실제 의미 |
| --- | --- | --- |
| 시작·source binding | `recovery/moving-frontier-glow-fix-v1/render_proof.mjs:10`, `:45` | 명시된 immutable source commit과 각 입력을 비교한다. |
| Scene 선택·잠금 | `recovery/moving-frontier-glow-fix-v1/reference_runtime.mjs:45`, `:55` | 새 Scene은 원본 map-engine Scene과 frontierProfile 이외 모든 필드가 같아야 한다. |
| 기존 서버 | `reference_runtime.mjs:99` | `recovery/v5/serve.py`를 실제 지정 입력으로 시작한다. |
| 실제 backend | `reference_runtime.mjs:117`, `:152` | Chromium에 SwiftShader를 명시하고 실제 GL backend 문자열을 확인한다. NVIDIA 결과가 아니다. |
| compile·factory 선택 | `reference_runtime.mjs:131`, `:138` | TerritoryControl·ReferenceCameraTrack을 컴파일하고 V4 확장 factory를 실제 호출한다. |
| native/GIS 재사용 | `web/map_infographic_v1/map_engine_unit_gpu_adapter_v4.mjs:123` | 기존 renderer factory 하나를 만든다. |
| 확장 인스턴스화 | `map_engine_unit_gpu_adapter_v4.mjs:127` | terrain V4, territory, frontier V3, presentation, national badges를 순서대로 만든다. |
| 카메라·레이어 실행 | `map_engine_unit_gpu_adapter_v4.mjs:157`, `:167`, `:170` | 매 프레임 실제 bounds 갱신. Native 기본 foreground/DEM은 명시적으로 꺼지고 확장 재질·점령·전선·roll·표식이 그려진다. |
| 전선의 실제 재질 참조 | `map_engine_unit_gpu_adapter_v4.mjs:174` | frontier가 `terrain.outputTexture`를 받는다. 완성 화면 위 이미지 덧씌우기가 아니다. |
| 픽셀 캡처 | `reference_runtime.mjs:145`, `render_proof.mjs:107` | drawFrame 뒤 readPixels·PNG SHA를 기록한다. |
| 인코딩 | `render_proof.mjs:137` | 실제 FFmpeg argv가 receipt에 보존된다. |

원본 ReferenceCameraTrack은 `reference_camera_adapter_v1.mjs:67`에서 V5의 실제 frame176 admission을 읽은 뒤, caller가 제공한 5초 keyframe을 별도 C1 트랙으로 평가한다(`:101`). 이 5초 카메라 트랙은 나중의 80초 역사 Scene에서 자동으로 추출된 구간이 아니다.

## 기존 고급 기능의 정확한 성격

| 기능 | 이전 65422 상태와 근거 | 그대로 역사 영상에 옮길 수 없는 부분 |
| --- | --- | --- |
| 두 세력 영토 색상 | `TERRAIN_READABLE_ORANGE_PURPLE_V4`, 보완적 scalar control; 실제 모든 프레임 diagnostics | 경계 keyframe 자체는 현대 가상 시나리오다. 역사 점령 자료로 재해석하면 안 된다. |
| 움직이는 전선 core/halo | `MOVING_FRONTIER_GLOW_FIX_V1`: 중심 2.5px, sigma3.5/support10, actual terrain texture; 전체 캡처 diagnostics | 역사 점령 경계가 확보돼야 동일한 소유권 계약으로 적용할 수 있다. |
| 카메라 추적·회전·확대 | 5개의 명시적 bounds/roll keyframe, 약 11°→5°; actual frame receipts | 기존 80초 카메라의 상태를 버리고 이 좌표를 사용하면 다른 Scene으로 바뀐다. |
| 지형·바다 | NE1 baked relief source SHA `49127186…143a`, terrain V4/ocean V4 실제 실행 | 당시 ASTRA DEM/GEBCO/BMNG가 적용된 영상은 아니다. 물리 DEM 조명으로 주장하지 않는다. |
| 국가별 표식 | ROK/US50-star/DPRK/PRC/현대 러시아 삼색기, 8개 caller-owned 표식 | 실제 한국전쟁 시기별 부대 위치·참전 게이트가 아니다. 역사 자료 없이 위치를 옮기면 안 된다. |
| native 제목·라벨 | 새 Scene이 optional foreground를 꺼서 written words 0 | 역사적 불확실성 표기 등 다른 Scene의 정보를 묵시적으로 제거하면 안 된다. |
| Flow/Event/Planner | 파일 inventory 존재, 이 캡처의 해당 효과 실행은 증명되지 않음 | 파일 포함·import closure를 기능 APPLIED로 집계하면 안 된다. |
| SFX | 원본 `audio:false`, MP4의 audio stream 없음 | 이전 고급 5초의 클릭 음원을 재사용했다는 주장은 근거 없다. |

## 후속 F / Reference V2 이미지와의 구분

| 후속 후보 | 실제 소스·이미지 | 확인된 출력 근거 | 확인되지 않은 것 |
| --- | --- | --- | --- |
| Visual Quality F | source `17393dd6…`; digest `sha256:92698c51b718a051c9ccf48fc31c2755962038854119f5b572d5ce11e72086ae` | CI38821837659, 실제 software draw/readPixels 10회·PNG8장; ASTRA 거리 경계·영토 opacity·Scene 카메라 비교 | 이 감사 자료는 전체 150프레임 MP4나 실제 NVIDIA 사용자 승인을 제공하지 않는다. |
| Reference Visual V2 | source `e9feafc7…`; digest `sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5` | CI38831714161, main12+unit2 selected draws; gained-only 색상·source grade·white/front/domain gold·unit scale·camera hold | 전체 150프레임 software movie나 NVIDIA MP4 품질 승인이 아니다. |

Reference V2의 실제 선택 경로는 `ref2_runtime.mjs:71`의 Quality F plan → `ref2_adapter.mjs:30`의 source/territory/frontier profile 설정 → `:33`의 기존 Quality/ASTRA boot다. `ref2_adapter.mjs:36`과 `:45`는 실제 선택된 factory diagnostics를 반환한다. 이는 old65422를 나중에 새 이미지가 생성했다는 증거로 소급 사용할 수 없다.

## 원인 판정 시 지켜야 할 경계

1. old65422의 V4 factory 호출을 확인했으므로 “기존 renderer가 전혀 사용되지 않았다”는 일반화는 틀리다. 이전·이후 경로에서 같은 base renderer를 써도 **scene-owned 확장 factory, complementary control source, 카메라 presentation, national unit Scene** 선택은 다를 수 있다.
2. old65422의 현대 가상 경계와 표식 좌표를 한국전쟁 역사 Scene에 대입해 모양만 되살리는 것은 안전한 연결 수정이 아니다.
3. 원본 receipt가 `userVideoApproved:false`인 상태를 기술 PASS로 뒤집어 사용자 최종 승인처럼 보고하지 않는다.
4. 새 결과 `66461`의 실제 생성 job·source·image·Scene·pixels 확인은 별도 신규 provenance와 대조한다. 이 문서만으로 새 결과의 경로나 원인을 추측해 확정하지 않는다.

원본 근거의 immutable URL, 정확한 source/asset/Scene SHA와 known unknowns는 같은 디렉터리의 `OLD_CANDIDATE_PROVENANCE.json`에 저장했다. 원본 파일·FINAL·Candidate·데이터는 변경하지 않았다.
