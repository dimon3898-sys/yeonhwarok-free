# 서울에서 도쿄로 이동한 민간 항공 연결의 다음 목적지가 타이베이로 바뀐다면?

총 길이: 12.0초 · 품질: HIGH

훅: 다음 목적지가 바뀐다면?

| 장면 | 시간 | 장소 | 역할/주요 사건 | 카메라 | 조명 |
|---|---|---|---|---|---|
| S001 | 0–2.5s | Seoul | hook: country_reveal, route_start, entity_departure, destination_preview, hook_reveal | FLAT_COUNTRY_FOCUS | GEOGRAPHY_READABILITY |
| S002 | 2.5–5s | Tokyo | progression: milestone_reveal, country_reveal | FLAT_ROUTE_FOLLOW | GEOGRAPHY_READABILITY |
| S003 | 5–7.5s | Tokyo | variable: arrival, new_variable, route_blocked | FLAT_NEXT_EVENT_PREVIEW | GEOGRAPHY_READABILITY |
| S004 | 7.5–10s | Taipei | response: route_reroute, network_expand | FLAT_MULTI_COUNTRY | GEOGRAPHY_READABILITY |
| S005 | 10–12s | Taipei | payoff: final_reveal | FINAL_REVEAL | CINEMATIC_NIGHT |

## 사실과 가정
- **FACT**: Seoul의 위치는 공개 GIS 원본 좌표로 확인됩니다.
- **FACT**: Tokyo의 위치는 공개 GIS 원본 좌표로 확인됩니다.
- **FACT**: Taipei의 위치는 공개 GIS 원본 좌표로 확인됩니다.
- **FACT**: 공개 좌표로 계산한 경로의 구면 길이는 약 1,156 km입니다. 실제 항공편/항해 시간은 계산하지 않습니다.
- **FACT**: 공개 좌표로 계산한 경로의 구면 길이는 약 2,103 km입니다. 실제 항공편/항해 시간은 계산하지 않습니다.
- **ASSUMPTION**: 입력한 도시 연결과 화면의 이동 시간은 시각화를 위한 가정입니다. 실제 항공편 일정이나 성능 예측이 아닙니다.
- **SIMULATION**: 검증된 위치를 연결하는 구면 경로의 공간적 차이와 연결망을 시각화합니다.
- **FACT**: 공개 좌표로 계산한 Seoul -> Taipei 구면 길이는 약 1,485 km입니다. 비행 시간이나 실제 운항 결과가 아닙니다.
- **FACT**: 표시한 KOR/JPN/TWN 윤곽은 보존된 Natural Earth 공개 GIS 원본입니다. 지리 도형 참조이며 정치적 지위에 대한 주장이 아닙니다.
- **ASSUMPTION**: 도쿄 도착 뒤 타이베이 민간 후속 연결이 잠시 보류되고, 별도 항공기 두 대가 타이베이 연결을 재개한다고 가정합니다. 실제 공항 폐쇄·전쟁·날씨·운항 예측이 아닙니다.
- **SIMULATION**: 보류·재배정 가정에 따라 첫 항공기는 도쿄에 정지하고 별도 Tokyo -> Taipei 및 Seoul -> Taipei 연결을 시각화합니다.
- **FACT**: Shanghai의 위치는 보존된 공개 GIS 좌표에서 확인됩니다.
- **SIMULATION**: 기존 연결망에서 Shanghai로 가상 연결 한 개가 추가됩니다. 실제 운항, 수요 또는 미래 결과가 아닙니다.

