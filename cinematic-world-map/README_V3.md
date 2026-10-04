# CINEMATIC WORLD MAP — MASTER V3

V3는 기존 GIS·geodesic·camera·scene 기반을 공유하되 실제 3D Earth 공간의 재질·조명·대기·구름·항로·항공기를 새로 구성한다. V1/V2 코드, 자산, 보고서와 영상은 보존한다. 이번 범위는 20초 마스터의 그래픽 품질이며 UI·60초 생성기·TTS·업로드 자동화는 포함하지 않는다.

현재 **MASTER V3의 유음·묵음 20초 MP4 제작 및 객관 검사 완료** 상태다. 최종 규격은 1080×1920/30fps/H.264/yuv420p/BT.709 limited range다. 전체 600프레임 디코딩에서 black/frozen/duplicate, 문자 clipping·label/plane 근접·label overlap은 0이고, Chrome mobile viewport의 실제 20초 재생은 600프레임/drop 0/corruption 0으로 끝났다. 원본 크기 Chrome 재생은 20초 완료했으나 presentation drop 2가 있어 모바일 결과와 구분한다. 실제 최종 AAC 음량과 두 MP4의 전체 RGB 동일성을 확인했다. 직접 청취·실물 스마트폰·사진 수준 타깃 동급·시청 지속률 향상은 인증하지 않는다. 자세한 근거와 한계는 [QUALITY_REPORT_V3.md](QUALITY_REPORT_V3.md)에 기록한다. 다운로드 위치는 마지막 전달 절을 참조한다.

r15는 `Renderer.init()`에서 Open Sans를 `document.fonts.load()`/`check()`한 뒤 `window.ready`를 열어 glyph 준비를 보장한다. 검수된 r15 앞 10초와 r23 뒤 10초를 순차 렌더하고 picture bitstream을 재압축 없이 연결했다. `outputs/v3_r15_r23_first10_input_equivalence_bounded.json`은 0~10초/120Hz 1,201개 pose에서 `complete=true`, `exactInputsEqual=true`, `staticInputsEqual=true`, mismatch 0을 확인한다. 10초 경계와 ±1/120초 shutter 준비를 포함해 마지막 준비 시각은 10.008333초다. scope는 **렌더 입력 동등성**이며 GPU draw·새 RGB 비교가 아니다. 별도 `outputs/v3_final_picture_identity.json`은 최종 유음/묵음 전체 600 RGB와 검수된 r15 앞 300 RGB의 실제 동일성을 확인한다. 이전 결함 프리뷰와 실패 검사 로그는 보존하며 최종 전달본에 사용하지 않는다.

검증된 r15 앞 10초의 SHA-256은 다음과 같다. 완성한 앞 두 구간의 source manifest에서 같은 값을 확인했다.

```text
src/engine_v3.js   dbf5454a80967dc13d53501990eaf1c5d1b72483791e8347ef78d5009a42666e
src/renderer_v3.js 46b0fea8a2ae66291cae839db9b6ed331ca68a9167587c507136bbbb5f6b81b7
```

검수한 r15 engine/renderer snapshot, SHA와 설명은 `docs/review-sources/v3-r15/`에 보존했다. 원래 구간은 재압축하지 않고 유지한다.

r23 후반 완성 구간의 동결 소스 SHA-256은 아래와 같다. r21 기하 검사의 engine과 같으며 r22 layout은 같은 camera/overlay를 검사한 자료다. 구간별 source manifest와 입력 proof로 두 버전의 검사 범위를 구분한다.

```text
src/engine_v3.js   7e35b088d7de740d61c2e0c8765f0b941839b8896bc297e8765adf991f4f4aad
src/renderer_v3.js b378269674833f9a79cbbbb2d9c24b004d5ca398063ca897ec1a5359eed0d6d3
```

## 실행 환경

