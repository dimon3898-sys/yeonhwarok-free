# Gate 1 · SUEZ STATIC PROOF

최종 승인 상태: **USER_PENDING**. Codex는 Visual PASS 또는 Gate 2 진행을 선언하지 않습니다.

최종 원본: [1080×1920 lossless PNG](iteration-05/proof.png).
실제 저해상도 Preview: [540×960 PNG](iteration-05/preview.png).
반복 비교: [5회 contact sheet](visual-iterations.png). Contact sheet는 기존 실제 PNG의 썸네일 모음이며 별도 지도 Renderer가 아닙니다.

## 실제 구현

독립 `MAP_INFOGRAPHIC_RENDERER_V1_GATE1`, WebGL2, Three.js r170 자원/geometry 관리, 명시적 GLSL 3.0.
GPU region ID / 별도 MSAA coverage → 실제 terrain RGB linear sampling → region material → relief/light/sea → 전용 primary glow → screen-space boundary → marker/text GPU quads → PNG.
Canvas는 font coverage atlas를 준비할 때만 사용합니다. 최종 지도·텍스트·프레임 합성에는 Canvas 2D 또는 DOM을 사용하지 않습니다.
부모 Earth renderer, v024 colorization wrapper, 런타임 shader 문자열 치환을 사용하지 않습니다.

## 5회 시각 반복

| 반복 | 가장 큰 차이 | 수정 | 실제 PNG 결과 |
|---|---|---|---|
| 1 | Secondary가 밝고, Primary가 작음. 하단 raster seam | 최초 독립 GPU material/frame graph | Terrain variation·국가 형태 확인. seam/우선순위 문제 남음 |
| 2 | 밝기·context 범위·seam | Secondary luminance 감소, Egypt 중심 framing, 기존 native tile 안으로 viewport 제한 | seam 제거, Primary 확대. 지형/글자 대비 보완 필요 |
| 3 | Primary의 평탄한 밝기, 경계 계단, 제목이 배경에 분리 | 실제 terrain luminance contrast, ribbon analytic AA, title contrast plate | 실제 detail이 더 보이나 노란 highlight 과함 |
| 4 | Highlight, 회색빛 바다, dark boundary edge | highlight shoulder, 실제 raster의 해양 variation을 유지하는 sea material, edge/glow 조정 | clipping 감소, sea/land 대비 향상. GPU pixel evidence 32/32 통과 |
| 5 | 제목과 사건 지역 간 공간적 분리 | Title plate를 Egypt 북쪽 sea context로 이동; 동일 factory 실제 Preview 생성 | 최종 PNG 제출. 최종 35개 검증 통과. 사용자 시각 승인 대기 |

모든 비교는 사용자 inline VISUAL TARGET과 실제 WebGL2 PNG를 보고 수행했습니다. 목표 이미지 원본 파일을 로컬로 복제하거나 AI로 다시 만들지 않았습니다.
최대 5회 제한으로 추가 visual revision을 실행하지 않습니다.

## 11개 시각 비교 항목 — 최종 관찰

| 항목 | 관찰 및 한계 |
|---|---|
| Terrain detail | 실제 NE1 raster의 variation 유지. 가짜 detail/sharpening 없음 |
| Terrain relief | BAKED HILLSHADE + 기존 2K RELIEF PROXY. 목표의 사진 같은 깊이/사선 입체감보다 지도형 표현이 강함 |
| Primary salience | Egypt 전체 형태에 강한 warm material과 밝은 boundary 적용 |
| Secondary separation | 주변 5개 검증 국가에 낮은 luminance의 통일된 cool material 적용 |
| Neutral context | 다른 지역은 원래 terrain variation 중심으로 유지 |
| Boundary clarity | GIS 실제 rings, GPU pixel ribbon, core/contrast edge |
| Glow quality | Primary 전용 target·blur. 전체 Bloom 없음. 절제된 halo |
| Sea/Land | sea는 국가 role chroma의 영향 없음. 정밀 coastline/운하 bank 검증은 별도 데이터 필요 |
| Marker | 검증된 canal waypoint steady state. 위치 precision의 한계 유지 |
| Text | 실제 CANAL CLOSED / SUEZ CANAL + 기존 가정 시나리오 고지. GPU draw, safe area 유지 |
| 전체 인상 | 기존 단순 alpha polygon 경로에서 벗어난 colored terrain 구조. 목표와 같은 품질이라는 최종 판단은 사용자가 수행 |

## Actual pixel evidence

- Primary core width, 50% coverage: median **6.7px**, 9개 단면.
- Secondary: median **3.0px**, 19개 단면.
- Glow 10% response half-range: 중심에서 약 **12.4px**. Core 바깥 약 9px까지.
- Linear luminance median: Primary **0.620**, Secondary **0.345**.
- Terrain luminance correlation to neutral GPU ablation: **0.998982**.
- Terrain gradient ratio to neutral ablation: **1.335**. 해상도 증가나 신규 DEM detail을 뜻하지 않습니다.
- GPU ID / 실제 polygon 내부 표본: **4169개, mismatch 0**.
- Sea 내부 role colorization ON/OFF 최대 channel delta: **0**.
- Proof polygon에는 Hole이 없습니다. 실제 registry UAE MultiPolygon/Hole의 triangulation 면적 unit 검증을 수행했으며 다른 지역 Proof를 생성하지 않았습니다.
- Source precision: Natural Earth 1:50,000,000. 위 수치는 독립적 정밀 해안선 측량 합격을 뜻하지 않습니다.
- Text/Marker safe-area 및 실제 glyph/marker pixels 검증 완료.
- 동일 factory 540px Preview와 downsampled 1080px Final의 평균 절대 pixel 차이: **1.629/255**.

