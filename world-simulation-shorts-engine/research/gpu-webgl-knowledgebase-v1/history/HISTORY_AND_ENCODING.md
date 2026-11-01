# 기존 복구 이력과 FFmpeg 판단 기준

연구 기준: 2026-11-01 KST, 소스 `296402e71257c7847d0045215ca0cdaf3dd700d2`. 기존 실행 증거를 읽었으며, 테스트·브라우저·GPU·빌드·게시·운영 코드 변경은 0회다.

## 먼저 구분할 결론

복구 기록의 PASS는 **각 조치가 다룬 범위의 PASS**다. 파일 복구, 진단 정보 전달, 소스 무결성, 이미지 게시 성공은 WebGL2 초기화나 실제 영상 완성을 증명하지 않는다. 해당 경계를 유지하면 이미 해결한 문제를 반복하는 일을 줄일 수 있다.

최근 작업 `studio-7d7a08be1d09817c903f41484bce3f33`의 저장된 safe diagnostic에서도 `UP2_WEBGL2_REQUIRED` / `PAGE_EVALUATE_FIRST_NATIVE_DRAW` / 0프레임이 확인됐다. 이는 과거 `studio-37dfbc8dab786a4d7c99cde6fae2f821`과 같은 실패 조건이다. 최신 safe diagnostic에는 작업 당시 실제 imageID·전체 launch argv·Chromium GPU 오류 원문이 없다. 옵션 복원 설정이 저장됐다는 증거와 이 작업이 그 digest로 실제 실행됐다는 증거는 구분해야 한다.

최신 원문: [CAPTURE_DIAGNOSTIC.json](../evidence/latest-job/CAPTURE_DIAGNOSTIC.json), 수집 경위: [INTAKE.json](../evidence/latest-job/INTAKE.json). 원본 식별자: `/WORLD_ENGINE/capture-diagnostic-studio-7d7a08be1d09817c903f41484bce3f33/CAPTURE_DIAGNOSTIC.json`.

## 조치별 해결 범위

| 조치 | 실제 해결·확인된 내용 | 해결되지 않은 내용·남은 조건 | 반복하지 않을 작업 | 증거 |
|---|---|---|---|---|
| UP2 오류 상세 표시 | controller→handler→관리자 UI에 제한된 code/field/blocked scene 정보 전달. HTTP adapter 6개·합성 mobile DOM 6개 PASS. 인증·정책·컴파일 판정 유지 | 당시 실제 UP2 하위 원인의 수리나 원격 UI 성공은 별개. 테스트는 합성 controller/DOM 범위 | 라벨·컴파일러 재개발, 상세 표시 전체 재개발, 기존 12개 재실행 | [UP2 RESULT][P1] |
| Namibia PNG 복구 | 실제 target 경로의 누락으로 보고된 원본 PNG 한 개를 이미지에 추가. 6,518,687 bytes, SHA256 `0d7d5e2d…83c82068`, UID1000 읽기 및 부모 설정·레이어 보존 | 원본 누락이 시작된 최초 부모 단계는 미확정. 전체 지역·WebGL 실패 해결을 의미하지 않음 | 동일 PNG 복사·이미지 재빌드, 전체 지역 CPU 컴파일 | [Namibia CHECKPOINT][P2] |
| 캡처 실패 진단 개선 | private receipt의 예외가 safe export에서 `UNCLASSIFIED_EXCEPTION/PAGE_EVALUATION`으로 축약되던 경로 보완. 안전한 `capture.failure` 및 evaluate 단계 보존. Python 8개·Node 5개 집중 PASS | 과거 `studio-c7f880…`의 이미 유실된 예외 원문은 복원되지 않음. GPU 실패를 고친 조치가 아님 | 새로운 전체 진단기 개발, 기존 13개 재실행, 다른 작업 receipt를 과거 원문으로 대체 | [캡처 진단 CHECKPOINT][P3] |
| 캡처 소스 무결성 복구 | 실제 capture source `0161ac…`와 nested generated manifest의 과거 pin `39bdff…` 불일치 확인. pin 한 항목과 기존 runtime/startup 해시 연결 갱신. 변경 범위 6개 PASS | 원격 WebGL 초기화와 GPU 캡처는 미검증. 무결성 통과는 하드웨어 사용 증명이 아님 | 무결성 검사 우회, 캡처 코드 재작성, 기존 소스 패키징 전체 재실행 | [무결성 CHECKPOINT][P4] |
| 기존 WebGL2 실패 확인 | 작업 `studio-37dfbc…`에서 `getContext('webgl2', …)`가 null을 반환한 조건 확인. 첫 native draw·프레임·FFmpeg 이전 | null을 만든 driver/ANGLE/sandbox/device 조건은 safe JSON에 없음 | 라벨·FFmpeg를 원인으로 단정하거나 동일 전체 렌더 재현 | [정확한 작업의 safe JSON][P5] |
| GPU 진단 실행기 v1 | 실제 1회 호출이 `DIAG_ENVIRONMENT_LAUNCH_FAILED`로 차단됐고 배포 종료·노드 해제 확인. 전체 렌더 0회 | 바깥 예외 경계가 단계·type·errno를 버려 정확한 실패 연산 미확정. 실제 WebGL 호출 횟수·브라우저 실행 여부도 미확인 | v1 동일 명령 재실행, 이 결과를 WebGL2 FAIL/PASS로 해석 | [진단 CHECKPOINT][P6] |
| 실행기 v2 안전 메타데이터 | v1 바깥/안쪽 경계의 제한된 stage/type/errno 보존만 추가. 신규 3개 집중 PASS | 실행기 실패 자체가 고쳐진 것은 아님. 원격 실행 PASS 없음. 기존 JS 진단기는 이전 profile SHA 고정 | 새 실행기 무조건 개발 또는 기존 v2를 새 이미지에 그대로 실행 | [진단 CHECKPOINT][P6], [기존 JS pin][P7] |
| 성공 Chromium 옵션 복원 | `--disable-vulkan-surface` 한 줄과 필요한 해시 파일 3개만 변경. 신규 9개 집중 PASS, 1회 빌드·게시·전체 백업, gCube 설정 저장 | 직접 원인이라는 인과는 미확정. 최신 실패의 실제 imageID/argv 연결도 추가로 필요. 코드·게시 PASS와 WebGL PASS를 구분 | 같은 옵션 재복원·동일 이미지 재빌드, 원인 없는 다른 옵션 조합 실험 | [복원 CHECKPOINT][P8] |

