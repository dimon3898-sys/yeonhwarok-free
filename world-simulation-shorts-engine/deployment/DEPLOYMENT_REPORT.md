# 무료 모바일 운영 검증 — 2026-10-06

**결과: 제한적 성공.** 기존 엔진을 보존한 인증·background job·복구·다운로드 계층과 Codespaces 배포 설정을 준비했다. 로컬 2CPU/8GB Docker에서 실제 HIGH 영상까지 검증했다. 외부 웹앱 환경은 아직 생성하지 않았다. GitHub 계정의 로그인·무료 할당량·과금 차단 확인과 개인 Codespace 생성은 사용자가 해야 한다. localhost와 저장소 생성 페이지는 실행 중인 모바일 웹앱 URL이 아니다.

## 사용자가 해야 할 일

1. GitHub 개인 계정에 로그인해 남은 Codespaces 무료 할당량을 확인한다. 유효한 결제수단이 없는 계정은 공식 문서상 초과 사용이 차단된다. 결제수단이 있다면 **전체 개인 계정의 Codespaces 제품 전체 $0 예산 + Stop usage**가 실제 적용됐는지 확인한다. $0 설정을 할 수 없거나 차단이 불명확하면 환경을 만들지 않는다. 카드나 유료 플랜을 추가하지 않는다.
2. https://codespaces.new/dimon3898-sys/yeonhwarok-free?quickstart=1 에서 기존 환경을 재개하거나 **2-core** 환경 하나를 생성한다. 이는 생성/재개 페이지다.
3. Ports의 **7860 / Private**을 연다. 비공개 workspace의 `world-simulation-shorts-engine/deployment/runtime/mobile/owner-code.txt` 코드를 앱 로그인에 입력한다. GitHub private-port 인증과 앱 코드 인증을 모두 사용한다. 작업 후 Stop하고, 삭제 전 결과·계획·체크포인트를 백업한다.

실제 웹앱 주소는 환경 생성 후 표시되는 `https://CODESPACENAME-7860.app.github.dev`다. 아직 검증되지 않은 주소를 만들어 안내하지 않는다. 가입·Secret·카드·유료 API를 자동으로 추가하지 않았다.

## 무료 후보 판정

2026-10-06 공식 자료의 원문 URL·응답 상태·SHA·인용을 `docs/evidence/free_mobile_hosting_research_v001/`과 `free_mobile_codespaces_terms_v001/`에 보존했다. 조사 당시 원본 서버8090에 대한 검토 문장은 조사 기록이며, 최종 외부 wrapper 포트는7860/내부 콜백7861이다.

| 방식 | 판정 및 확인한 제한 |
|---|---|
| GitHub Codespaces 개인 Free | 조건부 후보. 월120 core-hour는2-core 최대60 활성시간이며 남은 계정 할당량에 의존한다. 2-core/8GB/32GB, 저장15GB-month. 중지 후에도 저장 사용량이 누적되고 사용자 Docker 이미지도 계산 대상이다. 기본 idle30분/설정5–240분, 최대 연속12시간. 상시 무료 서버가 아니다. |
| Hugging Face Spaces | 무료 CPU basic 자체는2CPU/16GB/50GB ephemeral이나, 신규 Gradio/Docker compute Space 생성은 현재 PRO/Team 조건을 요구한다. 이 앱의 비용0원 신규 배포 후보에서 제외했다. |
| Render Free | 0.1CPU/512MB·idle15분·휘발성 저장이며 무료 persistent disk/background worker가 없다. 이 렌더러의 실사용 환경으로 부적합하다. |
| Railway Free / Fly trial | Railway의 작은 무료 자원·이미지/디스크 제한과 Fly의 짧은 trial/유료 전환 조건 때문에 상시 무료 전체 엔진으로 선택하지 않았다. |
| GitHub Actions | 공개 저장소 표준 runner는 batch 후보이나 웹앱 호스팅 용도가 아니다. 계정/저장소 billing을 확인하지 않고 workflow를 활성화하지 않았다. |
| 현재 Cloud + GitHub deliverables | 실제 사용 가능한 추가 서버비0원 대안. 현재 Cloud의 기존 이용 조건에 의존하므로 Cloud 자체를 무료 서비스라고 주장하지 않는다. 완성 파일의 공개 HTTPS 다운로드를 검증한다. |

GitHub API와 일부 배포 서비스는 현재 실행환경의 네트워크 정책에서 접근이 거부됐다. 정책을 우회하지 않았다. 이미 성공한 공식 자료 수집을 반복하지 않았으며, 이번 재개에서 자체 요청에503은 관측되지 않았다. 이전 자료와 실패 로그를 보존했다.

