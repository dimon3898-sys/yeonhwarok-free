# 무료 단일 앱 URL 후보 재확인

확인 시각: 2026-10-06T16:13:18.065444+09:00 (KST).

**Cloudflare Workers Free + D1은 고정 URL·로그인·작업 queue를 맡길 공식 무료 후보다.** 실제 Python/FFmpeg/Chromium 렌더는 별도로 허용된 compute backend가 필요하다. 기존 Cloud 세션은 현재 가능한 작업 자원이지만 영구 상시 worker는 아니다. 새 HF Docker Space에는 유료 생성 자격이 필요하며, 무료 Gradio ZeroGPU는 오래된 인증 계정과 별도 호환 검증을 요구한다. 실제 provider 배포·로그인·무료 비용·모바일 end-to-end 운영은 확인하지 않았다.

| 후보 | 현재 공식 조건 | 판단 |
|---|---|---|
| 새 HF Docker Space | CPU Basic은 무료 시간당2vCPU·16GB·50GB지만 **생성과 복제에는 PRO/Team/Enterprise 유료 플랜 필요** | 새 no-card/no-paidplan 배포 경로로 추천 불가 |
| 기존 HF compute Space | CPU Basic48시간 idle 후 sleep, 방문 시 wake; `*.hf.space` HTTPS; 로컬 파일은 restart/stop 시 소실 | 사용자에게 이미 해당 Space 자격이 있다면 조건부 후보. 계정·실제 build·렌더 미검증 |
| HF 무료 ZeroGPU 예외 | 이메일 인증 + 생성30일 지난 개인 계정: **Gradio 전용 최대2개**. Python3.12.12 지원, requirements/packages 설치 가능 | 기존 Docker를 그대로 올리지 못함. 별도 Gradio/ASGI gateway와 CPU/RAM·장시간 background 검증이 필요한 조건부 후보 |
| Render Free | 전용 공식 instance 표0.1CPU·512MB, web-only, 월750h,15분 idle 후 sleep | 작은 화면·queue bridge 후보. 기존 렌더 worker 자원으로 부적합 |
| Railway Free | 월$1 credit,1vCPU·0.5GB RAM,1GB 임시disk·0.5GB volume·4GB image | 지속 무제한 무료가 아니고 renderer 메모리/디스크 부족 |
| Railway anonymous VM |2vCPU·2GB,SSH로 초기화,24h claim window, 미claim 파일 삭제 | 일시 preview이며 지속 모바일 운영 서비스 아님 |
| public 표준 GitHub Actions | ubuntu-24.04 x64:4CPU·16GB·문서상14GB, public 표준compute 무료, job최대6h | 개발·테스트·프로젝트 publication workflow. 일반 production app backend 사용은 아래 약관 제한을 확인해야 함 |
| Cloudflare Workers + D1 Free | Workers100k 요청/일·CPU10ms/호출; static asset 무료. D1읽기5mrows/일·쓰기100krows/일·총5GB | 고정 public workers.dev URL, auth/queue/metadata 후보. renderer는 별도 compute backend 필요 |

HF ZeroGPU의 무료 GPU quota5분/일과 decorated GPU 함수 기본60초를 CPU/SwiftShader 렌더의 제한으로 임의 적용하지 않았다. 반대로 그 수치가 긴 CPU background job이나 필요한 CPU/RAM을 보장한다고 해석하지도 않았다. 새로운 HF 계정은30일 자격 조건을 바로 충족하지 않는다.

HF의 과거 persistent storage 옵션은 최신 config 문서에서 더 이상 제공되지 않는다고 명시한다. 현재는 Storage Bucket mount가 권장된다. Bucket은 무료 allowance가 있지만 초과 과금하며, free public storage는 best-effort이다. 앱 owner code는 provider Secret으로 설정하고 프로젝트·checkpoint·영상은 실제 영구 volume에 저장해야 한다. 이 환경에는 HF secret/outbound identity가 없고 native HF 공식 docs 요청은 상속 proxy CONNECT403이었다. 승인된 official GitHub raw 원문을 읽었으며 proxy/TLS를 우회하지 않았다.