## 검수
{
  "passed": true,
  "errors": [],
  "warnings": [
    {
      "code": "NARRATION_TARGET_ID_NOT_IN_GIS_CATALOG",
      "scene_id": "S001",
      "event_id": "E001",
      "target_id": "KOR"
    },
    {
      "code": "NARRATION_TARGET_ID_NOT_IN_GIS_CATALOG",
      "scene_id": "S002",
      "event_id": "E006",
      "target_id": "JPN"
    }
  ],
  "retention": {
    "passed": true,
    "errors": [],
    "warnings": [],
    "metrics": {
      "meaningful_event_count": 12,
      "average_event_interval": 1.0091,
      "max_event_gap": 2.2667,
      "first_3s_events": 4,
      "event_types": 11,
      "max_same_kind_run": 1,
      "peak_count": 1,
      "camera_events_counted": false
    },
    "events": [
      {
        "id": "E001",
        "kind": "country_reveal",
        "time": 0.1,
        "duration": 1.041667,
        "target_id": "KOR",
        "coordinates": {
          "lon": 126.997785,
          "lat": 37.568295,
          "source_id": "natural_earth_places",
          "location_id": "seoul"
        },
        "claim_id": "FC01",
        "role": "cause",
        "caused_by": null,
        "meaningful": true,
        "text": "KOREA",
        "description": "KOREA",
        "value": null,
        "unit": "",
        "absolute_time": 0.1,
        "scene_id": "S001"
      },
      {
        "id": "E002",
        "kind": "route_start",
        "time": 0.666667,
        "duration": 1.041667,
        "target_id": "R_SEOUL_TOKYO",
        "coordinates": {
          "lon": 126.997785,
          "lat": 37.568295,
          "source_id": "natural_earth_places",
          "location_id": "seoul"
        },
        "claim_id": "M01",
        "role": "cause",
        "caused_by": "E001",
        "meaningful": true,
        "text": "",
        "description": "SEOUL / TOKYO",
        "value": null,
        "unit": "",
        "absolute_time": 0.666667,
        "scene_id": "S001"
      },
      {
        "id": "E003",
        "kind": "entity_departure",
        "time": 1.166667,
        "duration": 1.041667,
        "target_id": "aircraft_main",
        "coordinates": {
          "lon": 126.997785,
          "lat": 37.568295,
          "source_id": "natural_earth_places",
          "location_id": "seoul"
        },
        "claim_id": "M01",
        "role": "progression",
        "caused_by": "E002",
        "meaningful": true,
        "text": "",
        "description": "FIRST CONNECTION",
        "value": null,
        "unit": "",
        "absolute_time": 1.166667,
        "scene_id": "S001"
      },
      {
        "id": "E004",
        "kind": "destination_preview",
        "time": 2.0,
        "duration": 0.5,
        "target_id": "tokyo",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "claim_id": "F02",
        "role": "hint",
        "caused_by": "E003",
        "meaningful": true,
        "text": "TOKYO",
        "description": "TOKYO",
        "value": null,
        "unit": "",
        "absolute_time": 2.0,
        "scene_id": "S001"
      },
      {
        "id": "E005",
        "kind": "milestone_reveal",
        "time": 0.666667,
        "duration": 1.041667,
        "target_id": "R_SEOUL_TOKYO",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "claim_id": "M01",
        "role": "progression",
        "caused_by": "E004",
        "meaningful": true,
        "text": "599 km",
        "description": "수정된 Scene 시각과 실제 렌더 경로 진행률에서 다시 계산한 남은 구면 거리; 압축된 이동 시간은 가정",
        "value": 599,
        "unit": "km",
        "absolute_time": 3.166667,
        "scene_id": "S002"
      },
      {
        "id": "E006",
        "kind": "country_reveal",
        "time": 1.9,
        "duration": 0.6,
        "target_id": "JPN",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "claim_id": "FC01",
        "role": "progression",
        "caused_by": "E005",
        "meaningful": true,
        "text": "JAPAN",
        "description": "JAPAN",
        "value": null,
        "unit": "",
        "absolute_time": 4.4,
        "scene_id": "S002"
      },
      {
        "id": "E007",
        "kind": "arrival",
        "time": 0.1,
        "duration": 1.041667,
        "target_id": "tokyo",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "claim_id": "M01",
        "role": "consequence",
        "caused_by": "E006",
        "meaningful": true,
        "text": "ARRIVED",
        "description": "TOKYO",
        "value": null,
        "unit": "",
        "absolute_time": 5.1,
        "scene_id": "S003"
      },
      {
        "id": "E008",
        "kind": "new_variable",
        "time": 0.8,
        "duration": 1.041667,
        "target_id": "taipei",
        "coordinates": {
          "lon": 121.568333,
          "lat": 25.035833,
          "source_id": "natural_earth_places",
          "location_id": "taipei"
        },
        "claim_id": "A02",
        "role": "variable",
        "caused_by": "E007",
        "meaningful": true,
        "text": "ASSUMPTION",
        "description": "ASSUMPTION · NEXT STOP: TAIPEI",
        "value": null,
        "unit": "",
        "absolute_time": 5.8,
        "scene_id": "S003"
      },
      {
        "id": "E009",
        "kind": "route_blocked",
        "time": 1.6,
        "duration": 0.9,
        "target_id": "R_TOKYO_TAIPEI",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "claim_id": "A02",
        "role": "response",
        "caused_by": "E008",
        "meaningful": true,
        "text": "ASSUMED HOLD",
        "description": "ASSUMPTION · CONNECTION ON HOLD",
        "value": null,
        "unit": "",
        "absolute_time": 6.6,
        "scene_id": "S003"
      },
      {
        "id": "E010",
        "kind": "route_reroute",
        "time": 0.666667,
        "duration": 1.041667,
        "target_id": "R_SEOUL_TAIPEI",
        "coordinates": {
          "lon": 126.997785,
          "lat": 37.568295,
          "source_id": "natural_earth_places",
          "location_id": "seoul"
        },
        "claim_id": "M02",
        "role": "response",
        "caused_by": "E009",
        "meaningful": true,
        "text": "REROUTE",
        "description": "DIRECT LINK: SEOUL / TAIPEI",
        "value": null,
        "unit": "",
        "absolute_time": 8.166667,
        "scene_id": "S004"
      },
      {
        "id": "E011",
        "kind": "network_expand",
        "time": 1.433333,
        "duration": 1.041667,
        "target_id": "R_TOKYO_TAIPEI",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "claim_id": "M02",
        "role": "peak",
        "caused_by": "E010",
        "meaningful": true,
        "text": "",
        "description": "A SECOND CONNECTION JOINS",
        "value": null,
        "unit": "",
        "absolute_time": 8.933333,
        "scene_id": "S004"
      },
      {
        "id": "E012",
        "kind": "final_reveal",
        "time": 1.2,
        "duration": 0.8,
        "target_id": "P_FINAL_SHANGHAI",
        "coordinates": {
          "lon": 121.434559,
          "lat": 31.218398,
          "source_id": "natural_earth_places",
          "location_id": "shanghai"
        },
        "claim_id": "MP_CONTEXT",
        "role": "payoff",
        "caused_by": "E011",
        "meaningful": true,
        "text": "SHANGHAI",
        "description": "THREE CITIES · ONE NETWORK",
        "value": null,
        "unit": "",
        "absolute_time": 11.2,
        "scene_id": "S005"
      }
    ]
  },
  "semantic_visibility": {
    "schema_version": 1,
    "created_at_utc": "2026-10-05T21:41:07.301Z",
    "passed": true,
    "renderer_sha256": "c0f6c890e67ab5be7aea56739f384db01f1df962330564947dc3a1e378c172f9",
    "source_hashes": {
      "flat_semantics": "cd023936304a4579f1fe52849c66b47c5e94d69958c714e437b371dce511eedd",
      "map_transition": "044320a5b4f1757d0ea82f64d38a1f6880c9b9eabc518a653441cefb671df750",
      "adapter": "c0f6c890e67ab5be7aea56739f384db01f1df962330564947dc3a1e378c172f9",
      "legacy_renderer": "b378269674833f9a79cbbbb2d9c24b004d5ca398063ca897ec1a5359eed0d6d3",
      "aircraft": "fe23bb1b297f0fb16bbe492fcfc5245ab9461c9991195bbd6fe7a616ab12404b",
      "OpenSans": "cf5f5184c1441a1660aa52526328e9d5c2793e77b6d8d3a3ad654bdb07ab8424",
      "Noto": "91a6b21a427d1a5982e19e8875bfd6af620d0a372cd84967a0c225b90f342f6c",
      "certifier": "fd179e3510a417f863ddf30bb74395b975114fb6ecede8fcff61bdcc23c95414",
      "production_visual_adapter": "841eab94e44ed043cefd4c756315bc40564d49670ea18b4df8ef029371eacc51"
    },
    "fps": 30,
    "resolution": [
      2160,
      3840
    ],
    "scoped_scene_ids": null,
    "opening_hook_eligible": true,
    "events": [
      {
        "event_id": "E001",
        "scene_id": "S001",
        "kind": "country_reveal",
        "target_id": "KOR",
        "coordinates": {
          "lon": 126.997785,
          "lat": 37.568295,
          "source_id": "natural_earth_places",
          "location_id": "seoul"
        },
        "scheduled_local_time": 0.1,
        "eligible_frames": 30,
        "eligible_primitives": [
          "country_highlight"
        ],
        "first_eligible_local_time": 0.16666666666666666,
        "projection_at_scheduled_time": {
          "x": 0.4999569657969183,
          "y": 0.49999668506875444,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "country_highlight",
        "visible_seconds": 1,
        "onset_latency_seconds": 0.06666666666666665,
        "allowed_onset_delay_seconds": 0.18333333333333332,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E002",
        "scene_id": "S001",
        "kind": "route_start",
        "target_id": "R_SEOUL_TOKYO",
        "coordinates": {
          "lon": 126.997785,
          "lat": 37.568295,
          "source_id": "natural_earth_places",
          "location_id": "seoul"
        },
        "scheduled_local_time": 0.666667,
        "eligible_frames": 31,
        "eligible_primitives": [
          "route_head"
        ],
        "first_eligible_local_time": 0.7,
        "projection_at_scheduled_time": {
          "x": 0.47439411827831546,
          "y": 0.49802757501452527,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "route_head",
        "visible_seconds": 1.0333333333333334,
        "onset_latency_seconds": 0.033332999999999946,
        "allowed_onset_delay_seconds": 0.03333333333333333,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E003",
        "scene_id": "S001",
        "kind": "entity_departure",
        "target_id": "aircraft_main",
        "coordinates": {
          "lon": 126.997785,
          "lat": 37.568295,
          "source_id": "natural_earth_places",
          "location_id": "seoul"
        },
        "scheduled_local_time": 1.166667,
        "eligible_frames": 30,
        "eligible_primitives": [
          "3D_entity"
        ],
        "first_eligible_local_time": 1.2333333333333334,
        "projection_at_scheduled_time": {
          "x": 0.4032993833615323,
          "y": 0.49255113670985207,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "3D_entity",
        "visible_seconds": 1,
        "onset_latency_seconds": 0.0666663333333335,
        "allowed_onset_delay_seconds": 0.2733333333333333,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E004",
        "scene_id": "S001",
        "kind": "destination_preview",
        "target_id": "tokyo",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "scheduled_local_time": 2,
        "eligible_frames": 13,
        "eligible_primitives": [
          "world_label"
        ],
        "first_eligible_local_time": 2.033333333333333,
        "projection_at_scheduled_time": {
          "x": 0.7868552554523898,
          "y": 0.5331808983150824,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "world_label",
        "visible_seconds": 0.43333333333333335,
        "onset_latency_seconds": 0.033333333333333215,
        "allowed_onset_delay_seconds": 0.43333333333333335,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E005",
        "scene_id": "S002",
        "kind": "milestone_reveal",
        "target_id": "R_SEOUL_TOKYO",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "scheduled_local_time": 0.666667,
        "eligible_frames": 28,
        "eligible_primitives": [
          "world_label"
        ],
        "first_eligible_local_time": 0.7333333333333333,
        "projection_at_scheduled_time": {
          "x": 0.7161064830470532,
          "y": 0.5253566877815748,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "world_label",
        "visible_seconds": 0.9333333333333333,
        "onset_latency_seconds": 0.06666633333333327,
        "allowed_onset_delay_seconds": 0.43333333333333335,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E006",
        "scene_id": "S002",
        "kind": "country_reveal",
        "target_id": "JPN",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "scheduled_local_time": 1.9,
        "eligible_frames": 16,
        "eligible_primitives": [
          "country_highlight"
        ],
        "first_eligible_local_time": 1.9333333333333333,
        "projection_at_scheduled_time": {
          "x": 0.5016658062882201,
          "y": 0.5002351057884865,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "country_highlight",
        "visible_seconds": 0.5333333333333333,
        "onset_latency_seconds": 0.03333333333333344,
        "allowed_onset_delay_seconds": 0.18333333333333332,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E007",
        "scene_id": "S003",
        "kind": "arrival",
        "target_id": "tokyo",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "scheduled_local_time": 0.1,
        "eligible_frames": 31,
        "eligible_primitives": [
          "geographic_pulse"
        ],
        "first_eligible_local_time": 0.13333333333333333,
        "projection_at_scheduled_time": {
          "x": 0.5004602899197175,
          "y": 0.49983726495192593,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "geographic_pulse",
        "visible_seconds": 1.0333333333333334,
        "onset_latency_seconds": 0.033333333333333326,
        "allowed_onset_delay_seconds": 0.07500001333333334,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E008",
        "scene_id": "S003",
        "kind": "new_variable",
        "target_id": "taipei",
        "coordinates": {
          "lon": 121.568333,
          "lat": 25.035833,
          "source_id": "natural_earth_places",
          "location_id": "taipei"
        },
        "scheduled_local_time": 0.8,
        "eligible_frames": 28,
        "eligible_primitives": [
          "world_label"
        ],
        "first_eligible_local_time": 0.8666666666666667,
        "projection_at_scheduled_time": {
          "x": 0.15367648833364145,
          "y": 0.6347700664691075,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "world_label",
        "visible_seconds": 0.9333333333333333,
        "onset_latency_seconds": 0.06666666666666665,
        "allowed_onset_delay_seconds": 0.43333333333333335,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E009",
        "scene_id": "S003",
        "kind": "route_blocked",
        "target_id": "R_TOKYO_TAIPEI",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "scheduled_local_time": 1.6,
        "eligible_frames": 26,
        "eligible_primitives": [
          "route_barrier"
        ],
        "first_eligible_local_time": 1.6333333333333333,
        "projection_at_scheduled_time": {
          "x": 0.8000065109665683,
          "y": 0.39044149675985934,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "route_barrier",
        "visible_seconds": 0.8666666666666667,
        "onset_latency_seconds": 0.033333333333333215,
        "allowed_onset_delay_seconds": 0.03333333333333333,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E010",
        "scene_id": "S004",
        "kind": "route_reroute",
        "target_id": "R_SEOUL_TAIPEI",
        "coordinates": {
          "lon": 126.997785,
          "lat": 37.568295,
          "source_id": "natural_earth_places",
          "location_id": "seoul"
        },
        "scheduled_local_time": 0.666667,
        "eligible_frames": 31,
        "eligible_primitives": [
          "route_head"
        ],
        "first_eligible_local_time": 0.7,
        "projection_at_scheduled_time": {
          "x": 0.44323835035943526,
          "y": 0.3801163457156923,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "route_head",
        "visible_seconds": 1.0333333333333334,
        "onset_latency_seconds": 0.033332999999999946,
        "allowed_onset_delay_seconds": 0.03333333333333333,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E011",
        "scene_id": "S004",
        "kind": "network_expand",
        "target_id": "R_TOKYO_TAIPEI",
        "coordinates": {
          "lon": 139.749462,
          "lat": 35.686963,
          "source_id": "natural_earth_places",
          "location_id": "tokyo"
        },
        "scheduled_local_time": 1.433333,
        "eligible_frames": 29,
        "eligible_primitives": [
          "network"
        ],
        "first_eligible_local_time": 1.4666666666666666,
        "projection_at_scheduled_time": {
          "x": 0.7504009410643122,
          "y": 0.41079106476899085,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "network",
        "visible_seconds": 0.9666666666666667,
        "onset_latency_seconds": 0.033333666666666595,
        "allowed_onset_delay_seconds": 0.03333333333333333,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E012",
        "scene_id": "S005",
        "kind": "final_reveal",
        "target_id": "P_FINAL_SHANGHAI",
        "coordinates": {
          "lon": 121.434559,
          "lat": 31.218398,
          "source_id": "natural_earth_places",
          "location_id": "shanghai"
        },
        "scheduled_local_time": 1.2,
        "eligible_frames": 23,
        "eligible_primitives": [
          "network",
          "world_label"
        ],
        "first_eligible_local_time": 1.2333333333333334,
        "projection_at_scheduled_time": {
          "x": 0.373760687557916,
          "y": 0.4750377046422656,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "first_primitive": "network",
        "visible_seconds": 0.7666666666666667,
        "renderer_supported": true,
        "onset_latency_seconds": 0.03333333333333344,
        "allowed_onset_delay_seconds": 0.03333333333333333
      }
    ],
    "failures": [],
    "scope": "Shared selected-renderer pose, Earth occlusion or projected-map geography, atmospheric handoff visibility, event primitive eligibility and installed-font advance layout at every 30fps pose. No canvas/WebGL, shader brightness, texture visibility, aesthetic assessment or actual rendered-pixel/QC claim.",
    "font_layout_policy": "Installed OpenSans/Noto glyph advances; whole strings reserve3% for shaping uncertainty. Final browser font/rasterization QC remains required.",
    "semantic_input_sha256": "78f3d022e40476ad9d73168be25bebd1b7c267937d6ec00c2734086dd83d3659",
    "certified_plan_bytes_sha256": "c95fb20b8b4af69d3182dae924388ee2e2a2b881c1b8f458a7b45e405b00740e",
    "certificate_source_fingerprint": "d04f29ca26690e36ad54515c014ab361506433baa62b4b72076f0eb56cc5e44b",
    "certificate_cache_hit": false
  },
  "narration_alignment": {
    "passed": true,
    "errors": [],
    "warnings": [
      {
        "code": "NARRATION_TARGET_ID_NOT_IN_GIS_CATALOG",
        "scene_id": "S001",
        "event_id": "E001",
        "target_id": "KOR"
      },
      {
        "code": "NARRATION_TARGET_ID_NOT_IN_GIS_CATALOG",
        "scene_id": "S002",
        "event_id": "E006",
        "target_id": "JPN"
      }
    ],
    "scenes": [
      {
        "scene_id": "S001",
        "narration_present": true,
        "narration_event_ids": [
          "E001",
          "E002",
          "E003",
          "E004"
        ],
        "scope": "scene_context",
        "event_bindings": [
          {
            "event_id": "E001",
            "kind": "country_reveal",
            "scope": "scene_context",
            "local_time": 0.1,
            "absolute_time": 0.1,
            "target_id": "KOR",
            "target_kind": "unresolved_target",
            "target_scope": "unresolved",
            "target_source_ids": [],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 126.997785,
                "lat": 37.568295,
                "source_id": "natural_earth_places",
                "location_id": "seoul",
                "verified": true
              }
            ],
            "claim_id": "FC01",
            "claim_status": "FACT",
            "claim_source_ids": [
              "natural_earth_countries"
            ],
            "word_anchor": false
          },
          {
            "event_id": "E002",
            "kind": "route_start",
            "scope": "scene_context",
            "local_time": 0.666667,
            "absolute_time": 0.666667,
            "target_id": "R_SEOUL_TOKYO",
            "target_kind": "route",
            "target_scope": "declared_in_scene",
            "target_source_ids": [
              "natural_earth_places"
            ],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 126.997785,
                "lat": 37.568295,
                "source_id": "natural_earth_places",
                "location_id": "seoul",
                "verified": true
              },
              {
                "lon": 139.749462,
                "lat": 35.686963,
                "source_id": "natural_earth_places",
                "location_id": "tokyo",
                "verified": true
              }
            ],
            "claim_id": "M01",
            "claim_status": "SIMULATION",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          },
          {
            "event_id": "E003",
            "kind": "entity_departure",
            "scope": "scene_context",
            "local_time": 1.166667,
            "absolute_time": 1.166667,
            "target_id": "aircraft_main",
            "target_kind": "entity",
            "target_scope": "declared_in_scene",
            "target_source_ids": [
              "natural_earth_places"
            ],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 126.997785,
                "lat": 37.568295,
                "source_id": "natural_earth_places",
                "location_id": "seoul",
                "verified": true
              },
              {
                "lon": 139.749462,
                "lat": 35.686963,
                "source_id": "natural_earth_places",
                "location_id": "tokyo",
                "verified": true
              }
            ],
            "claim_id": "M01",
            "claim_status": "SIMULATION",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          },
          {
            "event_id": "E004",
            "kind": "destination_preview",
            "scope": "scene_context",
            "local_time": 2.0,
            "absolute_time": 2.0,
            "target_id": "tokyo",
            "target_kind": "verified_gis_location",
            "target_scope": "declared_in_scene",
            "target_source_ids": [
              "natural_earth_places"
            ],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 139.749462,
                "lat": 35.686963,
                "source_id": "natural_earth_places",
                "location_id": "tokyo",
                "verified": true
              }
            ],
            "claim_id": "F02",
            "claim_status": "FACT",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          }
        ],
        "claim_references": [
          {
            "claim_id": "F01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "F02",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "F03",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FD01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FD02",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "A01",
            "status": "ASSUMPTION",
            "source_ids": [],
            "assumption_ids": []
          },
          {
            "claim_id": "M01",
            "status": "SIMULATION",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": [
              "A01"
            ]
          },
          {
            "claim_id": "FD03",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FC01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_countries"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "A02",
            "status": "ASSUMPTION",
            "source_ids": [],
            "assumption_ids": []
          },
          {
            "claim_id": "M02",
            "status": "SIMULATION",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": [
              "A01",
              "A02"
            ]
          }
        ],
        "geographic_targets": [
          "seoul",
          "tokyo",
          "taipei"
        ],
        "word_alignment": false
      },
      {
        "scene_id": "S002",
        "narration_present": true,
        "narration_event_ids": [
          "E005",
          "E006"
        ],
        "scope": "scene_context",
        "event_bindings": [
          {
            "event_id": "E005",
            "kind": "milestone_reveal",
            "scope": "scene_context",
            "local_time": 0.666667,
            "absolute_time": 3.166667,
            "target_id": "R_SEOUL_TOKYO",
            "target_kind": "route",
            "target_scope": "declared_in_scene",
            "target_source_ids": [
              "natural_earth_places"
            ],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 126.997785,
                "lat": 37.568295,
                "source_id": "natural_earth_places",
                "location_id": "seoul",
                "verified": true
              },
              {
                "lon": 139.749462,
                "lat": 35.686963,
                "source_id": "natural_earth_places",
                "location_id": "tokyo",
                "verified": true
              }
            ],
            "claim_id": "M01",
            "claim_status": "SIMULATION",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          },
          {
            "event_id": "E006",
            "kind": "country_reveal",
            "scope": "scene_context",
            "local_time": 1.9,
            "absolute_time": 4.4,
            "target_id": "JPN",
            "target_kind": "unresolved_target",
            "target_scope": "unresolved",
            "target_source_ids": [],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 139.749462,
                "lat": 35.686963,
                "source_id": "natural_earth_places",
                "location_id": "tokyo",
                "verified": true
              }
            ],
            "claim_id": "FC01",
            "claim_status": "FACT",
            "claim_source_ids": [
              "natural_earth_countries"
            ],
            "word_anchor": false
          }
        ],
        "claim_references": [
          {
            "claim_id": "F01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "F02",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "F03",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FD01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FD02",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "A01",
            "status": "ASSUMPTION",
            "source_ids": [],
            "assumption_ids": []
          },
          {
            "claim_id": "M01",
            "status": "SIMULATION",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": [
              "A01"
            ]
          },
          {
            "claim_id": "FD03",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FC01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_countries"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "A02",
            "status": "ASSUMPTION",
            "source_ids": [],
            "assumption_ids": []
          },
          {
            "claim_id": "M02",
            "status": "SIMULATION",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": [
              "A01",
              "A02"
            ]
          }
        ],
        "geographic_targets": [
          "seoul",
          "tokyo",
          "taipei"
        ],
        "word_alignment": false
      },
      {
        "scene_id": "S003",
        "narration_present": true,
        "narration_event_ids": [
          "E007",
          "E008",
          "E009"
        ],
        "scope": "scene_context",
        "event_bindings": [
          {
            "event_id": "E007",
            "kind": "arrival",
            "scope": "scene_context",
            "local_time": 0.1,
            "absolute_time": 5.1,
            "target_id": "tokyo",
            "target_kind": "verified_gis_location",
            "target_scope": "declared_in_scene",
            "target_source_ids": [
              "natural_earth_places"
            ],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 139.749462,
                "lat": 35.686963,
                "source_id": "natural_earth_places",
                "location_id": "tokyo",
                "verified": true
              }
            ],
            "claim_id": "M01",
            "claim_status": "SIMULATION",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          },
          {
            "event_id": "E008",
            "kind": "new_variable",
            "scope": "scene_context",
            "local_time": 0.8,
            "absolute_time": 5.8,
            "target_id": "taipei",
            "target_kind": "verified_gis_location",
            "target_scope": "declared_in_scene",
            "target_source_ids": [
              "natural_earth_places"
            ],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 121.568333,
                "lat": 25.035833,
                "source_id": "natural_earth_places",
                "location_id": "taipei",
                "verified": true
              }
            ],
            "claim_id": "A02",
            "claim_status": "ASSUMPTION",
            "claim_source_ids": [],
            "word_anchor": false
          },
          {
            "event_id": "E009",
            "kind": "route_blocked",
            "scope": "scene_context",
            "local_time": 1.6,
            "absolute_time": 6.6,
            "target_id": "R_TOKYO_TAIPEI",
            "target_kind": "route",
            "target_scope": "declared_in_scene",
            "target_source_ids": [
              "natural_earth_places"
            ],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 139.749462,
                "lat": 35.686963,
                "source_id": "natural_earth_places",
                "location_id": "tokyo",
                "verified": true
              },
              {
                "lon": 121.568333,
                "lat": 25.035833,
                "source_id": "natural_earth_places",
                "location_id": "taipei",
                "verified": true
              }
            ],
            "claim_id": "A02",
            "claim_status": "ASSUMPTION",
            "claim_source_ids": [],
            "word_anchor": false
          }
        ],
        "claim_references": [
          {
            "claim_id": "F01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "F02",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "F03",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FD01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FD02",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "A01",
            "status": "ASSUMPTION",
            "source_ids": [],
            "assumption_ids": []
          },
          {
            "claim_id": "M01",
            "status": "SIMULATION",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": [
              "A01"
            ]
          },
          {
            "claim_id": "FD03",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FC01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_countries"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "A02",
            "status": "ASSUMPTION",
            "source_ids": [],
            "assumption_ids": []
          },
          {
            "claim_id": "M02",
            "status": "SIMULATION",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": [
              "A01",
              "A02"
            ]
          }
        ],
        "geographic_targets": [
          "seoul",
          "tokyo",
          "taipei"
        ],
        "word_alignment": false
      },
      {
        "scene_id": "S004",
        "narration_present": true,
        "narration_event_ids": [
          "E010",
          "E011"
        ],
        "scope": "scene_context",
        "event_bindings": [
          {
            "event_id": "E010",
            "kind": "route_reroute",
            "scope": "scene_context",
            "local_time": 0.666667,
            "absolute_time": 8.166667,
            "target_id": "R_SEOUL_TAIPEI",
            "target_kind": "route",
            "target_scope": "declared_in_scene",
            "target_source_ids": [
              "natural_earth_places"
            ],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 126.997785,
                "lat": 37.568295,
                "source_id": "natural_earth_places",
                "location_id": "seoul",
                "verified": true
              },
              {
                "lon": 121.568333,
                "lat": 25.035833,
                "source_id": "natural_earth_places",
                "location_id": "taipei",
                "verified": true
              }
            ],
            "claim_id": "M02",
            "claim_status": "SIMULATION",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          },
          {
            "event_id": "E011",
            "kind": "network_expand",
            "scope": "scene_context",
            "local_time": 1.433333,
            "absolute_time": 8.933333,
            "target_id": "R_TOKYO_TAIPEI",
            "target_kind": "route",
            "target_scope": "declared_in_scene",
            "target_source_ids": [
              "natural_earth_places"
            ],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 139.749462,
                "lat": 35.686963,
                "source_id": "natural_earth_places",
                "location_id": "tokyo",
                "verified": true
              },
              {
                "lon": 121.568333,
                "lat": 25.035833,
                "source_id": "natural_earth_places",
                "location_id": "taipei",
                "verified": true
              }
            ],
            "claim_id": "M02",
            "claim_status": "SIMULATION",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          }
        ],
        "claim_references": [
          {
            "claim_id": "F01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "F02",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "F03",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FD01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FD02",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "A01",
            "status": "ASSUMPTION",
            "source_ids": [],
            "assumption_ids": []
          },
          {
            "claim_id": "M01",
            "status": "SIMULATION",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": [
              "A01"
            ]
          },
          {
            "claim_id": "FD03",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FC01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_countries"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "A02",
            "status": "ASSUMPTION",
            "source_ids": [],
            "assumption_ids": []
          },
          {
            "claim_id": "M02",
            "status": "SIMULATION",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": [
              "A01",
              "A02"
            ]
          }
        ],
        "geographic_targets": [
          "seoul",
          "tokyo",
          "taipei"
        ],
        "word_alignment": false
      },
      {
        "scene_id": "S005",
        "narration_present": true,
        "narration_event_ids": [
          "E012"
        ],
        "scope": "scene_context",
        "event_bindings": [
          {
            "event_id": "E012",
            "kind": "final_reveal",
            "scope": "scene_context",
            "local_time": 1.2,
            "absolute_time": 11.2,
            "target_id": "P_FINAL_SHANGHAI",
            "target_kind": "route",
            "target_scope": "declared_in_scene",
            "target_source_ids": [
              "natural_earth_places"
            ],
            "target_source_ids_known": true,
            "planned_route_scene_ids": [],
            "physical_activity_verified": false,
            "gis_references": [
              {
                "lon": 121.568333,
                "lat": 25.035833,
                "source_id": "natural_earth_places",
                "location_id": "taipei",
                "verified": true
              },
              {
                "lon": 121.434559,
                "lat": 31.218398,
                "source_id": "natural_earth_places",
                "location_id": "shanghai",
                "verified": true
              }
            ],
            "claim_id": "MP_CONTEXT",
            "claim_status": "SIMULATION",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          }
        ],
        "claim_references": [
          {
            "claim_id": "F01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "F02",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "F03",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FD01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FD02",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "A01",
            "status": "ASSUMPTION",
            "source_ids": [],
            "assumption_ids": []
          },
          {
            "claim_id": "M01",
            "status": "SIMULATION",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": [
              "A01"
            ]
          },
          {
            "claim_id": "FD03",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "FC01",
            "status": "FACT",
            "source_ids": [
              "natural_earth_countries"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "A02",
            "status": "ASSUMPTION",
            "source_ids": [],
            "assumption_ids": []
          },
          {
            "claim_id": "M02",
            "status": "SIMULATION",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": [
              "A01",
              "A02"
            ]
          },
          {
            "claim_id": "FP_CONTEXT",
            "status": "FACT",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": []
          },
          {
            "claim_id": "MP_CONTEXT",
            "status": "SIMULATION",
            "source_ids": [
              "natural_earth_places"
            ],
            "assumption_ids": [
              "A01",
              "A02"
            ]
          }
        ],
        "geographic_targets": [
          "seoul",
          "tokyo",
          "taipei",
          "shanghai"
        ],
        "word_alignment": false
      }
    ],
    "scope": "Declared same-Scene event/GIS/claim references and measured or supplied cue intervals; not speech recognition, lexical verification, word alignment, or proof that a named word occurs at an event timestamp",
    "lexical_content_verified": false,
    "word_alignment": false
  },
  "production_validation": {
    "passed": true,
    "errors": [],
    "warnings": [],
    "dead_time": {
      "passed": true,
      "errors": [],
      "warnings": [],
      "scenes": [
        {
          "scene_id": "S001",
          "pace": "FAST",
          "transition_seconds": 0.38,
          "meaningful_events": 4,
          "narration_estimate_seconds": 1.5517
        },
        {
          "scene_id": "S002",
          "pace": "FAST",
          "transition_seconds": 0.38,
          "meaningful_events": 2,
          "narration_estimate_seconds": 1.3793
        },
        {
          "scene_id": "S003",
          "pace": "FAST",
          "transition_seconds": 0.38,
          "meaningful_events": 3,
          "narration_estimate_seconds": 1.3793
        },
        {
          "scene_id": "S004",
          "pace": "FAST",
          "transition_seconds": 0.38,
          "meaningful_events": 2,
          "narration_estimate_seconds": 1.5517
        },
        {
          "scene_id": "S005",
          "pace": "FAST",
          "transition_seconds": 0.38,
          "meaningful_events": 1,
          "narration_estimate_seconds": 0.5172
        }
      ],
      "camera_motion_counted_as_event": false,
      "tts_playback_rate": 1.0,
      "automatic_remediation": "Scene-local motion timing; story gaps remain blocking until approved plan correction"
    }
  }
}
