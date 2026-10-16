# 한국전쟁 12단계 역사·공간 근거 검수

사용자가 지정한 12단계를 기존 자료와 대조했다. 사건의 날짜·순서와 해당 날짜의
정확한 전선 geometry는 별도 증거다. 이번 기록은 원래의 5개 도식적 snapshot을
그대로 보존하며, 나머지 단계의 전선·부대 위치를 만들어 채우지 않는다.

기계 판독 자료는 `history/CHRONOLOGY_12.json`, 기존 geometry의 출처·해시는
`history/EXISTING_GEOMETRY_MANIFEST.json`, 실제 공식 출처 접근 결과는
`history/OFFICIAL_RETRIEVAL_ATTEMPTS.json`에 있다. 기존 FINAL·renderer·camera·자료·
영상·이전 감사 기록은 수정하지 않았다. ASTRA 조사와 원래 전체 검사는 반복하지 않았다.

## 날짜 검수와 실제 접근 범위

기존 한국전쟁 자료에는 발발, 부산 교두보, 북진, 서울 철수, 정전의 다섯 날짜가
curated established-history 검토로 기록되어 있다. 별도 역사 참여 정책에는 중국군
첫 전투를 1950년 10월 25일로 구분한다. 정책은 10월 19일의 국경 통과와 첫 전투,
11월 하순의 대규모 반격이 다른 사건이라고 명시한다. 이 날짜 정책은 부대 좌표를
증명하지 않는다.

인천상륙 9월 15일과 서울 수복 9월 28일은 정립된 역사 연표에 근거한 curated
날짜로 기록했다. 이번 환경에서 공식 원문을 직접 받아 확인했다는 상태로 올리지
않았다. 넓은 진행 단계에는 정밀 일자를 붙이지 않고 월·연도 또는 근사적 phase
window를 사용한다. 기존 source가 `VERIFIED`라고 표기하더라도 그 검증 근거가
curated chronology인지, 실제 공식 본문 retrieval인지 구분해서 유지한다.

현재 proxy를 유지하고 TLS 검증을 켠 실제 공식 URL GET은 다음과 같이 차단됐다.

| 공식 URL | 실제 결과 | 원문 확보 |
| --- | --- | --- |
| `https://history.state.gov/milestones/1945-1952/korean-war-2` | HTTPS CONNECT `403 Forbidden` | 없음 |

이는 origin이 반환한 기사의 HTTP 상태가 아니다. proxy CONNECT 단계에서 차단되어
공식 본문 SHA는 null이다. 이전 자료의 U.S. Army와 Britannica 기록도 원래부터
본문 미확보/403 상태였으며, 이를 새 성공 증거로 바꾸지 않았다. 다른 proxy, TLS
검증 해제, GitHub Actions 우회 또는 대체 경로로 차단을 우회하지 않았다.

공식 원문 검증을 계속하려면 supported network 설정에서 `history.state.gov`,
`history.army.mil`, `www.history.navy.mil`의 HTTPS 접근이 필요하다. 네트워크
설정의 실제 반영을 확인한 뒤 원래 URL을 재시도해야 한다. 새 공식 본문이나 지도는
아직 수집하지 않았으며, 공식 원문 extract를 확보했다고 보고하지 않는다.

## 요청한 12단계와 공간 증거

| 단계 | 사건 | 날짜 표현 | 기존 geometry 근거 |
| --- | --- | --- | --- |
| 1 | 전쟁 발발 | 1950.06.25 | `START`, 같은 날짜의 도식 snapshot |
| 2 | 북한군 남하 | 1950년 6~8월, 근사 phase | 새 전선 없음. `START`·`BUSAN` 두 원본 사이의 도식 전환만 별도 허용 가능 |
| 3 | 낙동강 방어선 | 1950년 8~9월 | `BUSAN`의 원래 1950.09.01 snapshot만 있음 |
| 4 | 인천상륙작전 | 1950.09.15, curated reference | 상륙 경로·당일 점령선 없음 |
| 5 | 서울 수복 | 1950.09.28, curated reference | 당일 전선·시가전 geometry 없음 |
| 6 | 국군·유엔군 북진 | 1950년 9~11월, 근사 phase | `NORTH_ADVANCE`는 1950.11.24의 후반기 snapshot이며 phase 전체가 아님 |
| 7 | 중국군 참전 | 1950.10.25, 첫 전투 기준 | 당일 전선·중국군 실제 좌표 없음 |
| 8 | 전선 남하 | 1950년 11월~1951년 1월 | `NORTH_ADVANCE`·`SEOUL_WITHDRAWAL` 두 원본, 후자는 1951.01.04 |
| 9 | 국군·유엔군 재반격 | 1951년 상반기, 근사 phase | 새 1951년 반격 전선 없음 |
| 10 | 38선 부근 교착 | 1951년 중반 이후, 근사 phase | 교착 시작 시점의 별도 전선 없음 |
| 11 | 1951~1953 전선 변화 | 1951~1953년 | 이 기간의 국지 전선 변화 track 없음. 새로운 변화 애니메이션은 미허용 |
| 12 | 1953 정전협정 | 1953.07.27 | `ARMISTICE`, 단순화된 현재 경계로 표현한 근사 snapshot |