프로젝트 경로: `/workspace/yeonhwarok-free/cinematic-world-map`. Node 24, Python 3, FFmpeg/ffprobe, 시스템 Chromium이 필요하다. 검증한 라이브러리는 Three.js 0.170.0, Playwright 1.62.1, numpy 2.3.5, scipy 1.17.0, Pillow 12.3.0이며 기존 lockfile/requirements를 유지한다. GPU 없는 현재 환경에서는 Chromium SwiftShader를 사용한다. Blender 4.3.2는 renderer 비교 시험에만 사용했으며 최종 렌더의 의존성은 아니다.

처음 설치할 때:

```bash
cd /workspace/yeonhwarok-free/cinematic-world-map
npm ci
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

시스템 도구가 없는 Debian/Ubuntu 환경에서는 관리자 권한으로 FFmpeg와 Chromium을 설치한다. 여기서는 이미 설치되어 있다. node_modules, .venv, 출력 파일이 존재하는 환경에서는 재설치 대신 버전과 파일 보존 상태를 먼저 확인한다.

```bash
python3 -m http.server 8030 --bind 127.0.0.1 --directory /workspace/yeonhwarok-free/cinematic-world-map
```

다른 터미널에서 `curl --fail http://127.0.0.1:8030/index_v3.html`로 응답을 확인한다. 기존 프로세스를 임의로 종료하거나 기존 MP4를 덮어쓰지 않는다. 아래 렌더 도구는 같은 이름의 파일이 있으면 중단하므로 새 검수 이름을 사용한다.

## 렌더와 검수

같은 source를 유지한 0~5초, 5~10초, 10~20초 구간을 순서대로 제작하는 예다. 각 구간의 실제 영상 검수가 끝난 뒤 다음 구간을 실행한다. 출력이 이미 존재하면 새 이름을 선택하며 병렬 렌더를 하지 않는다. 다음 기하 검사는 렌더·전체 재생 검수와 구분한다.

```bash
cd /workspace/yeonhwarok-free/cinematic-world-map
node tools/preflight_v3.mjs --output=outputs/v3_preflight_new.json
node tools/check_aircraft_triangles_v3.mjs outputs/v3_triangles_new.json
node tools/layout_preflight_v3.mjs outputs/v3_layout_new.json
```

첫 구간과 정지 프레임:

```bash
node tools/render_v3.mjs --still=0.5,15 --width=2160 --samples=1 --prefix=v3_review_new_
node tools/render_v3.mjs --start=0 --seconds=5 --width=2160 --samples=1 --name=v3_segment_00_05_new_muted
.venv/bin/python tools/tag_video_v3.py outputs/v3_segment_00_05_new_muted.mp4 outputs/preview_5s_v3_new_muted.mp4
.venv/bin/python tools/mux_v3.py --input=preview_5s_v3_new_muted.mp4 --output=preview_5s_v3_new.mp4 --seconds=5
.venv/bin/python tools/validate_v3.py outputs/preview_5s_v3_new.mp4 --scene outputs/v3_segment_00_05_new_muted_scene_audit.json
node tools/playback_v3.mjs preview_5s_v3_new.mp4 --mobile --no-capture
```

첫 구간을 직접 검수한 뒤 5~10초를 렌더하고, 재압축 없이 10초 프리뷰를 만든다:

```bash
node tools/render_v3.mjs --start=5 --seconds=5 --width=2160 --samples=1 --name=v3_segment_05_10_new_muted
.venv/bin/python tools/concat_v3.py --output=v3_join_00_10_new_muted.mp4 v3_segment_00_05_new_muted.mp4 v3_segment_05_10_new_muted.mp4
.venv/bin/python tools/tag_video_v3.py outputs/v3_join_00_10_new_muted.mp4 outputs/preview_10s_v3_new_muted.mp4
.venv/bin/python tools/mux_v3.py --input=preview_10s_v3_new_muted.mp4 --output=preview_10s_v3_new.mp4 --seconds=10
.venv/bin/python tools/validate_v3.py outputs/preview_10s_v3_new.mp4 --scene outputs/v3_join_00_10_new_muted_scene_audit.json
node tools/playback_v3.mjs preview_10s_v3_new.mp4 --mobile --no-capture
```

10초까지 검수한 뒤 마지막 구간과 20초 결과를 만든다:

