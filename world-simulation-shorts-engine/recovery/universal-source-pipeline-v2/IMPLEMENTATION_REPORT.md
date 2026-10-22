# G2/G3 범용 연결 결과 — USER_REVIEW_REQUIRED

**범용 연결의 실제 픽셀 검증은 완료했다. 인천의 역사적 양측 통제면 검증은 미완료이며 G3는 실행하지 않았다.**
이번 영상은 다른 지역·주제의 명시적 `SYNTHETIC DEMO`다. 지형 재질 경계가 보이므로 최종 영상 품질은
`NEEDS_REWORK`이며, 기술 PASS를 역사 PASS 또는 사용자 승인으로 계산하지 않는다.

## 기준과 접근

- 기준: `e6ff697348a8e63c9308d7b4546682cbc6620c96`, 기존 G1 고정 결과 `b97f9aaa6d58d01566c17555ae4abbfd032c6386`.
- 새 분기: `development/universal-source-pipeline-20261022`; 새 namespace만 변경했다.
- 최신 G2/G3 지시서 전체와 기존 동일 SHA ASTRA MASTER를 읽었다. 새 대형 ASTRA evidence ZIP은 도구의
  32MiB 전송 제한으로 열지 못했다. 원본 ZIP을 읽었다고 주장하지 않고 기존 개별 Git 증거를 사용했다.
- 원본 65422와 기존 G1은 정확한 SHA로 식별했다. 64306 원본은 접근 불가이며 이전 의미 분석을 새 직접
  영상 비교로 표시하지 않았다. 자세한 파일별 접근 증거는 `reports/MASTER_ACCESS.json`에 있다.

## 실제 수정과 연결

수정 전 `PREFLIGHT_PATH_AUDIT.json`에 16개 기존 호출 경로·함수·라인을 조사했다. G1의 scalar/V4
입력을 다른 역사 Scene으로 바꾸는 대신 새 source Scene family를 기존 Studio Controller에 선택형으로
연결했다. 기존 Planner와 G1·다른 운영 입력은 기존 경로에 위임한다.

| 항목 | 결과 |
|---|---|
| 입력/계약 | 구조적 JSON Schema 및 서버 INDEX·출처·원본 geometry SHA 검사 |
| 역사 자료 | 실제 원문 PDF의 8개 진지선·29개 cubic 명령을 페이지 좌표 그대로 입력에 연결 |
| 통제면/전선 | 기존 SourceRegistry·GEOS·Area 검증기 재사용. 동일 field/frame의 owner/unknown/contested/sharedFront 소비 |
| 카메라 | 기존 Camera V5의 실제 브라우저 계산값. REGIONAL 입장 조건 유지 |
| 실제 렌더 | 기존 native map factory, Area V3, Marker, Glyph, FFmpeg 사용 |
| 작업 운영 | 기존 관리자 인증·Origin·CSRF·ProcessGuard 재사용. 별도 claim·detached worker·중복 방지 |
| 입력 보존 | 중립 source ZIP 1,087개 payload·SHA·안전 복원; 필수 temp-only 0 |
| 미지원 입력 | 알 수 없는 필드 거부. 비어 있지 않은 사용자 annotation/audio 슬롯은 명시적 차단 |

기존 전체 렌더러·카메라·셰이더·Line Engine을 복제하거나 새로 만들지 않았다. 원본 좌표·수치를
정밀한 것처럼 변경하지 않았다. 국명·한국전쟁 조건문을 핵심 연결 코드에 추가하지 않았다.
DEMO 지역과 가상 구역 recipe는 fixture 데이터이며 실제 전쟁·점령·오염 사실이 아니다.

실제 실행에서 확인한 네 연결 오류를 해결했다.

1. 브라우저가 `18.0`을 `18`로 직렬화하면 동일 숫자도 거부하던 비교 수정. bool은 숫자와 계속 구분한다.
2. 동일 Camera V5의 Node/Chromium 산술 차이를 문자열 일치로 거부하던 비교 수정. 최대 실측 차이는
   약 `6.57×10⁻¹³`픽셀. ≤256 ULP **및** ≤10⁻⁹픽셀을 동시에 요구하며 브라우저 V5 상태로 그린다.
3. 새 준비 코드가 기존 measured Layout API 버전명을 바꾸던 결함 수정. 원본 프로필을 그대로 보존한다.
4. GEOS의 명시적 빈 Polygon `[[]]`를 비어 있지 않은 polygon으로 그리던 결함 수정. 빈 상태만 건너뛰고
   잘못된 비어 있지 않은 도형을 숨기지 않는다.

실패했던 작업·claim은 보존했다. source ZIP 수정은 native 계획과 전이 SHA 3파일만 바뀌었으며
1,084개 payload, GeoJSON 541개 및 역사 파일 2개는 바이트 동일하다. 세부 증거는 `STUDIO_ATTEMPTS.json`,
`NODE_CHROMIUM_CAMERA_NUMERICS.json`, `NATIVE_FACTORY_SMOKE.json`, `FIXTURE_REVISION.json`에 있다.

## 역사 G2 판정

기존 공식 PDF 3종의 SHA를 검증했고 출처 원장 4항목·원문 인용 7개를 기록했다. 상륙은 1950-09-15,
원문 지도 진지선은 15일 밤·16일 밤이다. 서울 수복 28일과 환도 행사 29일을 구분했다.
날짜 확인을 해당 날짜의 지리 좌표·양측 점령 영역 확보로 취급하지 않는다.

원본 진지선은 `PDF_PAGE_POINTS_TOP_LEFT`에 있으며 독립 지리 기준점 0개, 원본 CRS/datum과 지리 변환·잔차는
미확인이다. 양측 owner masks도 없다. 작전 BHL·상륙 화살표·도시 채움·현대 해안선을 통제면으로 사용하지 않았다.

