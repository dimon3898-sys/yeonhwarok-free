# World Engine 단일 주소 운영 — 구현 및 검증 보고

검증일: 2026-10-06. **배포 계층 구현·로컬 통합 검증은 통과했지만 외부 배포는 미완료다.** 실제 World Engine HTTPS 주소는 아직 발급되지 않았다. 외부 계정 인증과 현재 무료 이용·과금 차단 조건 확인이 필요하다. 로컬 테스트를 Android 실기 또는 외부 클라우드 테스트로 보고하지 않는다.

## 앞으로의 사용자 경험

고정 World Engine 주소 → 앱 비밀번호 → 주제/기획 → 승인/생성 → 다운로드.

GitHub 개발 화면, VS Code, 터미널, Ports, Pull, Codespace Stop/Start를 일상 운영 절차에서 제외했다. 기존 Codespaces 설정은 보존했으며 새 Codespace는 만들지 않았다. 새 배포 후보는 `deployment/one_url/`에만 추가했고 기존 생성기 시작 경로를 강제로 바꾸지 않았다.

## miniature-doodle의 HTTP401

현재 사용자가 보고한 전체 동적 주소와 원격 응답 헤더/본문을 확보하지 못했다. **해당401의 실제 발생 계층은 미확정이다.** Codespace 이름만으로 주소를 추측하여 원인으로 단정하지 않는다.

현재 서버 코드를 직접 확인했다.

| 요청/조건 | 기존 World Engine 응답 |
| --- | --- |
| 비로그인 `GET /api/health` | 200 |
| 비로그인 `GET /auth/login` | 200 |
| 비로그인 `GET /` | 303, 로그인으로 이동 |
| 비로그인 보호 API/영상/다운로드 | 401, `AUTH_REQUIRED` |
| 잘못된 비밀번호로 `POST /auth/login` | 401, `LOGIN_FAILED` |
| Origin/Host 검증 실패 | 400 또는403; 401을 생성하는 코드가 아님 |

GitHub Private port는 앱 owner 인증과 별도의 GitHub 인증을 요구한다. 따라서 실제 로그인 화면 GET 자체에서401이면 현재 앱의 정상 응답과 다르지만, 응답 없이 GitHub proxy라고 확정할 수는 없다. 읽기 전용 `deployment/diagnose_access.py`는 실제 전체 HTTPS 주소가 있을 때 세 요청의 안전한 응답 서명을 기록한다. 인증 리디렉션을 따라가지 않고 쿠키·응답 본문·비밀번호를 저장하지 않는다. 진단 테스트20개를 통과했다.

## 무료 운영 후보 검토

현재 공식 자료를 확보해 비교했다. 계정에 로그인하거나 약관에 동의하거나 유료 서비스를 활성화하지 않았다.

| 후보 | 판단 |
| --- | --- |
| Codespaces / GitHub Actions | GitHub Additional Product Terms가 프로덕션 서비스 용도를 제한한다. 최종 운영 서버로 채택하지 않았다. Actions 운영 workflow도 활성화하지 않았다. |
| Hugging Face Spaces | 현재 문서는 일반 Docker/Gradio Space 신규 생성에 유료 플랜을 요구한다. 무료 ZeroGPU 예외는 계정 요건과 Gradio 제한이 있고 장시간 CPU 작업 적합성은 미검증이다. |
| Render / Railway 무료 | 확인된 CPU/RAM, sleep 또는 저장 제한 때문에 현 생성기의 실사용 렌더 서버로 채택하지 않았다. |
| Cloudflare Workers/D1 | 고정 진입 주소에는 적합하지만 FFmpeg/Chromium 장시간 렌더 계산을 대신할 수 없다. 외부 계정을 생성하지 않았다. |
| Modal | 고정 ASGI 주소와 CPU Sandbox/Volume 구조가 맞아 **조건부 배포 후보**를 구현했다. 무료 계정·월 크레딧은 공식 예제에서 확인했지만 실제 계정의 무카드 가입, 현 단가, 저장 비용, 초과 과금 차단은 확인되지 않았다. 0원 상시 운영을 보장하지 않는다. |

