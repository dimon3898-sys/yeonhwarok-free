# 한국전쟁 공식 전선 자료 V4 — 구현 및 검증 기록

2026-10-16, Asia/Seoul. 이 작업은 **원문 접근이 해결되지 않은 부분 구현**이다.
원본을 읽지 않고 좌표를 만들거나 기존 도식을 실제 점령선으로 승격하지 않았다.
새 CPU 도구의 실제 무료 CI 검사 74개는 통과했으나 실제 원문·좌표·영상 연결은 미완료다.

## 1. 공식 자료 목록과 실제 확보

[SOURCE_CATALOG.json](SOURCE_CATALOG.json)에 사용자 지정 URL 7개, NARA/AWM
공식 보완 진입점 2개, Army CMH 직접 PDF 대안 2개를 기록했다.
10개 URL을 실제 확인했으며 두 번째 GovInfo PDF는 같은 호스트의 CONNECT 거부
때문에 요청을 반복하지 않았다. 문서/지도 확보는 **0건**이다.

- GovInfo, IMHC, Truman, NARA, AWM: proxy CONNECT 403. 원본 서버의 PDF 응답이 아니다.
- Army 소개·요약·직접 PDF 경로: HTTP 403과 CDN Access Denied HTML.
- Navy: HTTP 503과 upstream TLS certificate verification failure.

원문 문서명·페이지·지도 날짜·축척·투영·개별 지도 권리는 아직 확인하지 못했다.
오류 본문 SHA와 원본 문서 SHA를 구분했으며 후자는 전부 null이다.
요청별 증거와 구체적인 대안은 [DATA_SOURCE_REPORT.md](DATA_SOURCE_REPORT.md)에 있다.
다른 proxy, TLS 검증 해제, CI 중계로 접근 정책을 우회하지 않았다.

## 2. 12개 사건의 역사 검증

[EVENT_EVIDENCE_MATRIX.json](EVENT_EVIDENCE_MATRIX.json)은 V3의 12개 사건 장을
보존한다. curated 사건 날짜, 기존 도식 기준일, 미확보 원본 지도 날짜를 분리했다.
공식 원문을 새로 확보한 사건은 0개이며, 사건 날짜만으로 전선 좌표를 승인하지 않는다.
북진·중국군 참전의 시간 중첩과 10월25일/11월24일의 차이도 유지한다.

38선, 작전 화살표, 예정 방어선, 최대 진출선 복합도, 현재 DMZ/NLL을 해당 날짜의
관측된 실제 육상 전선으로 대체하지 않는다. 인천 교두보처럼 떨어진 구간은 임의로
본전선에 연결하지 않는다.

## 3. 기존 5개 도식과 신규 전선 비교

보존된 도식 날짜는 1950-06-25, 1950-09-01, 1950-11-24, 1951-01-04,
1953-07-27이다. 기존 FACT_DATA, geometry manifest 및 V3 파일은 변경하지 않았다.
새 전선은 0개이므로 실제 위치 차이·우열·오차 비교 수치는 산출하지 않았다.
기존 생성 PNG와 영상은 공식 지도 원문이 아니다.

## 4. 새 좌표와 원본 근거

역사 좌표를 추가하지 않았다. 대신 세 가지 독립 CPU 기능을 구현했다.

| 파일 | 실제 기능 | 완료 범위 |
|---|---|---|
| `source_acquisition.py` | HTTPS/기존 proxy·CA, 허용 host redirect, 크기·시간 상한, 원본 byte SHA, 덮어쓰기 금지, HTML 오류와 PDF 전송 구분 | 모의 전송 검사; 이번 원문 다운로드 성공 없음 |
| `georeference.py` | GDAL/OSR와 NumPy를 사용한 알려진 CRS의 affine 정합·독립 검수점·원본 pixel 중심·오차 기록 | SYNTHETIC 검사; 실제 지도 정합 없음 |
| `front_evidence.py` | 문서/페이지 raster/정합/추적/review 해시 결합, source pixel의 좌표 재계산, 부분 선의 GeoJSON 후보 | SYNTHETIC 검사; 실제 역사 geometry 승인 없음 |

원본 PDF SHA와 추출한 지도 raster SHA는 별개다. 페이지·추출 recipe를 결합하지만
실행하지 않은 PDF 추출을 재현했다고 표시하지 않는다. Manifest·원본·정합 보고서·
추적 pixel·검수 기록은 모두 함께 영구 보존해야 한다.

열린 선은 Polygon으로 닫거나 상대 세력 점령 면적을 만들지 않는다. MultiLineString은
불명확한 틈을 유지하며 나누고, 기존 Area Core의 선당 129점 한계는 원본 edge가
보존되는 연속 조각으로 처리한다. 원본을 임의 단순화하거나 좌표 사이를 보간하지 않는다.

