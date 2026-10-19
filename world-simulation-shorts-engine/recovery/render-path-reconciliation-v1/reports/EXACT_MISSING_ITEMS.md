# 실제 누락 항목과 재사용 가능한 대안

범위: 151개 감사 기능 / 원래 미연결 53개. 기존 판정은 **SUPPORTING 104 · BLOCKED 18 · UNVERIFIED 14 · 해당 없음 15**, APPLIED **0**을 그대로 유지한다. SUPPORTING은 자료·계약·소비자 지원의 의미이며 사용자 영상에 고급 연출이 적용됐다는 뜻이 아니다. 원래 151개 ID와 8개 축, 원래 미연결 53개 구성은 `OLD_VS_NEW_FEATURE_MATRIX.json/CSV`에 보존했다. CPU 검사를 NVIDIA 증거로 승격하지 않았다.

## 1. 먼저 구별해야 할 세 영상

- 과거 고급 5초 65422 연관 영상은 SHA `f3de1bdf9244171a47c6e5eccca6aae1370f58d8bf4721a7658b6bca2eed2ef6`, 실제 렌더 소스 `2c097df2d02432a3f9ae4dae5d714dbc9eacd434`이다. 소스 체크아웃 + SwiftShader 실행이다. 실제 생성 컨테이너 digest는 원래 증거에 없다. 역사 한국전쟁 장면이 아니라 명시적 현대 가상 시나리오다.
- 확인 가능한 직전 소프트웨어 5초는 SHA `3899d87cbacfbb54f9a094ac0a37755b7a3dd5ba941634e37f4555d01de83f66`, 소스 `e23613195c356ad53874030f983a30a0e30d639f`이다. 이것도 소스 체크아웃 + SwiftShader 실행이다. 원래 80초 Scene의 전역 `[1400,1550)` 프레임이며 완료 V2 이미지 `a956…`나 나중 빌드 이미지 `7d45…`의 컨테이너에서 제작한 영상으로 표시하지 않는다.
- 사용자 파일명 `66461.mp4`는 현재 실제 파일·SHA·작업 연결이 없다. 위 3899 영상과 같다고 단정하지 않는다. 이 파일에 대한 원인 귀속은 UNKNOWN이다.

정확한 UTC·원본 명령의 확인 범위·소스/Scene/Asset SHA는 `OLD_CANDIDATE_PROVENANCE.json`, `NEW_OUTPUT_PROVENANCE.json`을 따른다. 원본 66430 MP4도 없어 실제 전체 80초 결과와 직접 비교했다고 주장하지 않는다.

## 2. 양측 점령장 / Scalar 영토: 실제 역사 자료 0개

기존 `SOURCE_DATA_CATALOG.json`은 검증 역할이 GEOMETRY인 20개 기록과 기존 4파일 자료 권한을 유지한다. package-owned `EXTENSION_SOURCES.json`의 신규 기록은 0개다. 현재 입력의 `overnight.visualExtensions.scalarTerritory`도 `null`이다. 고급 소비자가 파일로 존재하더라도 이 입력에서는 실행되지 않는 것이 정상이다.

실제로 필요한 기록은 다음과 같다.

| 계약 | 정확히 필요한 필드 | 현재 상태 |
|---|---|---|
| 검증 카탈로그 기록 | `sourceId`, `sha256`, `role=SCALAR_CONTROL_PLAN`, `verificationStatus=VERIFIED`, `payload` | 0개 |
| Scalar payload | `schema=WORLD_ENGINE_SCALAR_CONTROL_SOURCE_V1`, `plan`, `territoryStyle`, `frontierStyle`, `nativeDomain` | 검증된 역사 payload 없음 |
| `plan.intent` | 명시적 `semantic_mode=FACT_BASED_VISUAL_CONTROL`, `source`, 원본 `domain`, 서로 다른 `factions.winner/loser`, `longitudinal_knots`, `base_boundary_latitudes`, `boundary_keyframes`, `advance_direction`, `start_frame`, `total_frames`, `fps`, `interpolation` | 현재 근사 부분 전선만으로 채울 수 없음 |
| 시간·공간 근거 | 양측 세력 ID/역할, 자료 기준 날짜, 실제 통제 영역 의미, 닫힌 도메인, 날짜별 경계 값, 출처·라이선스·원본 SHA·불확실성 | 완전한 양측 점령장/일별 관측 자료 없음 |

코드: `universal-overnight-v3/visual_extensions.mjs:85–111`; `territory_control_adapter_v1.mjs:61–108,120–132`. 기존 Scalar 계약은 단일 도메인 안의 보완적 소유권과 단방향 위도 진행을 요구한다. 임의 전쟁의 모든 왕복 전선 변화에 그대로 맞는다고 주장하지 않는다.

