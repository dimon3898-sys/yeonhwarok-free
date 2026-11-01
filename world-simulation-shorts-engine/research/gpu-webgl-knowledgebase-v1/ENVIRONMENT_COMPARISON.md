# 성공·실패 환경 비교

관측된 실행값, 저장된 설정, 소스에서 예상되는 값을 구분한다. 최신 실패는 `studio-7d7a08be1d09817c903f41484bce3f33`다. 과거 180프레임 성공은 별도 작업 `studio-03d9b670cd764ce5823ea4720af1b410`다.

근거: [성공 안전 요약](evidence/reused/SUCCESS_ENVIRONMENT.json), [기존 이미지 계보](evidence/reused/IMAGE_LINEAGE_TO_INTEGRITY.json), [복원 CHECKPOINT][restore], [최신 실패 원문](evidence/latest-job/CAPTURE_DIAGNOSTIC.json), [정확한 소스 색인](system/SOURCE_INDEX.json).

| 항목 | 180프레임 성공 | 최신 0/300 실패 | 확인된 차이·한계 |
|---|---|---|---|
| 이미지 | 설정 G2 `sha256:9378a86d…21b62da`; 원본 receipt imageDigest=null | 저장 설정 surface-restore `sha256:c9fa126b…d3366b5`; latest safe JSON에 image 없음 | 서로 다른 설정 이미지. 두 작업의 orchestrator 실제 imageID 증거는 부족 |
| 의존성 계보 | G2 패키지 | G2→label→UP2→Namibia→diagnostics→integrity→surface. 기존 빌드 증거상 COPY와 시작 해시 갱신, 의존성 재설치 없음 | 설치 파일 상속 근거는 있지만 latest process의 실제 버전 관측과 다름 |
| Chromium | receipt155.0.8059.79, 코드 `/usr/bin/chromium`; 실행 후 경로 `/opt/google/chrome/google-chrome` | 같은 명시 경로의 소스, 실제 receipt 버전/실행 파일 미확보 | 최신 실행 바이너리 일치 미확정 |
| Playwright/Node | receipt1.62.1 / v24.19.0 | 계약과 이미지 계보는 동일 조합, latest 직접 관측 없음 | 공식 Playwright1.62.1 bundled Chromium은151.0.7922.34. 성공은 system Chrome155 조합 |
| 모드 | `headless:true`, selectedArgs에 `--headless=new`; full Chrome 경로 | 현재 소스도 동일 | 기본 headless-shell 경로와 동일시하지 않음 |
| Vulkan surface 옵션 | selectedArgs에 `--disable-vulkan-surface` | 제거되었다가 현재 소스에 한 번 복원됨; latest actual argv 없음 | 복원 후 같은 실패가 보고됐으나 실제 job argv 연결은 미확정 |
| 다른 profile 옵션 | 아래 9개 selectedArgs | 현재 profile은 같은 9개를 구성 | selectedArgs는 Playwright 기본 옵션을 포함한 OS argv 전체가 아님 |
| GPU/driver | RTX4080 SUPER renderer; 실행 후 driver580.159.03 관측 | 최신 작업의 GPU_ALLOCATION 원문 미확보 | 다른 진단 실행의 GPU/driver 값을 대입하지 않음 |
| 그래픽 API | 실제 ANGLE NVIDIA Vulkan1.4.312 / RTX4080 SUPER | WebGL2 null, renderer/vendor 값 미생성 | 실제 context 성공 여부는 확실히 다름 |
| 장치 노출·권한 | 실제 draw가 접근 성공을 증명; 장치별 mode/group/UID 숫자 미기록 | 최신 장치·group·mount·ICD 로딩 결과 없음 | 특정 권한/장치 누락은 미확정 |
| 사용자/sandbox | `rootTestOnly:false`, CHROMIUM_SANDBOX; 숫자 UID 미기록 | 코드 EUID/EGID1000 요구 및 chromiumSandbox:true; 최신 실제 argv 미확보 | root startup health와 실제 캡처를 구별 |
| 환경변수 | 실행 후 GPU_BACKEND=vulkan, render mode=gpu-required, NVIDIA capabilities=all, VK_ICD_FILENAMES=null | 같은 allowlist 소스; 최신 child 값 없음 | 새 VK_DRIVER_FILES 등은 allowlist에 없음. 기존 함수가 성공했으므로 그 자체를 회귀로 단정 불가 |
| ICD/loader | libGLX_nvidia.so.0, driver API1.4.312, libvulkan1 1.3.275.0-1build1 | 최신 선택 ICD·라이브러리 resolution 미확보 | API/loader 숫자 차이와 GLX 이름 자체는 실패 증거 아님 |
| WebGL2 호출 | 새 DOM canvas1080×1920, alpha=false, antialias=false, preserveDrawingBuffer=true | 같은 호출 코드, 반환 null | 호출 방식 변경은 확인되지 않음. 새 canvas여서 다른 context mode 선점 증거 없음 |
| 캡처·manifest | 기존 성공 소스 SHA 근거 있음 | 진단 추가·manifest 복구·profile 옵션 복원. 코드 해시가 달라도 의도된 변경 | 최신 오류는 integrity guard가 아닌 WebGL2 단계. 무결성 우회 불필요 |
| 라벨/native draw | native3회 검증×2구간, draw/readPixels 성공 | runtime context assert에서 중단 | 최신 라벨/native/encoder 미실행 |
| 출력 | 180프레임,6초,1080×1920/30,h264,fullDecode PASS | 0/300,MP4없음 | 성공은 10초 최신 라벨 제작 PASS가 아님 |
| 종료 | 캡처 exit0·영수증 있음 | cleanupVerified=true; browser exitcode 없음 | cleanup은 workload Finished/과금 중단 증거가 아님 |

