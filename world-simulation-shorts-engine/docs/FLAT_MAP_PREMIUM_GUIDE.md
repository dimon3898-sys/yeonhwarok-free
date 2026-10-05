# PREMIUM FLAT MAP 사용 안내

`FLAT_MAP_PREMIUM`은 기존 World Simulation Shorts Engine에 추가한 선택형 렌더 모드입니다. 기본 Planner와 기존 프로젝트는 계속 MASTER V3 Earth를 사용합니다. 사용자가 15초 샘플을 승인하기 전에는 기본 프리셋을 교체하거나 75초 영상을 다시 렌더하지 않습니다.

이 안내는 구현된 계약을 설명합니다. 샘플의 최종 영상 품질, 제작시간, 부분 재렌더 실측 결과는 별도의 품질·벤치마크 보고서에서 확인해야 합니다.

## 모드 선택과 계획 검수

실제 Scene 필드 이름은 `render_mode`입니다. `renderer_mode`라는 별도 필드는 사용하지 않습니다.

| Scene 설정 | 실제 백엔드 |
|---|---|
| `render_mode` 생략 또는 `MASTER_V3_EARTH` | 보존된 MASTER V3 렌더러 |
| `render_mode: FLAT_MAP_PREMIUM` | 독립적인 투영 지도 렌더러 |
| Earth Scene에 명시적 지도 전환 지정 | 보존된 V3를 사용하는 별도 대기 전환 어댑터 |
| `scene_type: CINEMATIC_CLIP` | 기존 외부 영상/FFmpeg 파이프라인 |

새 `FLAT_MAP` Scene Type 또는 기존 `COUNTRY_FOCUS`, `ROUTE`, `NETWORK` 등의 Scene에 Flat 모드를 명시할 수 있습니다. 기존 필수 Scene 필드, 사실·가정·시뮬레이션 구분, GIS 출처, 승인 해시, entry/exit state는 유지해야 합니다.

10~20초 검증 계획은 `metadata.flat_map_preview: true`와 실제 Flat Scene이 함께 있어야 합니다. 이 예외는 기존 Earth 계획의 20초 최소 길이를 변경하지 않습니다.

검수 순서는 기존과 같습니다.

1. Story/Scene JSON 작성 및 실제 GIS 출처 검증.
2. Schema, 인과관계, Retention, Event Diversity 검사.
3. 선택된 렌더러의 실제 카메라·경로·이동체·텍스트 배치에 대한 숫자 기반 사전 검수.
4. Scene Plan 확인과 해당 해시 승인.
5. Scene별 렌더, 오디오/자막 합성, 전체 프레임 QC와 재생 검수.

숫자 기반 사전 검수는 픽셀 렌더나 미적 품질 통과를 의미하지 않습니다. 줌·pan·카메라 회전만으로는 의미 있는 사건을 채우지 않습니다. 경로 변경은 실제 새 경로의 head, 차단은 실제 barrier, 네트워크 확장은 실제 추가 연결의 표시가 필요합니다.

## 15초 검증 계획 만들기

프로젝트 루트에서 새 파일 이름으로 실행합니다.

```bash
.venv/bin/python tools/build_flat_validation_sample.py \
  --output validation/my_flat_sample_v001.json \
  --quality HIGH \
  --project-root projects-flat-validation
```

Builder는 계획 JSON/읽기용 문서를 생성하고, Gate를 통과한 경우에만 새로운 ProjectStore 프로젝트를 등록합니다. **승인하거나 렌더를 시작하지 않습니다.** 기존 이름의 JSON/문서가 있으면 덮어쓰지 않고 오류를 반환합니다.

이 검증 저장소를 열 때는 기존 서버와 다른 포트를 사용하고, 서버의 `--projects`가 같은 저장소를 가리키도록 합니다. 이미 렌더 중인 서버를 다시 시작하지 않습니다.

등록 후 기존 모바일 UI에서 Scene Plan을 확인할 수 있습니다. API를 사용하는 개발자는 아래 기존 계약을 그대로 사용합니다.

