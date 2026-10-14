# WORLD ENGINE — 필수 지도 데이터 선별·수집 보고서

검증일: 2026-10-14 (Asia/Seoul). 첨부 MASTER 전체를 읽고 육지 지형·바다 수심·지표 텍스처만 조사했다. **3종 모두 한반도 실제 샘플 확보 완료.** WORLD ENGINE 저장소·소스·기존 manifest·FINAL에는 접근하거나 변경하지 않았다. 엔진 실행 및 영상 품질 합격 판정도 하지 않았다.

## 1. 최종 선택

| 용도 | 우선 자료와 기관 | 전 세계 범위·해상도 | 이번 취득 방식 | 판단 |
|---|---|---|---|---|
| 육지 높이 | Copernicus DEM GLO-30 / EU·ESA, DLR·Airbus 원자료; Sinergise 관리 AWS 공개 COG | 전 세계 육지 제품. 명목 30m; 한국 격자 1 arc-second. 공개 미러에는 일부 타일 누락 가능 | 2021 배포본의 한국 1° 타일 1개 수신 후 0.5° 크롭 | 산악 기복용 우선 채택. 건물·수목 포함 DSM이며 맨땅 DTM은 아님 |
| 바다 수심 | GEBCO_2026 / IHO·IOC GEBCO, Seabed 2030, BODC·CEDA 배포 | 극지 포함 전 세계 격자; 15 arc-second, 위도 방향 약 464m | CEDA OPeNDAP에서 2°×2° 부분만 취득 | 심해 색상·대륙붕 표현용 우선 채택. 격자 간격이 실제 측량 해상도를 보장하지 않음 |
| 지표색 | NASA Blue Marble: Next Generation / NASA Earth Observatory·GIBS | 전 세계 합성 영상; 원자료 명목 500m | 무음영 기본 레이어의 한반도 WMS PNG | 국가·대륙 줌의 기본색으로 채택. 도시 근접 확대용·현재 시점 영상은 아님 |

