# 서울에서 도쿄로 이동한 민간 항공 연결의 다음 목적지가 타이베이로 바뀐다면?

총 길이: 15.0초 · 품질: HIGH

훅: 다음 목적지가 바뀐다면?

| 장면 | 시간 | 장소 | 역할/주요 사건 | 카메라 | 조명 |
|---|---|---|---|---|---|
| S001 | 0–3s | Seoul | hook: country_reveal, route_start, entity_departure, destination_preview | FLAT_COUNTRY_FOCUS | GEOGRAPHY_READABILITY |
| S002 | 3–6s | Tokyo | progression: milestone_reveal, country_reveal | FLAT_ROUTE_FOLLOW | GEOGRAPHY_READABILITY |
| S003 | 6–9s | Tokyo | variable: arrival, new_variable, route_blocked | FLAT_NEXT_EVENT_PREVIEW | GEOGRAPHY_READABILITY |
| S004 | 9–12s | Taipei | response: route_reroute, network_expand | FLAT_MULTI_COUNTRY | GEOGRAPHY_READABILITY |
| S005 | 12–15s | Taipei | payoff: final_reveal | FINAL_REVEAL | CINEMATIC_NIGHT |

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
      "average_event_interval": 1.2136,
      "max_event_gap": 2.95,
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
        "time": 0.3,
        "duration": 1.25,
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
        "absolute_time": 0.3,
        "scene_id": "S001"
      },
      {
        "id": "E002",
        "kind": "route_start",
        "time": 0.8,
        "duration": 1.25,
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
        "text": "SEOUL / TOKYO",
        "description": "SEOUL / TOKYO",
        "value": null,
        "unit": "",
        "absolute_time": 0.8,
        "scene_id": "S001"
      },
      {
        "id": "E003",
        "kind": "entity_departure",
        "time": 1.4,
        "duration": 1.25,
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
        "text": "FIRST CONNECTION",
        "description": "FIRST CONNECTION",
        "value": null,
        "unit": "",
        "absolute_time": 1.4,
        "scene_id": "S001"
      },
      {
        "id": "E004",
        "kind": "destination_preview",
        "time": 2.4,
        "duration": 1.25,
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
        "absolute_time": 2.4,
        "scene_id": "S001"
      },
      {
        "id": "E005",
        "kind": "milestone_reveal",
        "time": 0.8,
        "duration": 1.25,
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
        "text": "648 km TO TOKYO",
        "description": "현재 저작된 곡선 위치에서 다음 도시까지의 구면 경로 거리",
        "value": 648.216513,
        "unit": "km",
        "absolute_time": 3.8,
        "scene_id": "S002"
      },
      {
        "id": "E006",
        "kind": "country_reveal",
        "time": 2.25,
        "duration": 1.25,
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
        "absolute_time": 5.25,
        "scene_id": "S002"
      },
      {
        "id": "E007",
        "kind": "arrival",
        "time": 0.1,
        "duration": 1.25,
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
        "text": "TOKYO",
        "description": "TOKYO",
        "value": null,
        "unit": "",
        "absolute_time": 6.1,
        "scene_id": "S003"
      },
      {
        "id": "E008",
        "kind": "new_variable",
        "time": 0.95,
        "duration": 1.25,
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
        "text": "ASSUMPTION · NEXT STOP: TAIPEI",
        "description": "ASSUMPTION · NEXT STOP: TAIPEI",
        "value": null,
        "unit": "",
        "absolute_time": 6.95,
        "scene_id": "S003"
      },
      {
        "id": "E009",
        "kind": "route_blocked",
        "time": 1.9,
        "duration": 1.25,
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
        "text": "ASSUMPTION · CONNECTION ON HOLD",
        "description": "ASSUMPTION · CONNECTION ON HOLD",
        "value": null,
        "unit": "",
        "absolute_time": 7.9,
        "scene_id": "S003"
      },
      {
        "id": "E010",
        "kind": "route_reroute",
        "time": 0.8,
        "duration": 1.25,
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
        "text": "DIRECT LINK: SEOUL / TAIPEI",
        "description": "DIRECT LINK: SEOUL / TAIPEI",
        "value": null,
        "unit": "",
        "absolute_time": 9.8,
        "scene_id": "S004"
      },
      {
        "id": "E011",
        "kind": "network_expand",
        "time": 1.7,
        "duration": 1.25,
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
        "text": "A SECOND CONNECTION JOINS",
        "description": "A SECOND CONNECTION JOINS",
        "value": null,
        "unit": "",
        "absolute_time": 10.7,
        "scene_id": "S004"
      },
      {
        "id": "E012",
        "kind": "final_reveal",
        "time": 1.65,
        "duration": 1.3,
        "target_id": "R_SEOUL_TAIPEI",
        "coordinates": {
          "lon": 121.568333,
          "lat": 25.035833,
          "source_id": "natural_earth_places",
          "location_id": "taipei"
        },
        "claim_id": "M02",
        "role": "payoff",
        "caused_by": "E011",
        "meaningful": true,
        "text": "THREE CITIES · ONE NETWORK",
        "description": "THREE CITIES · ONE NETWORK",
        "value": null,
        "unit": "",
        "absolute_time": 13.65,
        "scene_id": "S005"
      }
    ]
  },
  "semantic_visibility": {
    "schema_version": 1,
    "created_at_utc": "2026-10-05T10:27:15.201Z",
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
      "certifier": "1ddac64b9b9741e5387452534b9a727dd7ab80ecddae467d5c3e9ee18ffde770"
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
        "scheduled_local_time": 0.3,
        "eligible_frames": 38,
        "eligible_primitives": [
          "country_highlight"
        ],
        "first_eligible_local_time": 0.3,
        "projection_at_scheduled_time": {
          "x": 0.49967458007568016,
          "y": 0.4999749328534563,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "country_highlight",
        "visible_seconds": 1.2666666666666666,
        "onset_latency_seconds": 0,
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
        "scheduled_local_time": 0.8,
        "eligible_frames": 38,
        "eligible_primitives": [
          "route_head"
        ],
        "first_eligible_local_time": 0.8,
        "projection_at_scheduled_time": {
          "x": 0.4917806954267095,
          "y": 0.499366865711566,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "route_head",
        "visible_seconds": 1.2666666666666666,
        "onset_latency_seconds": 0,
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
        "scheduled_local_time": 1.4,
        "eligible_frames": 36,
        "eligible_primitives": [
          "3D_entity"
        ],
        "first_eligible_local_time": 1.4666666666666666,
        "projection_at_scheduled_time": {
          "x": 0.4579689807987181,
          "y": 0.4967623441622255,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "3D_entity",
        "visible_seconds": 1.2,
        "onset_latency_seconds": 0.06666666666666665,
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
        "scheduled_local_time": 2.4,
        "eligible_frames": 15,
        "eligible_primitives": [
          "world_label"
        ],
        "first_eligible_local_time": 2.466666666666667,
        "projection_at_scheduled_time": {
          "x": 0.7951970199640626,
          "y": 0.5337001235417382,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "world_label",
        "visible_seconds": 0.5,
        "onset_latency_seconds": 0.06666666666666687,
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
        "scheduled_local_time": 0.8,
        "eligible_frames": 35,
        "eligible_primitives": [
          "information"
        ],
        "first_eligible_local_time": 0.8666666666666667,
        "projection_at_scheduled_time": {
          "x": 0.7356969003505412,
          "y": 0.5275065594439314,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "information",
        "visible_seconds": 1.1666666666666667,
        "onset_latency_seconds": 0.06666666666666665,
        "allowed_onset_delay_seconds": 0.2833333333333333,
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
        "scheduled_local_time": 2.25,
        "eligible_frames": 21,
        "eligible_primitives": [
          "country_highlight"
        ],
        "first_eligible_local_time": 2.2666666666666666,
        "projection_at_scheduled_time": {
          "x": 0.5272205129587647,
          "y": 0.5033701903045757,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "country_highlight",
        "visible_seconds": 0.7,
        "onset_latency_seconds": 0.016666666666666607,
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
        "eligible_frames": 37,
        "eligible_primitives": [
          "geographic_pulse"
        ],
        "first_eligible_local_time": 0.13333333333333333,
        "projection_at_scheduled_time": {
          "x": 0.5000946498689883,
          "y": 0.499966536631978,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "geographic_pulse",
        "visible_seconds": 1.2333333333333334,
        "onset_latency_seconds": 0.033333333333333326,
        "allowed_onset_delay_seconds": 0.08333333333333334,
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
        "scheduled_local_time": 0.95,
        "eligible_frames": 35,
        "eligible_primitives": [
          "information"
        ],
        "first_eligible_local_time": 1,
        "projection_at_scheduled_time": {
          "x": 0.030836623095671364,
          "y": 0.6804897113082922,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": false
        },
        "renderer_supported": true,
        "first_primitive": "information",
        "visible_seconds": 1.1666666666666667,
        "onset_latency_seconds": 0.050000000000000044,
        "allowed_onset_delay_seconds": 0.2833333333333333,
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
        "scheduled_local_time": 1.9,
        "eligible_frames": 32,
        "eligible_primitives": [
          "route_barrier"
        ],
        "first_eligible_local_time": 1.9333333333333333,
        "projection_at_scheduled_time": {
          "x": 0.7902427439424015,
          "y": 0.3932975076364121,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "route_barrier",
        "visible_seconds": 1.0666666666666667,
        "onset_latency_seconds": 0.03333333333333344,
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
        "scheduled_local_time": 0.8,
        "eligible_frames": 38,
        "eligible_primitives": [
          "route_head"
        ],
        "first_eligible_local_time": 0.8,
        "projection_at_scheduled_time": {
          "x": 0.44469945024413526,
          "y": 0.3802449124923335,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "route_head",
        "visible_seconds": 1.2666666666666666,
        "onset_latency_seconds": 0,
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
        "scheduled_local_time": 1.7,
        "eligible_frames": 27,
        "eligible_primitives": [
          "network"
        ],
        "first_eligible_local_time": 1.7333333333333334,
        "projection_at_scheduled_time": {
          "x": 0.7501952906485888,
          "y": 0.41106218849284687,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "renderer_supported": true,
        "first_primitive": "network",
        "visible_seconds": 0.9,
        "onset_latency_seconds": 0.03333333333333344,
        "allowed_onset_delay_seconds": 0.03333333333333333,
        "render_mode": "FLAT_MAP_PREMIUM",
        "projection": "LOCAL_MERCATOR"
      },
      {
        "event_id": "E012",
        "scene_id": "S005",
        "kind": "final_reveal",
        "target_id": "R_SEOUL_TAIPEI",
        "coordinates": {
          "lon": 121.568333,
          "lat": 25.035833,
          "source_id": "natural_earth_places",
          "location_id": "taipei"
        },
        "scheduled_local_time": 1.65,
        "eligible_frames": 39,
        "eligible_primitives": [
          "information"
        ],
        "first_eligible_local_time": 1.7,
        "projection_at_scheduled_time": {
          "x": 0.32548699617383675,
          "y": 0.5365184657960074,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "first_primitive": "information",
        "visible_seconds": 1.3,
        "renderer_supported": true,
        "onset_latency_seconds": 0.050000000000000044,
        "allowed_onset_delay_seconds": 0.2833333333333333
      }
    ],
    "failures": [],
    "scope": "Shared selected-renderer pose, Earth occlusion or projected-map geography, atmospheric handoff visibility, event primitive eligibility and installed-font advance layout at every 30fps pose. No canvas/WebGL, shader brightness, texture visibility, aesthetic assessment or actual rendered-pixel/QC claim.",
    "font_layout_policy": "Installed OpenSans/Noto glyph advances; whole strings reserve3% for shaping uncertainty. Final browser font/rasterization QC remains required.",
    "semantic_input_sha256": "5826597929e6cd1f4c5e4c02667f99d22b940bcc5e3f4e6e1fb16ab8b44f61ba",
    "certified_plan_bytes_sha256": "55f40f51e16f3d50afd0af237fb7e0578afc1e398d3ab6b2afeddd559b167d2f",
    "certificate_source_fingerprint": "4f21625c5d100fba728aca69960103aaac9817ac577bf836daedfa1ddf96d851",
    "certificate_cache_hit": true
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
            "local_time": 0.3,
            "absolute_time": 0.3,
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
            "local_time": 0.8,
            "absolute_time": 0.8,
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
            "local_time": 1.4,
            "absolute_time": 1.4,
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
            "local_time": 2.4,
            "absolute_time": 2.4,
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
            "local_time": 0.8,
            "absolute_time": 3.8,
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
            "local_time": 2.25,
            "absolute_time": 5.25,
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
            "absolute_time": 6.1,
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
            "local_time": 0.95,
            "absolute_time": 6.95,
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
            "local_time": 1.9,
            "absolute_time": 7.9,
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
            "local_time": 0.8,
            "absolute_time": 9.8,
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
            "local_time": 1.7,
            "absolute_time": 10.7,
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
            "local_time": 1.65,
            "absolute_time": 13.65,
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
      }
    ],
    "scope": "Declared same-Scene event/GIS/claim references and measured or supplied cue intervals; not speech recognition, lexical verification, word alignment, or proof that a named word occurs at an event timestamp",
    "lexical_content_verified": false,
    "word_alignment": false
  }
}