| 요청 | 역할 |
|---|---|
| `GET /api/projects/{project_id}/versions/{version}/plan` | 저장된 계획 확인 |
| `POST /api/projects/{project_id}/approve` | `version`, `plan_hash`로 명시적 승인 |
| `POST /api/projects/{project_id}/render` | 승인된 `version` 렌더 시작 |
| `GET /api/projects/{project_id}/status?version={version}` | 실제 진행 상태 확인 |
| `POST /api/projects/{project_id}/revise` | `version`, 자연어 `request`로 수정 Diff 생성 |
| `POST /api/projects/{project_id}/revisions/{revision_id}/approve` | 수정 검수 후 새로운 승인 버전 생성 |
| `GET /download/{project_id}/{version}/final/final.mp4` | 해당 버전의 실제 최종 파일 다운로드 |

수정 승인과 렌더 시작도 별개입니다. 일반 자연어 기획 생성 API의 기본 표현을 Flat으로 강제 변경하지 않았습니다.

## Flat Scene의 추가 설정

다음은 기존 Scene JSON에 추가하는 필드의 예시이며, 독립적으로 실행하는 완전한 계획은 아닙니다.

```json
{
  "render_mode": "FLAT_MAP_PREMIUM",
  "camera_preset": "FLAT_COUNTRY_FOCUS",
  "flat_map": {
    "projection": "LOCAL_MERCATOR",
    "span_degrees": 24,
    "camera_start": {"lon": 130, "lat": 35, "span_degrees": 24, "tilt": 0.07},
    "camera_end": {"lon": 134, "lat": 35, "span_degrees": 20, "tilt": 0.07},
    "country_highlights": [
      {"country": "KOR", "source_id": "natural_earth_countries", "start_time": 0.1, "end_time": 3, "color": "#b5a77a", "opacity": 0.20}
    ],
    "focus": [
      {"target_id": "seoul", "coordinates": {"lon": 126.997785, "lat": 37.568295, "source_id": "natural_earth_places", "location_id": "seoul"}, "start_time": 0, "end_time": 3, "radius_degrees": 5, "strength": 0.18}
    ]
  }
}
```

카메라 중심은 구도를 위한 위치입니다. 도시·항구·공항·이벤트·경로점은 검증된 GIS 레코드에서 좌표를 가져오고 `source_id`를 유지합니다. 위 Seoul 좌표도 저장된 Natural Earth 레코드입니다.

기본 투영은 `LOCAL_MERCATOR`이며 `LOCAL_EQUIRECTANGULAR`도 선택할 수 있습니다. 극지방은 현재 지원하지 않습니다. Flat 카메라의 span/rotation/tilt은 `flat_map.camera_start/end`에 지정하며 기존 `camera_start/end`와 state는 유지합니다.

| Flat Camera Preset | 용도 |
|---|---|
| `FLAT_ESTABLISH` | 지리를 읽기 쉽게 제시 |
| `FLAT_COUNTRY_FOCUS` | 국가로 접근 |
| `FLAT_REGION_FOCUS` | 지역으로 접근 |
| `FLAT_ROUTE_FOLLOW` | 주 경로의 진행 추적 |
| `FLAT_ENTITY_FOLLOW` | 이동체 추적 |
| `FLAT_MULTI_COUNTRY` | 여러 지역과 연결 제시 |
| `FLAT_PULLBACK` | 지도 범위 확대 |
| `FLAT_NEXT_EVENT_PREVIEW` | 다음 사건 전에 해당 방향으로 시선 유도 |

## AUTO FOCUS와 다음 사건 예고

`flat_map.focus`는 시간에 따라 검증된 target을 전환하고 주변을 약간 어둡게 하여 핵심 지역을 강조합니다. 국가에는 반투명 tint를 적용해 지형을 유지합니다.

`FLAT_NEXT_EVENT_PREVIEW`는 다음 추가 설정을 사용합니다.