## 5. 공간 정확도와 불확실성

정합 도구는 알려진 수평 CRS, 원본 축척·근거, 4개 이상의 비공선 fit 기준점,
3개 이상의 독립 검수점을 요구한다. GDAL pixel corner와 원본 pixel center의
0.5 차이를 명시한다. 좌표 순서는 EPSG:4326 `[longitude,latitude]`다.
검증 범위 밖 외삽은 거부하고 잔차·추적·역사 자료 불확실성을 분리한다.

이것은 한정된 affine 기술 후보 경로다. 투영법 불명·비선형 종이 왜곡 등 모든
역사 지도를 처리하는 완료된 자동 좌표화 시스템이 아니다. 작은 잔차는 실제 전선의
역사적 정확도를 증명하지 않는다. 현재 실제 지도에 대한 공간 오차 수치는 없다.

기술 후보의 출력은 항상 `TECHNICAL_CANDIDATE_REVIEW_REQUIRED`,
`runtimeAdmission=NOT_ADMITTED`, `historicalTruthVerified=false`다. 합성 Fixture는
명시적으로 SYNTHETIC이며 한국전쟁 자료로 등록하거나 렌더링하지 않는다.

## 6. 80초 장면 구성

기존 80초·30fps·2,400프레임과 12개 작업 범위를 보존했다. 12개 사건 장은
각 200프레임이고 작업 분할 경계는 사건 장 경계와 독립적이다.
발발 → 남하 → 낙동강 → 인천 → 서울 수복 → 북진 → 중국군 첫 교전 → 전선 남하
→ 재반격 → 교착 → 1951~1953 변화 → 정전 순서를 유지한다.
각 장의 날짜·전선 자료 상태는 evidence matrix와 기존 V3 STORYBOARD에 있다.
새 자료 없는 구간은 기존 기준일을 표시하는 도식 문맥이며 실제 점령선으로 표현하지 않는다.

## 7. Scene JSON 연결 상태

[SCENE_CONNECTION_AUDIT.json](SCENE_CONNECTION_AUDIT.json)은 원본 V3 계획의
SHA·12개 사건 장/작업 범위·2,400프레임과 데이터 matrix 정합을 확인한다.
**새 역사 자료의 runtime 연결은 0건**이다. 보호된 Scene JSON은 변경하지 않았다.

기존 Area Core는 열린 전선만 있는 상태를 지원하지만, 동결된 WAR planner와
long-area 계약은 영역+전선이 모두 있어야 한다. V3는 기존 5개 상태와 source closure를
검증하므로 새 GeoJSON을 옆에 두는 것만으로 활성화되지 않는다. 원본이 확보되면
새 데이터 프로필/adapter가 기존 Area Core를 선택하도록 연결하고, 별도로 검증된
점령 면적이 없으면 전선에서 면적을 추론하지 않는 확장 경로가 필요하다.
원본이 없는 현재는 사용되지 않는 runtime이나 전체 renderer 복사본을 만들지 않았다.

## 8. 변경 파일과 해결한 문제

새 `recovery/verified-front-data-v4/` namespace와 별도 CPU workflow만 추가했다.
원본·오류 SHA 혼동, PDF와 raster SHA 혼동, 반 픽셀/축 순서, 정합 잔차와 역사
정확도 혼동, 열린 선의 임의 폐합, 날짜가 다른 지도 오표시를 검증 단계에서 거부한다.
기존 FINAL·V4·카메라·전선·ASTRA·GPU 실행·FFmpeg·Dropbox·claim은 변경하지 않았다.

## 9. 무료 검사

새 기능만 검사한다. 기존 107개 V3 검사나 과거 168개 전체 검사는 반복하지 않았다.
실데이터 검사는 원본 미확보로 BLOCKED다. 새 전선의 SwiftShader draw/readPixels는
자료 연결 전이므로 SKIP이며, 기존 V3의 성공 증거를 V4 전선 검증으로 재사용하지 않는다.
실제 무료 CI `38855732760-1`에서 **74 PASS / 0 FAIL / 0 SKIP**였다.
이는 합성·새 데이터 계약 검사 수치이며, 실제 지도·새 전선 draw의 BLOCKED/SKIP과 다르다.
고정 V3 이미지의 UID/GID 1000·네트워크 차단·읽기 전용 컨테이너에서 실행했다.
CI의 source/workflow Secret Scan 0건, 기존 추적 파일 변경 0건을 확인했다.
최종 전체 산출물 scan은 CI 기록 안의 공개 진단 파일 content SHA 한 값을
`generic-api-key`로 탐지했다. 실제 파일을 다시 SHA-256 계산해 동일함을 확인했으며,
credential은 0건이다. 원본 CI 기록이나 scanner 규칙을 바꾸지 않고
[분류 근거](SECRET_SCAN_CLASSIFICATION.json)에 raw 1건/비밀 아님 1건을 남겼다.
[TEST_RESULTS.json](TEST_RESULTS.json)과 [실제 CI 증거](runs/38855732760-1/cpu.json)에 기록했다.

