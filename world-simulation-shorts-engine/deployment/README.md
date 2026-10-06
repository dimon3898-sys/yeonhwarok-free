# 무료 모바일 운영 준비

기존 엔진과 MASTER/Flat/Rhythm 파일을 유지하면서 인증·작업 복구를 별도 계층으로 추가했다. 이 폴더는 새 렌더러가 아니다. 검증 결과와 실제 배포 상태는 `DEPLOYMENT_REPORT.md`에 기록한다.

## 휴대폰으로 시작하기

공식 저장소 진입 주소: https://codespaces.new/dimon3898-sys/yeonhwarok-free?quickstart=1 (이미 실행 중인 웹앱 주소가 아니다).

1. GitHub 개인 계정의 **Billing → Budgets and alerts**에서 Codespaces 유료 사용을 차단하고 포함 무료 할당량을 확인한다. 무료 할당량을 다 사용한 경우 진행하지 않는다. **유효한 결제수단이 없는 개인 계정은 공식 문서상 무료 할당량 초과 사용이 차단된다.** 이미 결제수단이 있으면 **전체 개인 계정의 Codespaces 제품 전체**에 $0 예산과 **Stop usage when budget limit is reached**가 실제 적용되는지 확인한다. compute 또는 storage 한쪽만 제한하거나 알림만 설정하는 것으로는 과금을 막지 못한다. $0 차단을 설정할 수 없거나 불명확하면 환경을 생성하지 않는다. 결제 수단이나 유료 플랜을 추가하지 않는다.
2. 저장소 **Code → Codespaces**에서 **2-core** 환경을 만든다. `.devcontainer/devcontainer.json`이 Python·FFmpeg·Chromium·기존 3D 자산과 서버를 준비한다. 이미 있던 Codespace는 재접속해 사용한다.
3. Ports의 **7860 / World Simulation mobile**을 연다. 포트 공개 범위는 **Private**로 유지한다. GitHub 로그인 후 소유자 코드 로그인 화면이 나온다.
4. 비공개 workspace의 `world-simulation-shorts-engine/deployment/runtime/mobile/owner-code.txt`에서 접근 코드를 복사해 이 화면에 입력한다. 이 파일은 Git에 저장되지 않는다. 채팅이나 공개 이슈에 코드를 붙이지 않는다.
5. 주제와 길이를 입력해 기획을 확인하고 승인한다. 렌더가 시작되면 브라우저를 닫아도 서버 작업은 계속된다. 이후 같은 프로젝트를 다시 열어 상태·영상·다운로드를 확인한다.

Codespaces의 자동 중지와 무료 할당량 제한은 별개다. 자동 중지가 발생하면 렌더도 중단될 수 있으며, 다시 접속하면 승인된 작업이 완료 Scene을 보존한 채 재개된다. 기본 idle은30분이고 계정 설정에서5–240분으로 변경할 수 있다. 최대 실행 수명은12시간이다. 백그라운드 파일 로그만으로 idle이 연장된다고 가정하지 않는다. **상시 무료 서버를 의미하지 않는다.** 중지된 Codespace에도 저장공간 사용량이 누적되며, 사용자 지정 Docker 기본 이미지도 저장공간 계산에 포함된다. 월15GB-month는32GB 디스크 크기와 다른 시간 누적 할당량이다. 따라서 무료 할당량과 비용 차단을 유지해야 한다.

## 기본값과 보호 한도

`PRODUCTION_SHORTS`: HIGH / FAST_PLUS / TTS OFF / Subtitle OFF / BGM ON / SFX ON. 기존 FAST·NORMAL·CINEMATIC과 TTS·자막 기능은 그대로 사용한다. 기본 배포 한도는 영상 180초·40 Scene, 프로젝트30개, 업로드16MiB, 동시 작업1개+대기1개, 남은 공간2GiB 이상이다. 75초 실전 영상은 이번 배포 검증에서 만들지 않는다.

소유자만 접근하며, 변경 요청에는 같은 사이트 Origin이 필요하다. 외부 포트에서 loopback 클라이언트라는 이유로 인증을 생략하지 않는다. 내부 렌더 콜백7861은 loopback에서만 읽기 요청을 받고 외부로 전달하지 않는다. 업로드는 WAV/MP3/MP4 형식·크기·코덱·길이 검수 및 제한된 ffprobe로 검사한다.

