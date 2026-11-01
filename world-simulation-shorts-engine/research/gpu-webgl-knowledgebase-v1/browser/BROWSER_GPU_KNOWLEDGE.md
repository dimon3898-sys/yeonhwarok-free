# WORLD ENGINE — Chromium·Playwright·ANGLE·WebGL2 근거집

조사일: 2026-11-01. 읽기 전용 연구. 운영 코드·브라우저 옵션·GPU·빌드·기존 PASS를 변경하거나 실행하지 않았다. 공식 문서의 일반 조건과 특정 실패 작업의 관측을 분리한다.

## 1. 이 작업에서 확정되는 실패 경계

최신 `studio-7d7a08be1d09817c903f41484bce3f33`의 안전 내보내기([원문](../evidence/latest-job/CAPTURE_DIAGNOSTIC.json))는 `capture.failure.code=UP2_WEBGL2_REQUIRED`, `diagnosticStage=PAGE_EVALUATE_FIRST_NATIVE_DRAW`, `renderedFrames=0`, `cleanupVerified=true`이다. `nvidiaVerified=false`는 해당 검증이 성립하지 않았다는 뜻이며, GPU 장치가 없다는 증명이 아니다.

현재 복원 소스의 `presentation_runtime_vulkan.generated.mjs:36`은 `canvas.getContext('webgl2', {alpha:false,antialias:false,preserveDrawingBuffer:true})`의 반환값이 없을 때 이 코드를 발생시킨다. 따라서 직접 차단 지점은 WebGL2 컨텍스트 확보다. 라벨 합성·프레임 PNG·FFmpeg 실패를 이 작업의 직접 원인으로 바꿔 설명하면 안 된다.

최신 안전 JSON에는 실제 실행 이미지 digest, 브라우저 버전, 최종 프로세스 argv, ICD, 브라우저 native stderr가 없다. 설정 저장과 실패 시각의 순서는 복원 이미지 사용 정황이나, 해당 작업과 실행 이미지·옵션을 묶는 증명이 아니다. “옵션을 복원해도 동일 이미지에서 실패했다”는 인과 결론은 아직 유보한다.

## 2. 공식 자료가 설명하는 경로

| 경계 | 공식 근거와 기술 조건 | WORLD ENGINE 적용 | 증명하지 못하는 것 |
|---|---|---|---|
| Headless → GPU | Chromium 문서는 `--enable-gpu`가 headless의 강제 소프트웨어 경로를 해제하고, Linux 기본 GL 탐지에는 X11/DISPLAY가 필요하다고 설명한다. ANGLE Vulkan은 일부 환경에서 X11 없이 동작한다. [B01] | 현재 명시적으로 ANGLE Vulkan을 선택한다. X11 부재만으로 실패를 확정할 수 없다. | enable-gpu가 드라이버·장치·Vulkan 초기화를 보장하지 않는다. |
| Chrome 실행 모드 | Chrome112부터 unified headless가 nondisplayed platform window를 생성하며, 132부터 구형 headless는 별도 shell이다. [B02] | 역사적 실제 실행 파일은 system Google Chrome155이며 `headless:new`를 쓴다. | Playwright 기본 headless-shell과 같은 실행 조건이라는 뜻이 아니다. |
| Playwright → binary | 각 Playwright 버전은 특정 bundled browser를 사용한다. 임의 executablePath의 호환성은 보장되지 않는다. [B03], [B04] | 정확한 v1.62.1 manifest는 Chromium151.0.7922.34/revision1234다. 성공 영수증의155.0.8059.79는 system binary 조합이다. [B05] | 같은155+1.62.1의 과거180프레임 성공이 있어 버전 차이만으로 현재 null 원인을 단정할 수 없다. |
| WebGL → ANGLE | ANGLE은 GLES를 Vulkan 등 native API로 변환하며 Linux Vulkan/GLES3 지원을 명시한다. [B09] | WebGL2의 GLES3 경로가 ANGLE Vulkan과 연결된다. | 지원표가 해당 컨테이너에서 선택된 드라이버 또는 초기화 성공을 증명하지 않는다. |
| ANGLE vs compositor | `--use-angle=vulkan`은 ANGLE backend, `--enable-features=Vulkan`은 Chrome compositor/raster backend다. [B10] | 두 옵션은 서로 대체하지 않는다. 두 계층의 초기화 결과를 구분해야 한다. | 모든 GPU 관련 설정이 하나의 스위치라는 뜻이 아니다. |
| Vulkan presentation | `--disable-vulkan-surface`는 VK_KHR_surface/swapchain 사용을 바꾸는 presentation 옵션이다. [B10] | 복원은 과거 성공 프로파일과의 한 차이를 줄인다. | NVIDIA 라이브러리 노출·ICD 선택·sandbox 권한을 자동 복구하지 않는다. |
| WebGL2 생성 | WebGL2 명세는 drawing buffer 생성 실패 시 contextcreationerror 이벤트와 null 반환을 정의한다. [B11] | 현재 assert는 이 경계 이후 구체적인 native 이유를 `UP2_WEBGL2_REQUIRED`로 압축한다. | null 자체는 드라이버·권한·GPU프로세스·버퍼 생성 중 어느 원인인지 알려주지 않는다. |
| 실패 메시지 | WebGLContextEvent.statusMessage는 플랫폼별 상세 문자열 또는 빈 문자열이다. [B12] | 기존 저장 메시지가 있으면 유용하지만 민감정보 제거가 필요하다. | 항상 원인이 들어 있다는 보장은 없다. 이번 연구에서는 listener나 새 진단기를 구현하지 않았다. |

