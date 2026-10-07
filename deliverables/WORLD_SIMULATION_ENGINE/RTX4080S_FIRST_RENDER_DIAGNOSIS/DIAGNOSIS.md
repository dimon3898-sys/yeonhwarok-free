# RTX4080S 첫 렌더 중단 — 확인된 이미지 결함과 검증

## 확인된 원인

**게시된 v008 기반 컨테이너에서 Scene 1 준비의 ENOENT / Node exit 1을 재현했다.** 승인된 지형 자산 `natural-earth-1-east-asia-expanded`가 `web/flat_assets/cache/` 아래에 있어 최초 Docker build의 `**/cache/**` 제외 규칙에 걸렸다. `tools/render_production_scene.mjs`는 Earth 장면에서도 FLAT SOURCES 전체의 source hash를 계산하므로, 이 자산 누락으로 Chromium launch 전에 첫 Scene에서 종료된다.

누락 파일:
`web/flat_assets/cache/terrain_99a6ebfafb2f78a29cea244d9a20cf732c619c4c97db868bf98255f34ec26624.png`

보존한 원본 SHA-256:
`23c9ed6b954528fb98267d103f6e066e650461a7a817304b6cc2d4aa3d55a522`

크기: 17,800,192 bytes. Public Domain의 기존 승인된 Natural Earth 자산이다. 새 지형이나 저품질 대체 이미지를 만들지 않았다.

## 같은 입력으로 수정 전 → 수정 후

원본 v008의 immutable base digest 위에 동일한 준비 검사·진단 코드만 올려 시험했다. 실제 entrypoint가 저장 경로와 cache 링크를 초기화한 뒤 UID1000에서 수에즈 20초 HIGH/FAST_PLUS 입력을 재구성하고, 승인·디렉터리·Scene 1 명령·Node source hash까지 실행했다. Chromium/FFmpeg/영상 렌더는 실행하지 않았다.

- 수정 전: missing source asset = natural-earth-1-east-asia-expanded, ENOENT, exit 1. [CI before](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37600213639).
- 수정 후: 동일 자산의 바이트·SHA를 복원, missing source assets = [], exit 0, preparation PASS. [CI after](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37600574405).
- 수정: 해당 파일만 읽기 가능한 권한으로 COPY; build에서 크기와 SHA를 검사. 미래 전체 build의 ignore에도 이 정적 자산만 정확하게 예외 처리한다. 일반 render cache·project·output·secret 제외는 유지한다.

`IMAGE_PREPARATION_BEFORE.json`, `IMAGE_PREPARATION_AFTER.json`은 이 컨테이너 실행 결과다. Node 렌더러 소스와 Chromium flags를 변경하지 않았다.

**원격 작업의 원본 exception/job id/실제 Scene JSON은 미확보다.** 해당 gcube/SSH 접근 권한이나 정확한 서비스 URL이 현재 환경에 없다. 따라서 로컬에서 확인한 게시 이미지의 확정 결함과, 직접 읽지 못한 원격 job 기록을 구분한다. gcube Workload를 시작·교체·삭제하지 않았다.

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

확인된 이미지 자산 복원과 함께 다음 진단 결함도 수정했다. GPU나 그래픽과 분리된 변경이다.

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

QA ON은 12~15초, 기본 12초를 허용한다. 일반 입력은 원래 20~3600초 정책을 유지한다. 승인된 planner/schema/promotion 파일을 덮어쓰지 않는다. 새로운 deployment QA adapter는 같은 planner 함수 코드에 per-call request validator를 적용하고, 별도 additive QA schema를 선택한다. 정상 요청의 schema 조건은 원본과 동일하다. QA에도 GIS/semantic/retention/approval gate가 적용된다.

짧은 shipping QA에서는 실제 시작하는 R_CAPE route event가 새 변수 역할을 갖는다. Scene/route/좌표를 삭제하거나 카메라 이동을 사건으로 계산하지 않는다.

