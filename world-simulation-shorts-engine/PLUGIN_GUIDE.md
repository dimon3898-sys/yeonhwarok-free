# Plugin guide

새 주제를 지원할 때 기존 V3 파일이나 엔진 전체를 다시 작성하지 않고 capability·GIS·Scene 계약·렌더 구현을 추가합니다. 이름만 등록해서 `available=True`로 만드는 것은 지원 완료가 아닙니다.

## 현재 capability

| 이름 | 현재 범위 |
|---|---|
| AVIATION | 검증 좌표의 구면 항공 경로·3D 항공기 |
| SHIPPING | 검증된 로테르담–싱가포르 해상 그래프와 수에즈/희망봉 비교 |
| NETWORK | 확인된 위치 사이의 가정 기반 연결 관계 |
| GEOGRAPHY | 현대 지리의 위치·관계·비교 |
| CINEMATIC_CLIP | 라이선스가 명시된 외부 영상 Scene 슬롯 |

WAR_VFX, TIME_MORPH, GEOGRAPHY_MORPH, TERRITORY_TIMELINE, WEATHER, DISASTER, SPACE, ECONOMY는 미설치 상태입니다. 관련 주제를 요청하면 `UNSUPPORTED_VISUAL_REQUIREMENT`와 `required_plugins`를 반환합니다. LAND_ROUTING과 추가 해상 경로도 검증 자료가 없으면 지원하는 것처럼 표시하지 않습니다.

역사 시간 필드가 있다는 이유로 과거 GIS가 지원되지는 않습니다. 역사 지도·과거 국가/해안/영토 상태에는 `HISTORICAL_GIS`와 해당 시간/영토 플러그인이 필요합니다. 현대 날짜를 붙인 여행과 실제 과거 지형 상태를 구분합니다. 자동차·트럭 등의 entity interface가 있더라도 도로 그래프 없는 육로 이동을 항공 arc로 대체하지 않습니다.

현재 최종 전경은 전체 주 경로를 실제 한 반구의 9:16 안전영역에 맞추는 방식입니다. 모든 노드가 한 시야에 들어오지 않으면 `MULTI_HEMISPHERE_OVERVIEW`를 반환합니다. 여러 전경으로 나누는 capability를 추가하기 전까지 지구 뒤쪽 노드를 앞으로 투영하는 편법을 사용하지 않습니다. STYLE 확장은 별도의 실제 조명/카메라 정책과 테스트를 추가해야 합니다. 알려지지 않은 스타일 이름은 `UNSUPPORTED_STYLE`입니다.

## 추가 절차

1. `PluginInterface`의 `validate(scene)`과 `prepare(scene, assets)` 계약을 구현합니다.
2. 원본 URL·저작자·라이선스·다운로드 날짜·출처 표시·SHA를 기록하고 GIS 자료를 추가합니다. 좌표는 AI 출력으로 채우지 않습니다.
3. Scene Type, Entity와 요구 시각 사건을 명시합니다. Schema, 참조·타이밍·경계 상태 검사와 실제 렌더 구현을 함께 연결합니다.
4. 역할에 맞는 카메라·조명을 선택하고 자동/직접 가독성 검수 방법을 정의합니다.
5. 실제 Scene MP4, 모든 프레임 감사, 모바일 크기 검수와 실패 복구를 통과한 뒤 capability를 활성화합니다.

플러그인은 자신이 과학적 계산을 수행하는지, 계산된 외부 결과를 표시하는지, 가정 기반 시각화인지 분명히 기록해야 합니다. 선박 경로를 그렸다는 이유로 물류 가격·도착 시간 예측이 되지 않습니다. 폭풍 이미지를 표시하는 기능도 실제 기상 예측과 다릅니다.

표시 프록시와 실제 데이터도 분리합니다. 현재 선박 경로 오버레이의 표시 높이는 약 3km이지만 실제 이동 waypoint는 수면 부근입니다. 선박·항공기의 확대된 3D 크기나 프록시의 지표 여유를 물리적 운항 고도·크기라고 설명하지 않습니다. 플러그인은 감사 메타데이터에서 실제 경로와 표시 오버레이를 구분하고 지리 좌표를 바꾸지 않아야 합니다.

## 확장 데이터 계약

`HistoricalState`는 `year`, `date`, `era`, `timeline_position`, `geometry_state`, `transition_duration`을 받습니다. `GeographyMorphInterface.transition(before, after, duration)`은 시간 상태 사이의 형상 변화를 위한 계약입니다. 현재 현대 지구를 회전시키는 동작을 대륙 분리나 역사 국경 변화로 대체하지 않습니다.

`WarEffectsInterface`에는 missile trail, impact, explosion, shockwave, smoke, radar, fleet, fighter, territory change 계약이 있습니다. `WeatherInterface.visualize(state, scientific_source)`는 출처 있는 과학 상태와 가정 기반 상태를 구분합니다. 필요한 실제 플러그인은 별도 구현해야 합니다.

외부 영상은 `CINEMATIC_CLIP` Scene의 `cinematic_clip`에 `path`, `trim_start`, `license` 또는 `user_owned`를 명시합니다. 영상 길이가 부족하면 마지막 프레임을 억지로 늘리지 않고 실패합니다. match cut, atmospheric, motion blur, zoom 전환을 선택할 수 있으며 다른 영상과의 밝기·카메라 방향·색감 연결은 직접 검수도 필요합니다.

지도 Scene의 의미 있는 사건을 외부 영상에서 수행했다고 자동으로 가정하지 않습니다. 정보 공개용 클립은 `annotations`에 사건별 `event_id`, 일치하는 `time`, `duration`, `text`, `fact_status`, `source_ids`를 제공합니다. 실제 그려진 오버레이와 그 시간만 렌더 감사에 남깁니다. 물리적인 항로 시작·이동체 출발·도착을 요구하는 Scene을 임의 MP4로 교체하면 해당 사건의 실제 증거가 없으므로 차단합니다. 호환되는 정보 Scene을 선택하거나 명시적으로 Scene 사건을 수정하고 다시 승인해야 합니다. 가정 기반 Scene에 FACT 주석을 넣는 등 사실 상태가 맞지 않는 클립도 허용하지 않습니다.

## 테스트 기준

등록된 capability뿐 아니라 실제 렌더 가능 여부, 잘못된 좌표, 누락 자산·라이선스, 시간 초과, 불연속 경계, 지원하지 않는 연출을 검사합니다. 플러그인마다 최소 한 개의 실제 성공 Scene과 한 개의 실패 입력 근거를 남깁니다. 자동 QC 합격과 인간/직접 시각 검수 합격은 별도로 기록합니다.
