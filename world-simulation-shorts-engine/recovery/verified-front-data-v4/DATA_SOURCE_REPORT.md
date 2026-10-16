# V4 공식 전선 자료 확보 기록

이 문서는 `evidence/INITIAL_ACCESS.json`,
`evidence/HTTP_ERROR_CLASSIFICATION.json`, `evidence/OFFICIAL_ALTERNATIVES.json`에
기록된 실제 요청만 보고한다.
기준은 `1c45284bf9c531cba12707cdad6516f2e72fa638`이며 기존 V3 원문·계획·도식
좌표·렌더러·영상·이미지·claim은 변경하지 않았다.

## 실제 확보 상태

사용자가 정확한 URL을 제공한 항목은 **7개**다. Army 2개, GovInfo PDF 2개,
IMHC, Navy, Truman 각 1개다. 여기에 실제 접근 기록이 있는 공식 NARA·AWM
대체 조사 진입점 2개와 공식 CMH 직접 PDF 대안 2개를 더해
`SOURCE_CATALOG.json`은 11개 항목을 기록한다.
사용자의 검색 설명과 URL 경로는 실제 문서 표제·지도 날짜·페이지를 입증하지 않는다.
그 값은 원문을 읽기 전까지 null이다.

| 항목 | 실제 기록 | 역사 원문 확보 |
| --- | --- | --- |
| Army commemorative brochures | HTTP 403. 후속 오류 본문은 CDN `Access Denied` HTML | 없음 |
| Army brief summary | 공식 대안 요청에서 HTTP 403, CDN `Access Denied` HTML | 없음 |
| GovInfo `gpo111422` PDF | 관리 proxy의 HTTPS CONNECT 403 | 없음 |
| GovInfo `gpo84815` PDF | 같은 호스트 CONNECT 거부가 확인되어 요청 반복하지 않음 | 미실행 |
| IMHC `archvSeq=1000003314` | 관리 proxy의 HTTPS CONNECT 403 | 없음 |
| Navy map-list | HTTP 503. 오류 본문은 upstream TLS certificate verification failure | 없음 |
| Truman `m99` | 관리 proxy의 HTTPS CONNECT 403 | 없음 |
| NARA Korean War 조사 진입점 | 관리 proxy의 HTTPS CONNECT 403 | 없음 |
| AWM82 소장기록 진입점 | 관리 proxy의 HTTPS CONNECT 403 | 없음 |
| Army legacy `CMH_Pub_19-6.pdf` | 공식 대안 요청에서 HTTP 403, CDN `Access Denied` HTML | 없음 |
| Army legacy `CMH_Pub_20-2-1.pdf` | 공식 대안 요청에서 HTTP 403, CDN `Access Denied` HTML | 없음 |

위 오류는 같은 원인으로 합치지 않는다. CONNECT 403은 해당 원본 서버가 반환한
기사/PDF의 HTTP 상태가 아니다. Army의 CDN 거부 응답도 지도 원본이 아니다.
Navy의 503은 위 오류 본문에서 upstream 인증서 검증 실패가 관찰된 상태이며,
원본 페이지를 정상 확보한 상태가 아니다. TLS 검증 해제는 해결책으로 사용하지 않는다.
두 CMH 파일명은 시도한 URL의 식별자일 뿐 실제 문서명을 확인한 근거가 아니다.
두 번째 GovInfo URL은 실제 요청을 보낸 실패 사례로 집계하지 않는다.

오류 본문의 SHA는 진단 무결성만 증명한다. `originalSHA256`으로 재사용하지 않는다.
현재 새 역사 원문·지도 이미지·검증된 신규 전선 좌표의 개수는 모두 0이다.
추가 공식 다운로드 대안은 별도 접근 증거와 원문 검토를 통과한 경우에만 이 기록과
구분하여 승격할 수 있다.

## 12개 사건과 기존 화면의 관계

`EVENT_EVIDENCE_MATRIX.json`은 실제 V3 `eventChapters` 12개를 그대로 참조한다.
80초·30fps·2,400프레임이며 각 사건의 반열린 범위는 다음과 같다.

