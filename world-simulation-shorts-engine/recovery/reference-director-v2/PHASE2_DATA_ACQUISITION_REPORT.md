# PHASE 2 — 실제 정밀 지도 자료 조사 결과

**판정: DATA_DETAIL_BLOCKED. 정밀 지리 자료를 확보했다거나, 레퍼런스 장소가 식별됐다고 선언하지 않습니다.**

기준은 원격 `5cc9b98c628324814e1e63f9d0f8c6254ee84174`입니다. 첨부된 후속 지시서와 이전 `CAPABILITY_GAP_AND_PATCH_MAP.md`, `DATA_BINDING_AND_SOURCE_REPORT.md`, `SOURCE_DETAIL_AND_LICENSE_REPORT.md`, `REMAINING_LIMITS.md`를 전체 읽고 조사했습니다. 기존 자산이나 캐시는 변경하지 않았습니다.

## 실제 실행한 접근과 권한

공식 `request_permissions`에서 이번 turn의 `network.enabled=true` 권한이 반환됐습니다. 그러나 이 권한은 환경의 적용된 HTTP 프록시 도메인 정책을 게시하거나 변경했다는 증거가 아닙니다. 실제 명령은 기존 프록시와 TLS 검증을 유지했습니다.

다음 첫 요청에서 프록시 CONNECT 단계의 **403 Forbidden**을 확인했습니다. 응답 원문·지도 데이터·라이선스 문서를 읽었다고 처리하지 않았고, 동일한 차단 요청을 반복하거나 프록시/CI로 우회하지 않았습니다.

| 출처 | 실제 요청 목적 | 실제 결과 |
| --- | --- | --- |
| `en.wikipedia.org` | Peñón de Vélez de la Gomera 후보의 독립적인 지명·설명 확인 | CONNECT403, 원문 미확보 |
| `www.ign.es` | 스페인 공식 지리 자료 목록·정밀 소스·허가 조건 확인 | CONNECT403, 원문 미확보 |
| `overpass-api.de` | 실제 GIS 질의 전에 공개 OSM 서비스 상태 확인 | CONNECT403. 상태 조회만 시도했으며 지리 데이터 질의·다운로드는 미실행 |
| `api.github.com` | 기존 공개 자료 저장소 검색 | CONNECT403 |

허용된 `github.com`/`raw.githubusercontent.com`에서 합법적인 기존 출처를 추가로 확인했습니다. 공개 repository 검색은 동작했으나 후보의 검증된 정밀 자료를 찾지 못했습니다. Code search는 로그인되지 않은 상태라 사용할 수 없었습니다. 관련 없는 repository, 설명 문자열 또는 검색 결과를 지도 근거로 승격하지 않았습니다.

`wmgeolab/geoBoundaries`의 ESP 메타데이터 raw 파일은 **128바이트 Git LFS 포인터**였습니다. 예상887바이트/원본 SHA가 적혀 있다는 이유로 메타데이터나 지리 형상을 확보했다고 판단하지 않았습니다. 공식 GitHub 다운로드 경로도 redirect 연결 단계에서403으로 막혔습니다. 작은 메타데이터에 대한 확인에 한정했으며 대용량 국가/global raster를 내려받지 않았습니다.

요청별 URL, 상태, 실제 다운로드 문서의 SHA·바이트와 구분은 `reports/DATA_ACQUISITION_LEDGER.json`에 있습니다. 공개 HTML의 일회성 폼 값이나 내부 응답 원문은 공개 자료에 넣지 않았습니다.

## 실제로 확보·확인한 문서

| 공식 공개 문서 | 실제 bytes / SHA-256 | 확인 가능한 범위 |
| --- | --- | --- |
| IGN-CNIG `API-CNIG` README | 2,146 / `19c053293e0c3e1df239fc3748a6862a2c2211892e73ca62c18c50a9cf2bc867` | 공식 API가 WMS·WMTS·WFS·KML을 지원한다는 소프트웨어 문서. 특정 상세 영상/폴리곤·coverage를 확보한 증거가 아님 |
| 같은 repository LICENSE | 13,865 / `6e5399ad2f4548dc22dd9eff1c367d5d286efc15723894b3a3b772347b609d11` | **API 소프트웨어의 EUPL1.2**. PNOA/WMTS 지도 데이터의 재배포 허가로 오인하지 않음 |
| Natural Earth upstream LICENSE | 4,636 / `2631b5b39b6d1acc56de75235109b5af2dbb4b0ac5a127b6f06185977247fd4b` | 기존 보존 라이선스와 SHA 일치. Public Domain 사용·배포 조건 확인. 정밀도 보증은 아님 |

IGN API를 설치·통합·배포하지 않았습니다. API 소스의 라이선스와 실제 imagery/경계 데이터의 라이선스를 분리했습니다. 새 detailed raster, 실제 핵심 Polygon 또는 LineString을 내려받은 수는 **0**입니다.

## 장소·데이터별 상태

