# 65422 원본 실행 환경과 복원 규격

원본은 NVIDIA 컨테이너에서 제작됐다고 증명된 영상이 아니다. 원본 실행 기록은 **로컬 source checkout → Node → Playwright → Chromium → ANGLE SwiftShader**다. 따라서 실제 원본 코드 경로를 무료 소프트웨어 환경에서 복원한다. 원본을 제작한 OCI image digest, 전체 OS/kernel 및 드라이버 패키지 목록은 기록에 없어 `UNVERIFIED`로 남긴다.

| 항목 | 원본 증거로 확인한 값 |
|---|---|
| 렌더 소스 commit | `2c097df2d02432a3f9ae4dae5d714dbc9eacd434` |
| 원본 report 영구 저장 commit | `45af879d7417abba58e9ebd59d8e6630a785ac28` |
| 원본 video SHA-256 | `f3de1bdf9244171a47c6e5eccca6aae1370f58d8bf4721a7658b6bca2eed2ef6` |
| 원본 capture signature | `d8b2150ba064cd0c0d59ba6e0dc0d2bfd408bbc3d3bb66d64eb479564565ee9a` |
| 원본 runtime source signature | `b81774e0d8627f0269901daff6fdbd5fdbc06f7dec85f35849f4150525c1126c` |
| Node | `v24.19.0` (원본 runtime 코드가 검증) |
| Playwright | `1.62.1` (원본 runtime 코드가 검증) |
| Chromium | `/usr/bin/chromium`, `154.0.8037.57` (원본 runtime 코드가 검증) |
| Chromium 시작 옵션 | `--no-sandbox --enable-unsafe-swiftshader --use-angle=swiftshader --disable-dev-shm-usage` |
| 웹 렌더링 | Headless WebGL2, 1080×1920 canvas, DPR 1 |
| 실제 backend | `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)` |
| Python server | `/usr/bin/python3 -B recovery/v5/serve.py`, loopback HTTP만 허용 |
| Three.js | 저장소에 고정된 `web/vendor/three/0.170.0/three.module.js` |
| 원본 FFmpeg 라이브러리 기록 | MP4 tags: `Lavf61.7.103`, `Lavc61.19.101 libx264` |
| 현재 FFmpeg 실제 버전 | `7.1.5-0+deb13u1`, gcc14 Debian build; 완전한 원본 패키지 버전 동일성은 미확인 |
| 출력 | H.264 High / yuv420p, 1080×1920, 30fps, 150프레임, 5초, 오디오 없음 |
| 원본 실행 시간 | 2026-10-14 01:41:44.200Z → 01:45:55.384Z (251.184초, 당시 기록) |

## 정확한 입력

엔진 기준 상대 경로는 원본 그대로 유지한다. 실제 파일 bytes와 SHA는 원본 report의 `sourceBindings` 73개 및 별도 capsule manifest에 기록한다.

| 역할 | 경로 / 값 |
|---|---|
| 원본 실행 진입점 | `recovery/moving-frontier-glow-fix-v1/render_proof.mjs` |
| 원본 runtime | `recovery/moving-frontier-glow-fix-v1/reference_runtime.mjs` |
| 실제 GPU adapter | `web/map_infographic_v1/map_engine_unit_gpu_adapter_v4.mjs` |
| Scene | `recovery/moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json` |
| Scene SHA | `aac147932d687f065469c224dbe2a02494f17c01a9be87383e771ada3f275159` |
| Scene schema/version | `MAP_ENGINE_UNIT_SCENE_V4` |
| 의미 | `COUNTERFACTUAL_REFERENCE_VISUAL_STUDY_NOT_KOREAN_WAR_HISTORY` |
| territory | ORANGE/PURPLE 상보 scalar, 64 longitudinal knots, 11 boundary keyframes, 선형 보간 |
| Scene 시간 | local `[0,150)`, 30fps; 이후 역사80초 plan의 일부 구간이 아님 |
| 기본 native camera anchor | frame176 |
| camera keyframes | frame0,38,75,112,149; bounds와 roll 원본 그대로 |
| roll | 10.997080633577195°, 11.997080633577195°, 11.997080633577195°, 10.097080633577194°, 4.997080633577195° |
| presentation | overscan1.36; 원본 화면 전체 GIS/projection과 일관된 회전 |
| 국기·군대 | 원본 fixture 8개; PRC1949 / DPRK1948 / ROK1949 / USmodern50star / RUSmoderntricolor |
| 군대 의미 | 현대 가상 시각연구 기호. 실제 한국전쟁 부대 위치·참전 사실을 주장하지 않음 |
| 실제 육지/바다 source | 기존 licensed Natural Earth1 baked-relief raster |
| NE1 SHA | `49127186cb2076131e49e3787454c31474e48ef206c27c6c637749173aca143a` |
| 지형 style | `NE1_SOURCE_COLOR_RESTRAINED_WARM_RELIEF_VISUAL_V4` |
| 바다 style | `WORLD_ENGINE_SOURCE_TONE_BLUE_OCEAN_V4` |
| territory style | `TERRAIN_READABLE_ORANGE_PURPLE_V4` |
| frontier style | `MOVING_FRONTIER_GLOW_FIX_V1` |
| frontier 주요 값 | near-white core2.5px; gold halo sigma3.5px/support10px/alpha0.35; settledStrength0.08; velocityWindow12frames |
| DEM / ASTRA | 원본 native draw `dem:false`; ASTRA 지형·수심·지표 GPU layer는 원본에서 선택하지 않음 |
| native labels/title | 원본 `graphics:false`/명시적 optional foreground 없음; public video text 없음 |
| 추가 표현 | 화살표·경로·장식 전선·새 시각효과 추가 없음 |

## 실제 호출과 합성 순서