따라서 `G2_FULL_AREA=BLOCKED`, 지리적 `VERIFIED_LOCAL_ONLY`도 미승인, `G3_HISTORICAL=NOT_RUN`이다.
현재 새 pixel consumer도 SYNTHETIC 전용이다. 자료가 생겨도 검증된 역사 consumer 입장 검사와 비영점 전역
프레임 소비를 별도로 확인해야 한다. 전역 [600,800) 입력이 실제 렌더됐다는 주장은 하지 않는다.

필요한 후속 근거는 날짜별 source-qualified 양측 통제면/명시적 unknown·contested, 해안 정합, 독립 기준점,
원본 기준·변환법·잔차·불확실성이다. 없는 상대 영역을 보완하거나 부분 진지선을 해안에 닫아 만들지 않는다.
현재 자료와 정확한 누락은 `HISTORY_READINESS.md`, `HISTORY_G2.json`, `HISTORICAL_PIPELINE_PREFLIGHT.json`에 있다.

## 실제 6초 DEMO와 시각 판정

- 실제 Studio HTTP 인증 → preflight → submission → start를 거쳤다. 중복 터치와 Controller 재연결은 동일
  작업 `studio-8975377b03cbcc47a2b0e0ce0981d4dc`를 반환했다. 브라우저·HTTP 연결을 닫은 후에도 worker가 완료했다.
- 캡처 코드 체크포인트: `1b415a84681e7f2a680d7f2ac2cd9705c9556fad`. 승인 입력·캡처·현재 adapter 해시 5개 일치.
- 1080×1920, 30fps, H.264, 6초, 신규 180프레임, 무음. 실제 SwiftShader이며 NVIDIA가 아니다.
- 캡처·인코딩·전체 디코딩 194.385초. 렌더 완료 상태 194.97초. NVIDIA 성능·요금 추정치로 사용하지 않는다.
- MP4 SHA-256: `39c7fd94af3a228bb66b7543aadee843bdd1a4443ba436e858b21327b70abcca`.
- 프레임 90 같은 입력의 추가 3개 ablation draw에서 전선 기여 1,774픽셀, 영역 색상 기여 30,405픽셀.
  ALL_ON 재그리기 raw SHA는 원래 프레임 90과 정확히 같다. 영상에는 원래 180프레임만 넣었다.
- owner/shared-front geometry는 인접 105구간에서 변했다. 카메라 폭 기준 최대 1.5배 확대·중심 이동 1.4142°.
  실제 V5 소비·동일 clock·LOCAL guard·GL·표식/예약 Safe Area 검사는 180/180 통과했다.
- 실제 MP4를 디코딩한 0.5초 간격 12시점과 원본 PNG를 육안 검토했다. 색상·공유 전선 변화는 보이나
  지역/global 지형의 직사각형 재질 경계가 뚜렷하다. CONTROL_OFF에도 남는다. **영상 품질 NEEDS_REWORK**다.
- 가상 격자 경계는 원래 작성된 기술 fixture이며 실제 해안·점령선이 아니다. G1의 상세 재질·국기·회전과
  동등한 스타일을 달성했다고 주장하지 않는다. 64306 원본 픽셀 비교·실물 휴대폰 재생은 미실행이다.

원본 7장 PNG, 동일 프레임 ablation 3장, 비교 PNG, 실제 PNG 컨택트시트, MP4 디코딩 컨택트시트를 보존했다.
이미지 생성 AI·기존 영상 반복·가짜 WORLD ENGINE 프레임은 사용하지 않았다.

## 검사와 보호

- 새 변경 범위 집중 검사 **52/52 PASS**: Python 35, native 준비 8, 카메라 수치 6, 빈 도형 3.
  구조적 Schema 예제 2종도 검증했으며 이 결과 자체는 렌더 승인 조건이 아니다.
- 기존 보호 소스 307개 / manifest 318항목 변경 0건. 기존 G1 namespace 변경 0건.
- 기존 G1 raw·PNG 150/150과 공개 8파일 SHA 재확인. G1을 다시 그리거나 튜닝하지 않았다.
  기존 encoded MP4는 원본과 byte/pixel exact가 아니라는 이전 한계도 그대로 유지한다.
- Secret 패턴 발견 0건, source ZIP 실제 복원/readback PASS, 필수 temp-only 0건.
- 기존 전체 104/151/233 검사, GPU 진단, 데이터 수집·개발을 반복하지 않았다.
- 유료 GPU, 기존 워크로드 조작, 신규 운영 이미지 배포, 전체 80초 제작, FINAL 승격을 수행하지 않았다.

## 다음 실행 지점

공개 결과·출처·계약·코드·검증은 이 분기에 저장한다. 고정 commit 다운로드의 HTTP 200·실제 다운로드 SHA는
별도 `DOWNLOAD_VERIFICATION.json`에 기록한다. 링크 대상 commit은 artifact checkpoint이며 후속 보고 commit과
달라도 동일 고정 파일을 가리킨다.

현 상태: `G2_PARTIAL_SOURCE_AND_GENERIC_RENDER_VERIFIED / G2_FULL_AREA_BLOCKED / G3_NOT_RUN / USER_REVIEW_REQUIRED`.
DEMO는 검수 자료이며 인천 역사 영상 대체물이 아니다. 사용자 최종 품질 승인이나 유료 실행 승인을 요청한
것으로 간주하지 않는다. 다음 작업은 누락 근거·재질 경계 해결을 분리해 진행해야 하며, 역사 게이트를
충족하기 전 G3·80초·FINAL로 넘어가지 않는다.