| 항목 | 실제 검증 상태 |
| --- | --- |
| 핵심 장소의 정체 | **UNVERIFIED**. Peñón de Vélez de la Gomera는 조사 후보일 뿐, 원본의 모양과 `85 m` 문자열만으로 확정하지 않음 |
| 핵심 Point | 독립된 출처와 정확도 근거 미확보. 추정 좌표를 입력하지 않음 |
| 상세 Polygon/MultiPolygon | 미확보. 원본 화면의 윤곽을 따라 그리거나 사각형으로 대체하지 않음 |
| 순서 있는 실제 경계 LineString | 미확보. 화면 픽셀 선을 지리적 경계로 오인하지 않음 |
| `85 m` | **OBSERVED_REFERENCE_TEXT_ONLY** 유지. 표시용 관찰 문자열은 허용되지만 실제 지리 길이·측량 정확도는 미검증 |
| 기존 국가·두 장소·overview RGB | 이전 source-qualified 자료를 보존. 정밀 해안 형상과 local basemap의 대체물로 사용하지 않음 |
| context 영역·스타일 그룹 | 기존 coarse context `COUNTRY_MAR`와 104개 source-ID→style-group 목록을 **authoring 데이터로 명시 선택**. 엔진의 국가·대륙 조건문을 추가하지 않음. 실제 소비 시 일반 source/projection 검사는 별도 필요 |
| 정밀 basemap 및 native sampling | 미확보. 기존 8K 지구 색상 지도를 확대하거나 가짜 지형/노이즈를 생성해 상세 원자료처럼 취급하지 않음 |

`REFERENCE_DIRECTOR_INPUT_V2.json`과 `EXPLICIT_COARSE_SELECTION_PROFILE.json`에 가능한 기존 coarse 선택을 준비했습니다. 주국가의 원본 component4는 **framing subject만** 명시 선택하고, 원본 12-part MultiPolygon을 render geometry로 그대로 유지합니다. 원본의 카메라 구도에 맞추기 위해 섬이나 국가 형상을 삭제·변형하지 않았습니다. 국가·대륙명 비교는 런타임 코드에 넣지 않았으며 소비자는 입력에 있는 ID/스타일 목록을 사용해야 합니다. 이 선택은 원본 픽셀의 정확한 복원이나 측량 정확도를 주장하지 않습니다.

따라서 이전의 선택 미정 2개 항목은 coarse authoring 선택으로 해소했고, 필수 detail/source 공백은 핵심 Point·상세 Polygon·실제 경계 LineString·native basemap **4개**로 남았습니다. 실제 coverage, 좌표계, 날짜, positional uncertainty, source SHA, 허가 조건과 native 해상도가 함께 검증되기 전에는 정밀 데이터 gate를 열지 않습니다.

## 필요한 가장 작은 다음 환경 조치

현재 적용 환경의 도메인 목록과 설정 초안은 별개입니다. 실제 연구를 재개하려면 다음 도메인을 환경의 **적용된 정책**에 반영한 뒤 접근을 재검증해야 합니다. 이 보고서는 게시 성공을 주장하지 않습니다.

1. `en.wikipedia.org`: 이미 실패한 후보 지명 원문 확인.
2. `www.ign.es`: 이미 실패한 공식 지리 catalogue/라이선스/실제 WMS·WMTS metadata 확인.
3. `overpass-api.de`: 이미 실패한 상태 확인 후에만, 필요한 작은 지역의 실제 OSM 자료 요청 여부 판단.
4. `www.openstreetmap.org`: OSM copyright/ODbL·attribution/사용 조건 확인용. 아직 요청하지 않았으며 허가가 있다고 미리 처리하지 않음.

추가 공식 군 지명 원문이 필요할 때만 `ejercito.defensa.gob.es`를 별도 검토할 수 있습니다. 이 도메인은 아직 요청·확인하지 않았습니다. 와일드카드·공용 우회 프록시·외부 CI 다운로드로 정책을 우회하지 않습니다.

접근이 복구돼도 후보 식별, source license, detail geometry, 측정의 의미 및 실제 영상 coverage가 자동 PASS가 되는 것은 아닙니다. 각 자료를 실제 확보·검증해야 합니다. 특히 공식 PNOA 서비스가 해당 작은 장소를 촬영·제공하는지는 아직 확인되지 않았습니다.

## 제작 gate에 대한 영향

Phase1의 실제 기본/opt-in 픽셀 검증은 독립적으로 진행할 수 있습니다. 그러나 Phase2는 **DATA_DETAIL_BLOCKED**이므로, 후속 지시서에 따라 12개 reference 시점·두 fixture를 포함한 Phase3 검수 제작 및 A/B/C Studio MP4는 이 자료 gate가 충족되기 전에는 허용되지 않습니다. 원래 source 영상이나 component 이미지를 Studio 출력으로 가장하지 않습니다.

기존 G1·G2·FINAL·Candidate·이미지·Scene·캐시·Secret을 수정·삭제하지 않았습니다. 유료 GPU/API·배포·80초 영상 제작은 수행하지 않았습니다.
