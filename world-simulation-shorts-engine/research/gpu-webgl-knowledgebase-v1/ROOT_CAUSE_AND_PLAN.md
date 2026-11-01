# 근본 원인 후보와 다음 최소 복구 계획

**확정한 직접 실패 조건은 WebGL2 context 생성 null이다. null을 만든 native 근본 원인은 미확정이다.** 다음 작업은 브라우저 옵션을 더 바꾸는 것보다 동일 실패 작업의 실제 실행 환경과 GPU 하위 오류를 연결하는 데 우선순위를 둔다.

근거 축: [최신 failure](evidence/latest-job/CAPTURE_DIAGNOSTIC.json), [코드 경로·로그 한계](system/SYSTEM_ARCHITECTURE.md), [성공/실패 비교](ENVIRONMENT_COMPARISON.md), [브라우저 공식 근거 B01–B13](browser/OFFICIAL_BROWSER_SOURCES.json), [NVIDIA 공식 근거 N01–N10](nvidia/sources.json).

## 후보 평가

| 후보·발생 원리 | 확신 수준 | 프로젝트와 공식 근거 / 반대 증거 | 최소 판별 증거 | 확인된 경우 최소 수정 |
|---|---|---|---|---|
| 컨텍스트 생성 실패 자체 | **확인됨** | latest `UP2_WEBGL2_REQUIRED`; runtime getContext null assert. WebGL2 명세의 null 의미[B11] | 이미 확보. 반복 재현 불필요 | 이 assertion을 제거하거나 우회하지 않음 |
| 실제 Chromium GPU process→ANGLE→native graphics 초기화 문제 | **유력한 조사 계층**, 세부 원인 미확정 | 브라우저 launch/import 이후 WebGL2 null. headless GPU flags는 초기화 성공 보장 아님[B01], [B10] | 같은 작업의 GPU process stderr/exit·ANGLE/Vulkan 오류·실제 argv | 최초로 확인된 실패 구성요소만 수정 |
| NVIDIA graphics 주입·ICD·라이브러리 로딩 불완전 | **가능성** | utility와 graphics는 별도[N03]; ICD JSON 발견과 SO 로딩 별개[N02], [N05]. 과거 동일 부모로 성공 | GPU_ALLOCATION, 실제 선택 ICD·driver library resolution·UID1000 device 접근 오류 | 누락된 주입/경로/접근 조건만 교정. host 문제면 gCube 측 설정/지원으로 해결 |
| capture와 startup health의 UID/sandbox/env/실행 파일 차이 | **가능성** | 소스상 wrapper/root/OffscreenCanvas와 직접 Chromium/UID1000/DOM 차이. Chromium sandbox 계층[N07] | 실제 capture argv·EUID/EGID·관련 env 전달·거부 오류 | 필요한 안전 변수/정확한 권한만. sandbox 전체 해제·privileged화는 기본 처방 아님 |
| 실배포 image/버전/argv가 저장 설정과 다름 | **가능성**, 증거 공백 | latest safe JSON에 없음. 같은 설정으로 실행됐는지 아직 미입증 | job와 결합된 실제 imageID, executable/version, 전체 argv | 실제 불일치 항목만 설정 교정. 정상 이미지 재빌드 불필요 |
| Playwright1.62.1과 system Chrome155 호환성·기본 flags 상호작용 | **가능성** | 공식 bundled browser는151, 임의 실행 파일 호환성 보장 없음[B03]–[B07]. 그러나 같은155/1.62.1로180프레임 성공 | latest 정확한 버전/argv와 해당 조합에서의 native 오류·적용 가능한 공식 결함 | 일치하는 결함이 확인될 때만 해당 패키지/인자 변경. 현재 일괄 업그레이드 근거 없음 |
| `--disable-vulkan-surface` 부재가 유일 원인 | **근거 부족** | 과거 성공 포함·중간 실패 소스에서 제거·현재 복원. 복원 이후도 같은 오류 보고; job argv는 미확보 | 기존 latest 원본의 selectedArgs와 실제 image 연결 | 이미 복원됨. 같은 복원을 반복하지 않음 |
| drawing buffer/GPU프로세스 자원 부족·드라이버 회귀 | **근거 부족** | null과 양립하지만 OOM/reset/crash/장치 코드 없음. 과거 같은 해상도 성공 | 해당 실패 시각의 제한된 allocation/crash/device-loss 증거 | 입증된 자원 한도 또는 해당 드라이버 결함만 처리 |
| 진단 v1의 `/proc` 접근·UID 전환 문제 | **가능성: 진단기만** | v1 외부 예외가 세부정보를 버림; proc 읽기는 권한 검사 대상[N08] | 이미 저장된 errno/stage가 있으면 확인. 현재 없으면 미확정 유지 | 진단 진입 조건만 수정; renderer 원인으로 전용하지 않음 |