## 3. 버전이 고정된 Playwright 소스에서 새로 확인한 증거

공식 `v1.62.1/packages/playwright-core/src/server/chromium/chromium.ts`의 `_innerDefaultArgs`는 기본 switches를 구성한 후 headless 관련 플래그를 넣고 마지막에 사용자 `args`를 추가한다. `chromiumSandbox:true`이면 자동 `--no-sandbox` 삽입을 생략한다. [B06]

프로젝트 `backend/profile_contract.mjs:34-77`은 입력 args에서 `--enable-unsafe-swiftshader`를 제거하고 `selectedArgs`를 기록한다. 그러나 Playwright v1.62.1은 그 다음 단계에서 해당 플래그를 자체 추가한다. 기본 `chromiumSwitches.ts`는 조건에 따라 `--enable-features=CDPScreenshotNewSurface`도 추가한다. [B06], [B07]

이것은 “프로젝트가 기록한 selectedArgs는 최종 브라우저 argv 전체가 아니다”라는 사실을 뒷받침한다. 실제 플래그 우선순위·SwiftShader 사용·중복 feature 옵션의 영향은 이번 자료만으로 확정하지 않는다. `--disable-software-rasterizer`의 존재만 보고 소프트웨어 fallback이 실제로 없었다고 단정하는 것도 피한다. 보안 옵션을 제거하거나 `ignoreDefaultArgs:true`로 바꾸는 처방은 승인된 복원 범위를 넘어가며 현재 근거로 필요하지 않다.

## 4. 버전·사례 적용 범위

| 자료 | 적용 버전/날짜 | 활용 범위 |
|---|---|---|
| Chrome155.0.8059.79 Linux Stable 릴리스 | 2026-10-13 [B08] | 성공 영수증의 바이너리 버전이 실제 공식 릴리스임을 확인. 포함된 보안 수정은 이번 장애의 원인 증거가 아니다. |
| Playwright v1.62.1 소스/manifest | 정확한 v1.62.1 태그 [B05]–[B07] | bundled binary와 default argv 조립을 버전 고정 근거로 판단. 현재 실패 컨테이너에 같은 패키지가 로드됐는지는 별도 증거가 필요하다. |
| Playwright v1.49 headless 전환 안내 | 2024-11-13 [B13] | maintainer가 GPU/WebGL 가용성 차이를 명시. 일반 모드 비교 근거이며 Chrome155에서의 특정 결함 확인이 아니다. |
| Chrome NVIDIA T4/V100 공식 사례 | 2024-01-16, NVIDIA525.105.17 사례 [B10] | 플래그만으로 끝나지 않고 native driver 문제를 구별해야 했다는 사례. RTX4080SUPER/580에525 드라이버 설치를 처방하면 안 된다. |
| WebGL1/2 명세 | 2026-06-30 Editor's Draft [B11], [B12] | API 실패 의미 근거. 특정 Chromium155 구현 버그 또는 conformance 통과를 증명하지 않는다. |
| Chromium/ANGLE main 문서 | 2026-11-01 열람, 고정155 revision 아님 [B01], [B09] | 계층·지원 조건 설명에 한정한다. |

