# RTX 5090 무료 호환성 검토 — 2026-11-08 KST

결론: 기존 검증 이미지의 코드·설정에서 RTX 5090 전환을 막는 정적 조건은 발견하지 않았다. 이미지 재빌드, Chromium 플래그 변경, 캡처·인코더 변경은 하지 않는다. 실제 RTX 5090 드라이버, WebGL2/Vulkan 초기화, 300프레임 완주는 사용자 배포 후 확인해야 한다. 하드웨어 PASS가 아니다.

검토 기준은 `deployment/korean-war-20s-native-20261107`의 `44164d508b4aedca6993a3bb5001ba9fb74ebe2a`, 기존 설치 패키지·정식 입력 연결 증거, gCube 저장 설정이다. 기존 PASS는 무효화하지 않았으며 재실행하지 않았다.

| 항목 | 무료로 확인한 근거 | 판정/실행 후 조건 |
| --- | --- | --- |
| 모델 허용 | `recovery/rtx-gpu-package-v1/gpu_launcher.py`, `recovery/production-studio-mvp-v1/studio_runtime.py`, `controller/safe_capture_export.py`에 RTX 5090 허용 조건이 이미 존재 | 코드 수정 불필요 |
| 드라이버 | NVIDIA 570.86.16 지원 목록에 RTX 5090 명시. Blackwell은 open kernel modules가 필요하고 kernel/userspace 드라이버 버전은 일치해야 함 | 실제 gCube 드라이버는 노드 미할당으로 미확인. 특정 버전으로 강제 변경하지 않음 |
| 컨테이너 그래픽 | 기존 `NVIDIA_DRIVER_CAPABILITIES=all` 유지. `deployment/gcube/graphics_runtime.py`는 provider-mounted NVIDIA EGL/GLX 라이브러리와 실제 Vulkan API 버전을 사용 | 호스트 드라이버가 공급하는 라이브러리·장치·ICD 연결은 실제 배포 사전검사 대상 |
| Chromium | 기존 고정 Chromium 155.0.8059.79, Playwright 1.62.1. `backend/profile_contract.mjs`는 ANGLE/Vulkan, WebGL, headless, GPU-required 조건과 UID1000 sandbox를 유지 | NVIDIA 하드웨어 draw 검증이 필요. 소프트웨어 fallback으로 PASS 처리하지 않음 |
| GPU 메모리 | 런처 총 VRAM 최소15GiB, 기본 사용예산8GiB와 예약2GiB. gCube 선택 사양32GB | 사양상 용량 충족. 실제 free VRAM은 기동 후 확인 |
| 컨테이너 자원 | vCPU12/RAM63GB/disk937GB, 기존 공유 메모리3GB. 기존 사전검사의 공유 메모리 하한2GiB 및 private disk free2GiB | 사양 검토 완료. 실제 할당/여유 공간은 기동 후 확인 |
| 캡처/인코딩 | `capture_nvidia.mjs` → 기존 `capture_vulkan.generated.mjs`; FFmpeg CPU libx264, 30fps/yuv420p | CUDA 전용 컴파일·NVENC 전환 불필요. vCPU 감소가 인코딩 시간에 줄 영향은 미측정 |
| 영구 기록 | 기존 ActiveCheckpointMirror → `/world-storage/capture-checkpoint-<jobid>/CAPTURE_CHECKPOINT.json`, 원래 mounted readback 게이트 유지 | 새 실제 마운트 읽기/쓰기·외부 회수는 사용자 배포 후 확인. private 원문 전체 보존 기능은 아님 |
| 비용 계산 | 기존 policy의 gpuHourlyRate360은 변경된 GPU 가격 상한1300과 불일치 | 이 필드만1300으로 수정. 7200초/10000KRW/재시도0/만료 시각 유지. 표시 단가는 VAT 별도이며 실제 청구액 증명은 아님 |

기존 이미지에 포함된 런타임 경로와 설치 해시 증거를 재사용했다. 새 GPU에서 발생하지 않은 오류를 가정해 이미지를 바꾸지 않았고, 기존 4080 성공을 5090 성공으로 전환해 기록하지 않았다.

## 공식 자료

- [NVIDIA 570.86.16 지원 GPU 목록](https://download.nvidia.com/XFree86/Linux-x86_64/570.86.16/README/supportedchips.html)
- [NVIDIA Open Linux Kernel Modules](https://download.nvidia.com/XFree86/Linux-x86_64/570.86.16/README/kernel_open.html)
- [NVIDIA Container Toolkit: driver capabilities](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)
- [NVIDIA Container Toolkit: host driver prerequisite](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- [Chrome: headless GPU initialization and verification](https://developer.chrome.com/blog/supercharge-web-ai-testing)

공식 자료는 호환 조건의 근거이며 gCube의 아직 미할당된 실제 노드에 대한 실행 증거가 아니다.
