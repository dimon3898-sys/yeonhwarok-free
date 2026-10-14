# WORLD ENGINE — 범용 지도 데이터 연결 인계서

상태: 데이터 조사·소형 샘플 수집만 완료. 2026-10-14. 구현 코드 없음. 기존 WORLD ENGINE·FINAL 변경 없음. 아래는 이후 Codex가 현재 렌더러를 확인한 뒤 수행할 구현 제안이며, 구현 완료·호환성 검증을 뜻하지 않는다.

## 1. 설계 계약

국가 이름이나 한국 좌표를 엔진 로직에 하드코딩하지 않는다. Scene JSON/설정의 `bbox`, `crs`, `zoom 또는 targetGroundResolution`, `sourceId`, `sourceVersion`으로 자료를 결정한다. 한반도 값은 테스트 fixture에만 둔다.

| 공급자 역할 | 우선 자료 | 반환하는 핵심 값 |
|---|---|---|
| TerrainSource | Copernicus GLO-30 | 미터 단위 Float32 높이, 정확한 transform, 점/셀 등록, 수직 기준, 유효 범위 |
| BathymetrySource | GEBCO_2026 | 미터 단위 signed 높이, 셀 중심 좌표, source/quality caveat |
| SurfaceTextureSource | NASA BlueMarble_NextGeneration | 지리 범위가 붙은 색상 텍스처, August 2004 시점, 출력 격자 |

공통 결과에는 status, sourceURL, version, bbox, native/output resolution, CRS, vertical datum, nodata, attribution, SHA-256를 넣는다. `unavailable`, `auth_required`, `version_changed`, `license_unverified`를 구분한다. 미존재 자료를 성공·가짜 지형으로 대체하지 않는다.

## 2. 권장 작업 순서

1. 현재 렌더러의 평면/지구 좌표계·높이 단위·GPU texture 형식·기존 land/ocean mask·색공간·LOD·캐시를 읽기 전용으로 확인한다. WebGL/GPU 호환성은 지금 확인되지 않았다.
2. 동봉 샘플의 해시를 검사하고 파일을 읽는 단계부터 검증한다. 원자료 캐시와 렌더용 변환 캐시를 분리한다.
3. TerrainSource를 연결한다. Float32 높이를 보존하고, 렌더용 양자화가 필요하면 scale/offset를 함께 저장한다. 자료를 색상값처럼 sRGB로 처리하지 않는다.
4. BathymetrySource를 연결한다. 원본 부호와 기준을 유지하고 수심색 함수에만 `max(0,-elevation)`을 적용한다. 지형·바다 경계 전이는 별도 처리한다.
5. SurfaceTextureSource를 연결한다. 색상 영상은 필요한 색공간 변환을 거쳐 기본색에 쓴다. Blue Marble의 바다색으로 수심을 역산하지 않는다.
6. 동일 공급자 규칙으로 임의 bbox 수집·캐시·재시작을 연결한다. 최종 판단은 실제 카메라 장면의 GPU 렌더로 한다.

## 3. 좌표·단위에서 반드시 지킬 점

- 내부 bbox의 표준 순서를 `[west,south,east,north]`로 고정한다. 이번 NASA WMS 1.3 EPSG:4326 요청은 `[south,west,north,east]`였다. 서버별 축 순서를 명시적으로 변환한다.
- Copernicus는 점 등록이다. 동봉 TIFF 외곽은 `[128.2498611111111,37.25013888888889,128.7498611111111,37.75013888888889]`. 요청 사각형으로 transform를 덮어쓰면 반 픽셀 오차가 생긴다.
- GEBCO NetCDF의 위도는 남→북으로 증가한다. 화면용 north-up raster에 쓸 때 행 방향을 확인한다. 두 개의 좌표축과 실제 15 arc-second 간격을 읽는다.
- PNG는 `.pgw` 및 `.prj`와 함께 읽는다. 첫 픽셀 중심은 `(124.0025,42.9975)`, 셀 크기는 `(0.005,-0.005)`이다.
- 지형의 EGM2008과 수심의 혼합 평균해수면 기준을 완전히 같은 datum으로 간주하지 않는다. 해안 이음부를 실측 정합했다고 주장하지 않는다.
- 전 세계에서 음수 고도만으로 바다를 판별하면 육지의 저지대·호수를 잘못 칠할 수 있다. 현재 엔진의 지리 마스크를 확인하고, 사용할 수 없으면 해안 처리 미완료로 남긴다. 이번 3종 범위를 넘어 별도 자료를 임의 수집하지 않는다.
- normal 계산은 경위도 차이를 그대로 미터 차이로 쓰지 않는다. 위도에 따른 동서 거리 변화와 지구/평면 투영을 반영한다. 과장 높이는 원데이터와 분리한 연출 설정이다.

