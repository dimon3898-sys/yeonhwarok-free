# 2026-11-08 재개: 원본 데이터 검토 결과

상태: **표현 입력 검사는 보존. 새 표면영상 후보는 FAIL. 배포·유료 제작은 HOLD.**

## 새로 확인한 자료

| 자료 | 이번에 실제 확인한 범위 | 적용 판단 |
|---|---|---|
| Copernicus GLO-30 인천 타일 | N37 E126, 29,862,574바이트, 3600×3600 Float32, EPSG:4326. 결측·비유한 값 0. 첫 샘플 중심 126°E, 38°N | 원본 읽기 성공. 전체 장면 고도 자료 승인 아님 |
| EOX 2016 한국 WMS 표면영상 | 125~131°E, 33~40°N, 3072×3584. 실제 다운로드 및 육안 확인 | 흰 공백·구름·해안 타일 경계가 있어 현재 후보 반려 |
| 기존 카메라 범위 | 기존 PREPARED 파일에 저장된 범위를 읽어 합집합 산출: 123.274042~131.725958°E, 32.2~44.2°N | 원본 600프레임 검사 재실행 아님. 두 새 샘플 모두 전체 범위를 덮지 못함 |

다운로드 URL·바이트·SHA256·검사 범위는 `evidence/source-qualification/`에 기록했다.
EOX 밝은 픽셀 개수는 단순 수치이며 구름/결측을 자동 분류했다는 뜻이 아니다.
원본 표면영상을 인공지능으로 메우거나 고도를 밝기에서 추측하지 않았다.

## 원본 출처와 조건

- Copernicus 공개 COG 설명: https://copernicus-dem-30m.s3.amazonaws.com/readme.html
- 실제 공개 타일 목록: https://copernicus-dem-30m.s3.amazonaws.com/tileList.txt
- 공식 DSM 설명·출처 표시 안내: https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
- EOX 조건: https://cloudless.eox.at/pricing
- 실제 WMS 목록: https://tiles.maps.eox.at/wms?service=WMS&request=GetCapabilities

Copernicus 자료는 건물·식생을 포함한 현대 DSM이다. 1950년 지형·해안선을 증명하지 않는다.
EOX 공식 페이지와 WMS 목록은 `s2cloudless` 2016 레이어를 CC BY 4.0으로 명시한다.
2018~2025 무료 조건은 비상업 조건이므로 이 작업에서 무단 대체하지 않는다.
공개 사용 시 해당 원본의 정식 출처 문구를 보존해야 한다.

## 기존 엔진에서 가능한 것과 연결이 필요한 것

1. `presentation_runtime.mjs`의 `REFERENCE_FOCUS_V2`에는 기존 얇은 해안 강조가 있다.
   넓은 발광·바다 질감을 입력값만으로 새로 활성화할 수 있다고 주장하지 않는다.
2. `renderer.mjs`는 `heightSource`의 해시·바이트·Float32·결측을 확인하고 R32F로 읽는다.
   현재 Studio 래퍼는 이를 전달하지 않으며 `presentationNativeMapOptions`가 `dem:false`다.
3. 엔진의 `contextTerrain`/LOD 기능도 현재 presentation factory 호출에는 연결되지 않는다.
   원본 카탈로그 최대 텍스처 크기는 4096이다. 넓은 첫 화면과 확대 장면을 한 장으로
   무리하게 묶어 확대 해상도를 확보했다고 주장해서는 안 된다.
4. 현재 `BAKED_RELIEF_V1`은 구워진 음영 자료에 대한 처리다. 새 광학 RGB 원본에 이
   분류를 붙여 통과시키면 안 된다. 실제 소스 분류와 재질 경로를 함께 확인해야 한다.
5. 바다 색에는 실제 원본 밝기 변화만 반영된다. 인공 파도 재질은 현재 연결된 기능이 아니다.

## 첫 미완료 단계와 최소 후속 범위

첫 미완료는 **전체 카메라 범위와 확대 수준을 충족하는 표면·고도 자료 승인**이다.
EOX 2016의 같은 요청은 다시 내려받거나 재검사하지 않는다. 이미 반려한 후보다.

- 기존 BMNG·Natural Earth는 보존한다. 대체 광학 자료는 구름/결측 마스크와 출처,
  좌표 정합, 확대 해상도, 전체 범위를 확인해야 한다. 해안선 역시 같은 좌표·시기
  한계를 명시한 원본이 필요하다.
- 고도는 승인된 실제 타일만 취합하고 샘플 중심·CRS·단위·NoData·해시를 기록한다.
  미제공 타일을 임의로 육지 고도 0으로 채우지 않는다.
- 승인 후에만 source catalog → source qualification → 서버 자산 바인딩 → 기존
  renderer factory `heightSource`/`contextTerrain` 연결을 최소 수정한다.
- 그 변경으로 영향을 받는 소스 입출력·좌표·경계 검사만 새로 수행한다. 기존 라벨,
  역사·지리 Scene, 600프레임 배치 PASS는 무효화 근거 없이는 재실행하지 않는다.
- 정식 Studio 경로와 변경 범위 검사 통과 후에만 새 이미지 빌드 여부를 판단한다.

이번 Work: 생성기 코드 변경 0, 이미지 빌드 0, 신규 Actions 실행 0, GPU 0,
Studio 렌더링 0, MP4 생성 0, 기존 PASS 재실행 0. 원본 데이터 수신은 영상 렌더링이 아니다.
