# WORLD ENGINE: NVIDIA·Vulkan·실행 권한 근거

조사 기준: 2026-11-01. 연구 전용. GPU·진단·테스트 실행, 운영 코드 수정, 이미지 빌드·게시는 모두 0회다. 이 문서는 기존 증거의 의미와 다음 판별에 필요한 정보만 정리한다.

## 판단

최신 작업 `studio-7d7a08be1d09817c903f41484bce3f33`의 보존된 안전 진단도 `UP2_WEBGL2_REQUIRED`, `PAGE_EVALUATE_FIRST_NATIVE_DRAW`, 0프레임이다. 앞선 작업 `studio-37dfbc8dab786a4d7c99cde6fae2f821`과 같은 **WebGL2 컨텍스트 생성 단계 실패**까지 확인됐다. 이 결과는 NVIDIA 라이브러리 누락, GPU 장치 권한, ANGLE 초기화, Chromium GPU 프로세스 중 어느 하위 단계가 실패했는지 구분하지 못한다.

현시점의 우선 조사 계층은 **실제 UID1000 캡처 프로세스의 Chromium→ANGLE→Vulkan→주입된 NVIDIA 그래픽 스택**이다. 특정 드라이버 결함이나 sandbox 권한 문제를 확정할 근거는 없다. Startup health 성공은 실제 캡처 성공의 대리 지표가 될 수 없다. 시작 health 코드에는 root/wrapper/OffscreenCanvas 경로가 있고 캡처 코드는 UID1000·직접 Chromium·DOM canvas를 요구하기 때문이다. 이 비교는 소스 기준이며 최신 실패 시점의 실제 wrapper 선택·UID·argv 관측은 미확보다. 이것은 두 실행의 비교 조건이 다르다는 사실이며, 차이의 존재가 원인을 증명하지는 않는다.

## 적용 버전과 공식 근거

| 구분 | 확인한 기술 사실 | 프로젝트 적용과 한계 |
|---|---|---|
| NVIDIA 580.159.03 | 해당 정확한 버전의 공식 Linux x86_64 배포 디렉터리와 README가 존재한다. `.run` 파일의 디렉터리 표시는 2026-04-24다. [N01] | 과거 성공 드라이버 버전은 실제 존재하는 공식 버전이다. 최신 실패 노드가 같은 드라이버였다는 증거는 별도 필요하다. |
| NVIDIA 580 Vulkan ICD | 이 버전은 `libGLX_nvidia.so.0`와 `libEGL_nvidia.so.0`를 Vulkan ICD로 사용할 수 있다. 기본 manifest는 전자를 참조하며 X11 client library가 없는 환경에 대해 후자를 설명한다. [N02] | 과거 성공 ICD가 `libGLX_nvidia.so.0`였다는 사실은 정상 구성이 될 수 있다. 이름만 보고 오류라고 판단하거나 임의로 EGL로 바꿀 근거가 없다. |
| NVIDIA Container Toolkit | `utility`는 NVML·nvidia-smi, `graphics`는 OpenGL/EGL/Vulkan용이며, `NVIDIA_DRIVER_CAPABILITIES`는 컨테이너에 주입할 드라이버 구성요소를 선택한다. [N03] | nvidia-smi 성공만으로 Vulkan/WebGL 준비를 증명할 수 없다. 과거 `all` 설정은 graphics가 의도됐음을 뜻하지만 현재 실제 mount 결과까지 보증하지 않는다. |
| Toolkit host injection | 공식 코드에서 EGL vendor manifest, Vulkan ICD JSON, 그래픽 라이브러리·symlink를 발견하고 컨테이너에 제공한다. [N04] | 같은 응용 이미지 digest라도 다른 호스트 드라이버·runtime 주입 결과는 가능하다. 현재 이미지의 부모 패키지 재사용과 최신 호스트 주입 동일성은 별개다. |
| Vulkan Loader | `VK_DRIVER_FILES`가 `VK_ICD_FILENAMES`보다 우선한다. 환경변수 미설정이면 표준 manifest 검색을 사용한다. JSON을 찾더라도 그 JSON이 가리킨 공유 라이브러리의 로딩은 별도다. [N05] | 과거 `VK_ICD_FILENAMES=null`은 실패 증거가 아니다. 기본 발견 경로가 성공했을 수 있다. 정확한 현재 ICD와 라이브러리 해석 결과가 미확보다. |
| Vulkan Loader 보안 | setuid/setgid 또는 filesystem capabilities 등 elevated 실행에서는 일부 환경변수와 사용자별 경로가 무시될 수 있다. [N05], [N06] | root 여부만으로 이 보안 모드가 적용됐다고 단정하지 않는다. 실제 secure-execution 조건이 기록되지 않았다. UID1000 캡처와 root health를 동일하다고 간주하지 않는다. |
| Chromium sandbox | Linux Chromium은 namespace와 seccomp 등 여러 sandbox 층을 사용하며 GPU 프로세스에도 seccomp가 적용된다. [N07] | sandbox가 관련될 수 있는 구조적 이유는 있지만 기존 nonroot 성공도 있었다. 현재 거부 로그 없이 sandbox 해제 또는 privileged 설정을 처방하지 않는다. |
| Linux proc | `/proc/PID/environ`은 최초 exec 환경을 나타내며 이후 환경 변경을 전부 반영하지 않는다. 접근은 `PTRACE_MODE_READ_FSCREDS` 검사 대상이다. [N08] | 진단 v1의 다른 프로세스 `/proc` 읽기는 실제 worker의 자기 환경 전달과 다르다. root라는 이름만으로 컨테이너 내 모든 읽기 성공을 보증하지 않는다. 실패 errno가 없으므로 권한 실패는 미확정이다. |

