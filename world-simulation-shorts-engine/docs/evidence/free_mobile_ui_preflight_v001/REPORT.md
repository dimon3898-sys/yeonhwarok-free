# Free mobile UI preflight

검사 시각: 2026-10-06T11:11:35.889409+09:00 (KST)

현재 UI의 필수 생성/승인/진행/복구/수정/다운로드 연결부는 구현되어 있다. 이번 검사는 소스만 확인했으며 실제 배포·로그인·서버 재개·새 MP4 생성·물리 휴대폰 접속을 실행하지 않았다.

인증서 28개 소스 SHA 일치: True. 기존 영상 파일은 읽지 않았다. UI/렌더러/서버/문서/검증 도구 소스는 변경하지 않았다.

## 실제 UI 범위

- **자연어 주제·길이·스타일·품질** — 구현: 주제 필수/최대3000자,20–3600초,4스타일,FAST/HIGH/CINEMA. 임의 주제 전체 지원은 플래너/GIS/모듈 게이트에 의해 제한됨. (web/index.html:28, web/index.html:29, web/index.html:30, web/app.js:405)
- **진행 속도와 오디오 선택** — 구현: FAST_PLUS 기본; FAST/NORMAL/CINEMATIC. TTS·자막OFF/BGM·SFXON. UI의 나레이션 파일 선택은 TTS를 끄며 사용권 확인 후 업로드. (web/index.html:31, web/index.html:32, web/app.js:405)
- **Story/Scene Plan 표시** — 구현: 훅,전체길이,장면목록/시간/장소/사건/카메라/조명/FACT구분/핵심장면/대본/검수/사용모듈/스코프가 명시된 렌더 예상. Story beats 전체는 별도 독립 화면에 표시하지 않음. (web/app.js:85, web/app.js:139, web/app.js:149)
- **정확한 기획 승인 후 렌더** — 구현: 전체게이트 passed+계획hash+최신버전+비활성job 조건. POST approve{plan_hash,version} 성공 후 POST render{version}; 기획생성만으로 render 없음. (web/app.js:184, web/app.js:337)
- **실제 진행 표시와 재접속** — 구현: 활성job 약2.2초 GET상태poll, 통신실패 시 반복중5초재시도; 화면재진입 visibilitychange 즉시status. 임의가짜진행률 없음. 처음 접속/수동불러오기 실패에는 자동 로그인/복구 없음. (web/app.js:218, web/app.js:238, web/app.js:437)
- **브라우저 닫기 후 작업 재개** — 구현: localStorage 마지막project ID, 내작업 목록, 서버에 지속되는job/디스크 체크포인트. UI는 서버 자체를 부팅하지 않음. 마지막 선택 historical버전은 localStorage에 따로 저장하지 않고 최신project로 복구. (web/app.js:75, web/app.js:209, web/app.js:439, web/index.html:20, RENDER_GUIDE.md)
- **실패한 단계 이어서 생성** — 구현: 실패상태 최신버전 resume버튼→정확계획 승인→render. 드라이버rawlog 기본접힘/완료Scene보존 안내. 실제 체크포인트 복구는 서버 구현에 의존. (web/app.js:238, web/app.js:337, web/app.js:420)
- **이전 버전과 부분 수정** — 구현: 버전목록·기획·완료출력 읽기, 이전버전 수정/승인금지. 자연어revise→영향Scene/Diff→별도명시승인→새버전render. 실제지원수정만 플래너가 허용. (web/app.js:196, web/app.js:346, web/app.js:423, web/app.js:432)
- **시네마틱 클립·외부 음성** — 구현: 권리확인 File POST /api/assets, clip삽입변경도 Diff/승인 구조. 타임스탬프와 의미검수/출처는backend. 파일45초 API 제한으로 큰 파일 업로드는 별도 실제검증 필요. (web/index.html:33, web/index.html:50, web/app.js:430, web/app.js:447)
- **실제 모바일 다운로드·재생** — 구현: 같은origin /download 실제첨부/무음/보고서/Scene파일; /media Range+playsinlinevideo. 전화가접근가능한HTTPS호스트는 UI자체가제공하지 않음. (web/app.js:292, web/app.js:309, web/index.html:57, tools/ui_end_to_end.mjs:244, tools/ui_end_to_end.mjs:333)
- **375px 레이아웃·접근성** — 구현: viewport-fit=cover,375/360반응형,min-width0,긴오류wrap,progress role/aria-live,입력label,하단safe-area,감소motion. 물리휴대폰 검증은 별개. (web/index.html:5, web/index.html:14, web/style.css)
- **인증 로그인·쿠키·사용자 분리** — 미구현: 인증화면/로그아웃/session expiry UI/CSRF토큰/계정별namespace 현재없음. APIcredentials same-origin이라 같은origin HttpOnly쿠키 wrapper와 호환. Shared owner auth로 제한; multi-tenant구현이라고 주장할 수 없음. (web/app.js:31, web/app.js:292, tools/ui_end_to_end.mjs:373)

## 새 배포에서 검증하거나 구현할 부분

