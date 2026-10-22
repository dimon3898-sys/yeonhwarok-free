# WORLD ENGINE 범용 입력·영상 연출 V2

**기술 판정: SOURCE_CHECKOUT_TECHNICAL_PASS. 영상 품질: USER_REVIEW_REQUIRED.**

기준 `b0d013832ee38571f9d3dfe685ce63f7083ba90f`에서 별도 브랜치
`development/universal-presentation-v2-20261022`로 작업했다. 실제 실행 코드는
원격 저장된 `002d90516551774aaf5740eb3968fdda07ed5600`이다.
기존 운영 이미지와 운영 화면은 변경하지 않았다.

## 실제 연결한 기능

| 항목 | 구현·실행 근거 | 남은 범위 |
|---|---|---|
| 한국어·영어 자연어 의도 | `presentation_prompt.mjs` → 기존 자료 검증기·Planner. 장면 범위, 날짜, 좌표, 경로, 연출 의도와 첨부 자료의 충돌 검사 | 제한된 문법과 첨부 자료 기반이며 자유로운 모든 문장을 이해하는 AI가 아니다. |
| 좌표 기반 지역 | `region_source.mjs`와 데이터 카탈로그. 기존 5개 지역 및 일본·호주 실제 draw | 실제 소스 범위·투영·해상도 제한을 적용한다. 없는 DEM·수심을 만들지 않는다. |
| 이동·확대·추적 | 기존 Camera V5와 reference camera 함수, 기존 Flow V2의 시간·경로 계산 재사용 | 마지막 키프레임이 가장 가까운 구도여야 한다. 회전·궤도·추적 중 가변 줌은 미지원이다. |
| 영토 색상·확장·축소 | 기존 Area V3를 원본 폴리곤·상태에 연결. 두 번째 장면의 이미 표시된 상태도 공개 Area API로 보존 | 자료에 없는 영역·사건·소유권은 생성하지 않는다. |
| 사건 강조 | 제공된 실제 위치에서 기존 표식 디자인을 지정 프레임 구간에 pulse | 새 이동 프로필의 지명·자막 raster 표시는 미지원이다. 요청하면 명시적으로 거부한다. |
| 장면·시간축 | 두 장면의 정확한 `[0,90)`, `[90,180)` 구간과 실제 CUT. 한 FFmpeg 스트림으로 합성 | CUT만 지원하며 dissolve를 구현했다고 표시하지 않는다. |
| Studio | 기존 로그인·Origin·CSRF·claim·분리 worker를 재사용한 인증 API 실행 | 기존 운영 textarea와 Docker 이미지에는 배포하지 않았다. |

실행 경로는 `자연어 + 제공 자료 → 검증/확인 요청 → 기존 Scene JSON →
소스·카메라 전체 범위 사전검사 → 기존 렌더 소비자 → FFmpeg`이다.
입력 계약·실행 가능한 예제는 `PRESENTATION_INPUT_CONTRACT.md`,
`SUPPORTED_INPUT_EXAMPLES.md`, `examples/*_NL.json`에 있다.

## 확인한 결함과 수정

- 두 번째 장면의 추적 지시가 첫 장면까지 적용되던 충돌을 장면 범위별로 분리했다.
- 같은 연도의 다른 날짜·불가능한 날짜·일치하지 않는 좌표·오래된 국가/위치 문맥을 조용히 통과시키던 새 어댑터 경로를 차단했다.
- 지도 준비 범위에 실제 이동 범위뿐 아니라 기존 엔진 초기화·분석 범위도 포함하도록 수정했다. 실제 소스 범위 검사는 유지했다.
- 새 어댑터의 숨겨진 텍스트와 원래 glyph 측정값 불일치를 수정했다. 지원하지 않는 표시 요청은 실패시킨다.
- Node/Chromium의 파생 카메라 계수 1ulp 차이는 같은 원본 키프레임을 기존 함수로 브라우저에서 다시 계산해 해결했다. 기존 canonical 검사를 제거하지 않았다.
- 영토 장면 전환 직후의 소실은 명시적 `PRESERVE_PROVIDED`와 기존 Area 공개 API로 해결했다. 경계 양쪽의 원본 영역·전선·색상 일치를 검사하며 시간 오프셋은 0이다.
- 캐시 변조·손상 및 재봉인된 부정확한 검증 기록을 실제 파일·소스·카메라 재검증으로 거부한다.

기존 Camera/Area/Flow/Event/Planner/렌더러·셰이더는 수정하지 않았다.
첫 미디어 감사의 잘못된 aggregate trace 가정은 `AUDITOR_SCOPE_CORRECTION.md`에
실패 기록과 수정 근거를 남겼다. 영상 재렌더링은 없었다.

## 검증 결과

