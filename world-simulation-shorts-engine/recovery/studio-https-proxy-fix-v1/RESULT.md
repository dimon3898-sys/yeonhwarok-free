# Studio HTTPS 프록시 호환성 복구 후보

판정: **STUDIO_HTTPS_PROXY_CANDIDATE_CPU_VERIFIED_GCUBE_CONFIRMATION_PENDING**.

새 이미지 등록과 독립 digest pull을 완료했다. 실제 gCube의 과거 헤더 오류 원인과 사용자 주소 등록 성공은 아직 확정하지 않았다. 유료 GPU 실행·워크로드 설정 변경·FINAL 승격은 하지 않았다.

## 실제 원격 확인

기존 Repository Secret `GCUBE_ACCESS_TOKEN`으로 공식 CLI0.4.2와 읽기 전용 API를 사용했다. 무료 Actions [39084897586](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39084897586)의 2026-10-18 **10:01:19 KST** 관측:

- #5373: `finish`, Pod: `Terminating`.
- 실제 설정의 서비스 주소는 사용자가 제공한 `https://ae20158c.service.gcube.ai:24999`와 일치했다. 포트8080, Command 비움, 기존 HTTPS 이미지/digest도 일치했다.
- 기존 관리자 코드 설정은 존재하고 형식 검증을 통과했다. PUBLIC_ORIGIN과 운영 정책은 미설정이었다. 값은 공개하지 않았다.
- `describe`와 `pods` 조회 성공. `workload logs`는 `WORKLOAD_NOT_RUNNING`으로 CLI 종료1. 이것은 컨테이너 종료코드가 아니다. 공식 Pod 로그 API는404였고 실제 컨테이너 종료코드는 미확보다.
- `/setup`과 `/setup/challenge` 등 제한된 공개 조회 6건은 모두404였다. 실제 Studio 응답이나 들어온 Host/Forwarded/XFP/XFH를 확보하지 못했다.

따라서 과거 요청의 브라우저 Origin과 서버 인식 Origin 차이를 수치나 문자열로 재구성하지 않았다. Origin 누락은 현재 HTTPS V1의 의도된 초기 설정 상태이고, 정책 누락은 제작 차단 사유이며 이 프록시 오류의 확정 원인이 아니다.

## 별도로 재현·수정한 코드 결함

기존 고정 HTTPS 정책은 X-Forwarded-Proto가 없으면 정상 처리하지만, HTTPS 외부 Host·포트와 mutation Origin이 모두 정확하게 일치해도 단일 `X-Forwarded-Proto: http`를 거부했다. 외부 TLS 종료 후 내부 HTTP 전달 홉 조건에서 기존 오류가 재현된다. **실제 gCube가 이 헤더를 보냈다는 증거는 없다.**

독립 확장 `FixedHTTPSProxyPolicy`는 이 단일 내부 홉 조건만 처리한다. 독립 설정 또는 관리자 인증 후 명시적으로 확인한 HTTPS 주소 하나에 고정하며, 요청에서 신뢰 주소를 추출하지 않는다. 원본 헤더를 바꾸지 않고 검증된 복사본에 기존 정책 전체를 다시 적용한다.

| 입력/보호 | 후보 동작 |
| --- | --- |
| 정확한 외부 Host와 포트 + 단일 XFP `http` + XFH 없거나 같은 외부 authority | 기존 고정 Origin·인증·CSRF 검증을 그대로 수행 |
| XFP 없거나 `https` | 기존 검증 유지 |
| 잘못된 Host/XFH/Origin, 외부 포트 누락 | 거부 |
| 중복 또는 체인 XFP/XFH, 모호한 값 | 거부 |
| 임의 내부 Host를 외부 주소로 변경 | 지원하지 않음, 거부 |
| Forwarded에서 새 Origin 추론 | 하지 않음; 기존처럼 신뢰 근거로 사용하지 않음 |
| mutation Origin 누락/null, 인증/CSRF 실패 | 거부 |
| 정책·실제 GPU admission 미충족 | 제작 차단 |

추가한 진단 기록은 개수·분류·이미 알고 있는 Origin과의 일치 여부만 출력하고 전역 횟수를 제한한다. 원본 헤더, URL, IP, Cookie, 본문, 코드, Secret을 기록하지 않는다. 실제 프록시 형태가 다르면 다음 승인된 실행에서 이 기록으로 구분할 수 있다.

## 변경 파일과 재사용

