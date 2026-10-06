# gcube 배포 검증 보고서

2026-10-06 KST. 공개 GHCR 이미지와 휴대폰 운영 설정을 준비했습니다. 기존 생성기·영상·캐시·Git 이력을 보존했습니다. **실제 gcube Workload, NVIDIA GPU 성능·과금, Android 실기, 클라우드 저장소 재배포 검증은 사용자 충전·Workload 생성 이후 단계입니다.** [휴대폰 5단계 안내](GCUBE_SETUP.md).

## 검증 결과

| 항목 | 확인한 결과 | 근거 |
|---|---|---|
| 공개 이미지 | `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v001`. 전체 이미지 build → 실제 CPU boot → owner 로그인 → 미승인 12초 계획 → 모바일 UI → 측정 JSON 첨부 확인 후 게시합니다. 익명 manifest/config HTTP 200을 확인했습니다. 최신 digest·정확한 소스 commit은 게시 증거에 기록합니다. | [GHCR 게시 증거](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/evidence/GHCR_FINAL_PUBLICATION.json), [CI workflow](../../../.github/workflows/gcube-image.yml) |
| 원본 보존 | 인증된 28개 source SHA 불변. 기존 MASTER·renderer·engine·web·data·테스트·assets를 수정하지 않았으며 75/80초 렌더를 실행하지 않았습니다. | [원본 비교·기존 회귀 분류](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/evidence/regression_classification.json) |
| 배포 검사 | **106/106 PASS**, 27.888초. GPU admission, bootstrap, native storage, 실제 HTTP/Origin/auth, fixture, 진단, EGL/Vulkan 선택을 검사했습니다. 별도 workflow 모의 공격 15종과 Bash 구문 3개도 통과했습니다. | [최종 검사 로그](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/evidence/gcube_focused_final.log) |
| 자연어·기본 설정 | 실제 375×812 Chromium 로그인→주제→미승인 계획 작성. FAST_PLUS/HIGH, TTS·자막 OFF, BGM·SFX ON 유지. | [모바일 계획 검사](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/evidence/MOBILE_PLANNING.json) |
| 짧은 실제 렌더 | 기존 12초 HIGH/FAST QA 계획, 5 Scene 모두 새 native 렌더, cache 재사용 0. 1080×1920/30fps/H.264, AAC 48kHz stereo. TTS·자막 OFF, BGM·SFX ON. | [native HTTP 인수 검사](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/evidence/HTTP_NATIVE_RENDER.json), [재접속 후 규격 검사](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/evidence/HTTP_NO_RERENDER_AFTER_RESTART.json) |
| 자동 QC | 전체 360프레임 검사 PASS, publication_quality=true. 주요 프레임 시각 확인. | [QC](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/qc_report.json), [contact sheet](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/contact_sheet.png) |
| 모바일 재생·다운로드 | 375×812 Chromium에서 12초 끝까지 재생, 360 decoded frames, dropped/corrupted 0. 실제 13개 첨부파일 다운로드. final/muted 서버 SHA·Range·HEAD 검수 PASS. 물리 Android 검사는 대기입니다. | [브라우저 결과](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/evidence/MOBILE_PLAYBACK_DOWNLOAD.json) |
| 재시작 복구 | task-owned 컨테이너만 재시작. 완료 Scene 5개·checkpoint 5개·계획/승인·최종 MP4 두 개, **14파일 SHA 전부 동일**. 원래 project complete 유지, 렌더 재요청 없음. 새 첫-boot QA는 미승인 상태로 준비됩니다. | [복구 증거](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/evidence/restart_proof.json) |
| 휴대폰 측정 기록 | 로그인 후 `/gcube/benchmark.json` 링크 실제 클릭·JSON 첨부 다운로드 PASS. CPU/GPU·WebGL·RAM 표본만 정제하며 secret/env/UUID/개인 파일 경로를 노출하지 않습니다. 포인트 소비량은 null로 남습니다. | [측정 링크 검사](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/evidence/mobile_measurement_browser.json) |
| 기존 전체 회귀 | **419개 method**, 569.851초. 기존 단일 planner 테스트의 **3개 subtest 실패**는 FAST 기대와 이미 승인된 FAST_PLUS 기본값의 불일치입니다. 원본 테스트를 변경하거나 실패를 통과로 계산하지 않았습니다. | [기존 로그](../../../deliverables/WORLD_SIMULATION_ENGINE/GCUBE_CPU_ACCEPTANCE_v001/evidence/engine_regressions.log) |

