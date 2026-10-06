# 무료 모바일 호스팅 조사 — 2026-10-06 UTC

**기존 웹 UI를 유지하는 무료 할당량 기반 후보는 개인 GitHub Codespaces의 2-core 환경이다.** 월 포함 quota와 계정의 결제 수단·실제 예산 차단 확인을 조건으로 추천하며, 상시 무료 호스팅이나 이미 완료된 원격 배포로 표현하지 않는다. 공개 GitHub Actions 표준 runner는 승인된 장면을 유한 시간 작업으로 렌더하는 별도 대안이다. 모바일에서 GitHub 로그인 후 private HTTPS 포트로 원래 앱에 접속하는 구성을 우선 검토한다. 현재 조사는 공식 문서와 기존 서버의 구조를 확인한 단계이며, 제공사 배포·계정 로그인·비용 0원은 검증하지 않았다.

Hugging Face CPU Basic의 “FREE” 표만 보고 신규 Docker 배포를 완전 무료라고 추천하면 안 된다. 최신 공식 원문에는 **새 Gradio/Docker Space 생성에 PRO 또는 Team/Enterprise 유료 플랜이 필요**하다고 명시되어 있다. 현재 무료 계정 예외인 최대 2개 Gradio ZeroGPU Space는 기존 Docker/Chromium 서버의 대체가 아니다.

## 실제 확인 범위

환경 runtime status는 current 관측이며 secrets·runtime variables·outbound identities가 모두 빈 목록이다. 네트워크 상태 필드는 unknown이고, 실제 /etc/codex/network-policy.json은 제한된 상속 프록시 경로다. TLS 검증과 프록시를 유지했다. huggingface.co·render.com·fly.io·docs.railway.com의 직접 문서는 CONNECT 403으로 접근이 막혔으며 우회하지 않았다. 허용된 raw.githubusercontent.com에서 **제공사의 공식 문서 저장소 원본을 HTTP 200으로 읽었다**. 공식 원문 main branch의 조회 시각·내용 SHA·바이트와 인용은 REPORT.json에 남겼다. 서비스의 실제 계정 자격·배포 동작을 시험한 결과와 구분한다.

cloud-environment runtime 및 onboarding setup 스킬의 네트워크·기존 파일 보존 지침에 따라 읽기만 수행했다. 가입, 카드 등록, 유료 활성화, 토큰 발급, 약관 동의, 배포, 서버 시작·종료, 엔진 수정, 새 렌더는 하지 않았다. 이번 연구자가 생성·갱신한 파일은 이 REPORT.md와 REPORT.json 두 개뿐이다. 최신 Codespaces 보완은 같은 두 파일만 갱신했다.

## 무료 조건 비교

| 후보 | 확인한 무료·자원 조건 | 중단·저장 | 현재 엔진에 대한 판단 |
|---|---|---|---|
| 개인 GitHub Codespaces | 2 core·8GB RAM·32GB nominal disk. 개인 Free 월120 core-hours·15GB-month | idle 기본30분(5–240), active 최대12시간, stop해도 storage 누적 | 원래 UI의 조건부 무료 후보. 카드·남은 quota·Stop usage 차단 확인 필요; 상시 호스팅 아님 |
| HF CPU Basic | 시간당 $0, 2 vCPU·16GB RAM·50GB 임시 디스크. **신규 compute Space 생성은 유료 플랜 필요** | inactive 48시간 후 sleep; restart/stop 시 로컬 데이터 소실 | Docker 호환성은 높지만 신규 완전 무료 조건에 맞지 않음. 기존 Space 자격은 미확인 |
| Render Free | 0.1 CPU·512MB RAM, workspace당 월 750 instance-hours. Free web service only | inbound 없는 15분 후 spin-down; 무료 persistent disk 없음 | 가벼운 웹 화면·상태 bridge 후보. 기존 4K Chromium 렌더 worker 자원으로 추천하지 않음 |
| Railway Free | 월 $1 credit, 1 vCPU·0.5GB RAM·1GB 임시 디스크·0.5GB volume·4GB image | 선택적 Serverless일 때 마지막 outbound 후 약 5–10분 sleep. 크레딧 기반 metering | 상시 무제한 무료가 아님. 동일 그래픽 품질의 렌더 worker로 부적합한 자원 조건 |
| Railway Trial | 일회성 $5, 최대 30일, 2 vCPU·1GB RAM. Trial은 카드 없이 가능 | 기간 또는 $5 소진 후 Free로 전환; 계정 검증 수준에 따라 outbound/port 제한 | 일시 체험이며 지속 무료 엔진 운영으로 간주하지 않음 |
| Fly 신규 Trial | 총 VM 실행 2시간 또는 7일, VM별 최대 2 vCPU·4GB, volume 총 20GB | **Trial VM은 실행 5분 후 자동 정지**; 카드 추가 시 trial 종료·과금 | 긴 렌더 작업에 맞지 않음. 신규 조직에는 상시 무료 tier 없음 |
| 공개 GitHub Actions 표준 Linux | ubuntu-24.04 기준 4 CPU·16GB RAM·문서상 SSD 14GB; public standard runner compute 무료 | job 최대 6시간; job 종료 시 VM 소실. cache·artifact 별도 보존 필요 | 장면별 렌더 worker의 가장 현실적인 무료 후보. 상시 웹 호스팅은 제공하지 않음 |

