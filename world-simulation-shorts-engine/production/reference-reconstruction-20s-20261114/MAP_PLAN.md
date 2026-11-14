# 몽골제국 20초 지도 설계

NASA BMNG 기존 지형과 native renderer만 사용한다. 원자료 EPSG:4326, 화면 GEOGRAPHIC_MERCATOR_V1. BMNG 최고 원본 21600×10800, 1각분이며 현재 승인된 Eurasia levels는 6600×6800(0.025°) 및 6000×7500(1/60°)다. 정확한 범위·SHA는 CAMERA_PLAN_600F.json의 terrainSourceLevels에 있다.

SOURCE_RELIEF_V1은 실제 지형 원본의 명암을 처리하며 고도·건물·파도를 생성하지 않는다. REFERENCE_FOCUS_V2, NATURAL_EARTH_V1 자연지리 맥락, nativeBoundaries=false를 유지한다. 현대 국경을 역사 경계로 노출하지 않는다. 영역 기본 RGBA=[1,.75,.12,.28]; 추가·축소 색과 이동 경계는 기존 FRONTIER_LIGHT_V1을 사용한다. 채색 아래 지형 질감을 보존한다.

모든 600 pose에서 실제 source coverage 1px gutter, screen/native density≤1, 승인된 closestBounds를 검사한다. 최대 scale=24.94963263616363px/Mercator degree. 원본 레퍼런스의 건물 수준 근접 디테일과 13배/약49배 확대는 이 자료로 재현 불가다. 이번에는 전체 변화영역을 유지하는 광역/지역 구도를 사용한다. 소스 한계를 감추기 위한 업스케일·가짜 지형은 없다.
