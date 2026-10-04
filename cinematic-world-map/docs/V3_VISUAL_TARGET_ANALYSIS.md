# MASTER V3 — visual target and renderer decision

분석일: 2026-10-04 KST. 사용자가 대화에 첨부한 세로 storyboard 이미지를 직접 관찰했다. 이미지의 지형·문구·랜드마크·수치를 데이터로 복사하지 않는다. 현재 로컬 attachment에는 원래 MP4만 있으며 target은 대화에 표시된 이미지로 비교한다.

## 타깃의 시각 원리

- 검은 우주와 곡면의 지구가 한 공간으로 이어진다. 밝은 외곽을 두꺼운 cyan 선으로 감싸는 대신, 얇은 blue rim과 수평선 haze가 별도로 읽힌다.
- 낮의 지표보다 밤의 도시권 불빛이 정보를 전달한다. amber 불빛은 작은 광점이 밀집한 실제 도시 패턴으로 보이고, cool 대기/항로와 대비한다.
- 구름은 지표 texture와 분리된 높이에 있다. 태양을 향한 윗면과 어두운 아랫면, cast shadow, 곡면을 따른 parallax가 공간을 만든다.
- 태양 방향과 terminator가 표면·구름·항공기에 동시에 작용한다. 밝은 낮/어두운 밤/빛나는 도시/대기 경계의 노출을 함께 잡는다.
- 항로는 표면 위의 3D curve이며 발광 core와 작은 head를 갖는다. 전체 네트워크는 주 항로보다 낮은 밝기로 유지한다.
- 항공기는 측면·상단·꼬리의 재질과 음영이 다르게 보여 실제 부피가 읽힌다. 단색 기호와 과도한 외곽 glow를 사용하지 않는다.
- 카메라의 규모 변화는 orbital establishing → city approach → route chase → horizon → global pullback으로 목적이 다르다. HERO는 전경/중경/원경을 구분한다.
- 얇고 여백 있는 typography, 깊은 ocean blue, 자연 지표, warm amber와 atmospheric blue의 대비를 사용한다. 반복 HUD, 배경 사각형, 대형 설명 자막은 제거한다.

타깃에는 근접 항공기 및 실제 도시 랜드마크처럼 보이는 패널도 있다. 이번 20초는 실제 3D Earth 공간을 유지하며, 확인되지 않은 도시 사진/AI 지형/가짜 랜드마크를 삽입하지 않는다. 목표는 소재 복제가 아니라 재질·조명·깊이의 품질이다.

## 보존과 분리

V1/V2 프로젝트 197개 파일의 SHA-256과 archive를 구현 전에 저장했다. `/workspace/preserved-originals/cinematic-world-map-before-v3-20261004T044013.*` 참조. 기존 소스·지도·음향·문서·MP4는 수정하지 않는다. V3의 scene, assets, renderer와 report는 새 이름으로 만든다.

기존 `geo`, great-circle 계산, Hermite camera 보간, 항공기 tangent/orientation, SceneManager와 insertion 계약은 공유한다. Three 좌표에서 Blender 좌표로 `(x,y,z)→(x,−z,y)` 변환해 GIS 위치를 보존한다. 모든 행렬은 동일 nominal/subframe 시각에서 계산하며, 기존 temporal-render audit를 pose 원본으로 사용하지 않는다.

## 실제 기술 검토

환경: Blender 4.3.2 / Three.js 0.170 / SwiftShader / FFmpeg. GPU 및 `/dev/dri` 없음, 실질 CPU 4코어, RAM 32GiB.

| 기술 | 이번 목표에 대한 평가 |
|---|---|
| Three.js/WebGL/GLSL | 기존 구조와 결정론적 GIS/카메라 계산을 공유한다. 현재 생산 renderer는 별도 8K day/night/cloud 입력, depth를 고려한 Sun/Moon RGB Rayleigh 적분, HDR와 새 PBR 기체를 사용한다. CPU SwiftShader 비용은 실제 정지 프레임/짧은 MP4로 측정하며, 완전한 volumetric cloud renderer로 설명하지 않는다. |
| CesiumJS | 고해상도 globe/terrain streaming에 강하다. 기본 GIS 스타일과 remote tile/credit 관리가 추가되며, 이번 짧은 영화 조명·항공기 재질의 지름길은 아니다. |
| deck.gl/MapLibre | 벡터 GIS와 데이터 레이어에 적합하다. 이 작업의 핵심인 사진 같은 구면 재질·구름·일관된 광원은 별도 Earth renderer가 필요하다. |
| Blender Eevee | raster shadows·PBR·volumes를 같은 장면으로 구성할 수 있다. GPU 없는 환경에서는 실시간 속도를 가정하지 않고 실제 프레임 시험한다. |
| Blender Cycles | ray-traced sunlight/occlusion/atmospheric volume/cloud shadow와 aircraft PBR를 한 장면으로 처리할 수 있다. 이번 실제 CPU 시험은 540×960이며, 고해상도 최종 시간은 이 값만으로 확정하지 않는다. |
| WebGPU | 최신 물리적 scattering/cloud 구현 가능성이 있으나 현재 장치와 software adapter에서 검증되지 않았다. 기능 존재를 품질/속도 증거로 간주하지 않는다. |
| FFmpeg | 색상 태그, 고품질 downsample, H.264/AAC, 합성과 최종 media QA에 사용한다. Earth를 2D 프레임 도형으로 대신 그리지 않는다. |

