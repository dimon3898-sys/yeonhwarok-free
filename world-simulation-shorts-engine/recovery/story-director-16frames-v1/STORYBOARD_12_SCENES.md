# 80초 원본 12장면 스토리와 자료 한계

원본 80초·30fps·2,400프레임의 사건 장 순서는 유지한다. 이 문서는 렌더 전 소스 감사이며, 화면 품질 합격 증거가 아니다.

- 정규화된 원본 submission: `world-simulation-shorts-engine/recovery/universal-integration-completion-v2/fixtures/VALIDATED_80S_SUBMISSION.json` / SHA-256 `66bec5bb7dbe61106d3fc192d40623603782c5e4ca727781cfdb3496cf218ff3`.
- 원본 부모 Scene: `world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery/VIDEO_PLAN_80S.json` / SHA-256 `2632f9106962bb126bf333422bce2be5094d4af7b25c5701acdf4455a2829dc6`.
- 사건 장은 `productionV3.eventChapters`의 12개 `[startFrame,endFrame)`이다. `scenes`의 렌더 작업 분할 구간과 혼동하지 않는다.
- 첫 60프레임(0~2초)은 사건 Geometry 없음. 이후 도식 held-core 1,490프레임과 공식 지도에 근거한 근사·부분 전선 850프레임이다.
- 양측 전체 점령 폴리곤·관측된 매일의 전선·날짜별 국가 부대 좌표는 없다. 없는 상대편 영토를 보완하거나 국기/부대/상륙 경로를 생성하지 않는다.
- 기존 음향 설정은 무음이다. SFX scheduler 존재와 실제 오디오 출력은 별개다.