12개 사건 chapter가 12개 검증된 공간 상태를 의미하지 않는다. 각
`geometryEvidence`에는 원본 state ID, snapshot 날짜, 사건 날짜 일치 여부,
허용 사용법과 누락 증거를 기록했다. 원본 5개 geometry의 좌표·순서·정밀도는
변경하지 않았다. 정전 snapshot은 측량된 1953년 군사분계선이 아니다.

특히 북진 phase와 중국군 참전은 시간이 겹친다. 11월 24일 북진 snapshot을
보여준 뒤 중국군이 처음 참전했다고 설명하면 10월 25일 첫 전투와 모순된다.
사건 phase와 snapshot 날짜를 분리하고, 10월 25일 사건에 미래의 11월 24일
전선을 당시 전선처럼 사용하지 않아야 한다. `latestPrecedingSnapshotRef`는
이미 존재하는 날짜상 선행 snapshot만 뜻하며 당시 실제 전선의 인증이 아니다.
지도에 예전 snapshot을 유지한다면 그 snapshot의 날짜가 계속 보여야 한다.

검토한 presentation 정책은 6번 chapter에서 9월 29일~10월 24일을 **편집상 소개
구간**으로 사용하되 9월 1일 `BUSAN` snapshot을 날짜 표시와 함께 유지한다.
이 구간이 북진 전체 기간이라는 뜻은 아니며 북진은 11월까지 계속되었다고 구분한다.
7번 중국군 첫 전투 설명에서도 같은 이전 snapshot의 날짜를 유지한다. 8번에서
비로소 날짜를 명시한 11월 24일 `NORTH_ADVANCE`와 1월 4일
`SEOUL_WITHDRAWAL` 두 원본을 사용한다. 기존 날짜의 지도와 사건 chapter의 날짜는
각각 보이며, 없는 당시 전선을 대체 인증하지 않는다.

`history/AREA_OWNERSHIP.json`은 원래 자료의 held-core 의미를 area ID별로 연결한다.
발발 시점의 `AREA_START_0`은 ROK, 이후 네 원본은 ROK/UN의 도식적 held core다.
`PRIMARY`라는 shader role만 보고 세력을 추정하지 않는다. 이 polygon의 바깥이
모두 상대 세력 점령지라는 증거는 없으므로 enemy complement를 만들어 칠하지
않는다. 이 소유 의미 또한 정확한 전체 군사 통제나 실제 국가별 부대 좌표가 아니다.

원래 두 snapshot 사이의 도식적 전환은 실제 일별 점령선을 관측했다는 뜻이
아니다. 누락된 상륙·재반격·국지 전선·부대 이동을 날짜나 사건 제목만으로 생성하지
않는다. 날짜 근거 부족과 geometry 부족은 각자 공개하고, 적합한 범위만 사용한다.

## 남은 검증과 실행 가능한 해결책

현재 상태는 **curated chronology metadata와 기존 5개 도식 geometry 사용 가능,
공식 원문 직접 검증 및 추가 전선 geometry는 미확보**다. 이를 공식 지도 기반의
정밀한 12단계 전선 재현이나 실제 부대 이동 증거로 표시하면 안 된다.

공식 원문 접근이 열리면 발발·인천·서울·중국 참전·1951년 교착·정전의 날짜를
각 원문과 대조하고 URL, retrieval 시각, 실제 응답, SHA, 짧은 extract를 남긴다.
날짜가 확인되어도 추가 geometry를 자동 생성하지 않는다. 공식 상황도나 허가된
전선 vector가 확보되어야 날짜별 geometry의 출처·범위·정확도를 별도로 검토할 수 있다.
공식 원문 파일을 사용자가 직접 제공하는 방식도 가능하지만 실제 파일과 해시를
검사한 후에만 source 상태를 갱신한다.

이 작업에서 gCube 배포, 유료 GPU 실행, 80초 실제 영상, 외부 Dropbox 전달이나
영상 품질 PASS는 수행하거나 선언하지 않았다. 필수 temp-only source 파일은 0이다.
