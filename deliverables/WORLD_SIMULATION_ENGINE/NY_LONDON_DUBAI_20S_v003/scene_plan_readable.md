# 뉴욕에서 런던을 거쳐 두바이까지 이어지는 항공 여행

총 길이: 20.0초 · 품질: HIGH

훅: 뉴욕 → 런던 → 두바이 · 하나의 여정?

| 장면 | 시간 | 장소 | 역할/주요 사건 | 카메라 | 조명 |
|---|---|---|---|---|---|
| S001 | 0–4s | New York | hook: city_reveal, route_start, entity_departure, destination_preview | FAST_HOOK_DIVE | CINEMATIC_NIGHT |
| S002 | 4–8s | London | progression: milestone_reveal, milestone_reveal | ROUTE_CHASE | CINEMATIC_NIGHT |
| S003 | 8–12s | Dubai | variable: new_variable, arrival, route_start, network_expand | NETWORK_EXPANSION | GEOGRAPHY_READABILITY |
| S004 | 12–16s | Dubai | peak: peak_reveal, milestone_reveal | HORIZON_REVEAL | HERO |
| S005 | 16–20s | Dubai | payoff: arrival, network_expand, final_reveal | FINAL_REVEAL | CINEMATIC_NIGHT |

## 사실과 가정
- **FACT**: New York의 위치는 공개 GIS 원본 좌표로 확인됩니다.
- **FACT**: London의 위치는 공개 GIS 원본 좌표로 확인됩니다.
- **FACT**: Dubai의 위치는 공개 GIS 원본 좌표로 확인됩니다.
- **FACT**: 공개 좌표로 계산한 경로의 구면 길이는 약 5,570 km입니다. 실제 항공편/항해 시간은 계산하지 않습니다.
- **FACT**: 공개 좌표로 계산한 경로의 구면 길이는 약 5,473 km입니다. 실제 항공편/항해 시간은 계산하지 않습니다.
- **ASSUMPTION**: 입력한 도시 연결과 화면의 이동 시간은 시각화를 위한 가정입니다. 실제 항공편 일정이나 성능 예측이 아닙니다.
- **SIMULATION**: 검증된 위치를 연결하는 구면 경로의 공간적 차이와 연결망을 시각화합니다.