## 10. 기존 기능 보호

V3의 23개 source 해시와 원래 계획/도식 해시를 확인했다. 기존 추적 파일 수정은 0건이다.
새 도구에는 국가명·한국 좌표·전쟁 날짜 기반 엔진 분기가 없다. GPU 보안 검사나
저장소 권한 검사를 비활성화하지 않았다. GPU·영상 품질·외부 Dropbox 검증은 수행하지 않았다.

## 11. 신규 이미지

**새 태그·digest는 생성하지 않았다.** 검증된 새 전선의 실제 runtime 연결과 무료
draw 검증을 모두 통과한 경우에만 빌드하라는 데이터 gate가 충족되지 않았다.
CPU 도구를 넣은 이미지에 역사 재현 완료라는 이름을 붙이지 않았다.
기존 V3 이미지는 그대로 보존한다.

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:10f7cc1da15d5a94ddd5653c2a8d8b5f3658b8c0a0d9260cab729404d38c8deb
```

## 12. 미확보 자료와 구체적인 대안

공식 자료용 허용 도메인 요구를 기존 설정 초안에 추가했다. 현재 실행 환경은
restricted, allowed_hosts=[]이며 초안은 saved/requires_publish=true다.
환경 설정의 Publish는 아직 적용·성공으로 검증되지 않았다.

GovInfo 두 PDF와 IMHC/Truman 자료를 허용 설정 반영 후 우선 재시도한다.
Army CDN 거부와 Navy upstream TLS 오류는 단순 도메인 추가만으로 해결됐다고
가정하지 않는다. 공식 다른 배포본·공공 아카이브 또는 사용자가 적법하게 확보한
원문 파일이 대안이다. 문서 제목·페이지·지도 날짜·권리는 실제 확보 뒤 검토한다.

## 13. 실제 GPU 실행 조건

공식 원문과 검수된 좌표 → 데이터 adapter/Scene 선택 → 무료 실제 draw/readPixels
→ 새 후보 이미지와 독립 pull 순서다. 그 뒤에도 실제 계정 인증·요금·최대 비용·
시간·재시도·종료 정책과 사용자의 유료 실행 승인이 필요하다.
현재 작업은 gCube를 배포하거나 유료 GPU/API를 사용하지 않았다.

## 14. 재개 절차와 사용자 다음 행동

환경 설정에 저장된 공식 자료 도메인을 검토하고 Publish한 뒤 적용 상태를 확인한다.
동일한 차단 요청을 반복하지 않고 상태가 변경된 자료부터 재개한다. 예를 들어 GovInfo
원본을 수집할 때는 새 도구를 다음과 같이 사용할 수 있다. 이 명령은 현재 성공한 명령이 아니다.

```bash
python3 -B source_acquisition.py --url https://www.govinfo.gov/content/pkg/GOVPUB-D114-PURL-gpo111422/pdf/GOVPUB-D114-PURL-gpo111422.pdf --allowed-host www.govinfo.gov --output /PRIVATE_SOURCES/gpo111422.pdf
```

원본을 읽은 뒤 원문/지도 날짜·범례·권리·정합 근거를 기록하고,
`front_evidence.py --root /PRIVATE_SOURCES --manifest /PRIVATE_SOURCES/manifest.json`으로
기술 후보를 검사한다. 이 검사는 원문 판독·역사 검수·runtime admission을 대신하지 않는다.
기존 브랜치나 완료 영상을 초기화하지 않고 이번 체크포인트부터 이어간다.

판정은 원문 확보·역사 전선 연결이 미완료임을 유지한다. 실제 영상이나 FINAL을 승인하지 않았다.


## 원격 저장 및 판정

브랜치: `development/korean-war-verified-front-v4-20261016`.
Checkpoint A: `3ab504b`, 구현: `fc6017258e3390f68ff2bb646999930fdb52b0a0`,
CI 증거: `c12bd22baa9383e82f940ce3674745e11469c703`.
최종 보고서 저장 커밋은 이 파일의 Git 이력으로 식별한다.
필수 temp-only 파일은 0개다. 실제 원문은 없으며 모든 도구·계약·합성 검사·진단·재개 절차는 영구 저장한다.

판정: **VERIFIED_FRONT_DATA_V4_PARTIAL_SOURCE_ACCESS_REQUIRED**.
현재 유료 GPU 실행·새 후보 이미지·80초 MP4·FINAL 승격은 수행하지 않았다.