| 장 | 원본 시간(초) / 프레임 | 사건·날짜 | 실제 화면에 허용되는 자료 | 검증 범위·화면에서 남는 제약 |
|---|---|---|---|---|
| chapter-01 | 0.000–6.667 / [0,200) | 전쟁 발발 · 1950.06.25 | 0.000–2.000s NO_EVENT_GEOMETRY START; 2.000–4.000s SCHEMATIC_HELD_CORE START; 4.000–6.667s SCHEMATIC_HELD_CORE START | 도식 자료의 원래 날짜 유지·실제 사건 당일 점령선 주장 금지 |
| chapter-02 | 6.667–13.333 / [200,400) | 북한군 남하 · 1950년 6~8월 | 6.667–13.333s SCHEMATIC_HELD_CORE START | 도식 자료의 원래 날짜 유지·실제 사건 당일 점령선 주장 금지 |
| chapter-03 | 13.333–20.000 / [400,600) | 낙동강 방어선 · 1950년 8~9월 | 13.333–16.333s SCHEMATIC_HELD_CORE BUSAN; 16.333–20.000s SCHEMATIC_HELD_CORE BUSAN | 도식 자료의 원래 날짜 유지·실제 사건 당일 점령선 주장 금지 |
| chapter-04 | 20.000–26.667 / [600,800) | 인천상륙작전 · 1950.09.15 | 20.000–26.667s SCHEMATIC_HELD_CORE BUSAN | 도식 자료의 원래 날짜 유지·실제 사건 당일 점령선 주장 금지; 인천 상륙 부대·경로·지점 근거 없음 |
| chapter-05 | 26.667–33.333 / [800,1000) | 서울 수복 · 1950.09.28 | 26.667–33.333s SCHEMATIC_HELD_CORE BUSAN | 도식 자료의 원래 날짜 유지·실제 사건 당일 점령선 주장 금지 |
| chapter-06 | 33.333–40.000 / [1000,1200) | 국군·유엔군 북진 · 1950.09.29–1950.10.24 | 33.333–40.000s SCHEMATIC_HELD_CORE BUSAN | 도식 자료의 원래 날짜 유지·실제 사건 당일 점령선 주장 금지 |
| chapter-07 | 40.000–46.667 / [1200,1400) | 중국군 참전 · 1950.10.25 | 40.000–46.667s SCHEMATIC_HELD_CORE BUSAN | 도식 자료의 원래 날짜 유지·실제 사건 당일 점령선 주장 금지; 10/25 첫 전투와 10/19 월경·11월 공세 구분 |
| chapter-08 | 46.667–53.333 / [1400,1600) | 전선 남하 · 1950.11.24–1951.01.04 | 46.667–48.333s SCHEMATIC_HELD_CORE NORTH_ADVANCE; 48.333–50.000s SCHEMATIC_HELD_CORE NORTH_ADVANCE; 50.000–51.667s SCHEMATIC_HELD_CORE SEOUL_WITHDRAWAL; 51.667–53.333s ARCHIVAL_PARTIAL_FRONT cmh-front-1950-12-31 | 부분 전선만 표시·모든 점령 면 숨김 |
| chapter-09 | 53.333–60.000 / [1600,1800) | 국군·유엔군 재반격 · 1951년 상반기 | 53.333–55.533s ARCHIVAL_PARTIAL_FRONT cmh-front-1951-01-24; 55.533–57.767s ARCHIVAL_PARTIAL_FRONT cmh-front-1951-02-28; 57.767–60.000s ARCHIVAL_PARTIAL_FRONT cmh-front-1951-04-21 | 부분 전선만 표시·모든 점령 면 숨김 |
| chapter-10 | 60.000–66.667 / [1800,2000) | 38선 부근 교착 · 1951년 중반 이후 | 60.000–63.333s ARCHIVAL_PARTIAL_FRONT cmh-front-1951-05-19; 63.333–66.667s ARCHIVAL_PARTIAL_FRONT cmh-front-1951-06-24 | 부분 전선만 표시·모든 점령 면 숨김 |
| chapter-11 | 66.667–73.333 / [2000,2200) | 1951~1953 전선 변화 · 1951~1953 | 66.667–73.333s ARCHIVAL_PARTIAL_FRONT cmh-front-1951-11-12 | 부분 전선만 표시·모든 점령 면 숨김 |
| chapter-12 | 73.333–80.000 / [2200,2400) | 1953 정전협정 · 1953.07.27 | 73.333–76.333s ARCHIVAL_PARTIAL_FRONT cmh-front-1953-07-27; 76.333–80.000s ARCHIVAL_PARTIAL_FRONT cmh-front-1953-07-27 | 부분 전선만 표시·모든 점령 면 숨김 |

## 감독 의도와 원본 시간표 충돌

첨부 지시서의 10초 단위 8개 구간은 연출 의도다. 원본 12장의 사건 시점을 그 구간에 강제로 옮기지 않는다. 예를 들어 20초는 낙동강 방어가 아닌 인천상륙작전 장이며, 40초는 북진 장이 아닌 중국군 참전 장이다.

| 감독 구간 | 요청된 의도 | 원본 사건 장 | 판정 |
|---|---|---|---|
| 0–10s | 발발·남하 | 전쟁 발발, 북한군 남하 | PARTIAL_ALIGNMENT_PRESERVE_FROZEN_EVENTS |
| 10–20s | 서울 함락·남측 방어 | 북한군 남하, 낙동강 방어선 | CONFLICT_DO_NOT_RETIME_FROZEN_EVENTS |
| 20–30s | 낙동강 방어 | 인천상륙작전, 서울 수복 | CONFLICT_DO_NOT_RETIME_FROZEN_EVENTS |
| 30–40s | 인천상륙·서울 수복 | 서울 수복, 국군·유엔군 북진 | CONFLICT_DO_NOT_RETIME_FROZEN_EVENTS |
| 40–50s | 북진 | 중국군 참전, 전선 남하 | CONFLICT_DO_NOT_RETIME_FROZEN_EVENTS |
| 50–60s | 중국군 개입·역전 | 전선 남하, 국군·유엔군 재반격 | CONFLICT_DO_NOT_RETIME_FROZEN_EVENTS |
| 60–70s | 재반격·교착 | 38선 부근 교착, 1951~1953 전선 변화 | CONFLICT_DO_NOT_RETIME_FROZEN_EVENTS |
| 70–80s | 정전·최종 전선 | 1951~1953 전선 변화, 1953 정전협정 | CONFLICT_DO_NOT_RETIME_FROZEN_EVENTS |