최신 두 실패(37df·7d7a)의 직접 원인에서 제외되는 단계: 라벨 합성·프레임 전달·FFmpeg·MP4 저장. 모두 WebGL2 assert 다음이다. Namibia/JSON/300프레임 계획·source integrity는 이미 통과한 다른 범위이며, 현재 증거로 재검증할 이유가 없다. 이는 그 단계에서 미래 오류가 절대 없다는 보장이 아니다.

## 1. GPU 없이 먼저 끝낼 최소 증거 회수

정확한 job `studio-7d7a08be1d09817c903f41484bce3f33`의 기존 private 경로를 정상 관리·저장 기능에서 읽을 수 있을 때만 조사한다:

`<control_root>/handoff-gpu-jobs/<jobId>/`

| 기존 파일 | 회수할 안전 정보 | 한계 |
|---|---|---|
| `capture/CAPTURE_RECEIPT.json` | dependencies, browserProfile, 실패 단계/코드, native proof, capture 종료 사실 | selectedArgs는 full argv 아님. raw message의 경로 등은 제거 |
| `GPU_ALLOCATION.json` | model, driverVersion, memoryTotalMiB, uuidSHA256 | UUID 원문·계정 정보 불필요. NVML 정보만으로 graphics PASS 아님 |
| `LEASE_SUPERVISOR_RESULT.json`, `FIRST_CAPTURE_FAILURE.json`, 생성됐다면 `CAPTURE_PROCESS_RESULT.json` | 구조화된 exit/신호·시간·cleanup·첫 오류 | 일부 파일은 실패 이전에 생성되지 않을 수 있음 |
| `worker.log` 또는 플랫폼의 해당 시각 로그 | ANGLE/Vulkan/GPU process 관련 비민감 오류만 | 현재 코드가 원문을 보존했다는 보장은 없음. 전체 env/Owner/토큰을 내보내지 않음 |
| job와 묶인 플랫폼 실행 기록 | 실제 imageID/digest, 실행 시각·노드 | expected digest 환경변수는 actual imageID 대체 불가 |

이번에 접근 가능한 해당 Dropbox export 폴더에는 안전 JSON과 SHA만 있었다. private state root는 `/world-storage`와 분리되며 종료 후 생존 여부는 미확정이다. 다른 작업의 원문으로 대체하지 않는다. 같은 전체 검색이나 차단 Studio URL을 반복할 이유도 없다.

**현재 GPU 없이 확정적으로 처방할 운영 수정은 없다.** 증거 부족을 이유로 브라우저 인자·driver·JSON·sandbox를 변경하지 않는다.

## 2. 원문이 없다면 먼저 해결할 관측 제한

다음 GPU 실행에 앞서 기존 경로가 필요한 증거를 실제 보존할 수 있는지 결정해야 한다.

- `DEBUG`, `CHROME_LOG_FILE`, `VK_LOADER_DEBUG`는 현재 `_runtime_environment` allowlist에 없다. gCube env에 추가하는 것만으로 capture에 전달되지 않는다.
- capture는 pageerror를 기록하지만 browser native stderr의 지속 저장 sink는 없다. supervisor는 Node stdout/stderr를 합친 뒤 비JSON 행을 버린다. 따라서 다음 실행을 그대로 반복하면 같은 정보 공백이 남을 수 있다.
- 기존 캡처 CLI는 probeFrames/prepareOnly를 허용하지 않는다. 현재 명령을 1프레임 진단이라고 부르지 않는다.
- 기존 standalone 진단 JS는 복원 전 profile SHA에 고정되어 현재 이미지에 그대로 적용할 수 없다. 검사를 우회하지 않는다.

정상 gCube 관리 로그 등 기존 기능이 충분한 정보를 보존할 수 있다면 이를 우선한다. 그렇지 않을 때의 **최소 후속 변경 후보**는 새 진단 실행기가 아니라, 기존 capture/receipt 경로의 안전한 실행 식별·bounded native 오류 보존이다. 실제 적용 범위·필요 해시 연결·무료 검증 계획을 먼저 확정하고 별도 코드 작업으로 진행한다. 이 연구에서는 구현하지 않았고 이미지 빌드가 필요하다고 단정하지 않는다. 근본 원인이 기록되지 않은 상태에서 `failure.code` 필드만 또 만드는 작업도 필요 없다.

