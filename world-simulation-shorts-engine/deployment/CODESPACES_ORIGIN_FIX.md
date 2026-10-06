# 기존 Codespace 로그인 Origin 수정

동일 Codespace의 공개 HTTPS 주소를 서버에서 확인하고, 로그인뿐 아니라 모든 변경 API에 같은 Origin 검사를 적용한다. owner-code 인증과 승인된 생성기·렌더러·프로젝트·캐시·체크포인트는 유지한다.

## 원인과 변경

기존 `RequestPolicy`는 CLI로 전달된 정적 공개 주소만 허용했다. 시작 helper는 `CODESPACE_NAME`과 `GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN`이 모두 있을 때만 그 주소를 전달했고, 이미 실행 중인 서버는 HTTP 응답이 정상이라는 이유만으로 재사용했다. 공개 주소가 빠지거나 이전 프로세스가 남으면 올바른 Codespaces HTTPS Origin도 `INVALID_ORIGIN`으로 차단될 수 있었다. 프록시의 `X-Forwarded-Host`·`X-Forwarded-Proto` 처리도 없었다. 실행 중인 사용자의 Codespace 환경변수나 원본 프록시 헤더는 이 작업환경에서 직접 읽지 못했으므로, 그 중 어떤 경로가 실제 발생했는지는 단정하지 않는다.

서버 자체가 신뢰하는 환경변수 `CODESPACE_NAME`과 앱 포트에서 `https://<현재 Codespace 이름>-7860.app.github.dev` 하나를 구성한다. forwarding-domain 변수가 없거나 비어 있으면 공식 `app.github.dev` 도메인을 사용한다. 요청 Origin이나 프록시 헤더를 보고 새로운 주소를 허용 목록에 추가하지 않는다. 다른 Codespace·포트·도메인·HTTP Origin은 허용하지 않는다. Codespaces 밖의 명시적 HTTPS 공개 주소와 localhost 개발 방식은 유지한다.

공개 Host를 그대로 전달하는 경우와 Host가 localhost로 바뀌는 프록시 모두 처리한다. X-Forwarded-Host가 있으면 이미 설정된 정확한 HTTPS authority와 일치해야 한다. X-Forwarded-Proto가 있으면 모순·잘못된 값은 차단한다. 프록시 메타데이터 일부만 있거나 없어도 설정된 HTTPS Origin만 사용할 수 있다. 중복·쉼표 목록·사용자정보·경로·질의문자열 등이 포함된 주소 헤더는 거부한다. DNS 대소문자와 HTTPS 기본 포트443은 정규화한다. Docker bridge peer IP는 인증을 우회하는 근거가 아니다.

`Secure` 쿠키와 HSTS는 검증된 요청의 HTTPS 여부에 따라 적용한다. 따라서 Codespaces HTTPS 쿠키는 Secure·HttpOnly·SameSite=Strict를 유지하고, 같은 서버의 로컬 HTTP CLI도 사용할 수 있다. 누락·null Origin은 변경 요청에서 여전히403이며, CORS wildcard나 Referer 대체 허용은 추가하지 않는다.

## 기존 Codespace에 적용

현재 Codespace 이름은 **solid-space-fishstick**이다. 휴대폰에서는 [명령 입력 없는 기존 Codespace 자동 시작](CODESPACES_MOBILE_AUTOSTART.md)에 따라 최초 한 번 **Source Control → … → Pull**, 그다음 같은 환경의 **Stop → Start → Ports 7860**을 사용한다. 이후 재시작은 자동 main 반영·서버 준비를 수행한다. 터미널 명령을 입력할 필요가 없다.

Fast-forward가 불가능하면 자동 reset·stash·덮어쓰기를 하지 않는다. 변경된 파일은 그대로 보존하고 Git 충돌 원인을 확인한다. refresh는 해당 상태 폴더와 포트에 정확히 연결된 자기 서버만 정상 종료 신호로 갱신한다. 다른 프로세스나 진행 중인 작업을 강제 종료하지 않는다. 기존 owner-code와 세션·프로젝트 상태를 유지하며 새 Codespace나 컨테이너 재빌드가 필요하지 않다.

작업 상태 검사는 신호 직전에 다시 수행하지만 새 API 작업 접수와 원자적으로 잠기지는 않는다. 그 짧은 사이 작업이 접수되면 기존 정상 종료·checkpoint 복구 절차로 완료 Scene과 재개 상태를 보존한다. 진행 중 작업이 확인되면 갱신을 거부하며 강제 종료는 사용하지 않는다.

현재 관리형 작업환경의 GitHub Codespaces API 요청은 Forbidden이었다. 원격 저장소 반영과 사용자의 실행 중인 Codespace checkout·프로세스 업데이트는 별개다. 브라우저 새로고침만으로 아직 내려받지 않은 서버 코드를 자동 적용했다고 주장하지 않는다.

## 검증

앱 폴더에서 다음 명령은 격리된 fixture만 사용하고 영상을 렌더하지 않는다.

```sh
python3 -m unittest tests.test_codespaces_origin tests.test_codespaces_startup tests.test_mobile_deployment_security tests.test_mobile_deployment_jobs tests.test_mobile_production_cli tests.test_mobile_resume_evidence -v
```

변경 API 10종: 로그인·로그아웃, 프로젝트 생성·승인·렌더 접수·수정 미리보기·외부 클립, 수정 승인, 자산 업로드, 작업 취소. 각 경로에서 외부·다른 Codespace·다른 포트·HTTP·null·누락·위장 suffix Origin을 본문 읽기와 인증/상태 변경 전에 차단한다. 정상 Codespaces Origin은 각 기능의 dispatch까지 검증하며, renderer/worker는 모의 함수로 실제 실행을 막는다.

실제 Chromium의375px 화면에서 로컬 HTTP listener를 HTTPS Codespaces 프록시 형태로 연결해 폼 로그인303, 브라우저가 생성한 정확한 Origin, Secure·HttpOnly·SameSite=Strict 쿠키, 인증 세션, 로그아웃을 확인했다. 이 재현은 외부 Codespace에 실제 접속하거나 실제 휴대폰에서 검증한 결과가 아니다. 재현 도구의 redirect interception 한계를 피하기 위해 logout 검사는 redirect=manual로 수행했다.

검증 수치·원본 SHA 보존·재시작 smoke 결과는 함께 저장된 `validation/codespaces_origin_fix.json`을 확인한다. 이번 수정에서 영상 생성·MASTER/75초 재렌더는 수행하지 않았다.