```json
{
  "next_event": {
    "event_id": "E008",
    "coordinates": {"lon": 121.568333, "lat": 25.035833, "source_id": "natural_earth_places", "location_id": "taipei"},
    "event_time": 0.95,
    "lead_time": 0.65,
    "strength": 0.35
  }
}
```

이 객체는 `flat_map` 내부에 둡니다. 같은 Scene의 E008 시각과 좌표가 정확히 일치해야 하며 예고 구간은 Scene 시작 이전으로 벗어날 수 없습니다. 카메라 예고 자체는 새 사건으로 세지 않습니다.

## 이동체·경로·Map VFX

Flat은 `aircraft`, `cargo_ship`/`ship`, `vehicle`, `location_marker`, `city`, `port`, `airport`를 지원합니다. `ship` 별칭은 Flat 전용입니다. 이동체는 투영 지도 안에 배치한 3D 모델이며 표시상의 크기·높이는 지도 표현을 위한 것입니다. 경로 방향으로 회전하고 이동에 맞춰 core/head/trail을 표시합니다.

`entity_actions`는 기존 이동체를 ID로 지정합니다. Flat Scene당 표시할 수 있는 최대 이동체 수는 8개입니다.

| 지시 | 필요 조건 |
|---|---|
| `move` | 검증된 일반 경로 |
| `stop` | 기존 경로 위의 정지 위치·시각 |
| `reroute`, `split`, `diverge` | Scene에 미리 정의한 검증된 `route_id` |
| `merge`, `converge`, `follow`, `intercept` | Scene 안의 기존 `target_entity_id` |

이 기능은 시각적인 이동 지시를 처리합니다. 자동 항로 탐색·물리적 충돌 계산·과학적 요격 예측은 지원하지 않습니다. split을 사용할 때는 이동체와 분기 경로를 계획에 미리 포함해야 합니다. 순환 추적, 정의되지 않은 route/entity, 지원하지 않는 지시는 실패로 처리합니다.

Map VFX는 `PULSE`, `RADAR`, `WARNING`, `IMPACT`, `SHOCKWAVE`, `AREA_HIGHLIGHT`, `ROUTE_BLOCK`, `ROUTE_REROUTE`를 제공합니다. 장식용 pulse 하나는 Retention 사건으로 세지 않습니다. 효과음은 기존 라이선스 기록이 있는 procedural sound에 정확한 event timestamp로 연결합니다.

## Flat과 Earth 전환

Flat→Earth 전환은 앞 Scene의 `transition_out`과 다음 Scene의 `transition_in`을 모두 `FLAT_TO_EARTH`로 지정합니다. 반대 방향은 모두 `EARTH_TO_FLAT`로 지정합니다. `map_transition.duration`은 공유하는 대기 효과의 통과 시간을 정합니다.

지리 중심을 맞춘 pullback/tilt과 짧은 공유 대기 veil을 사용한 뒤 실제 MASTER V3 구체 렌더러로 연결합니다. 평면의 정점을 구체로 변형하는 projection morph는 구현하지 않았습니다. 두 영상의 단순 crossfade나 총 영상 시간을 줄이는 겹침 편집을 사용하지 않습니다.

불투명한 veil로 사건이 가려진 프레임은 실제 사건 표시로 세지 않습니다. 서로 다른 투영 공간의 카메라 위치를 같은 수치 단위로 비교하지 않고 실제 경계 프레임을 재생 검수합니다. 15초 샘플은 Flat→Earth를 보여주며 반대 방향의 실제 영상 품질까지 검증하지는 않습니다.

## 캐시·부분 수정·보존

국경·해안선은 Natural Earth vector를 사용하고 지형은 출처와 지리 등록 정보를 기록한 공유 raster를 사용합니다. 지역 terrain은 디스크 asset cache에서 재사용하며 등록된 파일·SHA·정확한 geographic bounds를 검증합니다. terrain URL은 등록된 `/static/flat_assets/`의 직접 파일 또는 `cache/` 하위 파일로 제한합니다. 렌더러의 projected geometry/texture Map은 브라우저 프로세스 단위의 캐시입니다.