Scene 설명은 의미 있는 사건의 간결한 표시명을 사용한다. 내부 거리 계산/provenance 문장은 Scene JSON에 그대로 보존한다. UI 변경은 새 버전의 코드를 사용해야 적용된다.


## 별도 QA 카메라 검사

재구성한 원래 20초 계획의 Scene 4 HORIZON_REVEAL에서 native camera angular gate(2.5도/프레임)를 넘는 별도 수치 위험을 발견했다. 이는 Scene 1 ENOENT와 별개다. `NUMERIC_PREPARATION.json`은 원래 입력의 결과이며 원격 Scene JSON의 측정값이 아니다. 기존 20초 계획과 renderer는 변경하지 않았다.

새 12초 shipping QA는 해당 장면에서 이미 존재하는 COUNTRY_APPROACH 프리셋을 선택하고, 카메라 travel/zoom에 Scene 전체 시간을 확보한다. 좌표·rig 시작/종료점·routes/entities/events/HERO lighting/HIGH/FAST_PLUS는 보존한다. 정상 production 입력에는 적용하지 않는다. 기존 프로젝트의 Scene JSON도 변경하지 않는다.

수정된 12초 QA의 모든 5 Scene이 보존된 numericPreflight의 카메라·entity·route 안전 조건과 semantic visibility gate를 통과했다. Scene 4 최대 각도는 2.485582781도/프레임이다. GPU 없는 canvas-free 검사이므로 실제 texture/shader/frame/MP4 성공을 의미하지 않는다. `QA12_NUMERIC_VERIFIED.json`과 테스트에 측정 범위를 기록했다.

## 공개와 실제 GPU 검증의 구분

v009는 확인된 이미지 자산 결함과 진단/QA/표시 개선만 포함하는 v008의 추가 layer로 준비한다. GPU runtime, proxy/security, renderer, 기존 assets와 기존 태그는 유지한다. 새 게시 태그를 덮어쓰지 못하는 guard 및 익명 Docker pull 검증을 유지한다.

실제 RTX4080S 12초 QA는 이 작업에서 실행하지 않았다. 기존 실패한 20초 계획의 HORIZON 카메라 위험까지 해결됐다고 주장하지 않는다. 다음 실환경 검증은 새로운 12초 QA 계획으로 수행해야 하며, GPU 검증·Scene 1 준비·각 Scene 실제 frame·MP4/QC/download를 별도로 확인해야 한다.

## 최종 회귀 결과

현재 코드의 core 429개 PASS(406.998초), gcube 205개 중 204개 PASS/1개 SKIP, v007 진단 31개 PASS. 총 665개 실행, 664 PASS/1 SKIP. [최종 container CI](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37601321302)에서 build, packages, UID 권한, source preparation, foreground boot, health/login, fail-closed GPU diagnostics, proxy/security/v007/new QA tests, 61초 이상 persistence가 통과했다. 실제 GPU frame/video 생성은 하지 않았다.

## 게시 완료

`ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v009` 게시 완료. [운영 이미지 publish + 익명 Docker pull](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37601972433) PASS.

독립 익명 registry 검증에서 release tag와 revision tag가 같은 digest, v001~v008 및 diag 태그 불변, v008 base layer 전체 동일, 추가 7개 layer의 접근·바이트·SHA, 복원 PNG의 읽기 권한, port 8000/entrypoint/secret 부재/CPU fallback 부재를 확인했다. `PUBLIC_IMAGE_PROOF.json`에 결과를 저장했다.

게시 이미지 revision: `373ea3c288c539532b186d46759387da8f4a58b7`.
Digest: `sha256:5f8250473de90076bfb7d2a357881523a1e4555ff3a5b970bb8e598fd4acfb9a`.

이후 문서 증거 commit은 운영 이미지 소스 revision과 구분한다. 실제 gcube 원격 job 파일이나 새 GPU 렌더를 확인한 것으로 표시하지 않는다.