- `NO_PUBLIC_ORIGIN_VERIFIED`: 이번 소스 검사에서 공개HTTPS주소,원격휴대폰접속,재부팅후지속호스팅을 실행/검증하지 않음.
- `NO_AUTH_E2E_OPTION`: 기존harness에는 login/cookie/storage-state 옵션 없음. 새 인증wrapper검증도구는 context 생성 직후 실제로그인 후 health/API/download 요청하고 로그인 비밀값을 증거에 저장하지 않아야 함.
- `FAST_INSPECT_RESOLUTION_CONFLICT`: harness --quality FAST의기획/승인 가능하나 inspectCompleted/playWholeVideo는1080×1920만허용. FAST실제540×960검증은새별도wrapper테스트에서계획quality기준규격으로검증해야함. 기존harness변경없이그대로FAST검사하면잘못실패함.
- `NO_AUTOMATED_RELOAD_OFFLINE_RETRY_SCENARIO`: 기존harness는enqueue후즉시종료하고complete검사를새실행으로수행. 같은375context reload/닫기·다시열기/임시statusGET실패/visibility회복/failedresume 검증은 별도추가필요.
- `SOURCE_ONLY_SHORT_JOB_LIMIT`: 기존UI/CLI 새계획 최소20초. --scene-only/--render-frames/--wait-complete는 없음. 짧은이미등록계획은 --approve-project로승인가능(전역 --duration은생략), enqueue후GET-only별도monitor. 단일Scene실제렌더QA fixture가필요하면부모가검증된내부계획을별도projectroot에등록;20초FAST는정직한프리뷰QA이며HIGH그래픽증거가아님.
- `DOC_DEFAULT_DRIFT`: 현재 index pace FAST_PLUS인데 USER_GUIDE/PRODUCTION_DEFAULT 문서설명은FAST. 인증배포대상현재UI기본값을FAST_PLUS로보존. 이작업에서문서/기본소스를고치지않음.
- `NO_SERVER_BOOT_BY_BROWSER`: reload/내작업복구는실행중서버를전제로함. 무료statichosting/GitHubPages만으로CPU렌더,상태파일,Range/API가작동하지않음.

## 원본 UI를 보존하는 인증 연결부

배포 전용 별도 로그인/인증쿠키 proxy 및 별도 검증도구만. 인증서의28파일·web/app.js·style.css·기존harness 변경금지.

UI/하위경로들은origin절대경로. HTTPS호스트루트에앱을공개하거나동일경로proxy. 앱을prefix경로에단순마운트하면static/API와sameorigin다운로드검사가깨짐.

로그인 HTML은별도wrapper가제공. 성공→같은origin 쿠키→원래 UI. 로그인화면과API401을구분해 API에HTML로그인redirect를반환하지 않음.

HttpOnly/Secure/SameSite쿠키, 같은origin nativevideo/Range/attachment에도 적용. 실제token값을 URL·localStorage·증거·스크린샷에저장하지않음.

wrapper에서인증및POST Origin검증을처리하여원본UI에CSRF헤더추가를요구하지않음. 인증이없는외부엔진포트를직접공개하지않음.

실제도달가능무료HTTPS런타임이없으면기존클라우드의허용된접근방법과GitHubdeliverable다운로드를구분해서제공;GitHub파일링크를작동중생성기처럼보고하지않음.

## 재사용할 도구

기존 도구는 375×812 Chromium, 실제 클릭, 정확한 plan_hash 승인 순서, 전체 재생, 첨부 Content-Disposition·전체 SHA, Range206, WebAudio 샘플, 가로넘침·JS오류를 기록한다. 새 로그인 wrapper의 테스트에서 이를 재사용하되 현재 도구에 없는 인증/재접속 기능은 별도 파일에 추가한다. FAST는 540×960이므로 기존 inspect의 1080×1920 assertion을 정직하게 별도 처리한다.

375px 기획만; 승인/렌더없음

```sh
node tools/ui_end_to_end.mjs --topic '서울에서 도쿄를 거쳐 싱가포르로 이어지는 민간 항공 경로' --duration 20 --pace FAST_PLUS --quality HIGH --base-url VERIFIED_ORIGIN --output-dir NEW_EVIDENCE_DIR
```

명시적으로 새 계획 승인·실제enqueue 후즉시반환

```sh
node tools/ui_end_to_end.mjs --topic SUPPORTED_TOPIC --duration 20 --quality FAST --pace FAST_PLUS --start-render --base-url VERIFIED_ORIGIN --output-dir NEW_EVIDENCE_DIR
```

이미등록된정확최신계획승인(20초미만QA계획도전역duration생략)

```sh
node tools/ui_end_to_end.mjs --approve-project PROJECT_ID --version VERSION --base-url VERIFIED_ORIGIN --output-dir NEW_EVIDENCE_DIR
```

NL부분수정Diff만;렌더없음

```sh
node tools/ui_end_to_end.mjs --revise-project PROJECT_ID --version VERSION --request 'Scene 2 카메라를 조금 빠르게 해.' --base-url VERIFIED_ORIGIN --output-dir NEW_EVIDENCE_DIR
```

명시적Diff승인·해당Scene새버전enqueue

```sh
node tools/ui_end_to_end.mjs --revise-project PROJECT_ID --version VERSION --request 'Scene 2 카메라를 조금 빠르게 해.' --approve-revision --base-url VERIFIED_ORIGIN --output-dir NEW_EVIDENCE_DIR
```

HIGH/CINEMA 완료된동일버전 전체재생/다운로드 SHA/Range(읽기전용)

```sh
node tools/ui_end_to_end.mjs --inspect-project PROJECT_ID --version VERSION --base-url VERIFIED_ORIGIN --output-dir NEW_EVIDENCE_DIR
```

모든 명령은 계획 예시이며 이번 읽기 전용 점검에서 실행하지 않았다. VERIFIED_ORIGIN은 실제 검증한 주소만 사용한다. 비밀값·인증 쿠키는 이 보고서에 저장하지 않는다.