원본 진입점은 Studio 프롬프트 파서 또는 역사 preset을 호출하지 않는다.

```text
openQualityRuntime(VISUAL_REFERENCE_STUDY)
→ 원본 fixture, Scene, savedScene, visual admissions와 5개 native input 검증
→ compileTerritoryControlPlan(original controlIntent)
→ compileReferenceCameraTrack(original base camera / anchor176 / 5 keys)
→ createMapEngineUnitGpuAdapterV4
  → 기존 native GIS / coverage / projection
  → 원본 NE1 육지·바다 material
  → 상보 scalar territory 색상
  → 실제 scalar 경계 + actualTerrainTexture를 참조하는 frontierV3 light
  → 원본 presentation overscan/roll
  → 원본 national unit badges
→ drawFrame(original local frame)
→ 실제 readPixels + canvasPNG + 양쪽 SHA
→ 원본 encoder 옵션으로150프레임 MP4
```

원본 `render_proof.mjs`를 기존 repository root에서 그대로 실행하면 기존 proof/public-review/cache에 쓰게 되므로 실행하지 않는다. 새 실행기는 독립 source capsule에서 **원본 `reference_runtime.mjs`를 직접 import**하고, 원본 assertions와 실제 capture 함수를 그대로 호출한다. 이것은 렌더러를 복제하거나 다시 구현한 경로가 아니다. 원본 원화·shader·Scene·asset은 변경하지 않는다.

```bash
node world-simulation-shorts-engine/recovery/exact-65422-reproduction-v1/tools/capture_original.mjs \
  --capsule=<검증된_원본_소스_capsule_절대경로> \
  --original-report=<45af879_원본_REPORT.json_절대경로> \
  --cache=<새로운_독립_capture_디렉터리>
```

이 CLI는 새 캡처용 개발 진입점이다. 사용자에게 모바일 터미널 실행을 요구하지 않으며, Studio 제작 API의 새 지원 명령이라고 주장하지 않는다. 원본 runtime source signature와 73개 바인딩 bytes를 검사하고 원본 cache/MP4를 새 draw로 재사용하지 않는다.

## 원본 인코딩

입출력 경로만 새 디렉터리를 사용한다.

```text
ffmpeg -hide_banner -loglevel error -nostdin
  -framerate 30 -start_number 0 -threads 2 -i <frames>/%03d.png
  -frames:v 150 -an -c:v libx264 -preset fast -crf 16
  -threads 2 -pix_fmt yuv420p -movflags +faststart <new-output.mp4>
```

원본 전체 argv는 `PRIMARY_EVIDENCE.json`이 참조하는 immutable REPORT의 `encodeCommand`와 새 capture report에 기록한다. MP4 container SHA, decoded video SHA, 실제 rawRGBA SHA, PNG SHA와 deterministic scene state를 분리하여 비교한다.

## 한계와 보호

- 실제 RTX/NVIDIA 동작이나 신규 GPU image 배포를 검증하지 않는다. 원본이 software capture이므로 유료 GPU는 필요하지 않다.
- 실제 66461/66463의 파일명→SHA, producing deployment, image digest는 증거 부족으로 미확인이다. 알려진 SHA3899d87c…와 임의로 동일시하지 않는다.
- 원본보다 좋은 지형/조명/SFX를 추가하지 않는다. 원본 재현과 레퍼런스65379 품질 승인은 별개다.
- 원본 private Scene 및 원시 진단은 원본 위치/무결성 바인딩으로 보존한다. Public Review에 내부 private 파일을 게시하지 않는다.
- 80초 재렌더링, 기존 workload 재배포, FINAL 승격, old claim/cache 초기화는 하지 않는다.

## 실제 복원 실행 결과

별도 capsule의 원본 73개 바인딩과 운영 의존성 7개를 immutable Git으로 확인했다. 실제 새 software draw에서 원본 runtime signature가 일치했고, **150/150 rawRGBA와 150/150 PNG bytes가 원본 capture SHA와 정확히 일치**했다. 카메라·회전·scalar 영토·전선·지형·presentation·국가별 표식·보호 상태 등 10개 deterministic state 범주도 전부 일치했다.

그러나 원본 옵션으로 새로 인코딩한 H.264 MP4를 전체 디코딩하면 **frame0부터 차이**가 발생한다. 전체 150프레임의 RGB8 평균 절대 차이는 1.0030724537037037/255, 최대 채널 차이는 63, 집계 PSNR은 43.973861559827164dB다. frame0의 평균 절대 차이는 0.37902504501028805/255다. 기술 규격과 PTS는 일치하지만 완성 MP4 픽셀은 같지 않으므로 최종 판정은 **`REPRODUCTION_NEEDS_REWORK`**다.

원본과 새 파일의 SEI는 모두 `x264 core164 r3108 31e19f9` 및 동일한 인코딩 옵션을 광고한다. 이는 원본 binary build, libswscale 색 변환, CPU feature dispatch까지 같다는 증거가 아니다. PNG 이후 인코딩 단계가 최초 차이 지점이라는 것은 확인했으나 정확한 하위 원인은 미확인이다.

추가 GPU draw 없이 2회만 인코딩을 분리 시험했다. `-cpuflags 0`은 frame0 차이를 악화시켰고, `-filter_threads 1`은 원본 옵션 후보와 MP4 전체 bytes가 같았다. 원인 근거가 없으므로 두 시험을 해결책으로 승격하거나 렌더러/Scene/셰이더를 수정하지 않았다.

실제 비교 증거: `comparison/ALL_150_FRAME_COMPARISON.json`, `ENCODING_DIFFERENCE_AND_TRIALS.json`. 원본 화면 조건의 복원 성공과 최종 MP4의 엄격한 재현 실패를 구분한다.