## 저장 및 복구

새 상태는 `deployment/runtime/mobile/`에만 저장한다. `projects/`, 승인된 계획, job ticket, checkpoint, 버전별 영상은 이 폴더 아래에 보존한다. 기존 공용 Scene cache는 기존 경로를 사용한다. Codespaces workspace와 Docker named volume은 유지되지만, Codespace/볼륨을 삭제하면 해당 실행 상태도 사라진다. 결과는 검증된 export로 저장소 `deliverables/`에 추가할 수 있다. 과거 파일을 덮어쓰거나 이력을 정리하지 않는다.

서버 재시작 시 계획 해시와 승인 기록이 같은 작업만 재개한다. 완료 Scene은 해시·해상도·FPS를 검수해 캐시 또는 checkpoint로 재사용한다. 미완성 Scene의 부분 파일도 보존하고 새로운 시도로 기록한다. 소유자 코드·세션·private job 로그는 export 대상에서 제외한다.

## 현재 Cloud에서 비용 추가 없이 운영

외부 웹 서비스 계정이 없더라도 현재 실행 환경에서 기존 엔진을 사용하고, 검증된 결과만 GitHub deliverables에 추가해 HTTPS로 다운로드할 수 있다. 이 방법은 현재 Cloud의 기존 이용 조건에 의존하며, 새 서버 비용을 추가하지 않는다.

아래 CLI는 JSON 작성 없이 기존 기획·승인·백그라운드 렌더 API·검증 export를 사용한다.

```sh
cd world-simulation-shorts-engine
python3 -m deployment.start_codespace
python3 -m deployment.production_cli --state-root deployment/runtime/mobile plan --topic '서울에서 도쿄를 거쳐 타이베이로 연결되는 항공 경로' --duration 20
```

기획만 생성되며 자동 렌더하지 않는다. 일반 사용자는 모바일 화면에서 승인하면 된다. 자동화 담당자는 `production_cli --help`의 status/approve/render/export 명령을 사용할 수 있다. render는 접수만 하고 HTTP 연결을 종료하므로 휴대폰 연결과 렌더 수명이 분리된다.

## Docker

저장소 루트의 Docker whitelist는 코드·허가된 공용 자산·기존 인증서만 포함한다. 오래된 프로젝트·영상 전체·Git·private runtime을 이미지에 복사하지 않는다. 실행은 비 root UID1000이다. private checkout 파일 권한은 이미지 내부에서만 읽기 가능하게 정규화한다. 현재 관리형 VFS Docker에서는 큰 설치 레이어를 마지막에 배치해 디스크 사용을 줄인다.

```sh
docker build -f world-simulation-shorts-engine/deployment/Dockerfile -t world-simulation-mobile .
docker run -d --name world-simulation-mobile -p 7860:7860 --cpus 2 --memory 8g --shm-size 512m \
  --mount type=volume,src=world-engine-state,dst=/opt/world-engine/world-simulation-shorts-engine/deployment/runtime \
  --mount type=volume,src=world-engine-cache,dst=/opt/world-engine/world-simulation-shorts-engine/cache \
  --mount type=volume,src=world-engine-audio,dst=/opt/world-engine/world-simulation-shorts-engine/assets/audio \
  world-simulation-mobile
```

이 명령 자체는 공용 HTTPS를 제공하지 않는다. 인터넷 공개는 인증된 HTTPS 서비스/비공개 Codespaces 포트 전달을 사용한다. 관리형 Cloud에서 이미지 빌드는 runtime 스킬의 proxy CA secret mount 지침을 따라 TLS 검증을 유지한다. runtime volume과 캐시는 삭제하지 않는다.

## 검증 도구

`mobile_e2e.mjs`는 375px 실제 브라우저에서 로그인·기획·승인·브라우저 종료 후 재접속·영상 전체 재생·첨부 다운로드 SHA·Range를 검사한다. 소유자 코드/쿠키를 기록하지 않는다. `--mode plan-only`는 렌더하지 않고, `approve`는 이미 검수된 20초 이하 테스트 계획에만 사용할 수 있다.

`build_validation_sample.py`는 기존 12초 검증 계획을 새 프로젝트에 복사하고 S001 카메라 timing만 변경한다. 승인/렌더는 시작하지 않는다. 이것은 배포 회귀 검증 전용이며, 기존 영상과 캐시를 덮어쓰지 않는다.