```bash
node tools/render_v3.mjs --start=10 --seconds=10 --width=2160 --samples=1 --name=v3_segment_10_20_new_muted
.venv/bin/python tools/concat_v3.py --output=v3_join_00_20_new_muted.mp4 v3_segment_00_05_new_muted.mp4 v3_segment_05_10_new_muted.mp4 v3_segment_10_20_new_muted.mp4
.venv/bin/python tools/tag_video_v3.py outputs/v3_join_00_20_new_muted.mp4 outputs/master_cinematic_20s_v3_muted.mp4
.venv/bin/python tools/mux_v3.py --input=master_cinematic_20s_v3_muted.mp4 --output=master_cinematic_20s_v3.mp4 --seconds=20
.venv/bin/python tools/validate_v3.py outputs/master_cinematic_20s_v3.mp4 --scene outputs/v3_join_00_20_new_muted_scene_audit.json
node tools/playback_v3.mjs master_cinematic_20s_v3.mp4 --mobile --no-capture
```

`concat_v3.py`는 기본 strict 모드에서 완성 manifest, 연속 구간 시각, 모든 source SHA-256 일치, stream format/색 태그/frame count를 확인하고 picture를 bitstream copy한다. scene audit도 합친다. 위 동일 source 예시는 그대로 사용한다. 실제 최종본처럼 검수한 r15 앞 두 구간과 r23 후반을 연결할 때만 아래 검증된 compatibility proof를 지정한다. 도구는 proof 완료·동등성·source SHA·해당 구간 시간 범위를 확인하며 전체 source 차이를 무조건 허용하는 옵션이 아니다. 기존 결과는 보존하고 새 출력 이름으로 재현한다.

```bash
.venv/bin/python tools/concat_v3.py --compatibility=outputs/v3_r15_r23_first10_input_equivalence_bounded.json --output=v3_join_00_20_r15_r23_new_muted.mp4 v3_segment_00_05_review_r15_muted.mp4 v3_segment_05_10_review_r15_muted.mp4 v3_segment_10_20_review_r23_muted.mp4
```

`tag_video_v3.py`는 **묵음 picture용**이며 video만 복사하고 BT.709 limited-range VUI·title·`assets/v3/CREDITS_V3.txt`의 attribution을 넣는다. audio를 넣기 전에 실행한다. tag/mux는 새 scene audit를 만들지 않으므로 검수에는 원래 segment 또는 concat audit를 전달한다. 입력 proof는 새 GPU/RGB 동등성이나 최종 20초 품질 승인으로 해석하지 않는다.

위 mux 명령은 보존한 `assets/audio/v3/score_master.wav`를 사용한다. 실제 최종 AAC 측정은 **−18.31 LUFS / −2.49dBTP / LRA 7.9LU**이며 `outputs/v3_final_audio_validation.json`이 근거다. 원 score와 최초 6초 교차상관은 0.99999355, 측정 지연 0초(0.25ms 해상도)다. 20초 재생에서 audio decode를 확인했으나 직접 청감은 수행하지 못했고 `direct_listening=false`를 유지한다. 이는 각 효과음의 청감·믹스 합격을 의미하지 않는다. 새 음향이 필요할 때만 `tools/sound_v3.py`로 raw를 만들고 새 출력 이름으로 2-pass loudnorm을 적용한다. 설계 목표는 −18.5 LUFS / −2.2dBTP / LRA 9다. `outputs/v3_sound_normalization.json`의 −19.17 LUFS / −2.20dBTP / LRA 6.20은 **pass1의 출력 예측**이며 실제 pass2 WAV나 최종 AAC의 측정값이 아니다. mux는 −0.3dB를 추가 적용한다. 기존 raw/master/cue 파일을 보존하고 불필요하게 재생성하지 않는다.