기존 성공과 현재 소스의 selectedArgs:

```text
--disable-dev-shm-usage
--headless=new
--enable-gpu
--enable-webgl
--use-gl=angle
--use-angle=vulkan
--enable-features=Vulkan
--disable-vulkan-surface
--disable-software-rasterizer
```

이 목록에 없는 Playwright 기본 인자는 [정확한 v1.62.1 소스 분석](browser/BROWSER_GPU_KNOWLEDGE.md)을 참고한다. `--enable-unsafe-swiftshader`가 기본 인자로 추가되는 사실과 실제 소프트웨어 렌더러 사용은 다른 명제다.

## 소스 계보를 실행 동일성으로 해석하지 않는 이유

이미지의 고정 부모와 COPY-only 변경은 의존성 패키지의 무근거 변경 가능성을 낮춘다. 하지만 NVIDIA 장치·그래픽 라이브러리 주입은 호스트 런타임에 의존한다. 또한 같은 이미지여도 실행 바이너리·환경·sandbox 조건이 달라질 수 있다. 현재 증거는 호스트 변경을 입증하지도, 배제하지도 못한다. [NVIDIA 공식 조건](nvidia/NVIDIA_VULKAN_KNOWLEDGE.md).

## 진단 v1 실패는 별도 사건

`DIAG_ENVIRONMENT_LAUNCH_FAILED`는 worker 환경을 `/proc`에서 읽고 UID를 전환하는 진단 wrapper의 바깥 예외였다. 실제 Studio는 이미 UID1000으로 실행된 worker의 환경을 전달한다. v1은 stage/type/errno를 버렸으므로 정확한 실패 지점은 미확정이다. 이 결과는 WebGL2 실패의 재현이나 renderer의 권한 실패 증거가 아니다. 기존 v2는 관측 필드만 보완했으며, JS profile SHA pin은 현재 복원 이미지와 맞지 않는다. [이력·정확한 pin](history/HISTORY_AND_ENCODING.md).

[restore]: https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/webgl-surface-restore-v1/CHECKPOINT.json
