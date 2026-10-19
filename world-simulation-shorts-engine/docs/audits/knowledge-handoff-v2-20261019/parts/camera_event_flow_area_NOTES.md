# Camera / Event / Flow / Area: 현재 Studio 연결 감사

기준은 `c0f2868e9cab8a269c2bd8552dc09920e5e53863`의 소스와 현재 `V4_ARCHIVAL_80S` 실행 경로다. 역사적 FINAL 승인과 현재 80초 영상에서 실제 선택되는 기능을 분리했다. 이 감사에서는 렌더링이나 Permanent Gate를 새로 실행하지 않았다. 현재 80초 MP4를 확인하지 못했으므로 모든 `OUTPUT_VERIFIED`는 `NOT_VERIFIED`다.

## 가장 중요한 연결 사실

현재 Studio 80초 경로는 보존된 V4 역사 자료 → V3 production adapter → V5 native bridge + ASTRA → 명시적으로 공급된 Polygon/Front → 사건 및 원본 지도 날짜 → 원래 Marker/Label 순서다.

- `universal-production-v3/production_adapter.mjs:33–58`은 `compileLongAreaRequest`, 기존 `createAreaNativeBridge`, ASTRA, `createProductionNativeCamera`, `createProductionAreaPass`를 선택한다.
- 같은 파일 `85–129`에서 실제 프레임을 합성한다. `119`에는 `nationalUnitPositions:0`, `122`에는 `fictional65422SceneUsed:false`가 명시돼 있다. 5초 가상 시나리오의 군대 아이콘/국기 위치를 역사 영상에 자동 상속하지 않는 구조다.
- `universal-auto-video-v2/long_area_timeline.mjs:27–57`은 `WAR`, Polygon, Front Line, 최소 두 개의 time step을 요구한다. `83–90`에서 현재 활성 기능은 `AREA_REVEAL`, `FRONT_LINE`, `STATE_TRANSITION`, `AREA_HOLD`로 제한된다.
- `universal-production-v3/production_area_pass.mjs:13–14`은 합성할 때 `impacts`와 `propagations`를 비운다. Area Core에 기능이 존재해도 현재 WAR 80초 경로에서 자동 실행되는 것은 아니다.

## 5초 고급 연출이 그대로 반영되지 않는 구조적 이유

### 전선과 영토

5초 가상 스칼라 분류기는 역사 Polygon의 소유권을 결정할 수 없다. 현재 V3는 `production_visual_profile.mjs:24–44`에서 출처와 연결된 `areaStyles`만 허용하고, 상대 세력 영역을 나머지 공간으로 추정하는 complement를 금지한다. `production_area_pass.mjs:24–27`은 `originalV2ScalarClassifierApplicable:false`를 기록한다.

장편 전환은 공급된 상태 A/B의 가중치 crossfade다(`long_area_timeline.mjs:71–87`). 이는 경계 정점이 실제 이동하는 topology morph와 다르다. 과거 지도 날짜가 드문 구간에서는 `production_visual_profile.mjs:87–105`의 `HOLD_SUPPLIED_SNAPSHOT`이 실제로 정지 상태를 유지한다. 사건 날짜가 바뀌더라도 없는 전선 좌표를 생성하지 않는다. 전선이 천천히 전진하는 5초 시연과 다르게 보일 수 있는 코드 근거다.

현재 흰색/금빛 전선 자체는 연결돼 있다. `production_visual_profile.mjs:7–44`와 `production_area_pass.mjs:4–27`의 명시적 스타일을 사용한다. 이전 자동 Teal/Cyan 대비 선택기가 현재 production front에서 호출되는 것은 아니다. 동작하는 발광이 있어도 5초 가상 시나리오의 이동 경계 알고리즘과 같은 것으로 간주하면 안 된다.

### 카메라

V5 Minimum Context와 Natural Turnaround는 보존돼 있고 `area_native_bridge_v3.mjs:88–114`에서 매 프레임 평가된다. 그러나 장편 사건 카메라는 별도 보수적 프로필이다.

`production_camera.mjs:30–41`의 `factor=Math.max(1,...)`는 승인된 부모 framing보다 더 가까운 확대를 허용하지 않는다. `44–85`는 이전/다음 전체 Geometry와 기존 Graphic을 모두 안전 영역에 유지하며, `[1,.65,.4,.2,.1]` 강도로 후보를 검사한다. 후보가 안전하지 않으면 현재 view를 유지한다. 이는 5초 레퍼런스의 확대/회전 경로를 그대로 가져오는 기능이 아니다.

`camera_detail_approach_adapter_v1.mjs`는 출처가 결합된 Visual Detail 인증을 받아 V5 도착 뒤 접근/정착/Lock을 수행하는 FINAL 소스다. 현재 장편 adapter가 이를 호출하는 것은 아니며 `detailSmootherstep` easing만 재사용한다. “Detail Lock”이라는 진단 문구만으로 별도 Suez Detail Adapter 전체가 실행된 것으로 판정하면 안 된다.

### Flow와 Event

`flow_core_v2.mjs`는 Route Reveal / Directional Flow / Moving Object / Endpoint Pulse / Hold와 heading을 실제 구현한다. Area Core가 `sampleFlowRoute`를 import하는 것은 `AREA_MOVE` 지원을 위한 재사용이다. 현재 WAR 80초 경로에서 Flow 계획이나 이동 객체를 생성하는 증거는 없다.

