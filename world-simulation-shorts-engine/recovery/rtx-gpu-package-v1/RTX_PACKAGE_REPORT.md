# RTX 4080 SUPER 실행 패키지 보고

이번 결과는 기존 코드의 별도 실행 패키징입니다. 영상 기능·시각 효과를 추가하거나 승인된 소스를 튜닝하지 않습니다. 실제 NVIDIA 하드웨어 검증, GPU 렌더링, 영상 품질 판정, gCube 배포는 수행하지 않습니다.

## 재사용 기준과 보호

| 항목 | 고정 기준 |
|---|---|
| ASTRA CPU | `a002d89492734bfa9d17b98145ee6cb9a3b366a2` |
| 65422 전선 발광 | `45af879d7417abba58e9ebd59d8e6630a785ac28` |
| Phase A | `21036824888dffbe232934d0332420c5910b98a4` |
| 이전 GHCR 이미지 | `sha256:7e32d5a7a66c00f162b4275dfa4b88e7556abadf2a2f7ea473fa8a70d611e31e` |
| 새 작업 브랜치 | `development/rtx-gpu-package-20261015` |
| 구현 체크포인트 | `25fa96e038c07fe30c1ae4a99b069b20d32e56d1` — 원격 확인 완료 |

CPU 기준 커밋에 Phase A와 전선 커밋이 이미 포함되어 있습니다. 두 기준 사이의 `web`, 기존 `deployment/gcube`, 전선 recovery, V5 recovery 변경은 0건으로 확인했습니다. 브랜치를 병합하거나 기존 checkout의 미커밋 작업을 덮어쓰지 않았습니다. 기존 FINAL·승인 MP4·렌더러·공개 API 변경은 0건입니다.

이전 이미지 감사 결과를 재사용했습니다. 이전 이미지는 승인된 최신 ASTRA/150-frame 전선 런타임을 실행하는 패키지가 아니므로 덮어쓰거나 그대로 최신 통합 이미지라고 지정하지 않습니다. 이전 digest는 출처 증거입니다. 새 이미지의 실제 build/push/digest는 생성하지 않습니다.

## 구현 파일

| 파일 | 기능 |
|---|---|
| `source_contract.json`, `stage_package.py` | 원본 140개 파일, 66개 런타임 route, 184개 import 연결의 명시적 closure·커밋·SHA·크기 검증. Git 없는 컨테이너에서도 staged bytes 검증 |
| `package_overlay.json`, `prepare_context.py` | 새 패키지 파일만 명시적으로 선택하여 isolated Docker context 생성 |
| `bootstrap.py` | 할당 장치 그룹 보존, engine UID 전환, 전용 runtime/storage 준비, CPU 의존성 확인 |
| `gpu_launcher.py` | GPU 필수, 허용 모델/드라이버/VRAM/공유 메모리 검사, 기존 NVIDIA WebGL2 draw/readPixels probe 재사용, software 거부, health-only 기본 진입점 |
| `hardware_runtime.mjs` | 기존 65422 런타임의 scene/camera/renderer factory/진단 재사용. 브라우저 실행 경계만 별도 하드웨어 모드로 연결 |
| `hardware_render.mjs` | 기존 150-frame 캡처/인코딩 설정 재사용, 별도 출력·원본 보존, 소스/하드웨어 기반 resume·캐시 검사 |
| `Dockerfile`, `Dockerfile.dockerignore`, `dependency_contract.json` | 원본 소스 변경 없이 native GDAL/libnetcdf, Node/Playwright/Chromium, FFmpeg, EGL/OpenGL/Vulkan 의존성을 구성 |
| `verify_dependencies.py` | 실제 버전·module origin·native API·Float32/signed elevation/PNG/neutral 보존 검사. 누락과 버전 충돌은 실패 |
| `GCUBE_EXECUTION.md`, `DEPENDENCY_VALIDATION.md` | 배포 전 설정, 명령, 출처 pin, 실제 실행한 검사와 미실행 항목 |
| `GPU_HARDWARE_VALIDATION_TODO.md` | 실제 GPU·영속성·새 영상·ASTRA GPU 연결의 남은 검사 |