Render 전용 instance-types 표와 같은 가이드의 Free 설명은 0.1 CPU지만, 해당 가이드의 다른 문장에는 0.5 cores가 남아 있다. **전용 표의 0.1을 주출처로 사용하고 이 문서 간 불일치를 숨기지 않는다.** Render 무료 카드 요구·무료 bandwidth 숫자는 이번 접근 가능한 공식 자료로 확정하지 못했다. Railway Free의 별도 카드 요구도 Trial의 카드 없음 문구로 대신 확정하지 않았다.

자원 적합성 평가는 기존 2160×3840 내부 Chromium/SwiftShader 렌더 구조와 문서상 한도를 비교한 것이다. Render/Railway에서 실제 OOM이 발생했다거나 HF/Actions에서 몇 분 걸린다는 실측은 하지 않았다. 기존 환경의 12초 HIGH 파이프라인 996.576초를 다른 제공사의 예상 시간으로 환산하지 않는다.


## 추가 검토: 개인 GitHub Codespaces — 원래 UI를 유지하는 조건부 후보

2026-10-06 03:07–03:10 UTC(12:07–12:10 KST)에 GitHub 공식 docs 원문을 HTTP 200으로 확인했다. 개인 계정의 포함 무료 quota 안에서 기존 Python 서버와 Docker·Chromium·FFmpeg를 함께 실행할 수 있는 가장 유력한 **대화형 후보**다. 이는 상시 운영 서비스가 아니며, 현재 계정의 남은 무료 quota·기존 결제 수단·예산과 외부 provider 생성은 확인하지 않았다. 실제 Codespaces 배포·휴대전화 접속·렌더 속도 실측을 통과했다는 뜻이 아니다.

