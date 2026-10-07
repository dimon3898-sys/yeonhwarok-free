# RTX4080S 첫 렌더 중단 — 증거와 수정 범위

## 결론

**실제 gcube 중단 예외·exit code는 미확보다. 원인 해결이나 RTX4080S 재렌더 성공을 주장하지 않는다.** 현재 환경에는 해당 서비스 URL, 승인된 gcube/SSH 접근, 실제 20초 작업의 Scene JSON·job failure 파일이 없다. 기존 운영 v008을 재배포하거나 GPU를 시작하지 않았다. 원인이 확인되기 전에는 v009 운영 이미지를 게시하지 않는다.

게시된 v008의 익명 manifest/config/COPY layer 확인을 다시 수행했다. `V008_IMAGE_IDENTITY.json`은 이미지 식별 기록이며 실제 원격 job 증거가 아니다.

## UI 상태가 의미하는 범위

`deployment/mobile_server.py::worker.progress`는 `scene_start`를 `Scene 1/5 · 장면 준비`로 표시한다. `engine/rendering.py::render_project`는 이 이벤트 이후 다음을 수행한다.

1. 프로젝트 render checkpoint를 기록한다.
2. Scene type과 승인된 visual adapter에 따라 page/tool을 고른다.
3. 프로젝트·버전·Scene 식별자를 포함한 내부 loopback URL과 Node argv를 만든다.
4. `CPULocalBackend.run`이 Node를 실행한다.
5. Node는 결과 덮어쓰기 방지, 크기·FPS·duration 검수, source/asset 읽기·hash를 수행한다.
6. INITIALIZING checkpoint 이후 Chromium launch, 내부 page/plan/texture/font 로드, renderer init, numeric preflight를 수행한다.
7. FFmpeg를 시작하고 첫 프레임을 전달한 뒤에야 `scene_render`가 나온다.

따라서 마지막 UI 문구만으로 1~7 중 어느 항목인지 알 수 없다. 브라우저 실행 전 실패라고 단정할 수 없다. 일반 예외는 failed, 작업 중단 신호는 interrupted, worker 비정상 종료는 outer scheduler의 failed 경로로 이어진다. 기존 timeout은 cancel 상태로 합쳐졌다.

## 확인된 진단 결함과 수정

v008의 renderer stderr/stdout은 합쳐진 tail 문자열이었다. worker는 예외 type/message 일부를 private failure 파일에 남기지만 UI는 항상 WORKER_FAILED로 바꾸었다. outer worker의 stdout/stderr는 DEVNULL로 버리고 exit code도 지웠다. traceback 위치·실패 stage가 없어 첫 실패의 원인 위치를 안정적으로 확인할 수 없었다.

수정은 GPU나 그래픽과 분리했다.

- stdout/stderr를 동시에 drain하고 각각의 bounded tail, return code, duration, command category를 수집한다.
- command, environment, 요청 본문은 저장하지 않는다. URL/query, credentials 및 전체 내부 경로는 마스킹한다.
- worker failure 기록에 stage, scene id, exception type, traceback의 파일명/함수/행을 보존한다.
- outer worker exit 1은 이미 보존된 구체적인 실패를 덮지 않는다.
- timeout과 사용자 cancel을 구분한다.
- UI에 안전한 code/stage/scene/exit 정보를 표시한다.
- GPU 판정, proxy/owner 인증, renderer, quality와 cache key 로직은 변경하지 않는다.

`BEFORE_AFTER.json`은 **동일한 로컬 exit-7 재현 fixture**의 결과다. 실제 gcube 예외라는 뜻이 아니다.

수정 전: public WORKER_FAILED, 실패 Scene/stage/exit 없음.
수정 후: public SCENE_RENDERER_EXIT, scene_start, S001, exit 7, 별도 stderr tail.

## 재구성한 입력의 검증

수에즈 폐쇄 20초 HIGH/FAST_PLUS/TTS OFF 입력을 현재 승인된 코드에서 재구성했다. 실제 원격 Scene JSON의 복제라고 주장하지 않는다.

- 5 Scene 및 Rotterdam/Rotterdam/Suez Canal/Singapore/Singapore 위치 순서 재현.
- 전체 plan/GIS/asset/semantic visibility 검수 통과.
- Rotterdam 항로 start/end는 검증된 서로 다른 Rotterdam/Singapore 좌표다.
- Scene 1·2 준비 디렉터리와 Node 명령, source/asset 파일 읽기·hash 통과.
- canvas-free Scene 1·2 카메라/route/entity 수치 검사 통과. GPU frame/texture/shader 성공 증거는 아니다.
- 완료된 Scene 1·2의 fake unit-test media/audit bytes를 유지하고 Scene 3부터만 재시도하는 checkpoint 테스트 통과.

## Probe와 production 실행 경로

startup은 검증된 profile을 CHROMIUM_PATH wrapper, WORLD_ENGINE_GPU_PROFILE, loader 환경으로 gateway에 전달한다. gateway→worker→Node는 이를 상속한다. production tool에 남은 원래 SwiftShader 옵션은 wrapper가 제거하고 선택된 `--use-gl=angle`, Vulkan 또는 gl-egl, `--disable-software-rasterizer`로 치환한다. 신규 테스트는 실제 production tool의 args와 자식 프로세스의 환경 상속을 검증한다.

Probe는 작은 WebGL2 draw/readPixels이고 production은 asset·shader·4K scene·postprocessing·FFmpeg가 포함된 경로다. 같은 profile 사용이 전체 Scene 성공을 보증하지는 않는다. 실제 gcube production argv/runtime record는 미확보다.

## 별도 QA 및 문구 표시 수정

QA ON은 10~15초, 기본 12초를 허용한다. 일반 입력은 원래 20~3600초 정책을 유지한다. 승인된 planner/schema/promotion 파일을 덮어쓰지 않는다. 새로운 deployment QA adapter는 같은 planner 함수 코드에 per-call request validator를 적용하고, 별도 additive QA schema를 선택한다. 정상 요청의 schema 조건은 원본과 동일하다. QA에도 GIS/semantic/retention/approval gate가 적용된다.

짧은 shipping QA에서는 실제 시작하는 R_CAPE route event가 새 변수 역할을 갖는다. Scene/route/좌표를 삭제하거나 카메라 이동을 사건으로 계산하지 않는다.

Scene 설명은 의미 있는 사건의 간결한 표시명을 사용한다. 내부 거리 계산/provenance 문장은 Scene JSON에 그대로 보존한다. UI 변경은 새 버전의 코드를 사용해야 적용된다.

## 게시 보류

수정은 별도 Git branch에서 검증한다. CI-only Dockerfile/workflow는 v008 runtime 위에 확인된 진단·QA·표시 수정만 올려 container boot/login/health/persistence를 검증하며 registry write/push 권한과 단계가 없다. gcube-v009 또는 다른 운영/진단 태그를 게시하지 않는다. main의 기존 운영 배포를 변경하지 않는다.

다음에 필요한 증거는 원래 실패 job의 `.failure.json`, job ticket/status, 실제 `scene_plan.json`, Node `.checkpoint.json`에 남은 exception/exit/frame 기록이다. 현재 원격 파일에 접근하지 못했으며 ephemeral 컨테이너가 이미 삭제됐다면 복구를 보장할 수 없다. 해당 증거 없이 특정 renderer 문제를 수정하거나 GPU 재시도를 권하지 않는다.