전체 새 파일 및 SHA는 `PACKAGE_FILES.json`, `SHA256SUMS`에 기록합니다. 원본 소스 계약 SHA는 `5938d0f33168daae415d9573701cafe290bcdd9850a14f4cb61c966560640180`입니다. 원본 파일 총량은 70,186,954 bytes이며 전체 저장소나 node_modules를 무차별 복사하지 않습니다.

## 하드웨어 실행 경계

지원 기본값은 RTX 4080 SUPER 16 GB이며 4090/5090을 허용합니다. 한 개의 실제 allocation, 모델·UUID·드라이버 일치, 실제 colored draw/readPixels 통과가 필요합니다. SwiftShader/llvmpipe/lavapipe/CPU 모드는 렌더링 전에 실패합니다. 단위 테스트의 주입 결과는 `TEST_ONLY`이며 실제 서버/렌더 dispatch에 사용할 수 없습니다.

기본 VRAM 예산은 8 GiB, 여유 예약은 2 GiB입니다. 실제 사용량 증가를 polling하여 초과/장치 변경/조회 실패 시 중단합니다. 드라이버 차원의 강제 메모리 예약은 아닙니다. `/dev/shm`은 최소 1 GiB available, 설정 권장은 2 GiB입니다. 결과는 전용 `/world-storage/rtx-gpu-package-v1`에 저장해야 하며 실제 gCube 영속 mount와 재시작 보존은 후속 확인 대상입니다.

기존 ASTRA 파싱·공급자·취득 계획·캐시·Scene 준비는 다시 구현하지 않습니다. 중립 CPU 데이터와 지역 샘플을 포함하되, 새 GPU texture packing/material/shoreline mask 연결은 이번 작업에 포함하지 않습니다. 승인된 renderer를 임의로 수정하여 그 연결을 해결하지 않습니다.

## 검증과 미실행 항목

정확한 테스트별 결과와 명령은 `evidence/CPU_VALIDATION.json`, 의존성 관측은 `DEPENDENCY_VALIDATION.md`와 evidence에 기록합니다. 기존 233개 CPU suite와 전체 Permanent Gate를 반복하지 않습니다. 기존 전선 집중 회귀 4개는 재사용된 표현의 보호 확인을 위해 실행합니다.

실제 NVIDIA GPU/드라이버 주입, Chromium 하드웨어 WebGL2, hardware frame capture, 새 MP4, gCube registry pull·storage·SSH 연결은 미실행입니다. 새 이미지가 빌드되지 않았으므로 최종 이미지 크기와 digest는 미확인입니다. 환경의 Docker 저장 공간 부족 및 MCR proxy 차단은 실제 발생한 제한으로 기록하고, 기존 자료 삭제·proxy 우회 없이 공식 native base/browser 대안을 사용합니다.

현재 검증된 source/launcher 패키징과 미검증 하드웨어 항목을 구분합니다. 영상 품질 PASS, 기존 영상과 BIT_EXACT, GPU 사용 가능 여부를 선언하지 않습니다.

## 저장 및 종료

필수 runtime 소스·asset·fixture·계약·build 구성·실행 문서는 GitHub 개발 브랜치에 저장합니다. context와 임시 native 검사 rootfs는 원본 계약으로 재생성할 수 있으며 필수 temp-only 파일은 0개입니다. Secret Scan과 최종 원격 커밋 확인 결과는 `evidence/SECRET_SCAN.json`, `evidence/PERSISTENCE.json`에 기록합니다.

최종 준비 판정은 실행 증거의 결과를 따릅니다. 이후 사용자의 검수와 실제 하드웨어 실행 승인을 기다립니다. GPU 배포·유료 작업·FINAL 승격·새 영상 기능 개발을 자동 시작하지 않습니다.

## 최종 CPU 준비 판정

**GPU_PACKAGE_READY_FOR_HARDWARE_VALIDATION**. 집중 테스트 104개 PASS, staged 원본/overlay 160개 검증 PASS, 기존 API 66개 HTTP 200·원본 SHA 일치, Compose config 및 BuildKit `--check` PASS(경고 0), 실제 GPU 없음 실패 처리 PASS, Secret Scan 0건입니다. 기존 FINAL/렌더러/셰이더/카메라/전선 변경 0건, 필수 temp-only 0개입니다. 새 이미지 build·digest·GPU/영상 품질 검증은 미실행이며 후속 실제 하드웨어 검증이 필요합니다. 사용자 검수 후 다음 실행 범위를 결정합니다.
