# v004 opt-in 렌더 어댑터 기술 기록

이 문서는 구현 설정과 검증 범위를 기록한다. 최종 MP4의 영상미 평가, 전체 QC 통과 또는 제작 완료를 선언하지 않는다.

## 적용 범위와 보존

`visual_polish.version = "v004"`인 새 Scene에만 `SceneFlatPolishRenderer`를 적용한다. 기존 `SceneFlatRenderer`를 상속하며 기존 Scene JSON, 이벤트 시각, 경로 진행률 및 검증된 GIS 좌표를 유지한다. 기본 생성기 프리셋을 교체하지 않는다.

기존 `web/flat_renderer.js` SHA-256은 `144487d6824a10cedb4c002629620859817d0b0b89e4fdc65d805c6e29c8dde4`, `web/flat_semantics.js`는 `cd023936304a4579f1fe52849c66b47c5e94d69958c714e437b371dce511eedd`로 보존되었다. 새 어댑터 수정 전 초안들은 `docs/evidence/flat_polish_adapter_drafts/`에 별도로 보존했다. MASTER V1/V2/V3, 기존 75초 영상, Git 이력 및 기존 렌더 캐시를 이 어댑터 작업에서 변경하지 않았다.

현재 Flat 어댑터 SHA-256: `329e0da4ec4d21f0f4d26e63257709718dd27c7af3c406fe062e320657da554b`.

## 실제 데이터와 재질

| 항목 | 실제 사용 데이터와 처리 |
| --- | --- |
| 국가·해안선 | 기존 Natural Earth 1:50m GeoJSON 벡터 폴리곤과 경계 |
| 지형 표면 | Natural Earth I shaded relief/land cover 원본 21,600×10,800에서 확대·생성 없이 잘라낸 2,880×4,380 PNG |
| 지역 범위 | WGS84/EPSG:4326, 약 동경 104–152°, 남위 8–북위 65° |
| 지역 밖 표면 | 기존 8,192×4,096 전 지구 day texture |
| 미세 relief | 기존 2,048×1,024 topology raster의 재질 음영 미분; 측량 DEM이나 실제 고도 메시가 아님 |
| 지역 경계 연결 | 경계 안쪽 12°에서 지역 raster와 전 지구 raster의 source/neighbor 샘플을 smoothstep으로 혼합. 화면을 가리는 veil이 아닌 재질 혼합 |

지역 PNG SHA-256은 `23c9ed6b954528fb98267d103f6e066e650461a7a817304b6cc2d4aa3d55a522`이다. 원본·저작자·Public Domain 라이선스·정확한 crop 영역·다운로드 날짜는 [assets/flat/SOURCES.json](../assets/flat/SOURCES.json)의 `natural-earth-1-east-asia-expanded` 항목에 기록되어 있다. 이는 현재 위성 촬영·실시간 구름·고해상도 DEM 데이터가 아니다.

Flat 재질은 기존 지형을 샘플링한 뒤 미세 local contrast와 색 대비를 조정한다. 선택 국가의 tint는 원래 지형 명도에 비례하므로 지형을 불투명한 단색으로 교체하지 않는다. 선택 상태에 따라 주변 육지는 밝기 0.92·채도 0.90, 선택 육지는 exposure 1.075·local contrast 1.10을 적용한다. 선택 경계와 AUTO FOCUS는 기존 시간 창을 따라 부드럽게 활성화된다.

## 이동체·경로·라벨