공식 근거: [Copernicus 사양](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM), [AWS 배포 정보](https://registry.opendata.aws/copernicus-dem/), [GEBCO 2026](https://www.gebco.net/data-products-gridded-bathymetry-data/gebco2026-grid), [NASA Blue Marble](https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/).

**전 세계 지원과 전 세계 동일 품질은 다르다.** 극지·작은 섬·해안·자료가 부족한 지역의 상세 표현은 별도 검증이 필요하다. 이 패키지는 한국 검증 샘플이지 한국 전용 연결 설계가 아니다. 추가 데이터셋은 선택·다운로드하지 않았다.

## 2. 버전·좌표·파일 형식

| 항목 | Copernicus | GEBCO | NASA |
|---|---|---|---|
| 고정한 버전 | AWS 명시 2021 release. 소스 객체 Last-Modified 2022-05-09 | GEBCO_2026; 원자료 생성 2026-04-17, 공식 발표 2026-04 | 선택 레이어: August 2004, ongoing=false |
| 갱신 | AWS 미러 정기 갱신 없음. CDSE 확인 최신 목록은 2024_1; 서로 동일판으로 취급 금지 | 연도별 배포. 새 판·errata 확인 후 명시적으로 갱신 | 선택 레이어는 정적 합성. best URL 변경 가능하므로 해시 고정 |
| 수평 기준 | 제품 사양 WGS84-G1150/EPSG:4326. 실제 TIFF WGS84/EPSG:4326 | WGS84로 간주; 원격 메타데이터 EPSG:4326 | EPSG:4326. WMS 1.3 요청의 BBOX는 위도·경도 순 |
| 수직 기준 | EGM2008/EPSG:3855, m. 실제 TIFF에 수직 CRS가 내장되지 않아 manifest에 보완 | 평균해수면 가정; 원격 메타데이터 EPSG:5831. 일부 원천자료의 수직 기준 혼재 | 해당 없음 — 색상 영상 |
| 격자·형식 | Float32 GeoTIFF, RasterPixelIsPoint. 원격 원본 COG; 결과는 일반 tiled GeoTIFF | Int16 NetCDF4, 셀 중심 좌표, signed elevation: 음수=기준면 아래의 고도. 공식 GeoTIFF/ASCII도 제공 | WMS RGBA PNG; WMTS JPEG. PNG에 좌표가 없어 .pgw와 .prj 추가 |

Copernicus의 고위도 경도 간격은 일정하지 않다. COG 변환 과정에서 동·남쪽 중복 행/열이 제거됐다. 원본 격자를 보존해 자른 이번 TIFF의 실제 외곽은 요청 BBOX와 반 픽셀 차이가 있다. 정확한 수치는 manifest와 provenance에 기록했다. [배포자 COG 설명](https://copernicus-dem-30m.s3.amazonaws.com/readme.html)

GEBCO는 그린란드·남극의 표면/빙하 아래 버전을 구분한다. 이번 선택은 ice_surface_elevation 버전이다. 전 세계 격자를 제공하지만 모든 해저가 직접 측량된 것은 아니다. 최신 errata에는 북태평양 수심 오프셋과 오대호 수직 기준 불연속이 공지돼 있다. **한국 샘플에 해당 오류가 영향을 주는지는 확인 불가**다. [수직 기준·배포](https://www.gebco.net/data-products/gridded-bathymetry-data), [공식 오류 공지](https://www.gebco.net/data-products/gridded-bathymetry-data/data-set-errata)

NASA의 선택 레이어는 추가 지형 음영이 없는 Base Map 계열이다. 물리적 반사율 원자료로 보장되는 것은 아니다. 눈/구름 구분, 해안 합성, 작은 섬 표현에 한계가 있고 심해의 파랑은 수심 자료가 아니다. [Base Map](https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-map/), [레이어 메타데이터](https://gibs.earthdata.nasa.gov/layer-metadata/v1.0/BlueMarble_NextGeneration.json)

## 3. 사용 조건 검증

| 자료 | 무료 상업 YouTube 영상 | 캐시·변환·프로젝트 에셋 재배포 | 의무·제한 |
|---|---|---|---|
| Copernicus GLO-30 | 허용되는 것으로 판단. 라이선스는 무료 복제·배포·공중 전달·수정을 허용하며 비상업 제한이 없음 | 허용. 가공본에도 원라이선스 의무 전달 | 가공본 출처 문구, 면책 고지, 후속 사용자 의무. 기관 보증 암시 금지 |
| GEBCO | 명시적 상업 이용 허용 | 복제·가공·배포 명시 허용 | 출처 표시, 공식 보증·출처 오표시 금지. 항해·해상 안전용 사용 금지 |
| NASA Blue Marble | 정보 전달·편집 목적의 상업 영상 사용 가능 | 해당 영상의 사용·재게시 허용 근거로 지역 캐시·변환·에셋 전달 가능 | NASA Earth Observatory 크레딧. NASA 보증 암시·로고 권리와 혼동 금지 |

이는 각각의 공개 조건을 이번 사용 목적에 적용한 판단이다. NASA 전체 사이트의 제3자 콘텐츠까지 허가된다는 뜻은 아니다. NASA 영상이 아닌 생성기 결과물 전체를 NASA 제작·검증 결과로 표시하지 않는다. 기관이 데이터·생성 결과를 보증한다고 표현하지 않는다.

근거와 필수 고지는 `licenses/LICENSE_EVIDENCE.md`, `licenses/ATTRIBUTION.txt` 및 동봉한 `License-COPDEM-30.pdf`에 정리했다. GEBCO와 NASA는 임의의 CC 라이선스명을 붙이지 않았다.

## 4. 실제 수집 파일

모든 BBOX는 아래 표에서 **서경계, 남경계, 동경계, 북경계 — 경도·위도** 순서다.

| 파일 | 범위·크기 | 처리와 확인 |
|---|---|---|
| `samples/Copernicus_GLO30_2021_N37E128_crop.tif` | 요청 [128.25,37.25,128.75,37.75]; 1800×1800; 8,483,540 bytes | 원격 한국 1° 타일 45,141,829 bytes 취득 후 크롭. 보간 없음. 값 204.0~1574.2786m, 유효값 3,240,000개. 원본 창과 완전 일치 |
| `samples/GEBCO_2026_Korea_EastSea_subset.nc` | [128,37,130,39]; 480×480; 273,125 bytes | 공식 서버 부분 응답을 NetCDF4로 재포장. -2124~1613m, 음수 셀 142,575개. 정수값 일치. 원격 ASCII 응답도 보존 |
| `samples/BlueMarble_NextGeneration_Korea.png` | [124,33,132,43]; 1600×2000; 3,287,256 bytes | WMS 서버 출력 그대로. 출력 간격 0.005°, 위도 방향 약 557m. RGBA이며 alpha 전부 255. 좌표 sidecar 동봉 |

샘플 크롭/NetCDF 변환은 공식 원파일 그대로가 아니라 **공식 데이터에서 만든 지역 파생 파일**이다. 지형·수심값을 합성하지 않았고 지형 고도값을 인위적으로 높이지 않았다. PNG는 WMS 시각화 응답으로, 센서 원시 관측 파일이 아니다.

`DATA_MANIFEST.json`과 `DATA_MANIFEST.csv`에 세 데이터의 실제 파일 바이트·SHA-256·좌표·버전·URL·사용 조건을 기록했다. `SHA256SUMS.txt`는 패키지 내부 모든 파일(자기 자신 제외)을 검증한다. ZIP 자체 해시는 ZIP 밖의 `.sha256` 파일에 있다.

자료 미다운로드 항목: 없음 — 선택한 3종 샘플 모두 확보. CDSE 등록 API의 최신판 경로와 GIBS WMTS 경로는 확인만 했으며 추가 데이터 타일은 받지 않았다. 전 세계 원본·한국 외 별도 샘플·TID/마스크 등 추가 자료는 받지 않았다. 한국 BBOX 경계에 자연스럽게 포함되는 주변 육지·바다는 그대로 유지했다.

## 5. 자동 수집 가능성과 운영 조건

| 자료 | 반복 가능한 지역 수집 | 키·인증·유료 크레딧 | 이번 실행의 검증 범위 |
|---|---|---|---|
| Copernicus | 공개 타일 목록/STAC → 교차 타일 선택 → HTTPS/COG Range → 크롭 | 사용한 AWS 공개 경로는 불필요 | 실제 GET 200 및 1024-byte Range 206 확인. 이 환경의 GDAL TLS 실패로 본 샘플은 1개 타일 다운로드 후 로컬 크롭 |
| GEBCO | 버전 고정 OPeNDAP → 격자 좌표 확인 → 원하는 index 범위 요청 | 이번 CEDA GEBCO 경로는 무인증 성공 | DDS/DAS 및 480×480 ASCII 부분 요청 200 확인. NetCDF4 라이브러리 직접 원격 연결은 I/O 실패하여 표준 HTTPS 부분 응답 이용 |
| NASA | capabilities의 레이어/행렬 확인 → WMS BBOX 또는 WMTS 타일 | 사용한 GIBS 경로는 불필요 | WMS PNG 200 확인. WMTS 메타데이터만 확인; 타일 다운로드 미실행 |

공통: 정량 요청 한도·SLA·영구 서비스 유지 여부는 **확인 불가**. 무료 접근이 무제한 요청을 뜻하지 않는다. 작은 동시성, 재시도 상한, 디스크 캐시, 소스 버전·해시 고정을 전제로 한다.

GLO-30 공개 미러의 미존재 타일을 바다 또는 고도 0으로 단정하지 않는다. 전 세계 범용 연결에서는 같은 GLO-30의 등록 CDSE 경로로 해소하거나 명시적 미지원으로 중단해야 한다. CDSE의 계정·권한 설정과 실제 최신 타일 다운로드는 이번에 검증하지 않았다. 자격 증명은 요청하지 않았다.

## 6. 렌더러 인계와 종료 판단

높이는 지형 mesh/normal, 수심은 바다색·해안 전이, 지표 영상은 기본색으로 연결한다. 황금색 사광·영토 채움·이동 전선의 빛·카메라 동작은 렌더러 기능이다. 데이터 3종을 넣는 것만으로 레퍼런스 수준에 도달한다고 단정하지 않는다.

1080×1920 출력에서 국가·대륙 뷰를 구성하는 기본 자료로 선정했다. 근접 줌에는 텍스처 해상도가 먼저 부족해질 수 있다. 화면 픽셀 대비 원자료 간격으로 LOD를 정해야 하며, 기존 렌더러 호환성과 최종 영상 품질은 **미검증**이다. 구현 순서와 필요한 검수는 `CODEX_HANDOFF.md`에 있다.

3개의 선별 근거, 실제 소형 샘플, 좌표·무결성 정보와 사용 조건이 확보돼 추가 자료 조사를 종료했다.