Event arc-length는 Area Front에 실제 재사용된다(`area_core_v3.mjs:182–185,347–351`). Metric/Glyph와 배치도 실제 재사용된다(`area_annotation_v3.mjs:2–5,29–35,41–87`). 다만 현재 날짜/제목은 `visibleFraction=1`로 그린다. 원래 Suez의 `LINE → HOLD → METRIC_REVEAL → INFORMATION_HOLD` 전체 리듬이 현재 장편에 자동 실행되는 것은 아니다.

### Wave / Propagation

Area Core 11개 operation은 존재한다. 승인된 Tsunami Wave FINAL은 여기에 `wave_visual_v3.mjs` 및 `wave_gpu_adapter_v3.mjs`를 별도로 연결했다. 전자는 원래 coast를 참고한 2–3개 open front, 발생 pulse, 부분 해안 접촉, 에너지 fade를 구현한다. 완전한 원형 ring을 승인 영상에서 그리지 않는다. 이는 물리 시뮬레이션이 아니다.

현재 Studio WAR preset은 이를 선택하지 않는다. fixed RTX package에는 `wave_visual_v3.mjs` core가 있으나 독립 `wave_gpu_adapter_v3.mjs`는 포함되지 않는다. 파일 존재, 이미지 포함, 실제 호출을 분리해야 한다.

## 현재 Studio 프롬프트 호출 범위

이 영역의 개별 엔진 기능은 기존 Studio의 임의 자연어 명령으로 직접 호출할 수 없다. `VERIFIED_FRONT_V4_80S` / `V4_ARCHIVAL_80S` 같은 검증된 preset을 선택하면 그 안에 고정된 연결만 실행된다. `Flow를 추가`, `쓰나미를 실행`, `Suez Metric을 표시`, `5초 카메라와 동일하게`, `전선 topology morph` 같은 문구를 지원 명령으로 안내하면 안 된다.

별도 Scene의 `areas`, `front_lines`, `time_steps`, 소스 및 카메라 계약을 검증하는 경로와 현재 Studio가 받아들이는 Scene envelope도 구분해야 한다. standalone FINAL fixture를 현재 Studio 입력으로 바로 붙여넣을 수 있다고 주장하지 않는다. 정확한 Studio parser 계약은 전용 prompt audit 결과를 우선한다.

## 역사적 FINAL 계보

다음 Git commit object와 부모 manifest 참조를 확인했다. 새 FINAL 승격/재검증을 수행하지 않았다.

| 기능 | FINAL commit | Manifest SHA-256 / 상태 |
|---|---|---|
| Camera V5 | `29b8ee294360812b55ef577b62411de58159003b` | 원본 manifest blob identity는 현재 base와 동일; body SHA는 이 파트에서 미확인 |
| Event V1 | `f79f3d55d945ef0e53b03ac2ed666f48f28b5881` | `52d4f5f5e034079a58a6227deff71d36bf4b775af0df600daf689eec4f7701a1` |
| Flow V2 | `fbc3be89d94040271c7f54a051162913ad134bac` | `43f83ff77895ef8f4749b328a49a3acd0bb6b13667198347bb606e187efbe1e3` |
| Area V3 | `7da699c07cddf618f5e8a93ca735db51d31bbb39` | `672aa536a65c5f36d5e3f2b96a70c548897872093b9d602772fe75d96d14bc45` |

Event/Flow/Area manifest의 역사적 Gate 7/7 및 BIT_EXACT receipt가 존재한다. 현재 80초 출력의 품질이나 실제 NVIDIA 결과를 증명하는 자료로 확대 해석하지 않는다.

## 남은 제품 연결 작업 — 이번 감사에서 구현하지 않음

1. 검증된 기능을 선택할 수 있는 범용 Scene 및 Studio parser 확장.
2. 역사 자료를 왜곡하지 않는 실제 경계 이동/색상 전환 계약. 공급 상태 crossfade와 연속 전선을 구분해야 한다.
3. 출처가 확인된 국기/군대 위치 데이터와 marker adapter 연결. 5초 가상 위치를 역사적 부대 위치로 복사하면 안 된다.
4. 장편에서 허용할 별도 카메라 연출 프로필과 Safe Area/Detail admission.
5. Flow/Wave standalone 실행 adapter를 이미지와 Studio에 연결하는 작업. 관련 소스가 저장돼 있다는 이유만으로 이미 호출 가능하다고 표시하면 안 된다.

## 부록 파일

- `camera_event_flow_area.json`: 40개 기능, 현재 Studio 기준 8축 판정.
- `final_lineage.json`: FINAL Git object / manifest identity와 역사적 receipt 요약.

Root 추가 확인: Camera FINAL Manifest 본문을 정확한 Git blob으로 확보했고 SHA256 `ad90c34ab2186c8119bb9dba6d946b337935cdb49ea85c965f81f652dfa8bf1f`를 확인했다. 앞서 본문 미확인이라는 중간 메모는 이 확인으로 대체한다. 새로운 Permanent Gate는 실행하지 않았다.