안전한 기존 대안은 5단계 단순화된 ROK/UN held-core 영역과 8개 공식 근사·부분 전선의 고정 표시다. 기존 정책은 공식 부분 선이 표시되는 구간에서 근거 없는 영역을 억제하고, 관측되지 않은 날짜의 경계를 보간하지 않는다. 부분 전선을 해안까지 임의 연장·폐합해 적군 점령 다각형을 만들거나 held-core의 나머지를 적군 영토로 바꾸지 않는다. 근사·부분·도식 자격 표시도 보존한다.

## 3. Scalar 고급 전선의 네이티브 합성 계약: 조건부 미완료

기존 고급 소비자는 현재 프레임의 실제 지형 텍스처를 조명에 사용하고, 실제 도메인별 coverage로 외곽 빛을 제한한다. 다음이 추가로 필요하다.

| 공급 계약 | 필요한 실제 값 | 현재 알려진 상태 |
|---|---|---|
| 부모 슬롯 | `parentGeographicFrontPresent=false`, `parentTerritoryFillPresent=false` | 역사 부모 Area/front가 현재 장면을 이미 그리므로 중복 합성 금지 조건과 충돌 |
| 원본 경계 | `nativeBoundarySourceVerified=true`, `boundarySegments`, `internalBoundarySegments` | 브리지는 `frame/native/boundarySegments`만 명시적으로 publish |
| 지형 스냅샷 | `actualTerrainSnapshot.frame===frame`, `source=ACTUAL_CURRENT_NATIVE_TERRAIN`, 실제 `texture` | 현재 publish된 최상위 슬롯에 없음 |
| 역할별 coverage | `nativeRoleCoverage.frame===frame`, 검증된 `nativeDomain` | 현재 publish된 최상위 슬롯에 없음 |
| 프레젠테이션 | 실제 `presentationScale`, 원본 projection, safe area, 기존 graphic reservations | 현행 wrapper는 scale1, 회전용 계약 아님 |

코드: `universal-integration-completion-v2/production_camera_bridge.mjs:21–25`; `frame_context.mjs:9–14`; `universal-overnight-v3/browser_adapter.mjs:30–38`; `visual_extensions.mjs:138–145,204–226`.

이것은 **고급 Scalar를 활성화하려 할 경우의 실제 계약 공백**이다. 현재 Scalar 선택이 null이므로 이 슬롯의 부재가 3899 출력에서 예외를 일으켰다고 말하지 않는다. 가짜 texture, 전체 framebuffer 스크린샷, 추정 coverage, 중복 부모 전선을 공급해 검사를 통과시키면 안 된다. 실제 지형 소유자가 공개하는 확장 슬롯과 적법한 source-bound 양측 점령 자료가 준비돼야 한다. 기존 보호 렌더러를 무검증 변경하지 않는다.

현재 역사 경로의 `frontier_extension.mjs:88–108`은 기존 Area V3 contour의 alpha 반응이다. `terrainLightingConnected=false`와 `SCALAR_TERRITORY_AND_CURRENT_TERRAIN_TEXTURE_CONTRACT_REQUIRED`가 명시돼 있다. 이것을 과거 고급 `createControlFrontierLightPassV3`의 terrain-light/core/halo 실행과 같은 기능으로 표시하지 않는다.

## 4. 국가별 군대 및 이동: 실제 역사 위치·경로 0개

필요한 national 기록은 `role=NATIONAL_UNIT_SCENE`, `verificationStatus=VERIFIED`, `payload.schema=WORLD_ENGINE_NATIONAL_UNIT_SCENE_SOURCE_V1`와 `scenePlan/baseCameraPlan/currentNativeFrame/safeArea`다. `scenePlan.combatProfile`에는 실제 `units`와 `profiles`가 있어야 한다.

- 각 unit의 `id`, `profile_id`, 실제 역할, 날짜/참전 범위의 출처가 필요하다.
- 2400프레임 전역 계약과 일치하는 검증된 `anchor_frames`, `size_frames`, `rotation_frames`가 필요하다. 원래 graphic validator가 숫자 배열을 받아 준다는 사실은 역사 사실 검증이 아니다.
- 각 profile의 `country_id`, 원본 국기 geometry, 시대에 맞는 국기·역할이 필요하다. 국기와 국가 참전일만으로 부대 위치를 만들지 않는다.
- Flow는 실제 `route_geometry`, 출발/도착 anchor, 방향, actor/object role, 시작·이동·hold 시간과 출처·SHA, 도착 사건의 의미가 추가로 필요하다.