## 5. 다음 최소 판별 경로

확정: 컨텍스트 생성 실패. 유력한 조사 계층: 실제 브라우저 GPU프로세스와 ANGLE/native graphics 초기화 경계. 구체 원인은 미확정이다.

1. 기존 저장 자료에서 같은 job의 실행 이미지 digest·최종 executable/version·최종 argv·UID/sandbox를 우선 연결한다. 현재 selectedArgs만으로 완료 처리하지 않는다.
2. 같은 실행의 안전한 GPU프로세스 stderr/종료 코드, Vulkan loader/ICD 결과, browser GPU feature status를 확보하면 장치/라이브러리 문제와 ANGLE 선택·프로세스 차단을 구분할 수 있다. 전체 환경변수·인증자료는 필요 없다.
3. NVIDIA 장치 확인만으로 WebGL2 PASS를 선언하지 않는다. 유효한 Vulkan physical-device/driver 확인만으로도 browser context PASS는 아니다. 실제 캡처와 같은 UID·sandbox·binary·옵션에서의 결과가 필요하다.
4. 소프트웨어 fallback이나 sandbox 해제, 브라우저 업/다운그레이드, EGL backend 전환을 한꺼번에 시도하지 않는다. 원인이 확인되면 해당 계층 하나만 바꾼다.
5. 현재 연구에서는 GPU 없이 새로운 복구 성공을 입증할 수 없다. 기존180프레임 성공 증거와 최신 실패 사이의 실행 환경 연결을 먼저 완성하며, 증거가 저장되지 않았다면 추가 GPU 실행은 별도 승인 대상이다.

## 6. 고정 프로젝트 근거

- [최신 실패 원문](../evidence/latest-job/CAPTURE_DIAGNOSTIC.json)
- [captureVulkanDerived: Playwright·실행 파일·launch](https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs#L95-L100)
- [buildVulkanLaunchOptions: 옵션·sandbox·selectedArgs](https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/backend/profile_contract.mjs#L34-L77)
- [createNvidiaPresentationRuntime: WebGL2 생성](https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs#L36)

공식 출처 URL·버전·한계는 `OFFICIAL_BROWSER_SOURCES.json`에 저장했다. 직접 접근 불가였던 Chromium issue와 Chrome155 switch source는 인과 근거로 사용하지 않았다.

[B01]: https://chromium.googlesource.com/chromium/src.git/+/main/docs/gpu/using-gpu-hardware-in-headless-chrome.md
[B02]: https://developer.chrome.com/docs/automation-and-testing/headless
[B03]: https://playwright.dev/docs/browsers
[B04]: https://playwright.dev/docs/api/class-browsertype
[B05]: https://github.com/microsoft/playwright/blob/v1.62.1/packages/playwright-core/browsers.json
[B06]: https://github.com/microsoft/playwright/blob/v1.62.1/packages/playwright-core/src/server/chromium/chromium.ts#L349-L414
[B07]: https://github.com/microsoft/playwright/blob/v1.62.1/packages/playwright-core/src/server/chromium/chromiumSwitches.ts
[B08]: https://chromereleases.googleblog.com/2026/10/stable-channel-update-for-desktop_01668083673.html
[B09]: https://chromium.googlesource.com/angle/angle/+/main/README.md
[B10]: https://developer.chrome.com/blog/supercharge-web-ai-testing
[B11]: https://registry.khronos.org/webgl/specs/latest/2.0/
[B12]: https://registry.khronos.org/webgl/specs/latest/1.0/
[B13]: https://github.com/microsoft/playwright/issues/33566