## 실제 구현과 보존

- 원본 `server.py`, 엔진, UI, V3/Flat v004/Rhythm의 인증 소스28개 SHA를 유지했다. 기존 추적 파일 변경0개. 새 기능은 `deployment/`의 별도 wrapper다.
- 소유자 코드·scrypt/HMAC 세션·같은 Origin 검사·로그인 제한·안전한 파일 경로·미디어 형식 검수·최대 자원 한도를 추가했다. 코드/쿠키는 Git·내보내기에서 제외한다. 외부 접근에서 loopback이라는 이유로 인증을 생략하지 않는다.
- 공개 서버와 내부 렌더 콜백을 분리했다. 내부7861은 loopback GET-only이며, Chromium의 favicon 읽기만204로 허용한다. 실제 로그인 Origin 문제는 same-origin referrer 정책으로 수정했고 외부/null Origin은 계속 차단한다.
- 승인된 정확한 계획 hash의 job을 서버 프로세스로 실행하고 browser 수명과 분리했다. job ticket·checkpoint·Scene cache를 저장하고 미완료 승인 job만 재시작한다. 완성 job은 재실행하지 않는다.
- 반복 실행 가능한 Codespaces startup, nonroot UID1000 Docker, persistent state/cache/audio named volume, strict validated CLI export를 준비했다.
- `PRODUCTION_SHORTS`는 HIGH/FAST_PLUS/TTS OFF/Subtitle OFF/BGM ON/SFX ON이다. 기존 FAST/NORMAL/CINEMATIC·TTS·자막 옵션과 자연어 기획·버전 선택은 유지했다.
- 제한 환경의 기본 한도는180초/40 Scene·동시1+대기1·프로젝트30·업로드16MiB·남은 디스크2GiB·worker4시간이다. 과거 전체 생성기 기능을 삭제하지 않았다.

## 실측 검증

12초 QA는 기존 승인된 Rhythm 테스트를 새 프로젝트 `project_7d940e04242c`로 복사했다. **S001의 카메라 timing만1.8→1.733333초로 변경**해2.5초 Scene 하나를 새로 렌더했고 나머지4개는 기존 검증 캐시를 재사용했다. 기존 MASTER/75초 영상은 렌더하지 않았다.

| 항목 | 실제 결과 |
|---|---|
| 환경 | Docker CPU2개/RAM8GiB, UID1000. Python3.12.15·Node24.21.0·FFmpeg5.1.9·Chromium154.0.8037.92. 실제 Codespaces가 아닌 로컬 자원 제한 시험이다. |
| 출력 | 12.000초 /1080×1920/30fps/H.264/yuv420p/bt709, 내부2160×3840. BGM+SFX ON, TTS+자막 OFF. |
| 새 Scene 렌더 | 439.182576초, 새 Scene1개·캐시4개. |
| 조립·mux | 1.868508초. |
| 전체 프레임 QC | 14.716439초. 360프레임 decode, black0/정확한 duplicate0, QC PASS. |
| 성공한 실행 합계 | 457.927959초. 과거 캐시 생성 시간과 이전 실패 시도는 포함하지 않는다. 전체12초를 처음부터 렌더한 시간도 아니다. |
| 기존 같은 길이 S001 | 과거4CPU 작업에서257.323초. 이번439.183초는 약1.707배이나 카메라 timing·Chromium/FFmpeg도 다르므로 순수 CPU 비교나 provider benchmark가 아니다. |
| 모바일 크기 검증 | 실제 Chromium375×812, 입력·계획·승인·새 브라우저 재로그인·같은 job 복구 PASS. main 영상12초 전체재생, 360decoded/drop0/corrupt0/stall0. 물리폰/직접 청취는 검증하지 않았다. |
| 다운로드 | 13개 browser 첨부 다운로드와 HTTP SHA/bytes 일치, Range206. main17,667,422B, 무음17,246,069B. |
| 사건 검수 | 의미 있는 사건12개, 평균1.0091초/최대2.2667초, 첫3초4개/사건종류11개/Peak1개. 카메라 이동만을 사건으로 세지 않았다. |
| 오디오만 변경한 v002 | BGM OFF, 영상 Scene JSON 그대로.5개 모두 캐시,0개 native render. 완료 Scene checkpoint 직후 자신의 gateway 종료→동일 job 자동 재개→모든 Scene SHA 유지→QC PASS. 재개 실행14.428981초, job 접수~완료 wall30.434488초(중지·재시작·큐 대기 포함). |
| 영상 동일성 | v001/v002의 무음 MP4 SHA와360프레임 RGB decode SHA가 같아 오디오 변경으로 영상이 재렌더되지 않았음을 확인했다. |
| 이전 버전 | v002 생성 후 모바일 UI에서 v001 선택·전체재생·다운로드 PASS, 이력2개. |
| 최종 이미지 교체 | 최종 Dockerfile로 만든 새 이미지 `0895e3d53f4f…`에서 코드 수동 패치 없이 UID1000·2CPU/8GiB·Production/자산 검수 PASS. 기존 state/cache/audio 볼륨3개를 연결해 v001/v002 complete 상태가 보존됐다. |
| 수정된 복구 hook | 새 이미지의 v003 오디오 전용 재시작 회귀 시험에서 동일 job 복구·5개 cache·0개 Scene 렌더·모든 Scene SHA 유지·자동 provenance 보존 보정·원본 strict export 모두 PASS. 재개 실행15.367552초, QC11.468550초. v002와 최종/무음 영상 해시도 같다. |
| 관련 테스트 | Security/job23개·CLI16개·복구 증거10개, 총49개 PASS. 원본 인증 소스28/28 SHA 일치. |