- 공식 최소 머신은 **2 core·8GB RAM·32GB 저장 공간**이다. 실제 머신 선택 가능 여부는 계정·저장소·지역에 따라 달라진다. 기본값은 이용 가능한 최소 자원이며, 생성 화면에서 2-core를 확인해야 한다.
- 개인 GitHub Free 포함량은 월 **120 core-hours와 15GB-month**다. 2-core 머신에서 120 core-hours는 무료 compute가 전부 남았을 때 최대 약 **60시간의 활성 시간**이다. 초기 생성·설치·실행 시간도 활성 사용량을 소비한다. 15GB-month는 15GB 디스크 한도가 아니라 실제 파일·컨테이너 저장량을 시간에 따라 누적한 할당량이다. 기본 이미지 기반 dev container는 제외되지만, 사용자 지정 base image와 생성 자산·MP4는 계산 대상이다.
- **유효한 결제 수단이 없으면** 포함 quota 소진 시 추가 사용이 차단된다고 공식 문서에 명시돼 있다. 카드 등록 계정에서는 동일한 자동 $0 hard stop을 가정할 수 없다.
- 카드 등록 계정의 예산은 **Codespaces Product 범위**와 **Stop usage when budget limit is reached**가 필요하다. 알림만 설정하면 사용이 중단되지 않는다. 이번에 접근한 공식 원문은 모든 계정 UI에서 $0 값을 허용한다고 명시하지 않으므로, **$0와 실제 Stop usage 차단이 함께 저장되는지 사용자가 생성 전에 확인**해야 한다. 불가능하거나 모호하면 무료 배포 생성을 진행하지 않는다. 새 예산은 생성 전 사용료를 소급 차단하지 않는다.
- idle 기본은 **30분**, 사용자 설정 범위는 **5–240분**이다. 공식 deep-dive는 편집 파일 변경과 터미널 출력을 activity로 계산하므로 로그가 계속 출력되면 idle 종료되지 않는다고 설명한다. 단, idle 설정과 무관하게 **활성 실행 수명은 최대 12시간**이며 그 뒤 중지·재시작해야 한다. 렌더 keep-alive를 만들거나 종료 정책을 회피하는 방식은 사용하지 않는다.
- Codespace를 **중지해도 파일은 보존되지만 storage 사용량은 계속 누적**된다. 브라우저 탭만 닫으면 즉시 compute가 끝나는 것도 아니다. 작업 후 Stop을 명시하고, 외부로 결과·체크포인트를 보존한 뒤 더 쓰지 않을 Codespace만 사용자가 Delete해야 future storage 누적이 멈춘다. Delete는 이미 누적된 현재 월 사용량을 환불하지 않는다. 자동 삭제는 기본 30일이며 저장 공간의 영구 백업을 보장하지 않는다.
- 외부 앱 URL은 **https://CODESPACENAME-PORT.app.github.dev**이다. 기본 포트는 private로 본인만 접근하며 같은 GitHub 계정의 브라우저 로그인 흐름을 사용한다. public으로 바꾸면 URL을 아는 누구나 인증 없이 접근하므로, 현재 단일 사용자 엔진은 **private 유지**가 적합하다. 문서의 Change Port Protocol → HTTPS는 내부 앱 protocol 선택이다. 기존 Python HTTP 서버에는 HTTP upstream을 유지하며 외부 HTTPS 주소를 이용한다.
- 공식 repo deep link는 [생성·이전 작업 재개](https://codespaces.new/dimon3898-sys/yeonhwarok-free?quickstart=1)다. `?quickstart=1`는 일치하는 기존 Codespace를 먼저 재개하는 페이지를 연다. 로그인과 Create/Resume 선택은 사용자가 수행한다. 이는 이미 배포된 엔진 URL이 아니며, 검증되지 않은 machine/devcontainer query를 추가하지 않는다.
- 현재 `server.py`의 `--host 0.0.0.0 --port 8090`, 비동기 승인·render POST, 상대 경로와 Range 다운로드 구조는 동일 origin의 private forwarded HTTPS 뒤에서 작동하도록 구성할 수 있다. 프로젝트·cache·uploads는 Codespaces의 보존되는 **/workspaces** 아래에 있어야 한다. stop/rebuild 후 승인된 job을 명시적으로 재개하며, 체크포인트를 잃지 않게 한다. 기존 단일 사용자 렌더 lock·자산 라이선스·V3 그래픽을 바꾸지 않아도 된다.
- 8GB 한도가 실제 엔진의 최고 해상도 렌더를 견디는지, peak disk와 렌더 시간은 별도 local 제한 환경 시험 및 provider 실측이 필요하다. 이 조사는 문서만 확인했다. 현재 outbound GitHub API가 막혀 있고 runtime credential이 없으므로 사용자 대신 Codespace를 생성하거나 카드·계정 상태를 확인하지 않았다.

무료 조건을 유지하는 최소 사용자 절차는 **개인 부담 주체·남은 compute/storage quota 확인 → 결제 수단 없는 계정 또는 $0+Stop usage가 실제 저장되는 예산 확인 → 위 링크에서 2-core 선택·Create/Resume → private 8090 HTTPS URL로 앱 열기 → 작업 후 Stop 및 결과 외부 보존**이다. 카드 있는 계정의 비용 0원은 여기서 보장하지 않는다.

관련 공식 출처:
[기본 머신](https://raw.githubusercontent.com/github/docs/main/content/codespaces/about-codespaces/what-are-codespaces.md),
[무료 quota·요금](https://raw.githubusercontent.com/github/docs/main/content/billing/concepts/product-billing/github-codespaces.md),
[quota 계산](https://raw.githubusercontent.com/github/docs/main/content/codespaces/troubleshooting/troubleshooting-included-usage.md),
[예산 차단](https://raw.githubusercontent.com/github/docs/main/content/billing/how-tos/set-up-budgets.md),
[예산 소급 제외](https://raw.githubusercontent.com/github/docs/main/content/billing/concepts/budgets-and-alerts.md),
[idle 설정](https://raw.githubusercontent.com/github/docs/main/content/codespaces/setting-your-user-preferences/setting-your-timeout-period-for-github-codespaces.md),
[12시간 수명·보존](https://raw.githubusercontent.com/github/docs/main/content/codespaces/about-codespaces/understanding-the-codespace-lifecycle.md),
[터미널 activity](https://raw.githubusercontent.com/github/docs/main/content/codespaces/about-codespaces/deep-dive.md),
[private 기본값](https://raw.githubusercontent.com/github/docs/main/data/reusables/codespaces/port-visibility-settings.md),
[외부 HTTPS](https://raw.githubusercontent.com/github/docs/main/data/reusables/codespaces/using-tools-to-access-ports-1.md),
[repo 링크](https://raw.githubusercontent.com/github/docs/main/content/codespaces/setting-up-your-project-for-codespaces/setting-up-your-repository/facilitating-quick-creation-and-resumption-of-codespaces.md).


## Hugging Face 최신 저장소·Docker 상세

- 공식 spaces-overview 및 spaces-gpus 원문은 CPU Basic의 시간당 무료와 신규 compute 생성의 유료 플랜 필요를 **동시에** 명시한다. FREE 표는 생성 자격까지 무료라는 뜻이 아니다.
- CPU Basic은 inactive 48시간 후 sleep하고 방문하면 재시작한다. 현재 read-only 조사에서는 가짜 keep-alive를 만들거나 절전 정책을 회피하지 않았다.
- spaces-config-reference의 suggested_storage 설명에는 **“The persistent storage feature is no longer available so this setting will be ignored.”**라고 명시돼 있다. 과거의 persistent SSD 요금·/data 보존 설명을 현재 제공 옵션으로 재사용하면 안 된다.
- 현재 spaces-storage는 임시 로컬 파일시스템과 별도의 **Storage Bucket volume mount**를 설명한다. Bucket은 무료 생성·무료 allowance가 있고 초과 사용은 과금한다. Free public storage는 best-effort이며 Free private storage 표는 100GB다. 이것은 자동 제공되는 Space의 영구 로컬 디스크·무제한 무료 video scratch 보장이 아니다. 토큰·계정 자격·공개/비공개 데이터 조건을 따로 확인해야 한다.
- Docker 기본 노출 포트는 7860이며 README YAML의 app_port로 정한다. 컨테이너 runtime UID는 1000이다. 현재 server.py의 --host 0.0.0.0 --port 7860 설정은 별도 소스 변경 없이 가능하다.
- Spaces 외부 앱 주소는 HTTPS *.hf.space이고, 내부 Python HTTP 서버를 ingress 뒤에 둔다. outbound는 80·443·8080 포트만 허용한다고 원문에 명시된다.
- startup_duration_timeout 기본은 30분이고 변경 가능하다. 이는 시작 건강 상태 제한이지 렌더 job 또는 모든 HTTP 요청의 30분 제한이 아니다. 정확한 일반 job timeout·무료 bandwidth 숫자는 미확인이다.
- FFmpeg·Chromium·Node·Python은 일반 Dockerfile 의존성으로 설치할 수 있는 구조다. 이 프로젝트의 실제 HF Docker build는 수행하지 않았으며, 현재 제한 네트워크에서도 Hugging Face API 배포는 검증하지 못했다.

## Render·Railway·Fly 운영 세부

Render 공식 제공 Codex plugin README가 render-oss/skills를 원본으로 연결함을 확인했다. 해당 공식 자료는 0.0.0.0 바인딩 및 제공 PORT 사용을 요구하고 PORT는 흔히 10000이라고 설명한다. 이를 항상 고정된 포트라고 쓰지 않는다. 무료 서비스는 단일 인스턴스·persistent disk 불가이며 무료 background worker가 제공된다고 주장하지 않는다. 공식 가이드의 build 120분·pre-deploy 30분·start 15분 표기는 각각의 명령 제한이고 HTTP 연결이나 전체 worker lifetime과 혼동하지 않는다. 이 원문 확인만으로 public HTTPS 실서비스를 만들었다고 보고하지 않는다.

Railway는 Docker/container service와 자동 HTTPS를 지원하는 구조다. HTTP 연결은 계속 데이터가 전송되면 최대 15분, 무전송 상태는 5분 후 종료라는 원문을 확인했다. 기존 server.py처럼 POST로 작업을 받아 바로 202를 반환하고 상태를 polling하면 전체 렌더 시간 동안 한 연결을 유지할 필요가 없다. 이 timeout은 프로세스 background job의 수명과 다르다. Service build는 무료지만 일반 build hard timeout은 이번 자료로 미확인이다. RAM·CPU·저장·egress는 metering되고, egress는 $0.05/GB, volume은 $0.15/GB/month로 월 credit에서 차감한다. Free의 0.5GB volume 한도를 충분한 장면 캐시라고 간주하지 않는다.

Fly 공식 문서는 2026-09-23 MDX/Mintlify 이전을 기록한다. Trial은 카드 없이 시작 가능하나 카드 추가는 trial 종료·과금 개시다. 신규 조직은 상시 무료 tier·월 무료 allowance가 없다고 명시한다. rootfs는 임시이고 Fly Volume은 로컬 persistent storage다. 가장 작은 always-on shared-cpu-1x 256MB 예시는 최저 지역에서 $2.19/30일이며 egress 별도라 무료 추천이 아니다. 첫 10개 single-hostname SSL 인증서 무료라는 문구도 전체 VM 무료와 구분한다.

## GitHub Actions 하이브리드 상세

공개 저장소의 **표준 ubuntu-24.04 x64** worker를 선택한다. 최신 ubuntu-slim은 1 CPU, job 15분, heavy build 부적합으로 설명된다. 현재 샘플의 기존 환경 실제 16.6분 파이프라인조차 이 시간보다 길기 때문에 이를 무거운 worker 대안으로 추천하지 않는다. 표준 runner의 job 상한 6시간과 별개로 실행될 때 df·RAM·Chromium 초기화·실제 render 시간을 측정해야 한다.

무료 compute와 결과 저장을 분리한다. GitHub Free의 artifact allowance 표는 500MB, cache는 저장소당 10GB다. artifact는 기본 90일 후 만료하고 **다운로드에 GitHub 로그인·저장소 read access가 필요**하다. cache는 job VM의 영구 디스크가 아니므로 장면별 MP4·audit·Scene JSON hash·asset/renderer version을 가진 기존 캐시 계약을 유지해 export/restore해야 한다. 퇴출된 cache를 영구 백업으로 간주하지 않는다. 완성 MP4·QC·Scene Plan은 별도 불변 결과 저장을 사용한다.

Public Release asset은 별도 다운로드 후보다. 공식 원문은 release당 최대 1,000개 asset, 개별 파일 2GiB 미만, release 전체 크기·bandwidth 별도 상한 없음으로 설명한다. 일반 Git 단일 파일 100MiB 제한과 혼동하지 않는다. 모바일의 익명 다운로드에는 로그인 필요한 artifact 주소를 대신 제공하면 안 된다. 실제 Release 업로드·Range 재생·파일 SHA 확인은 이후 배포 단계의 검증이다.

GitHub 공식 수동 workflow 문서는 default branch의 workflow_dispatch, 입력 필드, Actions의 Run workflow 버튼을 설명한다. write permission이 있는 사용자 본인의 GitHub 모바일 브라우저로 주제·길이 입력 → 기획 workflow → 계획 확인 → 승인된 hash의 렌더 workflow를 실행하는 구조는 별도 제공사 토큰 없이 구성할 수 있는 후보다. 이번 조사에서 workflow나 원격 render를 생성·실행하지 않았다. 사용자 로그인·write access를 자동 충족했다고 가정하지 않는다.

GitHub Pages는 정적 검수·안내 UI만 가능하며 server.py API·thread·Chromium을 실행하지 않는다. 공식 문서는 commercial SaaS·거래 중심 사업의 무료 web hosting 용도를 허용하지 않는다. 개인 프로젝트의 정적 안내·계획 조회 사이트와 상용 생성 서비스를 구분한다. 문서상 site 1GB, soft bandwidth 월 100GB, deploy timeout 10분, custom Actions 외 build soft limit 시간당 10회다. 정적 페이지에 PAT을 넣지 않는다. job 안의 GITHUB_TOKEN이 브라우저에서 안전한 mutation 인증 backend를 대신해 주지 않는다.

## 현재 server.py 실제 호환 판단

현재 소스는 Local/LAN용 ThreadingHTTPServer다. CLI host·port·projects override가 있어 제공사 binding과 맞출 수 있고, 내부 renderer base_url은 loopback http://127.0.0.1:port를 사용한다. 상대 media/download URL, HEAD, Range 206, Content-Disposition을 제공하므로 같은 origin의 HTTPS ingress 뒤에서 모바일 재생·다운로드하는 구조와 맞는다.

렌더 요청은 사용자 승인·Plan Gate를 확인하고 202를 반환한다. daemon thread와 render_lock으로 무거운 작업을 한 번씩 진행하며 상태·체크포인트를 파일에 쓴다. 프로세스나 무료 host가 종료되면 daemon 작업은 끝나므로 파일이 실제 영구 보존되어야 회복 가능하다. --projects만 persistent volume으로 옮겨도 APP_ROOT/cache·uploads가 함께 보존되는 것은 아니다.

Python·Node·FFmpeg/FFprobe·Pillow/numpy/jsonschema·Playwright·system Chromium이 필요하다. 현재 renderer는 /usr/bin/chromium 또는 CHROMIUM_PATH, SwiftShader software WebGL, --disable-dev-shm-usage를 사용하며 HIGH/CINEMA 내부 2160 폭을 요구한다. world-simulation-shorts-engine과 형제 cinematic-world-map의 자산·src·node_modules 경로를 보존해야 한다. 공개 Docker build의 USER·writable cache/프로젝트·검증된 라이선스 자산 패키징은 별도 확인 사항이다. 기존 소스를 새로 작성하거나 그래픽을 2D placeholder로 바꾸는 해결책을 권하지 않는다.

서버에는 다중 사용자 인증·quota가 없다. POST는 Origin/Host가 같은지 검사하므로 별도의 Pages UI가 이 API에 cross-origin mutation을 바로 보낼 수 있다고 가정하지 않는다. 공개 렌더 worker를 연결할 때 인증은 기존 엔진 바깥의 deployment bridge에서 처리할 수 있지만 현재 runtime에는 해당 제공사 secret·identity가 없다. 이것은 완성 앱의 무료 원격 배포가 확인됐다는 근거가 아니다.

## 권장 선택과 남은 확인

1. 영상을 받는 사람에게 기존 공개 MP4/Release 다운로드를 제공하고, 신규 생성은 public 표준 Actions worker로 범위를 제한한다.
2. 모바일 기획·승인은 우선 사용자 GitHub 로그인·Run workflow 입력을 이용하는 후보로 정리한다. 별도 secret 없는 static app가 인증 API를 자동 호출하는 것처럼 만들지 않는다.
3. 기존 Scene 분할·부분 재렌더·캐시·QC·라이선스 구조를 그대로 사용하며 job 종료 전에 checkpoint와 결과를 내보낸다.
4. 실제 worker에서 자산 크기·디스크 잔여·RAM·렌더 시간을 측정한 뒤 해당 모드의 길이 지원을 주장한다. 이 조사에서는 75초나 새 샘플을 렌더하지 않았다.
5. 원래의 간단한 모바일 UI와 상시 작업 수신 서버가 반드시 필요하면 제공사 계정·허용 host·인증 연결·진정한 영구 저장이 확보된 뒤 배포 검증이 필요하다. HF 신규 Docker paid-plan 조건을 무시하거나 무료 서비스의 sleep을 우회하지 않는다.

계정·카드·API secret 없이 현재 여기서 완성 앱을 free always-on host에 실제로 배포했다고 주장할 수 없다. 이 보고서는 공식 조건·소스 호환성의 조사 결과이며 실서비스 HTTPS, 원격 실제 MP4 생성, 물리 스마트폰, 무료 비용 보장에 대한 end-to-end PASS가 아니다.

## 공식 출처

- [HF Spaces overview](https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/hub/spaces-overview.md), [hardware/sleep](https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/hub/spaces-gpus.md), [Docker](https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/hub/spaces-sdks-docker.md), [configuration](https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/hub/spaces-config-reference.md), [storage](https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/hub/spaces-storage.md), [Storage Buckets](https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/hub/storage-buckets.md), [storage limits](https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/hub/storage-limits.md).
- [Render official plugin ownership](https://raw.githubusercontent.com/renderinc/render-codex-plugin/main/README.md), [instance types](https://raw.githubusercontent.com/render-oss/skills/main/skills/render-scaling/references/instance-types.md), [configuration guide](https://raw.githubusercontent.com/render-oss/skills/main/skills/render-deploy/references/configuration-guide.md), [web services](https://raw.githubusercontent.com/render-oss/skills/main/skills/render-web-services/SKILL.md).
- [Fly pinned free trial](https://raw.githubusercontent.com/superfly/docs/1cf7488c7577de811549364ccb8b6a83f120e5ef/about/free-trial.mdx), [pricing](https://raw.githubusercontent.com/superfly/docs/main/about/pricing.mdx), [volumes](https://raw.githubusercontent.com/superfly/docs/main/volumes/overview.mdx).
- [Railway pinned plans](https://raw.githubusercontent.com/railwayapp/docs/f584b91714ce2a0c62fa518d8246514745dfd368/content/docs/pricing/plans.md), [trial](https://raw.githubusercontent.com/railwayapp/docs/main/content/docs/pricing/free-trial.md), [card FAQ](https://raw.githubusercontent.com/railwayapp/docs/main/content/docs/pricing/faqs.md), [serverless](https://raw.githubusercontent.com/railwayapp/docs/main/content/docs/deployments/serverless.md), [HTTP limits](https://raw.githubusercontent.com/railwayapp/docs/main/content/docs/networking/public-networking/specs-and-limits.md).
- [Actions runner table](https://raw.githubusercontent.com/github/docs/main/data/reusables/actions/supported-github-runners.md), [job limits](https://raw.githubusercontent.com/github/docs/main/content/actions/reference/limits.md), [runner reference](https://raw.githubusercontent.com/github/docs/main/content/actions/reference/runners/github-hosted-runners.md), [billing](https://raw.githubusercontent.com/github/docs/main/content/billing/concepts/product-billing/github-actions.md), [free quotas](https://raw.githubusercontent.com/github/docs/main/data/reusables/billing/actions-included-quotas.md), [artifact downloads](https://raw.githubusercontent.com/github/docs/main/content/actions/how-tos/manage-workflow-runs/download-workflow-artifacts.md), [manual workflow](https://raw.githubusercontent.com/github/docs/main/content/actions/how-tos/manage-workflow-runs/manually-run-a-workflow.md), [Pages limits](https://raw.githubusercontent.com/github/docs/main/content/pages/getting-started-with-github-pages/github-pages-limits.md), [Releases](https://raw.githubusercontent.com/github/docs/main/content/repositories/releasing-projects-on-github/about-releases.md).

각 원문의 UTC·HTTP status·SHA256·바이트·인용 범위는 [REPORT.json](REPORT.json)에 기록했다.