| 검사 | 실제 결과 |
|---|---:|
| 기존 회귀 검사 | 298 PASS, FAIL/SKIP 0 |
| 자연어·JSON Schema | 85 PASS |
| 지역 소스·캐시·좌표 | 최종 44 PASS |
| 연출·카메라·준비 계약 | 40 PASS |
| 인증 Studio·소스·claim | 최종 동결 소스에서 36 PASS |
| 새 핵심 검사 합계 | 205 PASS |
| 입력 사례 행렬 | 17/17 기대 판정 일치: 5 허용, 12 정확히 차단 |
| 실제 지역 draw | 기존 5개 + 신규 2개, 7/7. 21개 실제 프레임, 카메라 630개 시점 비교 |
| 실제 Studio 영화 | 3개, 총 540프레임 전체 디코딩·PTS·위치·시간 검사 PASS |
| 보호 | 307개 및 기준 6,439개 SHA 일치, 기존 캐시 565개 변경 없음 |

실제 역사 일부 자료 사례는 `UNSUPPORTED/FAMILY_NOT_CONNECTED`, 필수 전선·통제
근거가 없는 사례는 `NEEDS_INPUT`으로 구분했다. 역사 자료가 부족한 장면을
가상 설정처럼 통과시키지 않았다. 상세 명령·실패 이력·로그는 `reports/`에 있다.

## 실제 출력

모두 **1080×1920, 30fps, 6초, 180프레임, H.264, 무음**이다.

| 영상 | worker 실측 시간 | 실제 영상 SHA-256 |
|---|---:|---|
| [유럽 항공 연결](public-review/UP2_AVIATION_EUROPE.mp4) | 173.830초 | `cec3447d1f2b932bc2c55de5156300194f30eb7ed806f6732fbfdde2fe53a8b8` |
| [남미 무역 연결](public-review/UP2_TRADE_SOUTH_AMERICA.mp4) | 190.467초 | `28befce9d5ff11d05e5f9f4e989e1d16b278b1489386710b8a06cc74bd7bf1dc` |
| [아프리카 가상 영토](public-review/UP2_FICTIONAL_AFRICA.mp4) | 171.308초 | `c831b90282022ce58b7112b06498018a4227830cbceca11866e9d7c99440caf6` |

[24개 실제 프레임 비교](public-review/STUDIO_THREE_TOPIC_CONTACT_SHEET.png).
항공·무역 연결은 제공된 현대 도시 좌표를 사용한 명시적 가상 연결이며,
실제 운항편·항만 운송 실적을 재현했다는 주장이 아니다. 영토 직사각형도
입력에 명시된 가상 영역이다.

모든 작업은 실제 모바일 로그인 → 인증 API → 중복 시작 차단 → 분리 worker
경로를 거쳤다. 브라우저·HTTP 서버 종료 뒤 완료했으며, 재접속도 같은 작업 ID를
유지했다. 실제 렌더 실패·재시도·중복 렌더링은 없었다.

## 시각 검수와 한계

540프레임 자동 검사는 `FRAME_AUDIT.md`와 `reports/FINAL_MOVIES_AUDIT.json`,
직접 본 프레임·contact page의 정확한 범위는 `VISUAL_OBSERVATIONS.md`에 있다.
기술 PASS는 최종 영상 품질 PASS가 아니다.

유럽 영상은 전체 카메라 범위를 덮는 기존 글로벌 RGB를 사용한다. 남미·아프리카는
기존 NE1 재질을 사용한다. 유럽 RGB의 부드러운 지표와 어두운 바다는 NE1·실제
DEM·수심과 같다고 주장하지 않는다. 실제 사용 소스·원본 픽셀·저작권은
`SOURCE_CREDITS.md`, `reports/SOURCE_RELEASE_AUDIT.md`에서 확인할 수 있다.

레퍼런스 65379는 이번 작업에서 실제 파일 SHA와 전체 디코딩을 확인했고,
기존 시간 흐름 감사도 재사용했다. 이번 세 주제는 레퍼런스와 사건·지리가
달라 같은 사건의 픽셀 재현이나 레퍼런스급 품질 합격으로 판정하지 않았다.

추가 유료 LLM·GPU·API·배포, NVIDIA 하드웨어 검증, 80초 제작, FINAL 승격은
모두 실행하지 않았다. 현재 배포 Studio에 새 기능이 들어갔다고 주장하지 않는다.

## 저장과 다음 행동

원본 FINAL·Candidate·영상·Scene·Asset·기존 캐시·작업 기록은 보존했다.
공개 receipt는 필요한 검증 필드만 제공하고, 원래 진단 기록은 변경 없이
비공개로 남겼다. 공개 파일의 HTTPS·HTTP 200·다운로드 SHA 검증은 최종
원격 저장본의 `reports/DOWNLOAD_VERIFICATION.json`에 별도 기록한다.

사용자는 세 영상을 검수하면 된다. GPU 실행이나 설정 변경은 필요하지 않다.
**USER_REVIEW_REQUIRED**에서 중단하며 사용자 승인 없이 유료 제작·80초·FINAL로
진행하지 않는다.