- `proxy_policy.py`: 고정 HTTPS 호환 처리와 제한된 진단.
- `proxy_server.py`: 기존 SetupCore와 normal Studio 인스턴스의 정책만 확장. 기존 관리자 코드·private 기록·세션 폐기·UI·제작 경로 재사용.
- `proxy_bootstrap.py`: 원본 supervisor가 실행하는 정확한 UI 진입점만 교체. UID/GID, private 경로 검증, GPU admission, 비용 정책, 자식 종료 관리 유지.
- `parent.py`, `manifest.py`: 원본 모듈을 명시된 경로로 재사용하고 새 파일 및 부모 파일 SHA 검증.
- `remote.py`, 테스트, Dockerfile, `ci_package.py`, 독립 workflow2개: 읽기 전용 확인, 집중 검증, 추가 계층 패키징.

기존 HTTPS21개·Studio51개·엔진 inventory373개 SHA가 build와 독립 pull 모두 동일했다. 기존 FINAL·V4·렌더러·카메라·전선·영상·claim·이미지는 변경/삭제하지 않았다. Git 변경은 새 namespace와 새 workflow뿐이다.

## 무료 검증 결과

무료 공개 표준 runner의 [39085567166](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39085567166):

| 검사 | 결과/범위 |
| --- | --- |
| 집중 Python 검사 | 22/22 PASS: 정책16, HTTP4, bootstrap2 |
| 실제 CPU 컨테이너 | 3/3 PASS: 관리자 누락 종료1, 미설정 등록·재시작, 등록된 운영 모드 보호 |
| 모바일 Chromium + 실제 TLS fixture | 11/11 PASS: 초기 화면→기존 관리자 인증→명시적 주소 등록→새 Studio 로그인 |
| readonly 수집기 로컬 검사 | 5/5 PASS, runtime 이미지에 포함하지 않음 |
| Secret Scan | Gitleaks8.24.3 고정 SHA, 발견0 |
| 원본 파일·런타임 closure SHA | PASS |
| 신규 태그·Docker build·GHCR 등록 | PASS |
| 별도 runner digest pull·플랫폼·진입점·원본 SHA | PASS, linux/amd64 |
| 실제 gCube 헤더/등록·NVIDIA·영상 제작 | 미검증, 이번 작업에서 실행하지 않음 |

CPU 컨테이너의 legacy child는 테스트 마운트의 STORAGE EACCES/ENOENT로 종료했다. 이 결과로 NVIDIA 검증 실패를 주장하지 않는다. 검사한 것은 실제 자식 종료 후에도 웹 설정 UI가 살아 있고, GPU/정책 미충족 시 제작이 계속 차단되는 것이다. fixture의 파일·주소·코드는 검사 전용이며 배포 Secret에 사용하지 않는다.

## 신규 이미지

- 태그: `studio-proxy-v1-4589328-39085567166-1`
- 참조: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da`
- 실제 소스: `83bf1e0c7fc5955d9ff1d06441264f4c0d5a702b` (태그의4589328은 부모 체크포인트).
- 브랜치: `development/studio-https-proxy-fix-20261018`, CI 증거 저장 커밋: `616afcc`.
- 런타임 manifest SHA: `b25c07f5aefdf63c3919f2ab439c978308d9304e92a8e2c6e92c991259ee0d56`.
- 기존 immutable `468deaa…`에서 상속, 새 `/opt/world-engine-studio-https-proxy-fix`만 추가. 기존 태그 덮어쓰기 없음.

build.json의 `pullVerified=false`와 pull.json의 `imageBuilt=false`는 각 독립 job 단계 기록이다. build 성공·등록은 build.json, 독립 pull 성공은 pull.json에서 확인한다. 최종 `IMAGE.json`은 둘을 합친 검증 결과다.

## 사용자 다음 행동

정확한 입력값은 [GCUBE_SETUP.md](GCUBE_SETUP.md)에 기록했다. 사용자가 승인 후 새 이미지를 수동 배포하고, 그 실행에서 gCube가 실제 발급한 HTTPS 주소의 `/setup`을 연다. 기존 관리자 코드로 주소를 확인·등록한 뒤 새로 로그인한다. 종료된 이전 주소를 새 실행 주소로 가정하지 않는다.

주소 등록이 계속 거부되면 실행 중인 상태의 제한된 진단 로그를 읽기 전용으로 확보해야 한다. 인증·CSRF를 끄거나 임의 Host를 신뢰하지 않는다. 현재 운영 정책 미설정도 별도로 해결해야 실제 제작이 허용된다. 정책의 실제 요금·비용·시간·승인 만료는 사용자가 승인한 값만 사용한다.

필수 temp-only 파일0. 런타임 manifest·소스·테스트·재현·이미지/모바일/원격 증거는 이 branch에 영구 저장한다. 현재 상태는 실제 gCube 확인을 기다리는 복구 후보이며 실제 로그인 복구/80초 제작/영상 품질/FINAL PASS가 아니다.
