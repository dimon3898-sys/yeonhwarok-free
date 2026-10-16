# 범용 역사 지도 전선 디지타이징 계약 V1

이 계약은 국가·사건·시대와 독립된 자료 검수 기준이다. 기존 renderer, camera,
Area/Front Core나 V3 도식 좌표를 수정하지 않는다. 공식 지도에 실제로 확인되는
전선 구간만 별도 데이터 버전으로 추가한다. 수치 검수가 영상의 측량급 정확도를
약속하는 것은 아니다.

## 1. 원본과 지도 의미

각 원본은 출처 URL/reference, publisher, 실제 문서명, version, retrieval UTC,
원본 byte length와 SHA-256, 권리/라이선스 검토, 원본 영구 경로를 기록한다.
오류 HTML, archive 목록, 검색 결과, 책 표지는 전선 지도의 원본이 아니다.

지도별로 다음을 원문과 대조하여 기록한다.

- 원본 파일 SHA, PDF의 0-based 페이지 인덱스와 인쇄 페이지 번호.
- 지도 caption, 지도 기준일/시각/시각대 또는 명시된 날짜 범위.
- 실제 확인된 축척, 투영법, datum/CRS, graticule와 범례. 미표기 항목은 unknown.
- 선의 실제 의미: 관측 접촉선/통제 경계, 작전 목표·phase line, 예정 방어선,
  행정선, 최대 진출 범위의 복합도, 이동 화살표 또는 미분류.
- 증거로 사용할 수 있는 구간과 판독할 수 없는/누락된 구간.

사건일이 일치해도 지도 날짜나 실제 전선 의미를 대신 증명하지 않는다. 여러 날짜의
최대 진출선이 함께 그려진 복합도를 한 날짜의 동시 점령선으로 취급하지 않는다.
38선, 해안선, 현대 행정선, 현재 DMZ, 해상 NLL을 해당 시점 육상 접촉선으로 대체하지
않는다. Chinese border crossing, first combat, major counteroffensive 같은 서로 다른
사건도 분리한다.

## 2. 좌표 정합 근거

좌표 결과의 기본 순서는 GeoJSON EPSG:4326 `[longitude, latitude]`다. 원본 지도에
다른 투영법이 확인되면 그 투영법에서 먼저 정합하고 명시적인 변환을 수행한다.
원본 투영법을 알 수 없으면 그 사실, 채택 모델의 근거와 한계를 기록한다.

각 기준점에는 원본 pixel 위치, 확인된 지리 좌표와 별도 출처, 판독 근거, 사용/검수
구분을 기록한다. 실제로 존재하지 않는 기준점이나 좌표를 생성하지 않는다. GCP는
지도 전체에 분산시켜야 하며 한 구석에 몰린 점으로 외삽한 지역을 인증하지 않는다.
변환 모델의 수학적 최소 점수만 충족한 경우를 충분한 품질 근거로 오인하지 않는다.
가능한 독립 checkpoint나 leave-one-out 검수 결과를 기록하고, 없는 경우 없는 사실을
명시한다. 이 계약은 출처 없이 임의의 측량 오차 임계치를 설정하지 않는다.

변환 recipe에는 도구/버전, 원본 좌표계, 선택한 모델과 이유, 모든 GCP/checkpoint,
resampling 유무, 출력 CRS, 잔차의 단위와 분포, 지원 범위/기준점 hull, 지리 정합
검수 그림의 SHA를 기록한다. 원본 이미지는 변경하지 않는다. 지도 장식/접힌 자국/
scan 왜곡은 실제 지리 지점과 구분한다.

기존 Natural Earth 1:50M 해안은 세밀한 역사 지도 정합의 충분한 기준이 아니다.
현대 매립이나 실제 해안 변화 때문에 다른 구간도 있다. 해안에 맞추기 위해 원본의
전선을 임의 변형하지 않고 차이와 불확실성을 별도 기록한다.

## 3. 전선 추적과 불확실성

추적한 각 구간은 원본 SHA, 페이지, mapId, 지도 날짜, 해당 선의 범례/의미, 추적 pixel
좌표, GeoJSON 좌표, georeference recipe, 작성/검수 기록을 연결한다. 실제 vertex의
판독·추적·단순화 과정을 재현할 수 있어야 한다. 없는 곡선이나 구간을 interpolation으로
연결해 역사적 사실을 만들지 않는다.