최종 검사 첫 실행의 명령은 아래와 같다. `validate_v3.py`와 `verify_picture_v3.py`는 기존 검사 결과가 있으면 중단한다. `verify_picture_v3.py`는 현재 master·r15 결과 이름과 고정 출력 `v3_final_picture_identity.json`을 사용하므로 재현 복사본에서 처음 실행하며 기존 QA를 삭제하거나 덮어쓰지 않는다. `playback_v3.mjs`도 기존 JSON·캡처가 있으면 브라우저 실행 전에 중단하고 JSON을 exclusive 생성한다. 기존 검수 자료를 덮어쓰지 않는다. audio 재검사는 `--output`에 새 이름을 지정할 수 있다.

```bash
.venv/bin/python tools/validate_v3.py outputs/master_cinematic_20s_v3.mp4 --scene outputs/v3_picture_20s_muted_scene_audit.json
.venv/bin/python tools/verify_picture_v3.py
.venv/bin/python tools/check_audio_v3.py outputs/master_cinematic_20s_v3.mp4 --output=outputs/v3_final_audio_validation.json
node tools/playback_v3.mjs master_cinematic_20s_v3.mp4 --mobile --no-capture
node tools/playback_v3.mjs master_cinematic_20s_v3.mp4 --no-capture
```

내부 출력은 2160×3840 HDR WebGL scene, MSAA 2, 깊이와 카메라/기체 속도를 이용한 7탭 선형 HDR motion integration이다. 기본 `--samples=1`은 nominal time 한 시점이며 HERO에서는 같은 시점의 반사 cube 6개 면과 shadow pass가 추가된다. 빠른 운동의 번짐은 최종 1080px 기준 최대 motion 길이 8px로 제한하고 라벨은 이후 선명하게 합성한다. 이 근사는 tap별 depth rejection이나 완전한 다중 시간 렌더 적분을 하지 않는다. HERO cloud raymarch도 nominal ray 한 번이며 cloud를 여러 시간에 적분하는 구현은 아니다. 기체/배경 경계 섞임, volume/noise의 frame alias와 handoff는 실제 MP4에서 확인한다. `--samples=2`는 추가 full-scene temporal sampling을 위한 선택사항이며 기본 최종 설정 1과 구분한다. JPEG 99 pipe를 FFmpeg로 전달해 Lanczos 축소, 명시적인 full-range BT.601 → limited-range BT.709 변환, H.264 CRF 15 slow/30fps/yuv420p로 출력한다. `h264_metadata` bitstream filter의 `video_full_range_flag=0`, primaries/transfer/matrix=1로 BT.709 limited-range VUI를 명시한다. 실제 ffprobe·decode 결과를 확인한다. 사운드는 picture stream을 복사해 AAC 320kbps/48kHz로 추가한다. 최종 MP4는 SDR이며 내부 HDR buffer와 구분한다.

120초 동안 완료 프레임이 없으면 해당 렌더의 browser/encoder만 중단한다. checkpoint와 partial MP4를 보존하며, 원인을 확인하고 새 출력 이름으로 해당 구간을 복구한다. 작업 중 다른 렌더를 병렬 실행하지 않는다.

## 구조

`src/engine_v3.js`: 기존 geodesy와 scene 계약을 상속하는 CameraController, RouteAnimator, EntityAnimator, SceneManager. Seoul ICN → Tokyo NRT → Singapore SIN의 spherical great-circle arc, tangent orientation/bank, shot별 Hermite camera rig. r23 HERO는 같은 쪽 quarter-front에서 기체 기준 radial up `.145`, right `−.130`, forward `.095`의 camera와 forward `.008`/up `.014` aim, FOV 42°를 사용한다. 이 값은 Earth radius=1 좌표의 연출 rig이며 실제 촬영 거리의 단위가 아니다.

`src/aircraft_v3.js`: `createAircraftV3()`가 +Y forward/+Z up의 THREE.Group을 반환한다. 새로 제작한 original 31 mesh / 21,046 vertices / 37,888 triangles이며 19 geometry와 7 PBR material을 공유한다. smooth sampled fuselage, 곡면 airfoil의 swept/tapered wing과 dihedral, stabilizer/winglet, navy fin, white curved nacelle/inlet lip/recessed fan, conformal cockpit/windows/door seam을 사용한다. 외부 model/logo/texture와 자체 light는 없다. 기존 V1/V2 기체를 보존하며 scene controller가 pose/scale/opacity를 처리한다.