SFX 검수본 v002는 Docker build와 동시에 재생한 첫 검사에서 브라우저 drop2가 있었으나 파일360프레임/QC는 정상이고 재생이 끝났다. 직접 청취/물리폰 PASS로 확대하지 않는다. 렌더 peak RAM은 이번 시험에서 별도 기록하지 않았으므로 관측된 순간 메모리를 peak라고 보고하지 않는다. 70–80초 전체 무료 환경 성능은 측정하지 않았다.

첫 시도는 favicon403으로0/75프레임에서 실패했다. 해당 job·부분 파일·실패 로그를 보존하고 내부 favicon 정책만 수정한 뒤 실패 단계부터 새 attempt로 재개했다. 재시작 시험에서는 원본 엔진의 manifest에 cache 사용 사유가 남고 최종 result에는 checkpoint 사용 사유가 기록되어 strict export가 차단됐다. 새 deployment 계층에서 승인/QC/Scene·media·audit SHA를 검증하고 provenance 항목만 일치시킨다. 원 manifest 원시 bytes는 exclusive backup에 보존하고 receipt를 남기며, 다른 필드 차이는 실패한다. 기존 strict exporter와 렌더러는 변경하지 않는다.

최종 이미지 교체 때 VFS Docker의 반복 빌드로 여유 공간이2GiB 미만이 되어507 보호가 생성 요청을 차단했다. 렌더는 시작되지 않았다. 이번 작업에서 생성한 미사용 중간 이미지·build cache만 정리해 여유 공간4.9GiB를 확보했고, 같은 계획을 재시도해 복구 시험을 통과했다. 이전 검증 컨테이너는 중지 상태로 보존했고 프로젝트/cache/audio 볼륨을 삭제하지 않았다. 이 실패와 bounded wait 로그도 남겼다.

## 근거·운영 제한

실제 browser 보고서는 `docs/evidence/free_mobile_docker_{approve,playback}_v001/`, 오디오만 변경한 복구 증거는 `free_mobile_runtime_validation_v001/AUDIO_ONLY_RESTART_RESULT.json`, 전체 QC는 새 `deliverables/WORLD_SIMULATION_ENGINE/FREE_MOBILE_DEPLOYMENT_v001/native_v001/`에 있다. 최초 실패한 테스트 명령의 잘못된 module 이름 로그도 보존했고 실제16개 CLI 테스트는 올바른 module로 통과했다.

외부 Codespaces 생성/build/포트 인증·다운로드와 실제 휴대폰 hardware는 아직 검증하지 않았다. 로컬 시험을 provider 실측으로 표시하지 않는다. 무료 계정 할당량·과금 차단을 직접 확인할 수 없어 사용자 단계에서 멈춘다. 현재 추가 유료 서비스·카드·GPU API 활성화는0건이다.

온보딩의 `start_skill` 초안을 검증된 startup·복구·보존 절차로 저장했다. 기존 install/network/Secret 설정은 유지했다. 초안 저장은 환경 게시·외부 배포 완료를 뜻하지 않는다. 출처·다운로드·최종 Git 반영 증거는 저장소의 새 배포 산출물에 별도로 보존한다.