버전 주의: Toolkit의 현재 공식 문서는 1.20.0의 CDI/JIT-CDI 그래픽 장치 제한 변경도 설명하지만, gCube 호스트 Toolkit 버전·동작 모드는 미확보다. 해당 최신 동작을 현재 노드의 사실로 소급 적용하지 않는다. Khronos와 Chromium의 일반 문서는 설명 구조의 근거이며, 현재 배포 바이너리에 대한 실행 검증은 아니다.

## 실제 코드와 환경 전달

코드 기준은 `296402e71257c7847d0045215ca0cdaf3dd700d2`다. [nvidia_backend.py](https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/nvidia_backend.py#L63)의 `_runtime_environment()`는 정확한 키 allowlist다. `NVIDIA*`, `VK*` 전체를 전달하지 않는다.

| 캡처 자식에게 전달됨 | 해당 함수에서 전달되지 않음 |
|---|---|
| `NVIDIA_VISIBLE_DEVICES`, `NVIDIA_DRIVER_CAPABILITIES`, `VK_ICD_FILENAMES` | `VK_DRIVER_FILES`, `VK_ADD_DRIVER_FILES`, `VK_LOADER_DRIVERS_SELECT`, `VK_LOADER_DRIVERS_DISABLE` |
| `HOME`, `LD_LIBRARY_PATH`, `LIBRARY_PATH`, `DISPLAY`, `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR` | `XDG_CONFIG_HOME`, `XDG_CONFIG_DIRS`, `XDG_DATA_HOME`, `XDG_DATA_DIRS` |
| `GPU_BACKEND`, `WORLD_ENGINE_RENDER_MODE`, `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST` 등 정해진 실행 키 | 나머지 키 및 비밀값 |

`_verify()`는 `GPU_BACKEND=vulkan`, `WORLD_ENGINE_RENDER_MODE=gpu-required`, normal startup mode, 지정 digest 값 및 EUID/EGID1000을 요구한다. 이 검사는 전달 설정과 소스 무결성의 조건을 확인하며 실제 Vulkan 장치 생성의 성공을 대신하지 않는다. 같은 함수의 과거 성공 증거가 있으므로 allowlist 자체를 새 회귀라고 단정할 수 없다. 다만 현재 호스트/health 경로가 위에서 제외된 키에 의존했다면 실제 캡처 경로만 다를 수 있다는 **조건부 판별점**이 생긴다. 민감 환경 전체를 수집하지 말고 관련 키의 존재·허용된 값·전달 여부만 비교한다.

## 성공·실패 비교

| 항목 | 실제 180프레임 성공 | 최신 0프레임 실패 | 판단 |
|---|---|---|---|
| 작업 | `studio-03d9b670cd764ce5823ea4720af1b410` | `studio-7d7a08be1d09817c903f41484bce3f33` | 다른 작업 증거를 섞지 않는다. |
| GPU/driver | RTX4080 SUPER / 580.159.03 | 같은 작업에 귀속된 장치·driver 상세 미확보 | 배포 설정이나 과거 기록으로 채우지 않는다. |
| 실제 graphics renderer | ANGLE, NVIDIA Vulkan1.4.312, RTX4080 SUPER | WebGL2 null | Chromium의 GPU 하위 원인 미확보. |
| Vulkan loader | `1.3.275.0-1build1` | 이미지 상속 경로는 있으나 작업 시점 런타임 사실 미확보 | loader1.3와 driver API1.4의 숫자 차이만으로 불일치를 확정하지 않는다. 성공 기록이 존재한다. |
| capabilities | `NVIDIA_DRIVER_CAPABILITIES=all` | 실제 캡처 환경 미확보 | intent와 실제 graphics 주입은 구분한다. |
| ICD | NVIDIA manifest, `libGLX_nvidia.so.0`, API1.4.312, override null | 같은 작업의 ICD 선택·라이브러리 로딩 미확보 | EGL ICD 강제 변경 근거 없음. |
| Chromium/Playwright | 155.0.8059.79 / 1.62.1 | 부모 이미지 재사용, 현 작업 실행 바이너리/argv 증명 미확보 | 이미지 관계를 runtime attestation으로 표현하지 않는다. |
| sandbox/user | nonroot sandbox 성공; 당시 숫자 UID 미기록 | 캡처 코드 EUID/EGID1000 요구, root health와 다른 경로 | UID 차이를 원인으로 단정하지 않는다. |
| 결과 | 180프레임 캡처·MP4 | 첫 native draw 전 0/300 | 최신 실패의 라벨·FFmpeg 성능 문제를 조사할 단계가 아니다. |

최신 설정에는 `surface-restore-v1-41288263483`, digest `sha256:c9fa126b0bf0d06c109bbe45f9fe14b5cc71de4282a4a57455b3b5f19d3366b5`가 저장됐다. 설정 저장은 실제 실패 프로세스의 image ID/argv attestation이 아니다. 옵션 복원 후에도 null이 보고됐으므로 `--disable-vulkan-surface`만으로 해결됐다는 주장은 성립하지 않는다. 해당 복원 작업과 기존 PASS를 다시 실행할 이유는 없다.

## 원인 후보와 가장 작은 판별

| 후보 | 수준 | 연결되는 근거 | 필요한 최소 증거 | 확인된 경우에만 가능한 최소 조치 |
|---|---|---|---|---|
| 실제 캡처의 ANGLE/Vulkan graphics 초기화 실패 | **유력한 계층**, 특정 원인 미확정 | WebGL2 null, CPU 계획·소스검사 통과, root health와 다른 실행 | 같은 job의 GPU process/ANGLE/Vulkan 안전 오류, 종료 코드, 실제 argv | 최초 실패를 가리킨 구성요소만 수정. |
| 호스트 NVIDIA graphics 구성요소 주입/ICD 해석 불완전 | 가능성 | utility와 graphics 분리; 이미지 밖 host injection; ICD 발견과 SO 로딩 분리 [N02]–[N05] | 같은 UID1000 경로의 선택 ICD, loader 실패 코드, 실제 driver SO 해석 및 device access 결과 | 빠진 mount/참조/권한 항목만 provider 설정에서 교정. 추측으로 패키지 재설치하지 않는다. |
| health와 캡처의 env/사용자/sandbox 차이 | 가능성 | 실제 경로 차이와 명시적 allowlist | 두 경로의 관련 키 전달 여부, EUID/EGID, GPU 하위 오류 | 필요한 안전 변수 또는 정확한 접근 조건만 복원. sandbox 전체 해제 금지. |
| runtime cgroup/device 접근 상실 | 가능성 낮음, 조건부 공식 사례 | NVIDIA는 legacy hook·container update·systemd reload 후 GPU 접근 상실 사례를 설명한다. 주된 증상에 NVML Unknown Error가 있다. [N09] | 같은 실패 시점 NVML/device 오류 및 runtime update 이력 | 확인된 provider/runtime 원인만 처리. 일반적인 WebGL2 null의 확정 원인으로 사용하지 않는다. |
| `libGLX_nvidia.so.0`의 X11 client 의존성 누락 | 근거 부족 | 해당 driver 공식 조건은 존재 [N02] | 실제 라이브러리 resolution/누락 의존성 오류 | 필요한 의존성 복구 또는 공식 지원 ICD 선택 검토. 현재는 임의 변경 없음. 과거 같은 부모 성공이 반대 근거다. |
| 진단 v1의 `/proc` 권한/UID 전환 실패 | 진단기 실패 후보일 뿐 | `DIAG_ENVIRONMENT_LAUNCH_FAILED`는 stage/errno를 버림; `/proc/PID/environ`은 접근 검사 대상 [N08] | 이미 저장된 안전 stage/errno/type 또는 원문. v2 자체의 원격 실행 증거는 없음 | 확인된 v1 조건만 검토. renderer 원인과 동일시하지 않음. 기존 JS의 현재 profile pin 불일치도 선행 해결 대상이며 그대로 실행하지 않음. |

## 알려진 공식 사례의 적용 한계

580.159.03 문서의 Vulkan/X.Org 장치 열거 제약은 X 서버에 연결하는지, X.Org 버전과 표시 대상 GPU인지에 따라 달라진다. 현재는 단일 GPU·headless 실행에 대해 필요한 X 설정 증거가 없다. 이 사례를 근거로 X 서버를 새로 도입하지 않는다. 같은 문서의 관리자 권한 제한은 GPU 성능 카운터와 관련되며 일반 WebGL 렌더링을 위해 관리자 권한이 필요하다는 뜻이 아니다. [N10]

NVIDIA Toolkit troubleshooting의 SELinux 거부, runtime/cgroup 접근 상실은 각각 실제 거부 로그·해당 runtime 조건이 있을 때 적용한다. 보안 기능 비활성화, 임의 CAP_SYS_ADMIN 추가, 전체 container 재생성은 이번 증거에서 도출되는 처방이 아니다. [N09]

## 다음 최소 행동

1. 이미 확보한 최신 작업의 failure와 현재 소스·설정 연결을 보존한다. 최신 failure에 GPU 하위 진단이 없음을 명시한다.
2. 현재 저장된 같은 작업의 GPU process stderr 또는 loader 오류가 접근 가능하면 그것만 읽는다. 없다면 과거 성공의 내용을 최신 실행값으로 채우지 않는다.
3. 향후 별도 승인된 단 한 번의 진단에는 **실제 캡처와 같은 UID1000·Chromium 바이너리·sandbox·argv·allowlist·DOM WebGL2 호출**을 기준으로 삼는다. 기존 진단 기능을 우선 검토하되, 현재 JS profile pin 불일치와 capture CLI의 단축 모드 미지원을 먼저 해결할 수 있어야 한다. 호환성과 증거 보존 준비 전에는 실행 준비 완료가 아니다. [현재 실행 제한](../ROOT_CAUSE_AND_PLAN.md)을 따른다.
4. 한 실행에서 job ID와 image identity, browser exit, 안전한 GPU/ANGLE/Vulkan 오류, 선택 ICD, driver identity, 장치 접근 결과를 함께 귀속시킨다. 전체 환경변수·토큰·민감 경로는 기록하지 않는다. GPU 수명주기·비용 승인은 별도다.
5. 실제 null 원인이 해결된 뒤에만 10초 캡처로 이어간다. 이번 연구만으로 GPU WebGL2 PASS 또는 MP4 제작 PASS를 선언하지 않는다.

공식 출처와 적용 범위는 `sources.json`에 기계 판독 형식으로 보존했다. NVIDIA FAQ URL 한 건은 fetch timeout으로 읽지 못했으며 재시도하거나 그 내용을 근거로 삼지 않았다.

[N01]: https://download.nvidia.com/XFree86/Linux-x86_64/580.159.03/
[N02]: https://download.nvidia.com/XFree86/Linux-x86_64/580.159.03/README/installedcomponents.html
[N03]: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html
[N04]: https://github.com/NVIDIA/nvidia-container-toolkit/blob/main/internal/discover/graphics.go
[N05]: https://github.com/KhronosGroup/Vulkan-Loader/blob/main/docs/LoaderDriverInterface.md
[N06]: https://github.com/KhronosGroup/Vulkan-Loader/blob/main/docs/LoaderInterfaceArchitecture.md
[N07]: https://chromium.googlesource.com/chromium/src/%2B/0b6120702e8f69ce43b34b02903a1d32a0be07d3/docs/linux/sandboxing.md
[N08]: https://man7.org/linux/man-pages/man5/proc_pid_environ.5.html
[N09]: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/troubleshooting.html
[N10]: https://download.nvidia.com/XFree86/Linux-x86_64/580.159.03/README/knownissues.html
