# Studio V1 HTTPS bootstrap recovery — final candidate

**STUDIO_HTTPS_CANDIDATE_CPU_VERIFIED_HARDWARE_PENDING**

HTTPS Origin 없이 안전한 설정 UI를 시작하고, 인증된 실제 주소 등록 후 기존 Studio로 전환하는 별도 확장 후보를 구현·빌드·등록했습니다. 실제 #5373의 과거 최초 종료 원인과 종료코드는 여전히 미확인입니다. 현재 확인된 누락 Origin 시작 오류는 원본 이미지에서 재현됐으며 이번 후보가 이를 분리합니다.

## 1. 원본 재현 및 수정 전후

고정 원본 이미지 `sha256:5a35e44947aaed3fffe39aad2352ff17c22b9375b4591e635129feed4ec90d94`를 실제 무료 CPU Docker에서 실행했습니다. 종료코드는 아래 실행별 코드이며 gCube 과거 종료코드가 아닙니다.

| 실제 CPU 조건 | 종료코드/상태 | 검증 |
|---|---|---|
| BASELINE_HTTPS_ORIGIN_MISSING | 1 | PASS |
| BASELINE_OWNER_CODE_MISSING | 1 | PASS |
| BASELINE_INVALID_DIGEST_CONSTRUCTOR | 1 | PASS |
| BASELINE_OPERATOR_POLICY_MISSING_CONFIGURATION_ONLY | 0 | PASS |
| EXTENSION_OWNER_CODE_MISSING | 1 | PASS |
| EXTENSION_ORIGIN_MISSING_SETUP_AND_RESTART | RUNNING | PASS |
| EXTENSION_INVALID_DIGEST_WEB_ALIVE | RUNNING | PASS |
| EXTENSION_OPERATOR_POLICY_MISSING_WEB_ALIVE | RUNNING | PASS |

원본 Origin 누락: `STUDIO_HTTPS_ORIGIN_REQUIRED`, exit1. 새 후보: 웹 서비스 HTTP200 SETUP, 제작은503으로 차단됩니다. 관리자 코드 누락은 계속 exit1로 fail closed입니다. 정책/이미지 설정이 미완료여도 UI를 시작할 수 있으나 제작에는 원래의 엄격한 검사를 적용합니다. 잘못된 image digest 형식과 Scene/이미지 바인딩 불일치도 집중 검사했습니다.

CPU 환경의 기존 admission 자식은 저장소/하드웨어 사전검사에서 차단될 수 있습니다. 실제 로그에 나타난 단계만 기록했으며 이를 NVIDIA 검사 성공이나 실제 gCube 실패 재현으로 해석하지 않습니다. 자식 종료 후 UI가 유지되고 자동 재시도/렌더링이 없음을 확인했습니다.

## 2. 구현 및 보호

새 `https_bootstrap.py`가 원본 private 경로/owner 검사를 재사용하고, UID/GID1000 및 원본 장치 그룹 allowlist로 UI를 먼저 시작합니다. `https_server.py`는 설정/health 라우팅과 제작 admission만 감싸며, 일반 운영은 원본 StudioApplication/HTTP handler/Controller/runtime을 그대로 호출합니다. 원본 파일을 복사하여 새 렌더러를 만들지 않았습니다.

`setup_core.py`는 원본 OwnerSessions와 RequestPolicy를 재사용합니다. 관리자 코드,120초 browser-cookie challenge, 한 번만 쓰는 CSRF 확인, 명시적 HTTPS Origin 확인이 필요합니다. Host/Origin/forwarded header에서 등록 주소를 자동 추론하지 않습니다. 무인증 설정 변경/제작 API, CORS 허용, 인증/CSRF/GPU 검사 우회는 없습니다.

Origin 저장 전에 설정·운영 세션 키를 폐기하고 private0700 디렉터리의0600 파일에 원자적으로 저장합니다. 주소 변경과 제작 요청은 직렬화합니다. 느린 무인증 본문 수신과 health 응답은 이 잠금을 점유하지 않도록 분리했습니다. 기존 private Origin과 환경변수가 충돌하면 등록 주소의 UI를 유지하면서 제작을 차단합니다.