## 검수
{
  "passed": true,
  "errors": [],
  "warnings": [],
  "retention": {
    "passed": true,
    "errors": [],
    "warnings": [],
    "metrics": {
      "meaningful_event_count": 14,
      "average_event_interval": 1.4423,
      "max_event_gap": 2.42,
      "first_3s_events": 4,
      "event_types": 10,
      "max_same_kind_run": 2,
      "peak_count": 1,
      "camera_events_counted": false
    },
    "events": [
      {
        "id": "E001",
        "kind": "city_reveal",
        "time": 0.6,
        "duration": 0.7,
        "target_id": "new_york",
        "role": "cause",
        "caused_by": null,
        "meaningful": true,
        "description": "New York의 확인된 위치 공개",
        "text": "NEW YORK",
        "value": null,
        "unit": "",
        "coordinates": {
          "lon": -73.995718,
          "lat": 40.721562,
          "source_id": "natural_earth_places",
          "location_id": "new_york"
        },
        "claim_id": "F01",
        "absolute_time": 0.6,
        "scene_id": "S001"
      },
      {
        "id": "E002",
        "kind": "route_start",
        "time": 1.3,
        "duration": 0.7,
        "target_id": "R_01",
        "role": "cause",
        "caused_by": "E001",
        "meaningful": true,
        "description": "연결 경로 선택 공개",
        "text": "New York → London",
        "value": null,
        "unit": "",
        "coordinates": {
          "lon": -73.995718,
          "lat": 40.721562,
          "source_id": "natural_earth_places",
          "location_id": "new_york"
        },
        "claim_id": "M01",
        "absolute_time": 1.3,
        "scene_id": "S001"
      },
      {
        "id": "E003",
        "kind": "entity_departure",
        "time": 1.5,
        "duration": 0.7,
        "target_id": "aircraft_R_01",
        "role": "progression",
        "caused_by": "E002",
        "meaningful": true,
        "description": "DEPARTURE",
        "text": "DEPARTURE",
        "coordinates": {
          "lon": -73.995718,
          "lat": 40.721562,
          "source_id": "natural_earth_places",
          "location_id": "new_york"
        },
        "claim_id": "M01",
        "absolute_time": 1.5,
        "scene_id": "S001"
      },
      {
        "id": "E004",
        "kind": "destination_preview",
        "time": 2.4,
        "duration": 0.7,
        "target_id": "london",
        "role": "hint",
        "caused_by": "E003",
        "meaningful": true,
        "description": "다음 연결점 London 공개",
        "text": "LONDON",
        "value": null,
        "unit": "",
        "coordinates": {
          "lon": -0.118668,
          "lat": 51.501941,
          "source_id": "natural_earth_places",
          "location_id": "london"
        },
        "claim_id": "F02",
        "absolute_time": 2.4,
        "scene_id": "S001"
      },
      {
        "id": "E005",
        "kind": "milestone_reveal",
        "time": 0.5,
        "duration": 0.7,
        "target_id": "R_01",
        "role": "progression",
        "caused_by": "E004",
        "meaningful": true,
        "description": "실제 렌더 경로 진행률에서 계산한 남은 구면 거리; 압축된 이동 시간은 가정",
        "text": "3,532 km REMAINING",
        "value": 3532,
        "unit": "km",
        "coordinates": {
          "lon": -0.118668,
          "lat": 51.501941,
          "source_id": "natural_earth_places",
          "location_id": "london"
        },
        "claim_id": "M01",
        "absolute_time": 4.5,
        "scene_id": "S002"
      },
      {
        "id": "E006",
        "kind": "milestone_reveal",
        "time": 2.65,
        "duration": 0.7,
        "target_id": "R_01",
        "role": "progression",
        "caused_by": "E005",
        "meaningful": true,
        "description": "현재 실제 렌더 경로 진행률에서 계산한 남은 구면 거리; 압축된 이동 시간은 가정",
        "text": "1,568 km REMAINING",
        "value": 1568,
        "unit": "km",
        "coordinates": {
          "lon": -0.118668,
          "lat": 51.501941,
          "source_id": "natural_earth_places",
          "location_id": "london"
        },
        "claim_id": "M01",
        "absolute_time": 6.65,
        "scene_id": "S002"
      },
      {
        "id": "E007",
        "kind": "new_variable",
        "time": 0.8,
        "duration": 0.7,
        "target_id": "dubai",
        "role": "variable",
        "caused_by": "E006",
        "meaningful": true,
        "description": "다음 연결/대안이라는 새 변수 공개",
        "text": "NEXT · DUBAI",
        "value": null,
        "unit": "",
        "coordinates": {
          "lon": 55.286946,
          "lat": 25.214912,
          "source_id": "natural_earth_places",
          "location_id": "dubai"
        },
        "claim_id": "M01",
        "absolute_time": 8.8,
        "scene_id": "S003"
      },
      {
        "id": "E009",
        "kind": "route_start",
        "time": 1.15,
        "duration": 0.7,
        "target_id": "R_02",
        "role": "progression",
        "caused_by": "E007",
        "meaningful": true,
        "description": "THE NEXT CONNECTION",
        "text": "THE NEXT CONNECTION",
        "coordinates": {
          "lon": -0.118668,
          "lat": 51.501941,
          "source_id": "natural_earth_places",
          "location_id": "london"
        },
        "claim_id": "M01",
        "absolute_time": 9.15,
        "scene_id": "S003"
      },
      {
        "id": "E010",
        "kind": "network_expand",
        "time": 2.68,
        "duration": 0.7,
        "target_id": "N_03",
        "role": "progression",
        "caused_by": "E009",
        "meaningful": true,
        "description": "다음 연결점 London 공개",
        "text": "NEW CONNECTIONS",
        "value": null,
        "unit": "",
        "coordinates": {
          "lon": 13.399603,
          "lat": 52.523764,
          "source_id": "natural_earth_places",
          "location_id": "berlin"
        },
        "claim_id": "M01",
        "absolute_time": 10.68,
        "scene_id": "S003"
      },
      {
        "id": "E011",
        "kind": "peak_reveal",
        "time": 1.1,
        "duration": 0.7,
        "target_id": "R_02",
        "role": "peak",
        "caused_by": "E010",
        "meaningful": true,
        "description": "주요 연결과 전체 공간 관계 동시 공개",
        "text": "2,904 km TO THE NEXT CITY",
        "value": null,
        "unit": "",
        "coordinates": {
          "lon": 55.286946,
          "lat": 25.214912,
          "source_id": "natural_earth_places",
          "location_id": "dubai"
        },
        "claim_id": "M01",
        "absolute_time": 13.1,
        "scene_id": "S004"
      },
      {
        "id": "E012",
        "kind": "milestone_reveal",
        "time": 3.25,
        "duration": 0.7,
        "target_id": "R_02",
        "role": "progression",
        "caused_by": "E011",
        "meaningful": true,
        "description": "실제 렌더 경로 진행률에서 계산한 남은 구면 거리; 압축된 이동 시간은 가정",
        "text": "836 km REMAINING",
        "value": 836,
        "unit": "km",
        "coordinates": {
          "lon": 55.286946,
          "lat": 25.214912,
          "source_id": "natural_earth_places",
          "location_id": "dubai"
        },
        "claim_id": "M01",
        "absolute_time": 15.25,
        "scene_id": "S004"
      },
      {
        "id": "E013",
        "kind": "arrival",
        "time": 0.8,
        "duration": 0.7,
        "target_id": "dubai",
        "role": "progression",
        "caused_by": "E012",
        "meaningful": true,
        "description": "DUBAI",
        "text": "DUBAI",
        "coordinates": {
          "lon": 55.286946,
          "lat": 25.214912,
          "source_id": "natural_earth_places",
          "location_id": "dubai"
        },
        "claim_id": "M01",
        "absolute_time": 16.8,
        "scene_id": "S005"
      },
      {
        "id": "E014",
        "kind": "network_expand",
        "time": 1.88,
        "duration": 0.7,
        "target_id": "N_04",
        "role": "progression",
        "caused_by": "E013",
        "meaningful": true,
        "description": "연결망 범위 확대",
        "text": "NEW CONNECTIONS",
        "value": null,
        "unit": "",
        "coordinates": {
          "lon": -3.685297,
          "lat": 40.401972,
          "source_id": "natural_earth_places",
          "location_id": "madrid"
        },
        "claim_id": "M01",
        "absolute_time": 17.88,
        "scene_id": "S005"
      },
      {
        "id": "E015",
        "kind": "final_reveal",
        "time": 3.35,
        "duration": 0.7,
        "target_id": "dubai",
        "role": "payoff",
        "caused_by": "E014",
        "meaningful": true,
        "description": "전체 연결 구조와 가정의 한계 공개",
        "text": "CONNECTIONS REVEALED",
        "value": null,
        "unit": "",
        "coordinates": {
          "lon": 55.286946,
          "lat": 25.214912,
          "source_id": "natural_earth_places",
          "location_id": "dubai"
        },
        "claim_id": "M01",
        "absolute_time": 19.35,
        "scene_id": "S005"
      }
    ]
  },
  "semantic_visibility": {
    "schema_version": 1,
    "created_at_utc": "2026-10-04T17:17:08.788Z",
    "passed": true,
    "renderer_sha256": "c0f6c890e67ab5be7aea56739f384db01f1df962330564947dc3a1e378c172f9",
    "source_hashes": {
      "adapter": "c0f6c890e67ab5be7aea56739f384db01f1df962330564947dc3a1e378c172f9",
      "legacy_renderer": "b378269674833f9a79cbbbb2d9c24b004d5ca398063ca897ec1a5359eed0d6d3",
      "aircraft": "fe23bb1b297f0fb16bbe492fcfc5245ab9461c9991195bbd6fe7a616ab12404b",
      "OpenSans": "cf5f5184c1441a1660aa52526328e9d5c2793e77b6d8d3a3ad654bdb07ab8424",
      "Noto": "91a6b21a427d1a5982e19e8875bfd6af620d0a372cd84967a0c225b90f342f6c",
      "certifier": "de1798ac058f26a3033ff026ad195eadd5a4b4568ebd853cfe3bd50bf3dbe2a3"
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
        "kind": "city_reveal",
        "target_id": "new_york",
        "coordinates": {
          "lon": -73.995718,
          "lat": 40.721562,
          "source_id": "natural_earth_places",
          "location_id": "new_york"
        },
        "scheduled_local_time": 0.6,
        "eligible_frames": 19,
        "eligible_primitives": [
          "geographic_pulse"
        ],
        "first_eligible_local_time": 0.6,
        "projection_at_scheduled_time": {
          "x": 0.453977377116339,
          "y": 0.5536081540755433,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "first_primitive": "geographic_pulse",
        "visible_seconds": 0.6333333333333333,
        "renderer_supported": true,
        "onset_latency_seconds": 0,
        "allowed_onset_delay_seconds": 0.06133333333333333
      },
      {
        "event_id": "E002",
        "scene_id": "S001",
        "kind": "route_start",
        "target_id": "R_01",
        "coordinates": {
          "lon": -73.995718,
          "lat": 40.721562,
          "source_id": "natural_earth_places",
          "location_id": "new_york"
        },
        "scheduled_local_time": 1.3,
        "eligible_frames": 41,
        "eligible_primitives": [
          "route_head"
        ],
        "first_eligible_local_time": 1.3,
        "projection_at_scheduled_time": {
          "x": 0.3442165596668434,
          "y": 0.6313776236709077,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "first_primitive": "route_head",
        "visible_seconds": 1.3666666666666667,
        "renderer_supported": true,
        "onset_latency_seconds": 0,
        "allowed_onset_delay_seconds": 0.03333333333333333
      },
      {
        "event_id": "E003",
        "scene_id": "S001",
        "kind": "entity_departure",
        "target_id": "aircraft_R_01",
        "coordinates": {
          "lon": -73.995718,
          "lat": 40.721562,
          "source_id": "natural_earth_places",
          "location_id": "new_york"
        },
        "scheduled_local_time": 1.5,
        "eligible_frames": 39,
        "eligible_primitives": [
          "3D_entity"
        ],
        "first_eligible_local_time": 1.5666666666666667,
        "projection_at_scheduled_time": {
          "x": 0.302715564842188,
          "y": 0.6551843632306104,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "first_primitive": "3D_entity",
        "visible_seconds": 1.3,
        "renderer_supported": true,
        "onset_latency_seconds": 0.06666666666666665,
        "allowed_onset_delay_seconds": 0.2733333333333333
      },
      {
        "event_id": "E004",
        "scene_id": "S001",
        "kind": "destination_preview",
        "target_id": "london",
        "coordinates": {
          "lon": -0.118668,
          "lat": 51.501941,
          "source_id": "natural_earth_places",
          "location_id": "london"
        },
        "scheduled_local_time": 2.4,
        "eligible_frames": 38,
        "eligible_primitives": [
          "information"
        ],
        "first_eligible_local_time": 2.466666666666667,
        "projection_at_scheduled_time": {
          "x": 1.154470287762941,
          "y": 0.1993447240584672,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": false
        },
        "first_primitive": "information",
        "visible_seconds": 1.2666666666666666,
        "renderer_supported": true,
        "onset_latency_seconds": 0.06666666666666687,
        "allowed_onset_delay_seconds": 0.2833333333333333
      },
      {
        "event_id": "E005",
        "scene_id": "S002",
        "kind": "milestone_reveal",
        "target_id": "R_01",
        "coordinates": {
          "lon": -0.118668,
          "lat": 51.501941,
          "source_id": "natural_earth_places",
          "location_id": "london"
        },
        "scheduled_local_time": 0.5,
        "eligible_frames": 38,
        "eligible_primitives": [
          "information"
        ],
        "first_eligible_local_time": 0.5666666666666667,
        "projection_at_scheduled_time": {
          "x": 1.354407723900213,
          "y": 0.20974074486063682,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": false
        },
        "first_primitive": "information",
        "visible_seconds": 1.2666666666666666,
        "renderer_supported": true,
        "onset_latency_seconds": 0.06666666666666665,
        "allowed_onset_delay_seconds": 0.2833333333333333
      },
      {
        "event_id": "E006",
        "scene_id": "S002",
        "kind": "milestone_reveal",
        "target_id": "R_01",
        "coordinates": {
          "lon": -0.118668,
          "lat": 51.501941,
          "source_id": "natural_earth_places",
          "location_id": "london"
        },
        "scheduled_local_time": 2.65,
        "eligible_frames": 38,
        "eligible_primitives": [
          "information"
        ],
        "first_eligible_local_time": 2.7,
        "projection_at_scheduled_time": {
          "x": 1.2651957770518936,
          "y": 0.40273750982864165,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": false
        },
        "first_primitive": "information",
        "visible_seconds": 1.2666666666666666,
        "renderer_supported": true,
        "onset_latency_seconds": 0.050000000000000266,
        "allowed_onset_delay_seconds": 0.2833333333333333
      },
      {
        "event_id": "E007",
        "scene_id": "S003",
        "kind": "new_variable",
        "target_id": "dubai",
        "coordinates": {
          "lon": 55.286946,
          "lat": 25.214912,
          "source_id": "natural_earth_places",
          "location_id": "dubai"
        },
        "scheduled_local_time": 0.8,
        "eligible_frames": 38,
        "eligible_primitives": [
          "information"
        ],
        "first_eligible_local_time": 0.8666666666666667,
        "projection_at_scheduled_time": {
          "x": 1.975414916952705,
          "y": 0.599681480682793,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": false
        },
        "first_primitive": "information",
        "visible_seconds": 1.2666666666666666,
        "renderer_supported": true,
        "onset_latency_seconds": 0.06666666666666665,
        "allowed_onset_delay_seconds": 0.2833333333333333
      },
      {
        "event_id": "E009",
        "scene_id": "S003",
        "kind": "route_start",
        "target_id": "R_02",
        "coordinates": {
          "lon": -0.118668,
          "lat": 51.501941,
          "source_id": "natural_earth_places",
          "location_id": "london"
        },
        "scheduled_local_time": 1.15,
        "eligible_frames": 40,
        "eligible_primitives": [
          "route_head"
        ],
        "first_eligible_local_time": 1.1666666666666667,
        "projection_at_scheduled_time": {
          "x": 0.4917630937888183,
          "y": 0.5068884720355707,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "first_primitive": "route_head",
        "visible_seconds": 1.3333333333333333,
        "renderer_supported": true,
        "onset_latency_seconds": 0.01666666666666683,
        "allowed_onset_delay_seconds": 0.03333333333333333
      },
      {
        "event_id": "E010",
        "scene_id": "S003",
        "kind": "network_expand",
        "target_id": "N_03",
        "coordinates": {
          "lon": 13.399603,
          "lat": 52.523764,
          "source_id": "natural_earth_places",
          "location_id": "berlin"
        },
        "scheduled_local_time": 2.68,
        "eligible_frames": 27,
        "eligible_primitives": [
          "network"
        ],
        "first_eligible_local_time": 2.7,
        "projection_at_scheduled_time": {
          "x": 0.4339956692577921,
          "y": 0.4272775041440167,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "first_primitive": "network",
        "visible_seconds": 0.9,
        "renderer_supported": true,
        "onset_latency_seconds": 0.020000000000000018,
        "allowed_onset_delay_seconds": 0.03333333333333333
      },
      {
        "event_id": "E011",
        "scene_id": "S004",
        "kind": "peak_reveal",
        "target_id": "R_02",
        "coordinates": {
          "lon": 55.286946,
          "lat": 25.214912,
          "source_id": "natural_earth_places",
          "location_id": "dubai"
        },
        "scheduled_local_time": 1.1,
        "eligible_frames": 40,
        "eligible_primitives": [
          "information",
          "network"
        ],
        "first_eligible_local_time": 1.1,
        "projection_at_scheduled_time": {
          "x": 1.5623680568724418,
          "y": 1.0775444039892912,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": false
        },
        "first_primitive": "network",
        "visible_seconds": 1.3333333333333333,
        "renderer_supported": true,
        "onset_latency_seconds": 0,
        "allowed_onset_delay_seconds": 0.03333333333333333
      },
      {
        "event_id": "E012",
        "scene_id": "S004",
        "kind": "milestone_reveal",
        "target_id": "R_02",
        "coordinates": {
          "lon": 55.286946,
          "lat": 25.214912,
          "source_id": "natural_earth_places",
          "location_id": "dubai"
        },
        "scheduled_local_time": 3.25,
        "eligible_frames": 20,
        "eligible_primitives": [
          "information"
        ],
        "first_eligible_local_time": 3.3,
        "projection_at_scheduled_time": {
          "x": 1.0788227853356234,
          "y": 0.6375947043117133,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": false
        },
        "first_primitive": "information",
        "visible_seconds": 0.6666666666666666,
        "renderer_supported": true,
        "onset_latency_seconds": 0.04999999999999982,
        "allowed_onset_delay_seconds": 0.2833333333333333
      },
      {
        "event_id": "E013",
        "scene_id": "S005",
        "kind": "arrival",
        "target_id": "dubai",
        "coordinates": {
          "lon": 55.286946,
          "lat": 25.214912,
          "source_id": "natural_earth_places",
          "location_id": "dubai"
        },
        "scheduled_local_time": 0.8,
        "eligible_frames": 19,
        "eligible_primitives": [
          "geographic_pulse"
        ],
        "first_eligible_local_time": 0.8,
        "projection_at_scheduled_time": {
          "x": 0.8076572737676385,
          "y": 0.6006826819243831,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "first_primitive": "geographic_pulse",
        "visible_seconds": 0.6333333333333333,
        "renderer_supported": true,
        "onset_latency_seconds": 0,
        "allowed_onset_delay_seconds": 0.06133333333333333
      },
      {
        "event_id": "E014",
        "scene_id": "S005",
        "kind": "network_expand",
        "target_id": "N_04",
        "coordinates": {
          "lon": -3.685297,
          "lat": 40.401972,
          "source_id": "natural_earth_places",
          "location_id": "madrid"
        },
        "scheduled_local_time": 1.88,
        "eligible_frames": 24,
        "eligible_primitives": [
          "network"
        ],
        "first_eligible_local_time": 1.9,
        "projection_at_scheduled_time": {
          "x": 0.24706757318148073,
          "y": 0.5204413539961802,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "first_primitive": "network",
        "visible_seconds": 0.8,
        "renderer_supported": true,
        "onset_latency_seconds": 0.020000000000000018,
        "allowed_onset_delay_seconds": 0.03333333333333333
      },
      {
        "event_id": "E015",
        "scene_id": "S005",
        "kind": "final_reveal",
        "target_id": "dubai",
        "coordinates": {
          "lon": 55.286946,
          "lat": 25.214912,
          "source_id": "natural_earth_places",
          "location_id": "dubai"
        },
        "scheduled_local_time": 3.35,
        "eligible_frames": 18,
        "eligible_primitives": [
          "information"
        ],
        "first_eligible_local_time": 3.4,
        "projection_at_scheduled_time": {
          "x": 0.804641869454026,
          "y": 0.6178538641923872,
          "earth_occluded": false,
          "depth_visible": true,
          "inside_event_safe_area": true
        },
        "first_primitive": "information",
        "visible_seconds": 0.6,
        "renderer_supported": true,
        "onset_latency_seconds": 0.04999999999999982,
        "allowed_onset_delay_seconds": 0.2833333333333333
      }
    ],
    "failures": [],
    "scope": "Pure frozen-renderer pose, Earth occlusion, event primitive eligibility and installed-font advance layout at every 30fps pose. No canvas/WebGL, shader brightness, texture visibility, aesthetic assessment or actual rendered-pixel/QC claim.",
    "font_layout_policy": "Installed OpenSans/Noto glyph advances; whole strings reserve3% for shaping uncertainty. Final browser font/rasterization QC remains required.",
    "semantic_input_sha256": "e375e8abf754bf1c3e73c35621f16ee45b42f4c8cba17419b22b1d34ba89f633",
    "certified_plan_bytes_sha256": "83d96c5ab2fdd0be6e29239d47e85d440c9bfa775493fb00ff5ec1e2959d1736",
    "certificate_source_fingerprint": "dbe03bef3fa1b002bd2e22ebc0cf6ed765afd7c562b09d98ddd7fc90aeca9636",
    "certificate_cache_hit": true
  },
  "narration_alignment": {
    "passed": true,
    "errors": [],
    "warnings": [],
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
            "kind": "city_reveal",
            "scope": "scene_context",
            "local_time": 0.6,
            "absolute_time": 0.6,
            "target_id": "new_york",
            "target_kind": "verified_gis_location",
            "gis_references": [
              {
                "lon": -73.995718,
                "lat": 40.721562,
                "source_id": "natural_earth_places",
                "location_id": "new_york",
                "verified": true
              }
            ],
            "claim_id": "F01",
            "claim_status": "FACT",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          },
          {
            "event_id": "E002",
            "kind": "route_start",
            "scope": "scene_context",
            "local_time": 1.3,
            "absolute_time": 1.3,
            "target_id": "R_01",
            "target_kind": "route",
            "gis_references": [
              {
                "lon": -73.995718,
                "lat": 40.721562,
                "source_id": "natural_earth_places",
                "location_id": "new_york",
                "verified": true
              },
              {
                "lon": -0.118668,
                "lat": 51.501941,
                "source_id": "natural_earth_places",
                "location_id": "london",
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
            "local_time": 1.5,
            "absolute_time": 1.5,
            "target_id": "aircraft_R_01",
            "target_kind": "entity",
            "gis_references": [
              {
                "lon": -73.995718,
                "lat": 40.721562,
                "source_id": "natural_earth_places",
                "location_id": "new_york",
                "verified": true
              },
              {
                "lon": -0.118668,
                "lat": 51.501941,
                "source_id": "natural_earth_places",
                "location_id": "london",
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
            "target_id": "london",
            "target_kind": "verified_gis_location",
            "gis_references": [
              {
                "lon": -0.118668,
                "lat": 51.501941,
                "source_id": "natural_earth_places",
                "location_id": "london",
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
          }
        ],
        "geographic_targets": [
          "new_york"
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
            "local_time": 0.5,
            "absolute_time": 4.5,
            "target_id": "R_01",
            "target_kind": "route",
            "gis_references": [
              {
                "lon": -73.995718,
                "lat": 40.721562,
                "source_id": "natural_earth_places",
                "location_id": "new_york",
                "verified": true
              },
              {
                "lon": -0.118668,
                "lat": 51.501941,
                "source_id": "natural_earth_places",
                "location_id": "london",
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
            "kind": "milestone_reveal",
            "scope": "scene_context",
            "local_time": 2.65,
            "absolute_time": 6.65,
            "target_id": "R_01",
            "target_kind": "route",
            "gis_references": [
              {
                "lon": -73.995718,
                "lat": 40.721562,
                "source_id": "natural_earth_places",
                "location_id": "new_york",
                "verified": true
              },
              {
                "lon": -0.118668,
                "lat": 51.501941,
                "source_id": "natural_earth_places",
                "location_id": "london",
                "verified": true
              }
            ],
            "claim_id": "M01",
            "claim_status": "SIMULATION",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          }
        ],
        "claim_references": [
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
          }
        ],
        "geographic_targets": [
          "london"
        ],
        "word_alignment": false
      },
      {
        "scene_id": "S003",
        "narration_present": true,
        "narration_event_ids": [
          "E007",
          "E008",
          "E009",
          "E010"
        ],
        "scope": "scene_context",
        "event_bindings": [
          {
            "event_id": "E007",
            "kind": "new_variable",
            "scope": "scene_context",
            "local_time": 0.8,
            "absolute_time": 8.8,
            "target_id": "dubai",
            "target_kind": "verified_gis_location",
            "gis_references": [
              {
                "lon": 55.286946,
                "lat": 25.214912,
                "source_id": "natural_earth_places",
                "location_id": "dubai",
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
            "kind": "arrival",
            "scope": "scene_context",
            "local_time": 1.15,
            "absolute_time": 9.15,
            "target_id": "london",
            "target_kind": "verified_gis_location",
            "gis_references": [
              {
                "lon": -0.118668,
                "lat": 51.501941,
                "source_id": "natural_earth_places",
                "location_id": "london",
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
            "event_id": "E009",
            "kind": "route_start",
            "scope": "scene_context",
            "local_time": 1.15,
            "absolute_time": 9.15,
            "target_id": "R_02",
            "target_kind": "route",
            "gis_references": [
              {
                "lon": -0.118668,
                "lat": 51.501941,
                "source_id": "natural_earth_places",
                "location_id": "london",
                "verified": true
              },
              {
                "lon": 55.286946,
                "lat": 25.214912,
                "source_id": "natural_earth_places",
                "location_id": "dubai",
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
            "event_id": "E010",
            "kind": "network_expand",
            "scope": "scene_context",
            "local_time": 2.68,
            "absolute_time": 10.68,
            "target_id": "N_03",
            "target_kind": "route",
            "gis_references": [
              {
                "lon": -0.118668,
                "lat": 51.501941,
                "source_id": "natural_earth_places",
                "location_id": "london",
                "verified": true
              },
              {
                "lon": 13.399603,
                "lat": 52.523764,
                "source_id": "natural_earth_places",
                "location_id": "berlin",
                "verified": true
              }
            ],
            "claim_id": "M01",
            "claim_status": "SIMULATION",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          }
        ],
        "claim_references": [
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
          }
        ],
        "geographic_targets": [
          "dubai"
        ],
        "word_alignment": false
      },
      {
        "scene_id": "S004",
        "narration_present": true,
        "narration_event_ids": [
          "E011",
          "E012"
        ],
        "scope": "scene_context",
        "event_bindings": [
          {
            "event_id": "E011",
            "kind": "peak_reveal",
            "scope": "scene_context",
            "local_time": 1.1,
            "absolute_time": 13.1,
            "target_id": "R_02",
            "target_kind": "route",
            "gis_references": [
              {
                "lon": -0.118668,
                "lat": 51.501941,
                "source_id": "natural_earth_places",
                "location_id": "london",
                "verified": true
              },
              {
                "lon": 55.286946,
                "lat": 25.214912,
                "source_id": "natural_earth_places",
                "location_id": "dubai",
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
            "event_id": "E012",
            "kind": "milestone_reveal",
            "scope": "scene_context",
            "local_time": 3.25,
            "absolute_time": 15.25,
            "target_id": "R_02",
            "target_kind": "route",
            "gis_references": [
              {
                "lon": -0.118668,
                "lat": 51.501941,
                "source_id": "natural_earth_places",
                "location_id": "london",
                "verified": true
              },
              {
                "lon": 55.286946,
                "lat": 25.214912,
                "source_id": "natural_earth_places",
                "location_id": "dubai",
                "verified": true
              }
            ],
            "claim_id": "M01",
            "claim_status": "SIMULATION",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          }
        ],
        "claim_references": [
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
          }
        ],
        "geographic_targets": [
          "dubai"
        ],
        "word_alignment": false
      },
      {
        "scene_id": "S005",
        "narration_present": true,
        "narration_event_ids": [
          "E013",
          "E014",
          "E015"
        ],
        "scope": "scene_context",
        "event_bindings": [
          {
            "event_id": "E013",
            "kind": "arrival",
            "scope": "scene_context",
            "local_time": 0.8,
            "absolute_time": 16.8,
            "target_id": "dubai",
            "target_kind": "verified_gis_location",
            "gis_references": [
              {
                "lon": 55.286946,
                "lat": 25.214912,
                "source_id": "natural_earth_places",
                "location_id": "dubai",
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
            "event_id": "E014",
            "kind": "network_expand",
            "scope": "scene_context",
            "local_time": 1.88,
            "absolute_time": 17.88,
            "target_id": "N_04",
            "target_kind": "route",
            "gis_references": [
              {
                "lon": -0.118668,
                "lat": 51.501941,
                "source_id": "natural_earth_places",
                "location_id": "london",
                "verified": true
              },
              {
                "lon": -3.685297,
                "lat": 40.401972,
                "source_id": "natural_earth_places",
                "location_id": "madrid",
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
            "event_id": "E015",
            "kind": "final_reveal",
            "scope": "scene_context",
            "local_time": 3.35,
            "absolute_time": 19.35,
            "target_id": "dubai",
            "target_kind": "verified_gis_location",
            "gis_references": [
              {
                "lon": 55.286946,
                "lat": 25.214912,
                "source_id": "natural_earth_places",
                "location_id": "dubai",
                "verified": true
              }
            ],
            "claim_id": "M01",
            "claim_status": "SIMULATION",
            "claim_source_ids": [
              "natural_earth_places"
            ],
            "word_anchor": false
          }
        ],
        "claim_references": [
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
          }
        ],
        "geographic_targets": [
          "dubai"
        ],
        "word_alignment": false
      }
    ],
    "scope": "Declared same-Scene event/GIS/claim references and measured or supplied cue intervals; not speech recognition, lexical verification, word alignment, or proof that a named word occurs at an event timestamp",
    "lexical_content_verified": false,
    "word_alignment": false
  }
}
