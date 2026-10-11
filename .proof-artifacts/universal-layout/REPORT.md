# GENERAL_LAYOUT_PASS — Universal Layout

최대 3회 수정 안에서 Suez/Egypt, Japan/Tokyo, Switzerland/Alps의 동일 Software WebGL2 Renderer PNG를 검증했다. 실제 RTX4080S, Container, 영상, 다음 Stage는 실행하지 않았다.

## 원인과 변경 범위

기존 Layout은 제목을 Primary 위쪽 바다에만 두고, 국가명을 검증 catalog anchor에 고정했다. 변경 파일은 `web/map_infographic_v1/graphic_layout.mjs` 하나다.

- Marker → Location Label → Country Label → Event Title → Auxiliary 순서.
- 위치명은 Marker의 좌/우/상/하를 평가하며 Marker의 실제 위치와 디자인은 그대로다.
- 국가명은 기존 anchor가 유효하면 유지하고, 아니면 실제 Polygon/MultiPolygon 내부를 측정된 glyph bounds로 검색한다. Hole과 국가 밖 배치를 허용하지 않는다.
- 국가명 줄바꿈은 기존 글꼴·글자 크기 범위·최대 2줄 안에서 자동 계산한다. 최종 일본 Label은 한 줄이다.
- 제목은 화면 전체 안전영역 후보를 점수화한다. Primary, Marker, 다른 Label, 주요 경계를 피하며 바다 존재 여부는 조건이 아니다.
- 국가명 경계 여백은 실제 Core/Contrast Edge 반폭 + 1px AA를 기준으로 한다. Glyph Outline + 2px 여백은 유지하며, 희미한 Glow 꼬리 전체를 배제한다고 주장하지 않는다.

Renderer/Shader/Terrain/DEM/Lighting/Theme/국가 색감/Boundary/Glow/Marker/Font/GIS/Camera/Projection 소스·입력은 그대로다. 지역별 분기·수동 좌표 튜닝은 없다.

## 수정 기록

1. 우선순위와 범용 후보 검색 구현. Swiss 통과; Japan의 국가명 내부 여백 부족 확인. Suez 보조 문구에 불필요하게 추가된 경계 조건으로 이동 발생.
2. 기존 최대 2줄 안에서 자동 reflow·정밀한 내부 탐색 추가, 보조 문구 기존 규칙 복원. Suez 원본 PNG와 byte 동일. Japan 내부 여백 조건은 여전히 실패.
3. 국가명에 실제 Core/Edge+AA 여백 적용. 세 지역 통과. 이 이후 수정·렌더 없음.

## 최종 검증

최종 집중 검증 PASS 80 / FAIL 0 / ERROR 0 / SKIP 1.

- Pure Layout 14건: Hole, Concave, MultiPolygon, 자동 reflow, 우선순위, 결정론, 명시적 공간 부족 실패.
- 실제 동일 Renderer 통합 46건: 세 PNG, WebGL2/SwiftShader, `gl_error=0`, 한글 glyph, 충돌/안전영역/Primary·경계 회피, 원본 보존.
- 독립 파일·픽셀·GEOS 검증 20건: 1080×1920 lossless PNG, Marker anchor 실제 픽셀, 실제 국가 Polygon containment, 실제 경계 Core/Edge+AA 회피, 보호 소스·입력 동일성.
- SKIP 1: 실제 RTX4080S 검증 (사용자 금지).

세 PNG를 직접 시각 검수했으며 충돌·잘림은 없다. Suez PNG는 승인된 최종 원본과 byte 단위 동일하다.

Japan/Switzerland는 기존 `DEM_DATA_MISSING` 상태다. 기존 NE1 baked hillshade Terrain을 사용하며 새 DEM은 받지 않았다. Alps Marker는 기존 Sion/Valais Point의 대표 검증 좌표로서 Alps 중심점이라고 주장하지 않는다.

## 원본 PNG

- SUEZ_LAYOUT_GENERALIZED.png — `fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673`
- JAPAN_TOKYO_GENERALIZED.png — `57b8a03b5320b60e57a7acd964a35453f3da037703ecc911bcb00dcd4cf17f6e`
- SWITZERLAND_ALPS_GENERALIZED.png — `b7bbf8f325e0529c6de599e52ad333232a248890f1d235633d303f34ae494b19`

Universal Layout Source SHA-256: `ea7ac0d83455f4548c9bff5631d6c8557e3491809fe43fa912bbbd3bf1ddf7c6`.

최종 승인: **USER PNG REVIEW REQUIRED**. 다음 단계로 자동 진행하지 않는다.