## 3. 향후 승인된 GPU 한 번에서 함께 확보할 정보

GPU 실행은 이번 범위 밖이다. 기존 승인을 재사용하지 않으며, 목적·횟수·시간·비용·종료 책임이 명확한 별도 승인이 필요하다. 실행 전에 위 보존 경로가 준비되어 있어야 한다.

| 묶음 | 필요한 정보 | 판별 목적 |
|---|---|---|
| 실행 식별 | jobID, 실제 imageID/digest, capture source SHA, Chromium real executable/version, Playwright/Node version | 다른 이미지·작업·바이너리 혼용 배제 |
| 프로세스 조건 | 안전하게 정제한 full browser/GPU-child argv, EUID/EGID/관련 group, sandbox 상태, 허용한 GPU/env 키의 값·전달 여부 | selectedArgs·health와 실제 capture 차이 |
| Native graphics | GPU model/driver, 장치 접근 결과, 선택 ICD·driver SO 해석, 첫 Vulkan/ANGLE 오류·GPU feature 상태 | utility 정상과 graphics 초기화 실패 구분 |
| WebGL2 | 같은 DOM canvas/옵션에서 context 결과, 있으면 contextcreationerror, 성공 시 renderer/vendor와 native proof | 실제 목표 경로의 hardware WebGL2 확인 |
| 보존·종료 | 단계·frameIndex, 안전 stderr, exit/signal, receipt SHA, remote readback, workload Finished 및 노드 해제 | 정보 유실 및 불필요한 비용 방지 |

새 도구 개발 없이 사용할 **실제 지원 실행 모드**부터 선택한다. 진단 전용 승인이면 300프레임 CLI를 실행하지 않는다. 단축 동등 경로가 준비되지 않았으면 실행 준비 BLOCKED를 유지한다. 10초 제작까지 승인된 실제 작업은 이미 첫 native proof를 확인한 뒤 FFmpeg/프레임 루프로 진행한다; 단순 300프레임 재시도는 증거 확보 준비 없이 제안하지 않는다.

## 4. 결과별 복구와 MP4 연결

| 관측 결과 | 다음 최소 행동 |
|---|---|
| 같은 job의 actual image/argv 불일치 | 잘못된 연결만 교정. 이미지 내용이 맞다면 재빌드하지 않음 |
| NVIDIA mount/ICD/device 접근 실패 | 안전한 provider 진단 근거로 해당 주입·권한 문제를 해결. 앱의 GPU 가드를 약화하지 않음 |
| ANGLE/Chrome 특정 오류 확인 | 해당 버전 공식 근거와 맞는 최소 옵션/의존성 조정 하나만 검토 |
| 원인 여전히 불명 | 원문·SHA·환경 식별 보존 후 중단. 자동 재시도·다른 backend 무작위 전환 금지. 필요 시 gCube/Chromium 담당 경계에 증거 제공하되 외부 발송은 별도 지시 필요 |
| 실제 hardware WebGL2/native proof 성공 | 제작 승인 범위가 있으면 기존 GENERIC_LABELS_10S.json과 NVIDIA renderer로300프레임→ffprobe1080×1920/30/10초→SHA/영구 readback→다운로드→라벨 검수. 진단 전용이면 여기서 중단하고 제작은 별도 승인 |

성공·실패 모두 증거/산출물 보존 후 GPU 중지와 노드 해제를 확인한다. cleanupVerified만으로 과금 종료를 선언하지 않는다. 소프트웨어 fallback 또는 sandbox 해제로 얻은 결과를 기존 NVIDIA 성공으로 대신하지 않는다.

[B01]: https://chromium.googlesource.com/chromium/src.git/+/main/docs/gpu/using-gpu-hardware-in-headless-chrome.md
[B03]: https://playwright.dev/docs/browsers
[B07]: https://github.com/microsoft/playwright/blob/v1.62.1/packages/playwright-core/src/server/chromium/chromiumSwitches.ts
[B10]: https://developer.chrome.com/blog/supercharge-web-ai-testing
[B11]: https://registry.khronos.org/webgl/specs/latest/2.0/
[N02]: https://download.nvidia.com/XFree86/Linux-x86_64/580.159.03/README/installedcomponents.html
[N03]: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html
[N05]: https://github.com/KhronosGroup/Vulkan-Loader/blob/main/docs/LoaderDriverInterface.md
[N07]: https://chromium.googlesource.com/chromium/src/%2B/0b6120702e8f69ce43b34b02903a1d32a0be07d3/docs/linux/sandboxing.md
[N08]: https://man7.org/linux/man-pages/man5/proc_pid_environ.5.html