## 4. 지역 자동 취득·LOD·캐시

Copernicus: 공식 공개 타일 인덱스와 교차하는 타일만 선택한다. COG Range/overview를 우선한다. 지역 타일의 크기 상한을 둔 전체 타일 취득도 대안이다. 공개 미러는 2021판이며 전 세계 타일 완전성을 보장하지 않는다. 누락은 같은 자료의 등록 CDSE 경로 또는 명시적 중단으로 처리한다. 최신 CDSE 판과 2021 미러를 무기록 혼합하지 않는다.

GEBCO: DDS/DAS로 축·shape·변수를 확인하고 version-pinned OPeNDAP 부분 요청을 구성한다. 이번 직접 주소는 manifest에 있다. 범위·인덱스를 한국 숫자로 고정하지 않는다. 원격 `.nc` 전체 파일은 요청하지 않는다. ASCII 응답은 이번처럼 작은 샘플에 적합하며 넓은 영역은 서버가 지원하는 이진 subset 방식으로 검증 후 전환한다.

NASA: GetCapabilities에서 레이어·matrixset·정적/시계열 구분을 읽는다. `500m`의 EPSG:4326 WMTS는 Web Mercator XYZ와 타일 크기/행렬이 다르다. URL의 `{z,row,col}`만 바꿔 일반 slippy map 공식을 그대로 적용하지 않는다. WMS 요청 크기는 원자료보다 과도하게 올려도 상세가 증가하지 않는다.

LOD는 화면 공간 오차와 자료 해상도로 결정한다. 고정 카메라 높이 임계값을 모든 위도에 공통 적용하지 않는다. 원자료/정합 raster/normal/GPU texture별 캐시 키에 공급자·판·원본해시·타일·CRS·해상도·변환 버전을 넣는다. 카메라 이동 중 자료 취득은 렌더와 분리한다. 제한된 동시성·timeout·재시도 상한을 두고 성공 캐시는 재사용한다.

날짜 변경선 bbox는 두 구간으로 분할한다. 극지에는 EPSG:3857의 위도 제한을 그대로 적용하지 않는다. 남·서반구 타일명과 고위도 비정방 격자를 지원한다. 이번 수집으로 전 세계 edge case가 실증된 것은 아니다.

## 5. 구현 후 필요한 검수

| 검수 | 합격 기준 |
|---|---|
| 무결성 | manifest와 샘플 SHA 일치; 파싱 오류·NaN/무단 0 치환 없음 |
| 좌표 | height/texture/depth 위치·북쪽 방향 정합; 반 픽셀·WMS 축 뒤집힘 없음 |
| 수치 | 원높이 미터·수심 부호 보존; quantization 오차 기록 |
| 바다·해안 | 기존 마스크와 대조; 내륙 저지대를 바다로 칠하지 않음; datum 차이·해안 단차 처리 기록 |
| 범용성 | 동일 API로 임의 bbox 입력 가능; 날짜 변경선·극지·누락 타일에 명시적 결과. 추가 실데이터는 후속 작업 범위에서만 취득 |
| 캐시 | 같은 요청에서 재다운로드 없음; 중단 후 재개; 실패 파일을 성공 캐시로 쓰지 않음 |
| 라이선스 | 영상/에셋 배포 시 동봉 attribution·사용 조건 유지; 기관의 검수·보증 암시 없음 |
| 영상 | 1080×1920 실제 장면에서 LOD 전환·타일 이음·해안·지형 깜빡임 검사. 기능 PASS와 시각 품질 PASS를 분리 |

황금빛 사광은 normal·광원·tone mapping, 영토 채움·전선 glow·카메라 리듬은 엔진 로직이다. 이번 자료에 해당 효과가 포함된 것으로 취급하지 않는다. 이 인계서 자체가 FINAL 승격이나 기존 파일 교체를 승인하는 문서는 아니다.