## 진단 실행기 호환성에 관한 확정된 제한

`diagnose_webgl_once.mjs:12`는 이전 profile SHA256 `4306430e64633d67745b706b7c4992b77d12bb1bf3a8d64352b82d07936d17b2`를 고정한다. 같은 파일 65행은 실제 profile SHA가 다르면 `DIAG_CAPTURE_PROFILE_SOURCE_CHANGED`를 발생시킨다. 복원된 profile SHA는 `4e78b2d9f18107d70fda3c266c48d72103f7eaa63015b4dd1c1bb65e697e79a6`다. 따라서 **기존 v2 Python helper를 사용하더라도 기존 JS 진단기를 새 이미지에서 그대로 재사용할 수 없다.** 이는 정적 코드로 확인된 호환성 조건이며, 새 GPU 실험으로 다시 확인할 필요가 없다. 이번 연구에서는 pin을 수정하거나 검사를 우회하지 않았다.

## 인코딩은 현재 장애의 어느 위치에 있는가

실제 함수는 [`captureVulkanDerived`][C1]다.

| 단계 | 소스 위치 | 실행 조건·의미 |
|---|---|---|
| 첫 native draw 확인 | 102–110행 | WebGL2 context 생성, NVIDIA/Vulkan 검증과 기존 native draw/readback이 먼저 완료되어야 함 |
| FFmpeg 시작 | 113–116행 | 지원되는 실제 경로는 `probeFrames===null`만 허용하며 위 단계가 성공한 경우만 시작. 단축 진단 옵션은 지원하지 않음. PNG `image2pipe` / 입력 30fps / `libx264` / `yuv420p` / 무음 / `+faststart` |
| 프레임 전달 | 118–127행 | 실제 draw/readPixels·검사 후 PNG를 stdin에 전달. pipe backpressure를 기다리며 프레임별 기록 생성 |
| 인코더 종료 확인 | 129행 | stdin 종료 후 FFmpeg exit code 0 확인 |
| MP4 계약 확인 | 129–131행 | ffprobe로 단일 H.264 영상·무음·1080×1920·30/1·실제 읽은 프레임 수·길이 확인 |
| 전체 디코드·파일 SHA | 131행 | FFmpeg decode→null 프로세스 정상 종료 뒤 실제 VIDEO.mp4 bytes/SHA256 기록 |
| 실패·정리·영수증 | 133–136행 | 예외를 다시 던지고 finally에서 프레임 증거·CAPTURE_RECEIPT·SHA256SUMS 저장 시도 |

`studio-37dfbc…`와 최신 `studio-7d7a08…`의 정확한 단계·코드에 따르면 context 생성이 실패하여 **FFmpeg spawn에 도달하지 못했다**. 이 두 작업의 즉시 원인을 x264, 인코딩 속도, faststart, MP4 저장으로 설명할 수 없다. 다만 **0프레임이라는 숫자만으로 모든 작업의 FFmpeg 미실행을 단정하면 안 된다**. first native proof 이후 첫 프레임 검사 전에 인코더가 먼저 시작되는 코드이므로, 다른 작업은 단계 기록을 확인해야 한다.