다음 오차는 다른 필드로 유지한다.

- **Georeference residual**: 기준점/검수점과 변환 결과의 불일치.
- **Digitizing uncertainty**: 선 두께, scan/pixel 해상도, 추적 판독과 단순화.
- **Historical source uncertainty**: 원본 작성 시점, 보고 지연, 지도 자체의 축척·근사.

작은 GCP RMSE는 원본 전선의 역사적 정확도를 증명하지 않는다. 불확실성을 계산할
근거가 없으면 null 및 이유를 기록하고 정밀 좌표라고 부르지 않는다. 원본 축척이
없거나 기준점이 부족해도 판독 가능한 개략 구간을 별도 낮은 정확도 등급으로 검토할
수 있으나, 그 좌표를 관측된 정밀 전선으로 승격할 수 없다.

확인된 전선만 `LineString` 또는 `MultiLineString`으로 제공한다. 부분 전선에 임의
해안/국경을 연결해 polygon을 닫지 않는다. 영토 polygon은 원본이 그 소유 범위와
필요한 모든 경계를 별도로 입증할 때만 허용한다. 하나의 held-core 바깥을 모두 상대
세력 점령지로 추정하는 enemy complement는 허용하지 않는다. 임의 부대·국기 위치나
부대 이동 경로도 만들지 않는다.

## 4. 데이터·Scene 연결

새 원본 자료와 trace는 기존 5개 도식과 다른 ID·버전·manifest로 저장한다. 모든
geometry feature는 최소한 다음 provenance 필드를 가져야 한다.

```json
{
  "sourceId": "ORIGINAL_MAP_SOURCE_ID",
  "sourceSHA256": "ACTUAL_ORIGINAL_SHA256",
  "mapId": "REVIEWED_MAP_ID",
  "pdfPageIndex0": null,
  "printedPage": null,
  "mapDate": null,
  "lineMeaning": "REVIEW_REQUIRED",
  "georeferenceRecipeRef": null,
  "digitizationRecipeRef": null,
  "verifiedSegmentsOnly": true,
  "completeFrontClaimed": false,
  "uncertaintyRef": null,
  "licenseReviewRef": null
}
```

위 예시는 계약이며 실제 원본이나 완료된 좌표 데이터가 아니다. `null`을 근거 없이
채우지 않는다. geometry admission은 자료와 좌표의 검수 상태를 확인한 뒤 결정한다.

사건일, 원본 지도의 기준일, 이전 도식 snapshot 날짜는 독립 필드다. Scene은 해당
날짜의 실제 지도 근거가 있는 geometry만 선택해야 한다. 이전 도식을 문맥으로
사용하면 원래 snapshot 날짜와 도식 한계를 화면에 유지한다. 두 검증 snapshot 사이의
편집상 전환을 관측된 일별 통제로 주장하지 않는다.

기존 80초·2,400프레임·12장면과 범용 Scene 계약을 재사용한다. 데이터 source hash,
새 geometry, 지도 날짜나 전환 경계가 변경되면 기존 캐시 계약에 따라 영향을 받는
장면/인접 경계를 무효화한다. 기존 cache·claim·완료 영상을 삭제하거나 초기화하여
충돌을 우회하지 않는다.

## 5. 검증·승격 경계

원본 SHA, 실제 페이지/날짜/범례, 좌표 범위와 순서, CRS/transform, GCP/checkpoint,
구간 출처, geometry topology와 불확실성, Scene의 날짜·프레임 범위·장면 경계를
집중 검증한다. 기존 도식·보호 코드의 byte 해시는 바뀌면 안 된다.

새 자료가 실제 실행 경로에 선택된 경우에만 무료 SwiftShader draw/readPixels와
영토·전선 동기화, ASTRA, 기존 camera/marker 보호를 확인한다. CPU 또는 SwiftShader
성공을 NVIDIA 하드웨어나 실제 영상 품질 PASS로 표시하지 않는다. 데이터 연결이
없으면 사용되지 않는 자료만 넣어 신규 이미지를 완료라고 등록하지 않는다.

원문/권리/정합/출처 중 필요한 근거가 없으면 해당 feature의 admission을 보류하고
어떤 원본·기준점·설정이 필요한지 기록한다. 다른 안전한 작업은 계속할 수 있다.
현재 이 계약은 데이터 처리·검수 기준만 준비했으며 새 역사 전선 좌표를 제공하지 않는다.
