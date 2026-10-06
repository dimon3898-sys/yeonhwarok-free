# 기존 Codespace: 휴대폰에서 자동 업데이트·시작

대상은 기존 **solid-space-fishstick**이다. 새 Codespace를 만들거나 기존 환경을 삭제하지 않는다. 생성기·렌더러·자산·영상·프로젝트·캐시·체크포인트는 변경하지 않는다.

## 최초 한 번만 적용

1. [Codespaces 목록](https://github.com/codespaces)에서 기존 **solid-space-fishstick**을 브라우저로 연다. 편집기의 **Source Control**(가지 모양 Git 아이콘) → **… → Pull**을 누르고 완료를 기다린다. 저장소가 여러 개면 `yeonhwarok-free`를 선택한다. **Sync Changes는 사용하지 않는다**: Pull에 이어 Push도 수행하기 때문이다. 로컬 변경·충돌 경고가 나오면 파일을 버리거나 강제 덮어쓰지 않는다.
2. 같은 Codespace를 **Stop codespace → 이름을 눌러 Start → Ports의 7860 / Private 열기** 순서로 연다. 기존 owner-code로 로그인한다.

터미널 명령·새 Codespace·재빌드·새 Secret은 필요하지 않다. 이후에는 **Stop → Start → 7860 열기**만 사용한다.

**최초 Pull이 필요한 이유:** GitHub의 Stop/Start는 원격 main을 자동 다운로드하지 않는다. 원격 `.devcontainer` 수정도 기존 환경에 자동 적용되지 않는다. 이 패치는 이미 설치된 `postStartCommand` 문자열을 변경하지 않고 그 명령이 실행하는 **동일 파일**에 자동 업데이트를 추가했다. 최초 Pull 후에는 기존 시작 hook이 새 파일을 실행하므로 재빌드가 필요하지 않다. 원격 저장소 반영만으로 아직 내려받지 않은 실행 파일이 바뀌었다고 보고하지 않는다.

## 자동 준비 동작

기존 `.devcontainer/devcontainer.json`의 `postStartCommand`는 그대로다:

`python3 world-simulation-shorts-engine/deployment/start_codespace.py`

`CODESPACES=true`일 때만 다음 단계를 실행한다. localhost 개발·기존 Docker 서버 실행 방식은 유지한다.

1. 해당 상태 폴더의 서버·worker를 확인한다. 살아 있는 렌더/대기 작업이 확인되면 실행 중 소스를 변경하거나 서버를 강제 종료하지 않는다.
2. 공식 `dimon3898-sys/yeonhwarok-free` origin의 main을 최대45초 안에 fetch한다. 로컬 **main**의 현재 HEAD에서 **fast-forward만** 허용한다. 다른 브랜치·수정/staged 파일·로컬 커밋 분기·새 main 경로와 untracked/ignored 파일 충돌·symlink 경로 충돌이면 중단한다. 전용 fetch ref를 사용해 동시 fetch의 `FETCH_HEAD` 간섭을 피하며 configured refmap으로 다른 브랜치를 갱신하지 않는다. reset·stash·clean·force·자동 Push는 사용하지 않는다. 기존 로컬 변경과 Git 이력을 보존한다. checkout 변경 직전 확인된 유휴 gateway를 정상 종료하고 worker와 포트를 다시 검사한다.
3. 갱신된 파일을 새 Python 프로세스에서 읽고 기존 안전한 시작 helper를 실행한다. 이 내부 단계는 `--no-sync`로 재귀 업데이트를 방지하며 최대60초 안에 반환한다. 인증 서버 source fingerprint가 바뀌면 **확인된 유휴 자기 서버만** 정상 종료 신호로 갱신한다. 정상인 동일 서버는 재사용한다.
4. 인증이 필요한 `/api/health`와7860 준비를 확인한다. owner-code·세션·저장 상태를 유지한다. private 포트는 기존 Codespaces 전달 설정을 사용하며 공개 범위를 넓히지 않는다.

자동 시작 자체는 새 영상/75초/MASTER 렌더를 요청하지 않는다. Stop 전에 승인되어 중단된 기존 작업의 checkpoint 복구 기능은 보존한다. 원래 gateway의 정상 재개 정책에 따라 그러한 작업이 재개될 수 있다.

실패는 고정 오류 코드로 기록하며 무한 재시도하지 않는다. native Git stderr·owner-code·쿠키·토큰은 출력하거나 Git에 저장하지 않는다. 매 시도 기록은 비공개 `deployment/runtime/mobile/startup-history/autostart_*.json`, 최신 상태는 `startup-update.json`에 보존한다. network 실패·dirty/diverged Git·타인 프로세스·진행 중 worker는 자동 덮어쓰기로 우회하지 않는다.

Git checkout 중 timeout이 발생하면 일부 tracked 파일이 변경되었을 수 있다. 이를 자동 reset하지 않고 실제 Git 상태를 확인한다. 기존 gateway의 유휴 검사와 종료 신호 사이 새 작업 접수의 짧은 race는 정상 종료/checkpoint 절차로 보존하고, gateway 종료 후 살아 있는 worker가 있으면 checkout 갱신을 거부한다.

## 검증 범위

임시 bare Git 저장소의 실제 fast-forward·반복 시작·파일 보존·실패/timeout 검사와 기존 Origin/인증/작업복구 회귀 검사를 수행한다. 시작 subprocess fixture와 실제 로컬 gateway 검증은 원격 사용자의 Codespace 실행 검증과 구분한다. 결과는 `validation/codespaces_autostart.json`에 기록한다.

현재 관리형 작업환경에서 사용자 Codespaces API는 Forbidden이었다. 따라서 **solid-space-fishstick 내부의 최초 Pull을 원격으로 대신 수행했다고 주장하지 않는다.** 휴대폰 최초 적용만 위의 Git 화면 조작이 필요하다. 이후 자동 시작의 성공 여부는 준비 기록과 실제7860 화면으로 확인한다.

## 공식 근거

- [GitHub: devcontainer 변경 적용에는 rebuild가 필요함](https://docs.github.com/en/codespaces/setting-up-your-project-for-codespaces/introduction-to-dev-containers): 본 패치는 기존 명령·이미지를 변경하지 않아 최초 Pull 뒤 rebuild가 불필요하다.
- [Devcontainer lifecycle](https://containers.dev/implementors/json_reference/#lifecycle-scripts): `postStartCommand`는 성공한 컨테이너 시작마다 실행된다.
- [VS Code: Source Control의 … → Pull](https://code.visualstudio.com/docs/sourcecontrol/repos-remotes): Pull은 fetch 후 현재 로컬 브랜치 반영이며 Sync Changes는 Pull+Push다.
- [GitHub: 같은 Codespace Stop/Start](https://docs.github.com/en/codespaces/developing-in-a-codespace/stopping-and-starting-a-codespace): 목록에서 중지 후 이름을 눌러 재시작한다.

공식 문서 확인일: 2026-10-06. 명령을 유지한 최초 Pull 후 재시작 설계는 문서와 로컬 검사에 근거하며 실제 사용자 휴대폰 적용 완료를 의미하지 않는다.