로컬 native 영상은 이전 의존성 이미지에 현재 소스를 읽기 전용으로 연결한 **4 CPU/8GB RAM 비교 모드**에서 생성했습니다. 전체 GHCR 이미지의 CPU 부팅·로그인 검사는 CI에서 따로 수행했습니다. NVIDIA GPU나 gcube 노드의 실측으로 보고하지 않습니다. 첫 entrypoint→healthy 측정은 2.063086초이며 gcube 이미지 pull·노드 배치 시간은 포함하지 않습니다. 로컬 Docker 생성 호출은 13.188758초였습니다.

## 실제 CPU 시간

| 단계 | 실제 시간 |
|---|---:|
| FLAT 4 Scene, 10초 | 1,288.318077초 |
| HERO 1 Scene, 2초 | 1,609.822298초 |
| 전체 graphics | 2,898.140375초 |
| audio 준비 | 1.390565초 |
| assembly/audio mux | 2.055060초 |
| QC | 10.673994초 |
| 해당 버전 pipeline 전체 | **2,915.365194초, 48분 35초** |

Scene 실행 측정이며 기존 이미지 build·pull·코드 수정·모바일 재생 시간은 별도입니다. 첫 FLAT 구간은 기존 회귀 검사가 함께 실행된 기간과 일부 겹쳐 통제된 성능 비교로 취급하지 않습니다. 과거 동일 길이 FAST 자료는 FLAT 1,062.568579초 + HERO 1,398.629692초 = graphics 2,461.198270초였습니다. 이전 ONE_URL 20.600초는 Scene 5개를 모두 재사용한 조립·오디오·QC 실행으로 native/GPU 성능 비교값이 아닙니다. 실제 Codespaces native 성능 기록이나 gcube GPU 개선율은 확보되지 않았습니다.

QA 픽스처의 화면·텍스트·FAST timing은 원래 승인 계획을 보존했습니다. 새 자연어 Production 기본값 FAST_PLUS와 구분합니다. GPU fingerprint 소스 3개와 인증된 그래픽 소스 28개를 변경하지 않았습니다.

## GPU·영속성·비용의 남은 검증

Flat/Earth의 Three.js WebGL 그리기가 GPU 가속 대상입니다. 동일 engine UID로 NVIDIA 모델·드라이버·VRAM과 실제 WebGL2 draw/renderer를 확인해야 합니다. 지정하지 않은 GPU profile은 EGL→실패 시 Vulkan을 최대 한 번 검사하며, 두 경우 모두 하드웨어 draw가 필요합니다. CPU 전환은 명시적 비교 모드에서만 허용합니다. Canvas/readback·PNG 전송·`libx264` 인코딩·오디오·QC에는 CPU 작업이 남으며 CUDA Toolkit/NVENC를 사용하지 않습니다.

운영 Personal Storage는 gcube 자체 저장소의 `/world-storage`입니다. 시작 시 실제 mount·독립 process flock·0600·atomic rename·파일/디렉터리 fsync를 검사합니다. 로컬 bind 유지 및 단위 검수는 gcube Stop/재배포·장애 내구성의 증명이 아닙니다. 실제 저장소 요금·mount·같은 URL 유지·HTTPS proxy 전달 헤더도 확인해야 합니다.

이번 작업에서는 유료 gcube Workload를 만들거나 포인트를 사용하지 않았습니다. **GPU 테스트 소비 포인트·80초 1편 비용·월 30편 비용은 미측정**입니다. 실제 node 시간당 가격과 80초 Scene 구성·GPU/CPU 병목별 실측 시간을 확보한 뒤 부팅·유휴·재시도·네트워크·저장소·세금까지 합산합니다. 짧은 영상 시간을 단순 비례하여 확정 비용으로 보고하지 않습니다. RTX5070은 실제 제공·VRAM/CPU/RAM·가격이 충분한 최저가 후보일 때 우선합니다.

브라우저 닫기·로그아웃·서버 종료는 gcube 과금 중지가 아닙니다. 다운로드·저장 확인 후 **Workload 배포중지→종료**를 확인합니다. 실제 gcube 로그인/결제/Workload 생성만 사용자에게 남겼으며 Docker·Linux·Git·설치 명령을 요구하지 않습니다.

## 재사용 환경 설정

Codex 환경 초안에 현재 checkout과 gcube 개발·시작·검증 지침을 저장했습니다. 기존 설치 스크립트는 유지했습니다. 초안 저장은 현재 runtime 적용·환경 publish·gcube 배포를 의미하지 않으며, gcube 사용에 과거 Modal token 요구사항은 필요하지 않습니다.