Render 공식 설정 guide에는0.5cores 문장이 남아 있지만 전용 instance 표와 Free summary는0.1CPU라고 한다. 전용 표를 우선하고 불일치를 숨기지 않았다. Railway no-card Trial 문구를 별도 Free 계정 자격의 보장으로 바꾸지 않았다.

개인 Codespaces의 비공개7860은 GitHub 소유자 인증과 활성 Codespace가 필요하다. WorldEngine의 로그인 코드만으로 이 플랫폼 인증을 제거할 수 없다. 현재 사용자401의 정확한 원인은 이 조사에서 원격 headers나 사용자 브라우저를 검사하지 않아 단정하지 않는다.

이 조사는 가입·로그인·토큰 발급·카드·유료 활성화·배포·새 렌더를 수행하지 않았다. 기존 Cloud worker에 접속하는 고정 공용 URL과 안전한 queue/auth bridge가 자동으로 생겼다고 주장하지 않는다. provider 계정 자격과 실제 end-to-end 동작이 확인되기 전에 조건부 후보를 완성된 무료 앱으로 안내하면 안 된다.

정확한 원문 URL·HTTP 결과·조회UTC·SHA256·인용은 REPORT.json에 남겼다. 원문은 huggingface/hub-docs, render-oss/skills, railwayapp/docs, github/docs의 현재 main에서 다시 읽었다. 코드 수정 없이 /tmp 연구파일만 작성했다.

## Cloudflare 무료 portal 구체 조건

Workers는 기본 Free이며 Paid 최소$5/month 가입은 별도다. Free100k요청/일 한도는00:00UTC에 갱신하고 초과1027오류, CPU10ms 초과1102오류를 반환한다. 네트워크fetch/D1 대기시간은CPU 사용량에 포함되지 않는다. 다만 문서상 무거운 인증/SSR/큰 payload 파싱은10–20ms를 사용할 수 있어 실제 login CPU 검증이 필요하다. 기본 static assets 요청은 무료·무제한이다. 고정 URL은 `https://<worker>.<account-subdomain>.workers.dev`이며 사용자 취미 프로젝트에 제공된다.

D1 Free는 읽기5million rows/day·쓰기100krows/day·총5GB, DB최대10개·개별500MB다. Free 한도 초과는 query오류/신규쓰기 제한이며 자동 Paid 과금이 아니다. query에는 적절한 index를 두고 영상은D1에 저장하지 않는다. Root가 검토한 Release 결과물은 public repository에서는 공개 파일이므로 portal의 owner login이 MP4 자체를 private으로 만들지는 않는다.

현재 읽은 공식 문서는 기본Free를 명시하지만 정확한 “no credit card required” 문구는 발견하지 못했다. 실제 signup/Free account 상태는 사용자 로그인으로 확인해야 한다. CF account/배포 grant·D1/owner Secret·외부 worker connectivity가 없어 여기서 공개 URL 배포가 완료됐다고 말할 수 없다.

## GitHub Actions 약관에서 확인한 중요한 범위 제한

무료quota와 production backend 사용 허용은 다른 근거다. 현재 GitHub 공식 추가 제품 약관 Actions 절에는 다음 문구가 있다.

> Any activity that places a burden on our servers, where that burden is disproportionate to the benefits provided to users (for example, don't use Actions as a content delivery network or as part of a serverless application, but a low benefit Action could be ok if it’s also low burden); or

> You may only access and use GitHub Actions to develop and test your application(s).

따라서 public 표준runner가 무료라는 이유만으로 WorldEngine의 일반 production prompt→render 서버리스 backend를 공식 허용된 무료 운영 구조라고 주장하면 안 된다. 이 저장소의 CI·기존 renderer 개발/회귀검증·프로젝트 sample publication과 일반 앱 생산 worker를 구분해야 한다. Root에는 이 약관을 확인하자마자 알렸다. Codespaces 절도 production-facing app hosting을 예시로 제한한다.

공식 출처: `https://raw.githubusercontent.com/github/docs/main/content/site-policy/github-terms/github-terms-for-additional-products-and-features.md` (HTTP200,2026-10-06T07:18:49.755934UTC,SHA256f285d9291d579a75f809cb09ce2e92f4451705f67bb9030fa905db682aebf57d). Cloudflare의 정확한 현재 출처는 공식 `cloudflare/cloudflare-docs`의 `production` branch다.
