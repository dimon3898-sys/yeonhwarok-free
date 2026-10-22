# Remaining limits and exact restart gate

1. **CAPABILITY_EXTENSION_REQUIRED:** 보호된 `web/map_infographic_v1/renderer.mjs`에 opt-in flat similarity의 공통 forward/inverse 투영, 실제 지형 역샘플링 및 source-envelope admission이 필요합니다. 기존 `updateCamera(bounds)`의 기본 동작·최소 확대 제한·소스 검증은 유지해야 합니다. 최소 변경 지점과 회귀 조건을 `CAPABILITY_GAP_AND_PATCH_MAP.md`에 명시했습니다. 이번 작업에서는 해당 보호 파일을 변경하지 않았습니다.
2. **DATA_DETAIL_BLOCKED:** 실제 핵심 대상의 검증된 Point, 상세 Polygon/MultiPolygon, 순서 있는 실제 경계 LineString, 충분한 native 해상도의 지도 소스가 필요합니다. 문맥 채색 영역 및 국경 스타일 그룹의 명시적 선택도 필요합니다. 실제 필요 필드 6개와 형식은 `REFERENCE_DIRECTOR_INPUT.json`의 `gate.missingBindings`에 있습니다. 원본 영상의 윤곽을 따라 그리거나 새 지형을 만들어 채우지 않았습니다.
3. **정확도 구분:** 기존 Spain/Morocco 형상은 1:50m, 위치는 1:10m 지역 지도 자료입니다. 측량 정밀도로 확대할 수 없습니다. `85 m`는 화면 관찰 문자열로 사용할 수 있지만 독립된 지리 측정 사실로 확정할 근거는 없습니다. Spain 전체 MultiPolygon에서 섬을 임의 삭제하지 않았으므로 원본 화면에 맞출 component 선택도 명시해야 합니다.
4. **실제 픽셀 미검증:** 레퍼런스 12개 시점의 새 native static draw, 가상 fixture 2개를 포함한 native-map draw, 3개 Studio MP4와 546프레임 비교는 실행하지 않았습니다. 컴포넌트 PNG나 수학 테스트는 그 대체물이 아닙니다. NVIDIA/실물 Android 및 품질 PASS를 주장하지 않습니다.
5. **첨부 누락:** 경량 ZIP의 README에 적힌 22개 전 프레임 시트·이벤트 확대 이미지·패키지 SHA256SUMS는 실제 ZIP에 없습니다. 제공된 원본을 직접 순차 디코딩하여 전체 로그를 검증했으므로 원본 프레임 부재로 추정하지 않았습니다.

## 재개 지점

새 브랜치 `development/reference-director-v1-20261022`의 원격 저장본에서 이어갑니다. 위 1의 한정된 보호 코드 확장에 대한 별도 승인과 2의 검증된 상세 자료가 확보되기 전에는 native 제작 게이트를 열지 않습니다. 기존 503개 성공 검사를 이유 없이 다시 실행하거나 완료된 기능을 재개발하지 않습니다.

이 조건이 충족되면 공통 투영 훅의 새 opt-in 경로를 최소 수정하고, 새 profile 전용 glyph/Event 소비자를 연결한 뒤 12개 static draw → A/B/C 무료 Studio 창 → 실제 픽셀 검사 순서로 진행할 수 있습니다. 유료 GPU는 여전히 별도 승인 대상입니다.