모바일 PNG를 실제 검토하여 테스트 이미지의 한국어 글꼴 누락과 굵은 글씨의 fallback 우선순위 문제를 수정했습니다. 저장소의 기존 OFL 글꼴을 UI 전용으로 재사용했고, 지도/영상 폰트·글로벌 OS 폰트는 변경하지 않았습니다. 원본 UI CSS 규칙은 보존하며 UI 글꼴 선언만 추가합니다. WOFF2는 한글11172자를 포함하며 독립 재생성이 BIT_EXACT입니다. 라이선스·원본 SHA·recipe는 `web/fonts/`에 있습니다.

원본 Studio51/부모 엔진373 파일의 엄격한 SHA 검증 PASS, Git 보호 경로 변경0건입니다. FINAL/V4/renderer/camera/frontier/ASTRA/SFX/cache/claims/영상/기존 이미지/관리자 Secret을 변경·삭제·재설정하지 않았습니다. 상세 검증: `PROTECTION.json`.

## 3. 최종 무료 검증

- 집중 Python **50/50 PASS** — 설정/인증/Origin/CSRF/세션 폐기/느린 요청/정책/이미지 바인딩/원본 CSS 보존.
- 실제 원본/확장 CPU Docker **8/8 PASS** — 시작, 차단, 등록, 인증, 재시작.
- 실제 TLS 모바일 Chromium390×844 **11/11 PASS** — 한국어 font 다운로드·우선순위, 관리자 인증, 명시적1회 등록, 정상 로그인 전환, SFX·길이 선택 UI, 재접속, 무인증 제작 차단.
- PNG4장 원본과 외부 다운로드 HTTP200/SHA 일치. 최종 설정/제작 화면에서 한국어 제목·레이블·본문의 가독성을 실제 PNG로 확인했습니다.
- Secret Scan **0 findings**, 새 소스/테스트/설정 문서/workflow 범위. 이전 이미지 검사는 재사용했습니다.
- 신규 image build/push 및 별도 runner immutable digest pull/SHA 검증 **PASS**.
- 기존 전체104/168개 검사는 반복하지 않았습니다. 기존 Scene·SFX·Dropbox·GPU 실행 코드는 소스 해시 보호 및 UI/bridge 집중 회귀 대상으로 재사용했습니다.

증거: [최종 무료 CI](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39082529518), `runs/39082529518-1/build.json`, `pull.json` 및 SHA256SUMS. 초기에 발행된 다른 HTTPS 후보들은 보존했으며 최종 배포 권장본이 아닙니다. 이번 최종 후보만 아래에 지정합니다.

## 4. 최종 이미지와 저장

- Branch: `development/studio-https-bootstrap-20261018`
- Runtime source commit: `62d433b1c8e17b6c237890ade10e2b07e4df1b47`
- Tag: `studio-https-v1-85aef26-39082529518-1`
- Tag reference: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:studio-https-v1-85aef26-39082529518-1`
- Immutable reference: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:468deaa122ec9c687908e2142d1a5cd82331a8bc447d62154eabb5ff7c416833`
- Image digest / runtime binding: `sha256:468deaa122ec9c687908e2142d1a5cd82331a8bc447d62154eabb5ff7c416833`
- Extension manifest SHA256: `b46b2bff3e8ef5887e1e61b9c0d835d1135b57f2810ddcc94e36e7c461eec665`
- 원본 Studio manifest SHA256: `1f4129faaeb59027429d4d531da2b7e7b50156ca7c1652e700dd542c935b88de`
- Required temp-only files: **0**. Runtime source/assets/fixtures/recipe/evidence가 GitHub와 새 이미지에 보존됩니다. 테스트용 임시 TLS 키와 개발 도구 venv는 실행 필수 파일이 아닙니다.

## 5. 사용자 설정과 다음 행동

실제 GPU 배포는 이번 작업에서 하지 않았습니다. 검수 후 사용자가 수동 배포할 때:

1. 위 새 이미지, 포트8080, Command 비움, 공유 메모리2GB, 기존 `/world-storage` Dropbox 마운트와 NVIDIA graphics/utility 설정을 사용합니다.
2. 기존 `WORLD_ENGINE_STUDIO_OWNER_CODE` Secret을 그대로 유지하고 `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST=sha256:468deaa122ec9c687908e2142d1a5cd82331a8bc447d62154eabb5ff7c416833`를 설정합니다. `WORLD_ENGINE_STARTUP_MODE=normal`, `WORLD_ENGINE_RENDER_MODE=gpu-required`를 유지합니다.
3. 첫 시작의 `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN`은 없어도 됩니다. gCube가 실제 발급한 HTTPS 포트8080 주소를 열고, 그 실제 Origin과 기존 관리자 코드를 입력합니다. 주소를 명시적으로 확인·등록한 뒤 기존 Studio에 새로 로그인합니다.
4. 실제 GPU 요금·최대 비용·실행시간·재시도 상한·시간대 포함 승인 만료시각이 있는 `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON`을 기존 Secret/설정에서 제공해야 제작이 허용됩니다. 현재 값이나 승인 범위를 임의로 만들지 않았습니다. 정책이 없거나 만료됐으면 서버는 살아 있으나 제작은 차단됩니다.
5. 이후 검증된80초 Scene/제작 입력을 사용합니다. 터미널 명령이나 중간5초 샘플은 필요하지 않습니다. 실제 GPU admission과 원래 preflight/명시적 제작 동의를 통과해야 합니다.

자세한 설정과 Origin 변경/충돌 처리는 `GCUBE_SETUP.md`에 있습니다. 같은 private 파일시스템/컨테이너 재시작에서 지속성은 확인했지만, gCube가 컨테이너를 교체하는 경우 writable layer 지속성은 확인되지 않았습니다. 확인된 실제 Origin을 gCube 설정에도 저장하거나 승인된 private POSIX 볼륨을 사용해야 교체 후 유지됩니다. Dropbox를 private credential 저장소로 취급하지 않습니다.

## 6. 실제 GPU에서 남은 검증

실제 gCube HTTPS proxy Host/Origin 전달과 플랫폼 probe, NVIDIA/WebGL2 admission, 운영 정책에 따른80초 제작, 실제 VRAM/시간/비용, MP4 품질, Dropbox 외부 동기화/다운로드는 이번 무료 CPU 작업에서 검증하지 않았습니다. 이 작업의 UI/CPU PASS를 NVIDIA/80초 영상 PASS로 표시하지 않습니다. 유료 실행0건, FINAL 승격0건입니다.

## 7. 모바일 검수 화면

- [01_MOBILE_HTTPS_SETUP.png](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/d8f1b9fe8453612ae77aab27804b5e8d324a00b7/world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/runs/39082529518-1/mobile/01_MOBILE_HTTPS_SETUP.png) — HTTP200, source/download SHA256 identical.
- [02_MOBILE_HTTPS_CONFIRMATION.png](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/d8f1b9fe8453612ae77aab27804b5e8d324a00b7/world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/runs/39082529518-1/mobile/02_MOBILE_HTTPS_CONFIRMATION.png) — HTTP200, source/download SHA256 identical.
- [03_MOBILE_HTTPS_REGISTERED.png](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/d8f1b9fe8453612ae77aab27804b5e8d324a00b7/world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/runs/39082529518-1/mobile/03_MOBILE_HTTPS_REGISTERED.png) — HTTP200, source/download SHA256 identical.
- [04_MOBILE_STUDIO_READY.png](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/d8f1b9fe8453612ae77aab27804b5e8d324a00b7/world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/runs/39082529518-1/mobile/04_MOBILE_STUDIO_READY.png) — HTTP200, source/download SHA256 identical.

다운로드 확인의 기계 판독 기록은 `REVIEW_DOWNLOAD_VERIFICATION.json`에 있습니다. 테스트용 화면이며 실제 gCube 주소나 관리자 비밀값을 포함하지 않습니다.

## 8. 실제 추가·수정 파일

모든 구현은 새 namespace/workflow 안에만 추가됐습니다. 기존 보호 파일 수정은0건입니다.

- `.github/workflows/studio-https-bootstrap-v1.yml`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/Dockerfile`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/GCUBE_SETUP.md`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/IMPLEMENTATION_CHECKPOINT.md`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/ci_package.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/frozen.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/https_bootstrap.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/https_server.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/manifest.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/setup_core.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/tests/container_probe.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/tests/mobile_probe.mjs`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/tests/test_bootstrap.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/tests/test_health_concurrency.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/tests/test_https_server.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/tests/test_setup_core.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/tests/tls_fixture.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/web/fonts/LICENSE.txt`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/web/fonts/PROVENANCE.json`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/web/fonts/build_font.py`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/web/fonts/studio-setup-ko.woff2`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/web/setup.css`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/web/setup.html`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/web/setup.js`
- `world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/web/studio-font.css`