| 사건 | 프레임 범위 | 기존 도식 문맥 |
| --- | --- | --- |
| 발발 | [0, 200) | `START`, 1950-06-25 |
| 북한군 남하 | [200, 400) | `START`, 1950-06-25 |
| 낙동강 방어선 | [400, 600) | `BUSAN`, 1950-09-01 |
| 인천상륙 | [600, 800) | `BUSAN`, 1950-09-01 |
| 서울 수복 | [800, 1000) | `BUSAN`, 1950-09-01 |
| 국군·유엔군 북진 | [1000, 1200) | `BUSAN`, 1950-09-01 문맥 |
| 중국군 첫 교전 | [1200, 1400) | `BUSAN`, 1950-09-01 문맥 |
| 전선 남하 | [1400, 1600) | `NORTH_ADVANCE`, 1950-11-24 → `SEOUL_WITHDRAWAL`, 1951-01-04 |
| 국군·유엔군 재반격 | [1600, 1800) | `SEOUL_WITHDRAWAL`, 1951-01-04 문맥 |
| 38선 부근 교착 | [1800, 2000) | `SEOUL_WITHDRAWAL`, 1951-01-04 문맥 |
| 1951~1953 변화 | [2000, 2200) | `SEOUL_WITHDRAWAL`, 1951-01-04 문맥 |
| 정전 | [2200, 2400) | `ARMISTICE`, 1953-07-27 |

이는 장면 내용이나 새 전선을 추가한 표가 아니다. 사건 날짜, 이전 도식의 snapshot
날짜, 새 원본 지도의 기준 날짜는 서로 다른 필드다. 마지막 값은 현재 전부 null이다.
기존 화면의 snapshot 날짜와 도식 한계를 계속 표시해야 한다. 보유한 5개 snapshot의
원본 SHA도 matrix에 보존했다. 기존 자료의 curated 연표 검토를 공식 원문 직접 검증으로
승격하지 않았다.

북진 단계와 중국군 참전은 시간이 겹친다. 중국군 첫 교전 1950-10-25에 미래의
1950-11-24 전선을 당시 실제 전선인 것처럼 보여줄 수 없다. 기존 V3는 이를 피하려고
6·7번째 사건에 이전 날짜를 표시한 도식 문맥을 유지한다. 새 지도 확보 후에만 대체
가능성을 판정한다.

## 새 자료가 확보되면 필요한 검수

1. 원본 문서/이미지 전체를 저장하고 URL·실제 응답·retrieval 시각·길이·SHA를 기록한다.
2. 실제 문서명, PDF 페이지 인덱스와 인쇄 페이지, 지도 표제·기준 날짜·범례를 읽는다.
3. 관측 접촉선, 작전 단계선, 예정 방어선, 이동 화살표, 최대 진출 범위의 의미를 분류한다.
4. 권리·라이선스와 원본 보존/파생 좌표의 허용 범위를 검토한다. 정부 도메인만으로
   모든 첨부 지도의 권리가 동일하다고 가정하지 않는다.
5. 기준점·투영법·오차·추적 근거를 `ARCHIVAL_DIGITIZATION_CONTRACT.md`에 맞춰 기록한다.
6. 확인한 구간만 신규 GeoJSON 버전으로 추가한다. 불명확한 부분을 연결해 전체 점령
   polygon이나 상대 세력 보완 영역을 만들지 않는다.

접근 해결은 지원되는 네트워크 설정을 반영한 뒤 해당 원본 URL을 재확인하거나, 공식
대체 다운로드/공공 아카이브, 사용자가 적법하게 확보한 원문 업로드 순서로 진행한다.
단순 호스트 별칭·다른 proxy·TLS 검증 해제·CI 중계로 접근 정책을 우회하지 않는다.
같은 실패를 근거 없이 반복하지 않으며, 미실행 URL과 별도 대안의 결과는 새 증거로 남긴다.

이 자료 기록만으로 신규 이미지 등록, 실제 NVIDIA 렌더링, 80초 MP4, Dropbox 외부 전달,
영상 품질 또는 FINAL 승격을 통과했다고 주장하지 않는다.
