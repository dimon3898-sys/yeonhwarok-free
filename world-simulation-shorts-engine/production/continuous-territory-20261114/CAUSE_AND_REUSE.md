# 원인과 기존 기능 재사용

기준 원격 HEAD: 4f1ccf960bd3ca102f7de543c229299744673839. 별도 worktree에서 작업하며 이전 worktree의 미커밋 보고서·CHECKPOINT를 변경하지 않았다. 첨부 70391.mp4 및 64306.mp4는 기존 V3 증거와 SHA256이 일치한다.

기존 실제 캡처 증거 108–132프레임을 읽었다. 25프레임 동안 영토 도형 해시는 2개뿐이고 카메라 중심은 1개다. 두 원본 도형의 alpha만 변한다. 새 화면 캡처나 이전 PASS 테스트를 재실행한 결과가 아니다. OLD_V3_CAUSE_LEDGER.json에 값과 프레임을 보존했다.

area_core_v3.mjs stateAt은 이전/다음 states를 1-alpha와 alpha로 교차 표시한다. frameArea는 geometry를 그대로 복사한다. territory_effects_v2.mjs는 전체 added/removed 차집합의 alpha만 바꾼다. history_direction_v3.mjs는 108프레임 카메라 이동 뒤 25프레임 영역 표시, 47프레임 정지를 고정 배치한다. 따라서 경계 진행이나 추적은 입력 지시만으로 얻을 수 없었다.

| 기능 | 분류 | 조치 |
|---|---|---|
| 원자료 Polygon/MultiPolygon 및 시기 | REUSE | 데이터·좌표·순서 보존 |
| territory_delta_v2 차집합/중심/범위 | REUSE | 원본 상태 비교 그대로 사용 |
| Area V3 투영·삼각분할·라벨 보호 | EXTEND | 공통 presentation runtime에 연속 도형 선택 연결 |
| 매 프레임 중간 도형 | MISSING | 원본 두 상태 합집합 안에서 공유 경계 기반 거리 파동 |
| 이동 경계 강조 | EXTEND | 고정 차집합 대신 현재 경계 안쪽의 얇은 영역을 기존 Area pass로 출력 |
| 카메라·시간 감독 | EXTEND | 새 opt-in profile, 변화량/분리 지역과 원본 시간 순서에 따른 배분·동시 이동 |
| 지도 소스 및 Mercator | REUSE | 실제 공급 해상도·범위 검사 유지 |
| 최종 MP4 | REUSE | 기존 capturePresentation 및 FFmpeg 경로, SwiftShader CPU |

중간 도형은 역사적 정복 경로가 아니다. 연결된 새 영역은 기존 경계에서 진행하며 떨어진 영역은 그 영역 내부에서 독립적으로 나타난다. 임의의 연결 영토를 만들지 않는다. 화면에 시각적 보간을 표시한다.

기존 기술 PASS는 유효하며 무효화하지 않았다. 새로운 연속성·카메라·경계 강조 요구사항과 신규 profile의 실제 출력만 검증한다.
