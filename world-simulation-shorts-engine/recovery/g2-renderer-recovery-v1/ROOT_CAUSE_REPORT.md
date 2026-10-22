# ROOT_CAUSE_REPORT

기준 `0069e9af1c0888843289d312d86bad29ac26007e`, 새 분기 `development/g2-renderer-recovery-20261022`.
**G2 NEEDS_REWORK. PHASE 2가 실패했으므로 새 180프레임 Studio 제작은 실행하지 않았다.**

## 확인한 원인과 복구

| 현상 | 실제 증거 | 판정·수정 |
|---|---|---|
| 수직·직사각형 재질 경계 | 기존 MP4 전체 180프레임에서 첫 프레임부터 지속. 104°E·7°N의 실제 소스 경계를 카메라 투영한 위치와 일치 | 서로 다른 스타일의 지역 NE1·global RGB 전환이 원인 |
| 원본 shader의 소스 선택 | 보호된 `web/map_infographic_v1/renderer.mjs:143–151`의 `step` 기반 `inside`와 `mix(globalTerrain, terrain, inside)`. `:187`, `:206`의 baked 처리도 inside에 따라 달라짐 | shader는 수정하지 않음. 새 Plan에 실제 같은 NE1 원본의 넓은 native crop을 지정 |
| LOD/소스 입장 | 기존 `universal-source-pipeline-v2/native_runtime.mjs`는 LOD 1을 사용하며 기존 raster 밖에서 다른 스타일로 넘어갔음 | 새 단일 스타일 설정과 사전검사로 원래 180개 카메라 전부가 실제 crop 안에 native pixel 여유를 갖도록 검증 |
| 타일 로딩 누락·UV·투영·알파 오류 후보 | 기존 두 실제 이미지가 모두 표시되며 경계가 source extent와 정확히 일치. 영역을 꺼도 동일 경계. 기존 overlay는 같은 factory.screen 사용 | 이번 재질 경계의 원인으로 입증되지 않음. 무관한 loader·좌표·shader 수정 없음 |
| 영역 계단 | 원본 DEMO domain의 105정점·104변 전부가 0.25도 격자/축 정렬. 화면에서 약 9~15px | 렌더 해상도 오류가 아닌 작성된 합성 데이터의 형태. 원본 geometry를 그대로 보존하고 정밀도를 과장하지 않음 |

`reports/MATERIAL_AUDIT.json`, `DOMAIN_AUDIT.json`, `BASELINE_VIDEO_AUDIT.json`, `BASELINE_FRAME_AUDIT.csv`에 코드 위치·원본 수치·전체 프레임 증거가 있다. 기존 영상의 수직 RGB jump는 84.33~85.75, 수평은 8.00~9.08이다. 대조 구간 P99 12.13375/0.75는 새 결과에 맞춰 변경하지 않았다.

## 실제 데이터 복구

기존 출처 기록에 고정된 Natural Earth NE1 원본은 21600×10800, EPSG:4326, 1 arc-minute cartographic RGB, Public Domain이다. DEM 또는 현재 위성 영상으로 표시하지 않는다.

- 원본 699,969,932 bytes SHA: `b47bdddd1336b07f498c50eba5d70699ec57dd726a7ea0a85d2dca243236c9eb`.
- 첫 전체 요청은 응답 대기에서 타임아웃. 저장소 Git blob은 실제 raster가 아닌 134-byte LFS pointer임을 확인했다. 둘 다 원본 확보 성공으로 처리하지 않았다.
- 공식 raw URL이 HTTP Range 206을 지원함을 확인한 뒤 제한된 3개 동시 요청으로 한 원본을 복구했다. 각 Content-Range와 전체 SHA를 검사했다. 인증·유료 LFS·유료 API를 사용하지 않았다.
- 기존 지역 PNG의 decoded RGB와 이 원본의 대응 window가 완전히 일치했다. TFW·PRJ·README·권리 원문 SHA도 보존했다.
- 새 main crop 1817×2776, 원본 pixel box `[16371,2812,18188,5588]`, SHA `787579415aad212801251ddaaa1ee3d2366eebb93a35ba81d276105ef18737fb`.
- 실제 V5의 최소 west는 93°가 아니라 92.99999625696661°다. 전체 카메라 envelope와 8 native-pixel 여유를 포함해 잘랐다. 보간·확대·블러·재색칠·지형 생성 없음.
- `tools/prepare_recovery_plan.mjs`는 기존 Scale compiler로 새 자산의 LOD 메타데이터만 갱신한다. 카메라·GIS·Layout·팔레트·텍스트 등 13개 구성과 모든 source field는 동일하다.

새 helper `terrain_style.py`와 `fixtures/MAP_STYLE.json`이 단일 지도 스타일을 선택한다. 유효 범위 밖·필요 해상도 초과·날짜변경선 wrap·필수 gutter 없는 소스 가장자리는 실행 전에 명시적으로 거부한다. 없는 고도·수심을 만들지 않는다.

## PHASE 1 실제 화면 결과

기존 native runtime·Camera V5·Area V3·Marker·Glyph를 그대로 호출해 f0/f90/f179/f90을 그렸다. GL 오류 0, 같은 f90 raw 해시 일치, 실제 지형 PNG 자산의 HTTP 200·SHA 일치. 세 시점의 화면에서 직사각형 재질 경계가 사라진 것을 육안 확인했다. 이는 **부분 프레임 복구 증거**이며 새 6초 영상 전체 검수 결과가 아니다.

## 새로 확인된 차단 오류

PHASE 2의 Namibia 사막·해안은 4회 실제 draw에 성공했다. Nepal 산악 테스트는 **첫 draw 전에** 기존 measured Layout의 `NO_SAFE_BOUNDARY_CLEAR_LOCATION_PLACEMENT`로 실패했다. `LOCATION_LABEL`의 LEFT/RIGHT/ABOVE/BELOW 후보가 `COUNTRY_NPL` 경계 clearance를 충족하지 못했다.

기존 factory는 나중에 화면에 숨길 label이라도 초기 Layout을 검증한다. 이 입력 프로필과 기존 Layout 계약 사이의 문제가 드러난 것이며, 새로운 NE1 bitmap 손상 또는 GPU 오류로 단정하지 않는다. 실제 실패 기록은 `reports/PHASE2_NEPAL_HIMALAYA_ACTUAL_PROBE.json`에 있다.

사용자 지시의 “각 게이트 실패 시 다음 단계 진행 금지 / 즉시 중단”을 적용했다. 라벨 검사를 끄거나, 기준을 낮추거나, 성공하기 쉬운 지역으로 바꾸거나, 재시도로 실패를 숨기지 않았다. 새 Studio job·MP4·역사 G3·80초·유료 GPU·배포는 실행하지 않았다.

다음 작업에서는 **새 probe/Scene 프로필의 실제 활성 정보와 기존 Layout 입장 조건**을 먼저 대조해야 한다. 필요한 label은 기존 안전 배치 검사를 통과해야 하며, 사용하지 않는 정보의 비활성 계약이 기존 API에서 지원되는지도 확인해야 한다. 보호 Layout을 변경하거나 임의로 실패를 무시하는 해결은 승인하지 않았다.