일차 출처: [GitHub 약관](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features), [HF Spaces](https://huggingface.co/docs/hub/spaces-overview), [Render 무료 제한](https://render.com/docs/free), [Railway 플랜](https://docs.railway.com/reference/pricing/plans), [Modal 공식 web 예제](https://github.com/modal-labs/modal-examples/blob/main/07_web/basic_web.py), [Modal SDK](https://github.com/modal-labs/modal-client).

저장한 원문·인용·조회 시각·SHA 및 세부 비교는 `docs/evidence/one_url_hosting_review_v001/`에 있다. Modal 공식 예제의 "$30/month" 주석은 현 가격 계약 또는 이 계정의 자격 검증을 뜻하지 않는다.

## 구현된 배포 후보

- 배포된 ASGI front가 고정 HTTPS 주소를 제공하고, 이름 있는 CPU Sandbox를 로그인 후에만 할당한다. 사용자는 backend 이름·포트를 알 필요가 없다.
- 기존 owner-code 인증을 backend에서 유지한다. front 로그인은 서버 쪽에서 기존 인증 세션으로 연결하며 backend 쿠키를 브라우저에 전달하지 않는다.
- 정확한 front Origin/Host, Secure/HttpOnly/SameSiteStrict cookie, 허용된 API 경로, 업로드/요청 크기 제한을 적용했다. 임의 Origin, 임의 upstream, CORS `*`를 허용하지 않는다.
- 로그아웃 무효화와 월별 누적 계산 예약을 별도 control Volume에 명시적으로 commit하는 구조를 구현했다. 무료 조건·단가·확인 시각·과금 차단 증거가 없으면 할당을 거부한다. 입력된 증거의 형식을 검사하는 코드가 공급자의 과금 설정을 직접 검증하는 것은 아니다.
- 제안 compute 제한은 CPU4개/메모리8192MiB, 최대4시간, 활성/불명확 job이 없을 때만900초 유휴 종료다. 이 자원이 실제 Starter 계정에 허용되는지는 미검증이다.
- 초기 외부 검증은20초 이하로 제한한다. 브라우저 HTTP 요청이 아니라 서버 job/checkpoint가 작업을 소유한다.
- 기존 runtime/cache/audio 경로에 별도의 Volume을 연결한다. 생성 결과는 버전별로 보존하고 인증된 다운로드를 스트리밍한다.
- provider SDK와 relay 의존성은 선택적 별도 파일에만 추가했다. 원본 `requirements.txt`, renderer, `server.py`, `web/`, `engine/`은 수정하지 않았다.

자세한 운영자 전용 활성화 절차는 [one_url/README.md](one_url/README.md)다. 사용자가 터미널 명령을 실행하는 절차가 아니다.

## 실제 로컬 검증

별도 단일 로그인 front → 기존 Docker 인증 gateway → 기존 생성기를 직접 연결했다. 테스트 backend는 기존2CPU/8GB 제한 컨테이너이며, 외부 Modal compute는 아니다.

| 항목 | 실측 결과 |
| --- | --- |
| 회귀/신규 단위 테스트 | 최종183통과, 실패0, skip0. 실제 SDK1.6.1 구성·closure serialization 검사 포함; provider API 호출0 |
| 모바일 viewport | Chromium375×812, 수평 overflow0, browser error0 |
| 자연어 기획 | 20초 항공 네트워크 기획 생성, 승인 전 렌더0 |
| 짧은 승인/생성 | 별도12초 HIGH QA 프로젝트 승인, background job 한 번만 생성 |
| 브라우저 종료/재접속 | 동일 `job_5219ddaf559a`와 상태 복원 |
| Scene 재사용 | 기존 완료 Scene5개 cache 사용, 새 Scene 렌더0 |
| 출력 | 12.0초,1080×1920,30fps,H.264/yuv420p/BT.709 |
| 오디오 | BGM/SFX ON, TTS/Subtitle OFF. 기능 자체는 그대로 유지 |
| 자동 QC | PASS,360프레임 decode, black/duplicate/missing asset/broken route0 |
| 모바일 크기 전체 재생 | PASS,360프레임 decode, browser dropped2, corrupted0, stall0. 실기 Android 또는 직접 청취 검증 아님 |
| 다운로드 | 13개 browser attachment 및 HTTP SHA 일치, Range206/1024bytes |
| 최종 MP4 | 17,667,422bytes, SHA256 `4ee70ba02bf0a2deec809a04578325118beeb5dd050de976b875aa7bb99a06c5` |

이번 실행만의 실측: 오디오 준비2.104초, 조립/오디오 mux2.225초, QC13.062초, 총20.600초. 이전 Scene 렌더 시간은 포함하지 않는다. 이 수치를 전체12초 새 렌더 시간이나 무료 클라우드 성능으로 보고하지 않는다.

새 QA 프로젝트는 `project_23ae1a214d53/v001`이며 기존 결과를 덮어쓰지 않았다. 엄격한 export 검사 후 `deliverables/WORLD_SIMULATION_ENGINE/ONE_URL_MOBILE_ACCEPTANCE_v001/`에 영상·Scene·계획·QC·source report27개 파일을 추가했다. 인증 파일은 포함하지 않았다. 상세 결과는 `deployment/validation/one_url_mobile_candidate_v002.json` 및 `docs/evidence/one_url_qa_v001/`, `one_url_mobile_*`의 JSON과 스크린샷에 있다.

최종 검토에서 월 경계 비용 예약과 SDK의 미해결 Volume handle capture를 수정했다. 전체 수명+300초가 확인된 UTC 월을 벗어나면 신규 할당을 거부하고 실제 생성 직전 다시 검사한다. provider 생성 요청은60초로 제한한다. runtime/cache/audio Volume handle은 실행 시점에 얻어 front closure가 미해결 handle을 저장하지 않게 했다. 월말·연말·시간대 및 실제 SDK serialization 회귀 검사를 추가했다.

## 보존 확인

승인된 core/renderer28개 source SHA가 모두 동일했다. 기존 tracked 파일 변경0, MASTER 렌더0,75초 렌더0, 새 Codespace0, 결제/외부 서비스 활성화0이다. 기존 자료·Scene cache·checkpoint·Git 이력은 삭제하지 않았다. 새 파일만 별도로 저장한다.

## 남은 필수 외부 검증

1. 사용자만 할 수 있는 외부 계정 인증과 deployment credential 연결. credential 값은 채팅/Git에 넣지 않고 환경 설정에 등록해야 한다.
2. 실제 계정의 무료 자격, 무카드 조건, 현 CPU/RAM/storage 단가, 초과 과금 차단. 확인 전 provider resource를 생성하지 않는다.
3. 실제 `.modal.run` 발급, Android Chrome HTTPS 로그인/Origin/영상 생성/다운로드 및 compute 종료 후 재접속.
4. Sandbox Volume의 실제 저장 cadence와 강제 종료 후 job/Scene/최종 파일 보존. SDK의 background commit 설정 또는 로컬 fsync만으로 내구성을 인증하지 않는다.
5. 실제 image build/리소스 admission/렌더 실측, cold start 및 동시성. 한 front container/이름 있는 backend 제한은 분산 트랜잭션 잠금 검증을 대신하지 않는다.

**따라서 A/B 외부 운영 완료 기준은 아직 충족했다고 보고하지 않는다.** 사용자 계정 인증과 무료 조건 확인을 받은 뒤 위 검증을 계속해야 한다. 아직 발급되지 않은 World Engine 주소, localhost 또는 Codespaces Ports를 최종 접속 주소로 제시하지 않는다.