`src/renderer_v3.js`: EarthRenderer, RouteGraphics, EffectsEngine, Renderer. 실제 구면, 8K day/night/cloud textures, 분리된 cloud altitude layers, scene depth를 사용하는 Sun/Moon RGB Rayleigh single scattering, HDR grading과 3D aircraft를 처리한다. 대기는 12 view 표본과 Sun/Moon 방향 각각 4개 optical-depth 표본이며 HERO에서 대기 산란 노출을 낮춘다. Moon fill은 실제 달/태양 광도 비율을 재현하지 않는다.

`prepareHeroLighting()`은 12.8초 이후에만 material·reflection·shadow·volume 자원을 lazy 생성한다. 기존 paint geometry/material을 보존하고 HERO에만 MeshPhysicalMaterial coating을 사용한다. 최대 clearcoat `.65`, clearcoat roughness `.14`, environment intensity `.5`이며 128×128/면 half-float cube로 실제 scene의 Earth와 texture-shell cloud를 반사시킨다. 이는 저해상도 환경 반사 근사이며 cloud volume까지 정확한 광선 추적 반사로 풀지 않는다. 기체 자체 그림자는 Sun 1024²/Moon 512² PCFSoftShadowMap이다. direct light의 지구 차폐는 기체 중심 radial/horizon 근사이며 Hemisphere는 radial up에 맞춘다. HERO의 Moon 기본 intensity는 `.72`, Hemisphere는 `.17`이며 실제 천문 광량이 아니다. Sun은 최대 5° 연출 회전하고 Earth·cloud·aircraft·atmosphere가 같은 방향을 공유한다.

HERO volume cloud는 라이선스를 확인한 8K 실제 cloud coverage를 gate로 사용해 4.5~11km 높이에 original 64³ density noise를 더한다. noise는 12/36/108 공간 주파수 조합으로 두께·edge billow를 만들며 새로운 지형·도시 사진을 생성하지 않는다. bounded raymarch는 14 view 표본과 4 Sun optical-depth 표본을 사용하고 Sun 경로는 최대 40km다. scene depth로 plane/terrain 앞뒤 가림을 처리한다. 기존 4.5/7.5km 두 shell은 HERO 진입·복귀 시 fade handoff하고 나머지 shot과 반사 capture에 유지한다. 완전한 기상·multiple scattering·사진 수준 cloud 시뮬레이션으로 설명하지 않는다.

`SceneManager.insert_cinematic_clip()` 계약은 보존한다. 현재 마스터에는 외부 I2V를 사용하지 않는다. 좌표·항로·shot 표현을 분리했으며 이 세 도시 외 지역으로 확장할 수 있는 구조를 유지한다.

## GIS·자산·라이선스

- Earth day/night/cloud: Solar System Scope, CC BY 4.0. 실제 사용한 세 texture 모두 8192×4096이며 고정 GitHub mirror commit, 원본 설명, 크기와 hash는 `assets/v3/earth/SOURCES_V3.json`에 있다. 임의 지형이나 AI 지도를 생성하지 않았다.
- 기존 국가/해안 GeoJSON: Natural Earth public domain. V3에서 국가를 평평하게 칠하지 않지만 원본 벡터 데이터와 geodesy를 보존한다.
- 미세 지형 bump: 기존 three-globe texture, MIT. 실제 DEM mesh/도시 건물 모델은 아니다.
- Open Sans Light: Apache 2.0, font와 license copy를 함께 제공한다.
- 항공기 geometry: `src/aircraft_v3.js`의 새 original PBR 3D mesh. 지구 위에서 읽히도록 크기를 연출한 visual proxy이며 실측 aircraft scale이라고 주장하지 않는다. arc/기체 중심의 고도는 11~15km이며 항로와 시간 역시 연출된 시뮬레이션이다.
- 음악/효과음: 기존 프로젝트 synth primitive를 바탕으로 직접 제작한 V3 waveform, CC0. 외부 상업 음악·reference audio를 복사하지 않았다.