현재 명령은 `libx264`를 사용한다. GPU 캡처와 인코딩을 구분하며, 이 경로에 NVENC를 사용한다는 주장은 하지 않는다. 300개의 30fps 프레임은 10초라는 입력 계약이다. 최종 코드가 실제 프레임 수와 duration을 별도로 확인하는 이유도 이 계약을 검증하기 위해서다. `fullDecode:PASS`는 현재 구현이 전체 디코드 프로세스의 정상 종료를 관측했다는 뜻이며 라벨 가독성·카메라 품질까지 보증하지 않는다.

## 공식 FFmpeg 근거와 적용 범위

- [FFmpeg formats][F1]: image 입력의 `framerate`와 MP4 `faststart`의 역할을 설명한다. 기본 프레임률에 의존하지 않고 입력 30을 지정한 현재 코드와 연결된다. `+faststart`는 MP4 메타데이터 배치를 바꾸는 옵션이지 WebGL2를 활성화하는 옵션이 아니다.
- [FFmpeg codecs][F2]: `libx264`는 x264 H.264 encoder wrapper이고 해당 외부 라이브러리를 빌드에 포함해야 한다. 기존 180프레임 성공 영수증은 당시 인코더가 실제 동작했음을 보여준다. 현재 파일 상속 관계만으로 최신 실행의 바이너리 버전을 실측했다고 할 수는 없다.
- [ffprobe][F3]: `-show_streams`, `-show_format`, `-count_frames`로 스트림·컨테이너·읽은 프레임 수를 확인할 수 있다. 현재 MP4 계약 검사와 직접 대응한다.
- [FFmpeg CLI][F4]: 입력 `-framerate`와 출력 `-r`은 동일한 의미가 아니다. 현재 코드는 둘 다 30으로 고정한다. 출력 프레임률 설정만으로 실제 300프레임 캡처를 증명할 수 없어 프레임 증거와 ffprobe 결과를 함께 사용해야 한다.

문서는 2026-11-01 검색 시점의 공식 rolling 문서다. 기존 실행 증거에서 **정확한 FFmpeg/ffprobe 바이너리 실측 버전은 미확보**다. 저장소 dependency contract는 6.1.1이며 계약값과 해당 실행의 실측을 구분한다. 특정 버전의 FFmpeg 버그를 현재 장애 원인으로 연결할 근거도 없다. 공식 문서 직접 open은 도구 timeout으로 실패했고 동일 URL open을 반복하지 않았다. 공식 도메인의 검색 색인 본문을 사용했으며 이를 원문 전체 열람으로 표기하지 않는다.

## 다음 조사에서 이 이력을 사용하는 방법

1. 최신 작업의 실제 `capture.failure`와 현재 실행 이미지·argv를 먼저 연결한다.
2. WebGL2 이전 실패라면 기존 PNG·컴파일·라벨·FFmpeg PASS를 그대로 재사용한다.
3. 무결성 오류가 다시 나타날 때만 해당 실제 파일과 기대 pin을 확인한다. 전체 패키징을 재실행하지 않는다.
4. 인코더나 export 오류가 실제로 나타났을 때만 해당 단계의 exit code·bounded stderr·파일·저장 경로로 범위를 이동한다.
5. 같은 사용자/환경에서 context 생성이 성공했다는 증거 없이 300프레임 전체 작업을 반복하는 것을 복구 전략으로 삼지 않는다.
6. 향후 GPU를 사용한다면 새로운 승인 아래 단일 실행에서 실제 실행 식별자·안전한 초기화 오류·종료·저장 증거까지 연결한다. 이 문서는 실행 승인이 아니다.

[P1]: https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/up2-detail-display-v1/RESULT.json
[P2]: https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/namibia-png-recovery-v1/CHECKPOINT.json
[P3]: https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/capture-failure-details-v1/CHECKPOINT.json
[P4]: https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/capture-source-integrity-v1/CHECKPOINT.json
[P5]: https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/integrated-preflight-v3/evidence/prior-failure/CAPTURE_DIAGNOSTIC.json
[P6]: https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/webgl-init-diagnostic-v1/CHECKPOINT.json
[P7]: https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/webgl-init-diagnostic-v1/diagnose_webgl_once.mjs#L12
[P8]: https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/webgl-surface-restore-v1/CHECKPOINT.json
[C1]: https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs#L84
[F1]: https://www.ffmpeg.org/ffmpeg-formats.html
[F2]: https://www.ffmpeg.org/ffmpeg-codecs.html
[F3]: https://ffmpeg.org/ffprobe.html
[F4]: https://ffmpeg.org/ffmpeg.html