- 항공기는 기존 `createAircraftV3()`의 실제 3D 민간 항공기 메시를 재사용한다. 1080 기준 크기 설정의 하한은 첫 항공기 88, 이후 항공기 82이다. 이는 cartographic proxy의 설정값이다. 실제 투영된 폭·길이·반경은 방향·카메라·곡률에 따라 달라지며, native audit의 `screenRadius`는 실제 3D 모델 Box3 모서리의 투영으로 계산한 보수적 경계다.
- 움직이는 주 경로는 밝은 cyan core와 약한 glow/head를 유지한다. 표준 2160 내부 렌더 →1080 출력에서는 core가 약 5.5px이며, 곡률·원근감과 다른 내부 렌더 폭에서는 화면상의 굵기가 달라질 수 있다. 이미 지난 경로는 더 약하게 남는다. 경로 진행률과 물리적인 선두 위치는 변경하지 않았다.
- 같은 공항에서 정지한 항공기와 출발 항공기가 겹치면 정지 proxy만 최대 `(+58, −32)` 최종 기준 px만큼 시각적으로 분리한다. 충돌 정도에 따라 정지 proxy의 크기는 최대 0.77, alpha는 최대 0.68 비율까지 낮아진다. verified ground coordinate·route progress·Scene 상태는 그대로이며 audit에 원래 지리 anchor와 display offset을 각각 기록한다. 이 offset은 실제 비행 이동이 아니다.
- 도시 이름은 이미 로드되는 Noto Cinema 400, 1080 기준 최소 font 54를 사용한다. 폭은 해당 폰트의 실제 Canvas `measureText`와 letter spacing으로 측정하며 높이는 `font×1.25`의 보수적 layout box다. 1.45px dark edge와 약한 shadow를 사용한다. 정보 문구와 국가 이벤트 라벨의 기존 폰트·시간 창은 유지한다.
- 도시 라벨은 검증된 anchor와 Scene 항로의 도착 방향, 고정된 end framing을 기준으로 220px 공항 footprint 바깥의 동일한 상대 slot을 유지한다. 이동 중인 기체를 따라 후보 slot을 바꾸지 않는다. 실제 준비된 기체의 투영 Box3도 검사하며, 해결되지 않은 겹침은 `unresolvedOverlap`으로 기록한다. 라벨 위치가 움직여도 지리 anchor와 연결선은 보존한다.

## 실제 지형 투영 전환

별도 `geographic_polish_transition.js`가 원래 projected 좌표를 보존하면서 실제 tangent plane→spherical geographic 위치로 지형·해양·경로·기체를 변환한다. 기존 opaque atmospheric veil은 새 Flat frame 경로에서 그리지 않는다. `earth_polish_adapter.js`는 등록된 같은 지리 카메라에서 기존 실제 V3 구체로 연결하며, 표면 재질과 기존 cinematic 조명으로 정착한다.

land/ocean 메시의 분할과 ocean의 signed z·최대 0.0007 Earth-radius 시각적 depth separation은 곡률 전환에서 depth fighting을 막기 위한 표시 처리다. 실제 수심·지형 고도·DEM 계산 결과로 해석하면 안 된다. incoming Earth 라벨은 마지막 encoded Flat pose의 같은 항공기 메시·크기·표시 offset과 동일한 layout helper를 재구성해 연결한다. 이 재구성은 또 다른 GL 렌더나 새 texture 다운로드를 수행하지 않는다.

## 검증 범위와 남은 한계

`tools/flat_polish_contract_tests.mjs`의 21개 assertion은 기존 renderer source 보존, opt-in 제한, guarded shader 변경, 측정된 폰트 layout 정책, fade envelope 유지, 지리 anchor 불변 및 공통 출발점의 proxy 분리를 검사했다. 이 테스트는 영상 픽셀·모바일 가독성·영화적 품질의 인증이 아니다.

Root가 생성한 `docs/evidence/flat_polish_final_stills_v004_r03/S004_LAYOUT_SCAN.json`에는 실제 로드된 폰트와 준비된 3D 모델 경계로 계산한 90개 시각의 layout 기록이 있다. 현재 기록에서 도시별 상대 offset의 최대 프레임 변화는 4K 기준 SEOUL 약 `1.14e−13px`, TOKYO와 TAIPEI `0px`; `unresolvedOverlap` 기록은 0개이다. 각 프레임을 그린 결과나 최종 MP4 재생 검수를 대신하지 않는다.

한정된 지역 raster 밖에서는 기존 8K 표면을 사용하므로 전 세계 동일 지형 해상도를 보장하지 않는다. 공항 slot과 기체 proxy는 실제 모델 축척이 아닌 지도 가독성을 위한 표현이다. 역방향 EARTH→FLAT에 대한 이번 v004 실영상 검증을 이 문서에서 주장하지 않는다. 새 라벨과 등록 투영의 자연스러움, 마지막 재질 혼합 및 모바일 대비는 실제 최종 MP4 검수가 필요하다.

이번 어댑터는 TTS·BGM·효과음·ducking·자막 파이프라인을 변경하지 않았다. 음원 포함 여부와 자막 ON/OFF는 기존 승인된 프로젝트 설정을 따른다. 75초 전체 또는 MASTER 영상을 이 작업에서 다시 렌더하지 않았다.