정확한 attribution은 `assets/v3/CREDITS_V3.txt`를 참조한다. YouTube 게시 시 Solar System Scope 저자·원본 출처·[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 링크를 설명란에 포함한다. 출처 파일과 MP4 metadata에도 attribution을 보존한다.

## 품질과 한계

최종 근거와 한계는 [QUALITY_REPORT_V3.md](QUALITY_REPORT_V3.md)에 기록한다. `QUALITY_REPORT_V3_DRAFT.md`는 제작 당시의 초안으로 보존한다. 현재와 같은 engine의 r21 기하 검사에서 1,201개 자세의 numerical violation은 0, 최대 카메라 각도 변화는 1.462456470°/30fps frame이다. 같은 camera/overlay의 r22 layout 검사에서는 600프레임 중 358 label frame의 clipping·label/plane·label overlap·safe-scene 문제가 모두 0이다. r11 삼각형 검사는 변경되지 않은 기체·자세의 799개 가시 표본에서 지구 교차 0, 최소 여유 2.036287km를 기록하지만 연속 시간이나 cloud 교차를 증명하지 않는다. 최종 600프레임 decode·scene audit에서도 해당 결함과 정지·duplicate·black frame은 0이다. 서울/도쿄/싱가포르 glyph 폭은 각각 330.926/337.713/576.843px로 한 값이며 내부 2160px canvas의 metric이다.

주 작업자는 최종 모바일 contact 7장(0~19.5초, 0.5초 간격)과 동일 시점 V2/V3 비교 6쌍을 직접 확인했다. HERO의 공간·기체 재질 차이와 도착·전체 경로 연결을 확인했으나 매우 희미한 배경 network의 폰 가시성과 확대된 8K 표면·기체 중간톤에는 한계가 남는다. HERO는 저표본 3D density raymarch와 두 texture shell의 혼합이며 실제 weather simulation이 아니다. 지형은 topology bump이고 실제 DEM displacement/도시 건물 모델은 아니다. 반사 cube·shadow map·Sun/Moon 단일 산란도 각각 해상도와 근사가 있다. 파형·loudness·cue sync·audio decode 검사와 직접 청감을 구분한다. 로컬 target 원본이 없어 사진 같은 근접 항공기/도시 landmark와 동일 픽셀 비교하지 않았다. 실제 스마트폰·청감·시청 지속률·사진 타깃 동급을 이 문서에서 추정하지 않는다.

## 보존·전달 상태

`outputs/v3_preservation_final.json`에서 기존 197개 파일 SHA 변경/누락 0, V3 staging 전 기존 tracked repo diff 0을 확인했다. 보존 archive는 354,814,032B이며 SHA-256은 `cc3e9d306388489787344bdea3c99741ed1987c387d39fbb716e11969735ad1e`다. 로컬 최종 MP4·프리뷰·보고서와 QA는 `outputs/` 및 프로젝트 문서에 보존한다. 전달 파일은 저장소 루트의 `deliverables/`에 추가한다. [GitHub 다운로드 폴더](https://github.com/dimon3898-sys/yeonhwarok-free/tree/main/deliverables)에서 V3 영상·프리뷰·비교 이미지·보고서·검증 JSON·크레딧·SHA manifest와 `CINEMATIC_WORLD_MAP_MASTER_V3_20S.zip`을 제공한다. 일반 Git의 100MiB 파일별 제한에 맞는지 실제 최종 크기를 검사하며, 원격 commit·다운로드 해시 대조는 게시 후 최종 응답에서 보고한다.

최종 ZIP은 55,169,999B(약 52.6MiB), 유음 MP4는 21,211,440B, 무음 MP4는 20,503,139B다. 파일별 100MiB 제한 이내여서 일반 Git을 사용한다. ZIP은 50MiB 권장 경고 기준을 넘지만 하드 제한에는 해당하지 않으며 LFS pointer 또는 분할본이 아니다. 검증 묶음에는 원본 크기 재생의 2 presentation drop도 숨기지 않고 포함한다.