## 기존 좌표의 카메라 사용

서울 `[126.978,37.5665]`, 부산 `[129.0756,35.1796]`, 평양 `[125.7625,39.0392]`은 원본 `legacyScenePlan.locations`의 지명 맥락이다. 이는 전투·부대·상륙 좌표가 아니다. 전선·held-core의 기존 bbox로 구도를 정할 수 있으나 실제 확대/이동은 별도 픽셀 트레이스로 확인해야 한다.

## 공식 부분 전선의 정확도

CMH PUB21-2의 8개 날짜를 기존 GeoJSON과 SHA로 검증했다. 원본 지도 투영법·datum·전체 위치 정확도는 미확인이다. EPSG:4326은 출력/참조 기준이며 지도 원본 CRS를 증명하지 않는다. 모델 잔차 약 2.26~4.13km는 지도 총 오차가 아니다. 1951-05-19의 잉크 점선 간격을 연결하지 않으며, 1953-07-27은 정밀 측량 MDL이라고 주장하지 않는다.

## 16개 실제 샘플의 소스 상태

| 초 | 전역 프레임 | 원본 사건 | 소스 상태 |
|---|---|---|---|
| 0 | 0 | 전쟁 발발 | NO_EVENT_GEOMETRY: START (1950-06-25) |
| 5 | 150 | 전쟁 발발 | SCHEMATIC_HELD_CORE: START (1950-06-25) |
| 10 | 300 | 북한군 남하 | SCHEMATIC_HELD_CORE: START (1950-06-25) |
| 15 | 450 | 낙동강 방어선 | SCHEMATIC_HELD_CORE: BUSAN (1950-09-01) |
| 20 | 600 | 인천상륙작전 | SCHEMATIC_HELD_CORE: BUSAN (1950-09-01) |
| 25 | 750 | 인천상륙작전 | SCHEMATIC_HELD_CORE: BUSAN (1950-09-01) |
| 30 | 900 | 서울 수복 | SCHEMATIC_HELD_CORE: BUSAN (1950-09-01) |
| 35 | 1050 | 국군·유엔군 북진 | SCHEMATIC_HELD_CORE: BUSAN (1950-09-01) |
| 40 | 1200 | 중국군 참전 | SCHEMATIC_HELD_CORE: BUSAN (1950-09-01) |
| 45 | 1350 | 중국군 참전 | SCHEMATIC_HELD_CORE: BUSAN (1950-09-01) |
| 50 | 1500 | 전선 남하 | SCHEMATIC_HELD_CORE: SEOUL_WITHDRAWAL (1951-01-04) |
| 55 | 1650 | 국군·유엔군 재반격 | ARCHIVAL_PARTIAL_FRONT: cmh-front-1951-01-24 (1951-01-24) |
| 60 | 1800 | 38선 부근 교착 | ARCHIVAL_PARTIAL_FRONT: cmh-front-1951-05-19 (1951-05-19) |
| 65 | 1950 | 38선 부근 교착 | ARCHIVAL_PARTIAL_FRONT: cmh-front-1951-06-24 (1951-06-24) |
| 70 | 2100 | 1951~1953 전선 변화 | ARCHIVAL_PARTIAL_FRONT: cmh-front-1951-11-12 (1951-11-12) |
| 75 | 2250 | 1953 정전협정 | ARCHIVAL_PARTIAL_FRONT: cmh-front-1953-07-27 (1953-07-27) |

16장은 반드시 새 PNG 렌더와 provenance로 증명한다. 본 소스 문서만으로 FRAME_RENDER_PASS 또는 VISUAL_QUALITY_PASS를 부여하지 않는다.