선택한 day/night/cloud 텍스처 세 종은 실제 8192×4096이며 Solar System Scope CC BY 4.0 자산이다. 고정 mirror/치수/크기/SHA-256/license 근거는 `assets/v3/earth/SOURCES_V3.json`에 있다. 지표 relief는 보존된 topology bump이며 실제 DEM displacement mesh나 건물 단위 GIS가 아니다. Natural Earth 벡터 GIS와 실제 공항 좌표는 보존한다.

### 실제 Blender CPU 시험 결과

| 시험 | 출력/시각 | 실제 샘플 설정 | 장면 build | render |
|---|---|---|---|---|
| Cycles r2 | 540×960 / 0.5초 | CPU 24, denoise 끔 | 26.189780초 | 44.457663초 |
| Eevee Next r1 | 540×960 / 0.5초 | 기본 64; CLI 요청은 24 | 25.500072초 | 112.799741초 |

근거 파일은 `outputs/v3_probe_cycles_r2_benchmark.json`, `outputs/v3_probe_eevee_r1_benchmark.json`이다. 도구는 Cycles의 `scene.cycles.samples`만 설정하고 Eevee의 `taa_render_samples`는 설정하지 않았다. JSON의 Eevee `samples=24`는 CLI 요청값이며 실제 Eevee 설정 64와 구분한다. 동일 24-sample 조건의 비교로 해석하지 않는다. Cycles의 낮은 샘플·denoise 비활성 프레임에는 노이즈가 남았다.

Blender 시험 tool의 camera `clip_start`는 여전히 `.00001`이며 현재 생산 WebGL CameraController가 매 pose에 설정하는 near는 `.02`다. normalized Earth-scale scene에서 시험의 near/depth 설정과 software/EGL 조건을 함께 고려해야 한다. prototype의 clipping/조명/장면 구성 결함을 Eevee 고유의 품질 결함으로 돌리지 않는다. 이 값들은 해당 환경·시험 장면 한 프레임의 조건이며, Cycles/Eevee/WebGL의 전반적인 기술 우열이나 최종 4K·600프레임 속도를 증명하지 않는다.

현재 생산 경로는 WebGL/GLSL + FFmpeg다. 첫 5초 r1의 manifest는 내부 2160×3840, nominal scene sample 1, 7탭 motion integration, 150프레임의 총 경과 시간 1,083.371초를 기록한다. 이 시간은 프레임 전달/인코딩도 포함하며 새 r11/r12 scene의 소요 시간을 보장하지 않는다. r1은 실제 영상 검사에서 서울 label/aircraft 근접을 발견해 승인하지 않았다. 수정한 첫 5초 r2의 생산·검수를 진행 중이며, 기술 선택을 최종품질 승인으로 표현하지 않는다.

### 현재 생산 표현과 근사 범위

- 대기는 지구/opaque scene depth까지 view ray를 적분하고 고도에 따른 지수 밀도·RGB Rayleigh phase·Sun/Moon 방향의 optical depth와 지구 차폐를 계산한다. view 12개, Sun/Moon 방향 각각 4개 표본의 단일 산란 근사다. `.65` Moon scattering은 밤의 가독성을 위한 cinematic fill이며 실제 달/태양 광도 비율을 재현하지 않는다. 완전한 spectral/multiple scattering 또는 기상 계산은 아니다.
- 구름은 4.5/7.5km의 texture shell 두 겹과 태양 방향 투영의 근사 지표 그림자다. 완전한 volumetric cloud/self-shadow와 구분한다. 미세 지형 입력도 실제 DEM mesh와 구분한다.
- 새 original 기체 `src/aircraft_v3.js`는 31 mesh, 21,046 vertices, 37,888 triangles의 smooth fuselage/curved airfoil/white nacelle/recessed fan/PBR model이다. 기존 V1/V2 기체는 보존한다. 기체 크기는 visual proxy이며 실제 항공기 실측 크기·속도·운항 시간의 simulation으로 해석하지 않는다. scene의 Sun/Moon direct light는 기체 중심의 radial/horizon에 의한 지구 차폐 근사로 조절하고 Hemisphere를 radial up에 맞춘다.
- 생산 scene은 frame당 nominal 1회 렌더 후 depth-derived motion을 7탭 HDR 적분한다. tap별 depth rejection이나 완전한 다중 시간 렌더 적분은 아니므로 기체/배경 경계는 실제 MP4로 확인한다. 최종 출력은 SDR H.264이며 내부 HDR target과 구분한다.

실제 근접 항공기 사진·도시 landmark 패널과 동등한 미세 재질/영상미를 달성했다는 판단은 아직 하지 않는다. inline target의 지리·문구·수치·확인되지 않은 landmark를 자산으로 복제하지 않는다.

## 시각 검수 순서

1. 0.5초 및 HERO 정지 프레임에서 실제 공간·대기·구름·도시권·광원 검수.
2. V2와 같은 시간의 화면을 나란히 놓고 새 재질/lighting/depth가 즉시 구분되는지 확인.
3. 짧은 실제 MP4에서 camera acceleration, cloud parallax, route depth occlusion, aircraft bank 검수.
4. 검수 구도를 고친 후 20초를 순차 렌더. 완성 후 전체 decode/playback, 0.5/2/6/10/15/19초 비교, 모바일 가독성과 sound sync 검사.

기술 수치/직접 프레임 관찰/실제 재생과 assistant가 제공받지 못한 직접 청감을 구분한다. 과도한 bloom·particles·반복 pulse를 품질 향상 근거로 사용하지 않는다.