코드: `visual_extensions.mjs:113–123`; `national_unit_badge_v1.mjs:34–62`; 기존 기능별 Flow 필드/출처는 151행 matrix의 `inputContract`, `dependencies`, `auditEvidencePreserved`에 있다.

현재 `nationalUnits=null`, `completion.eventFlow.flows=[]`, `events=[]`, `areas=[]`이다. 직전 실제 150프레임도 national/scalar/Flow/추가 Event 활성화가 각각 0이다. 기존 지리 marker·지명은 군대 actor가 아니다. 기존 counterfactual 65422의 8개 unit 및 현대 국기를 역사 장면에 옮기지 않는다.

## 5. 카메라·전선의 실질 이동과 표본 구간

기존 소스는 전역 `[1400,1550)`를 보존했고 프레임/Area/카메라를 0부터 새로 초기화하지 않았다. 실제 ASTRA/native draw가 150프레임 실행됐다. 따라서 “옛 렌더러가 전혀 호출되지 않았다”, “무조건 basic V4로 fallback했다”, “preview가 시간을 reset했다”는 주장은 현재 증거로 성립하지 않는다.

그러나 해당 구간의 48개 수치상 서로 다른 camera bounds는 화면 기준 순이동 약 **0.6021px**에 불과하다. 실제 V5 turn 0, 유의미한 zoom/roll 0, 비교 가능한 실제 전선 좌표 변화 0이다. source schedule의 상태 이름 변화·alpha crossfade·부동소수점 차이는 역동적인 카메라·움직이는 실제 전선의 증거가 아니다. 원래 80초 Scene 자체가 날짜별 부분 전선 고정 표시와 도식 held-core 전환을 사용한다.

과거 5초의 회전은 별도 `reference_camera_adapter_v1` 및 일관된 overscan·지도 projection 변환이다. 완료 화면 전체 회전으로 대체하면 label/marker/coverage와 어긋난다. 기존 V5 코어를 바꾸지 않고 안전한 확장 슬롯/Scene 계약을 확보해야 한다. post-arrival Detail도 별도 실제 framing·safe-area 시각 admission이 남아 있다. 측량급 정밀도가 부족해서 막은 것이 아니다.

## 6. 지도·자료 범위·텍스트·SFX

- 기존 ASTRA 세 역할은 실제 소프트웨어 upload/draw 진단으로 150프레임 관측됐다. “ASTRA가 연결되지 않아 고급 표현이 전부 사라졌다”로 단정하지 않는다. 다만 지역 샘플 밖의 기존 재질 fallback과 NoData는 유지하며 전 세계 동일한 고해상도 지원이라고 표시하지 않는다. 개별 역할 ablation·해안 seam 품질·실제 NVIDIA 품질은 별도 검증이다.
- 65422는 Scene에서 원래 foreground/labels/title을 명시적으로 숨긴 no-text 시나리오다. 기존 역사 Preview는 도식·날짜·제목과 보호 reservation을 유지한다. 두 경로의 화면 구성이 다르며, 현재 역사 자료 자격 표시를 고급 장면처럼 보이게 하려고 삭제하면 안 된다.
- 65422 원본은 무음이다. 직전 3899 Preview는 원래 CC0 이벤트 1개를 기존 mixer로 잘라 합성했다. 5초·48kHz·240000 유효 sample과 video/PTS 보존은 실제 검증됐지만 reference의 조밀한 click rhythm이 적용됐다는 뜻이 아니다. 없는 사건 cue를 임의 생성하거나 reference 음원을 복제하지 않는다.
- 66461 실제 파일/작업 mapping과 66430 실제 MP4는 미확보다. 가짜 JobID·OCI digest·Scene hash로 채우지 않는다. 확보 시 공개 파일 SHA와 원래 receipt를 대조하는 것이 최소 추가 확인이다.

## 7. 이번 작업의 연결 오류 수정과 누락 자료를 섞지 않기

입력 직렬화·실제 엔트리포인트 선택·하드웨어 실패 처리·구간 선택 점수 같은 **재현 가능한 새 코드 결함**은 별도 수리·집중 테스트 증거로 기록한다. 이 표는 수리 이전의 확인 가능한 기존 3899 출력과 과거 65422를 비교한다. 새 후보 소스·이미지·추가 출력이 생기면 별도 receipt로 추가하고 기존 영상을 새 소스의 실행 증거로 다시 이름 붙이지 않는다.

자료가 0개인 역사 Scalar/군대 기능은 코드를 더 import하거나 영상 위에 효과를 덮는 것으로 완료할 수 없다. 기존 source-bound 대안으로 가능한 범위는 계속 진행하되, 자료가 없는 기능은 BLOCKED를 유지한다. 현재 32개 잔여 ID의 전체 목록은 `RECONCILED_REMAINING_FEATURES.json`에 있다.