Scene cache는 Scene JSON·자산 SHA·백엔드 구현 버전·품질·render context로 판정합니다. Flat은 독립된 키를 사용하며 일반 Earth의 기존 키를 변경하지 않습니다. 변경되지 않은 Clip도 실제 보존 소스와 코드를 비교해 기존 키를 유지하고 Clip 구현이 바뀌면 무효화합니다.

자연어로 “3~6초 카메라를 조금 빠르게” 등의 수정을 요청하면 Diff를 먼저 제시하고 승인된 새 버전에서 대상 Scene만 재렌더합니다. 바뀌지 않은 Scene은 검증된 cache/checkpoint에서 재사용하고 최종 조립·QC는 새 버전에 수행합니다. 실제 검증 프로젝트 `project_c047b389d1f8/v002`에서 S002 속도만 1.2배로 바꿔 1개 Scene을 렌더했고, Earth를 포함한 나머지 4개 MP4와 audit SHA는 동일했습니다. 이 실행은 총 290.544초였으며 기존 렌더 시간을 포함한 최초 제작 시간과 구분합니다.

의미 있는 `network_expand`는 실제 새 target route와 연결해야 합니다. 해당 경로는 `progress_start=0`이며 출발 시각이 사건 시각과 한 프레임 이내로 일치해야 합니다. 이미 진행 중인 경로 위에 나중에 사건 이름을 붙인 계획은 검수에서 거절합니다. 계속 보이는 전체 연결망은 `final_reveal` 등 역할에 맞는 사건을 사용합니다.

실패한 출력과 원본 버전을 보존합니다. 완료된 Scene은 재렌더하지 않으며 미완료 Scene을 다시 시도할 때는 새 attempt 파일을 만듭니다. Scene 단위로 재개하는 구조이며 미완료 MP4의 중간 프레임부터 덧붙이는 방식은 지원하지 않습니다.

TTS/BGM/효과음/ducking은 기존 파이프라인을 유지합니다. Flat 자막을 켠 경우 실제 렌더 후 label/entity/focus box를 확인해 안전한 위치의 별도 ASS를 만들고 원래 자막 파일을 보존합니다. 자막 OFF와 일반 Earth만 사용하는 영상은 기존대로 처리합니다.

## 주요 중단 이유

| 오류 | 수정 방법 |
|---|---|
| `CAMERA_RENDER_MODE_MISMATCH` | Flat 모드와 Flat camera preset을 함께 사용 |
| `UNVERIFIED_FLAT_GIS_COORDINATE` / `UNKNOWN_GIS_COUNTRY` | 실제 GIS catalog·국가 형태 사용 |
| `NEXT_EVENT_CAMERA_BINDING_MISMATCH` | 실제 event ID·시각·좌표와 일치시키기 |
| `NEXT_EVENT_CAMERA_NO_LEAD_WINDOW` | Scene 안에 사건 전 예고 구간 확보 |
| `FLAT_NETWORK_EVENT_TIMING_MISMATCH` / `FLAT_NETWORK_ROUTE_ALREADY_ACTIVE` | 새 경로의 실제 시작·0-progress를 네트워크 사건과 일치시키기 |
| `UNREGISTERED_OR_MISLOCATED_FLAT_TERRAIN` | 등록된 terrain과 정확한 bounds 사용 |
| `FLAT_ACTION_ROUTE_REQUIRED` / `FLAT_ACTION_TARGET_REQUIRED` | 미리 정의한 경로·이동체 지정 |
| `MEANINGFUL_EVENT_NOT_RENDERED` | 실제로 보이는 사건을 수정하고 카메라 이동만으로 채우지 않기 |
| `APPROVAL_REQUIRED` / `PLAN_CHANGED_AFTER_APPROVAL` | 최종 Scene Plan의 정확한 해시 확인·승인 |

아직 구현하지 않은 war·territory/time/geography morph·weather 등의 기능을 기존 효과로 대체하지 않습니다. 새 plugin은 기존 Earth/Flat 백엔드와 Scene 계약을 유지하면서 추가합니다.