## 데이터·라이선스

기존 1440×1680 native NE1 Suez tile: Public Domain, 21600×10800 원본의 cached crop. TIFF 원본 전체는 현재 checkout에 없으며 cached tile SHA256를 기존 manifest와 대조했습니다.
기존 source/texture를 교체하거나 외부 데이터를 다운로드하지 않았습니다.
Native terrain은 shaded-relief/land-cover 지도이며 satellite photograph 또는 새 DEM이라고 주장하지 않습니다.
GIS: Natural Earth Public Domain, 기본 de facto 경계 정책 그대로.
Marker anchor: SEAROUTE 1.6.0 Apache-2.0, Great Bitter Lake 부근 대표 network waypoint.
Font: Noto Sans CJK KR Bold OFL-1.1. Three.js와 원래 topology 예제 asset: MIT.
Global fallback: Solar System Scope/NASA CC-BY-4.0. 최종 framing은 NE1 tile 안에 있으므로 fallback의 visible contribution은 없습니다.
라이선스/credit: `iteration-05/asset-credits.json`, `iteration-05/licenses/`.

## 재현성 및 실행 증거

- Runtime: **ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)**.
- Chromium: **151.0.7922.173**. Software GL이며 NVIDIA가 아닙니다.
- 동일 context·plan 반복 PNG: byte-identical.
- Scene hash: `a702f337ec70f19de3c834cf3b57d71c7393a10c75a5474b42405511b1fcf72a`.
- Data hash: `a06f35a8dcc7ee3b9c062a5b9ea85585dc0b60067e501358c44eb552930afbd6`.
- Shader/source hash: `17d843163cf6648d8f6cc3199240c2962f69398c39f673354e5e7e802ad17d38`.
- Theme hash: `b0e9d9aaba4ccdc33e5c4503564120451557f76f0d18a75fb36a01004ce5c089`.
- Font hash: `da1f44844b4d65fc6eef82a0979404a38c78a4a5639b8e9ecf3590dc4cb880b0`.
- PNG SHA256: `3e4830cb7db4b6c585b6caec1d77330c257c54918432af5fad9678d6535f0d17`.

## 검증 결과

Gate 1 관련 실제 WebGL2 / source / topology / pixel / factory 검증:
**PASS 35 / FAIL 0 / ERROR 0 / SKIP 0**.
기존 1,286개 전체 regression을 실행하거나 재개하지 않았습니다. 기존 tracked 파일 변경은 0이며 새 Gate1 파일만 추가했습니다.
초기 검증 helper의 NumPy 2 uint8 산술 오류와 흰색 glyph만 가정한 threshold를 수정했습니다. 실제 font의 ivory 색상을 반영한 pixel 검증이며 Renderer 결과를 바꾸어 해당 검사를 우회하지 않았습니다.

## 성능·NOT RUN

Software 경로 render+PNG readback 약 **598.6ms**.
GL command submission 수치를 실제 GPU frame time으로 취급하지 않습니다.
Texture/render-target 메모리 산술 추정 **272.7MiB**; driver, glyph, geometry, readback 비용 제외. 실제 VRAM 실측 아님.
NVIDIA/RTX4080S 색감, blend, 실측 GPU memory/frame time: **NOT RUN**.
정밀 DEM / 정밀 수로 bank / 독립 고해상도 coastline 정확도: **NOT VERIFIED**.

## 종료 상태

5회 실제 정지 프레임 반복 완료. 최종 PNG와 증거 제출.
**사용자 APPROVE / REJECT 대기. Gate 2 진행 없음.**
영상·animation·TTS·SFX·BGM·Production·gcube·Container build/publish 실행 없음.

## Source-coastline 추가 진단

원본 native RGB와 GPU coverage를 직접 대조했습니다. RGB blue-color cue는 진단 proxy이며 검증된 수계 geometry가 아닙니다. 렌더용 mask를 새로 만들거나 geometry를 수정하지 않았습니다.
4px 해안 band의 source-color disagreement: 8443px. Band 바깥 country 외부 non-water-color 후보: 156px (0.0075% of frame).
국가 내부 blue-water 후보: 15707px. 내륙 호수/수계의 별도 정확한 water mask는 이 Gate에서 구현되지 않았고 해당 색조는 남은 한계입니다. 정밀 수계 containment PASS로 보고하지 않습니다.

## Visual convergence 평가

기술 검증은 PASS지만, 목표의 사진 같은 깊이·Relief와 내륙수계 표현을 충분히 충족했다고 입증하지 못했습니다. **VISUAL TARGET 수렴: 미충족(FAIL)** 로 남깁니다. 최종 Gate 승인 권한은 사용자에게 있습니다. 최대 5회 제한에 따라 실제 PNG와 증거를 제출하고 멈춥니다.
