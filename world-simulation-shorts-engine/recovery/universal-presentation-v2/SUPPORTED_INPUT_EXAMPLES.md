# 지원 입력과 사용 예제

이 후보는 한국어·영어의 제한된 연출 의도와 **첨부된 사실 데이터**를 연결합니다. 지명만으로 좌표를 검색하거나 역사 자료를 조사하는 AI가 아닙니다. 정확한 필드 규격은 `PRESENTATION_INPUT_CONTRACT.md`, 실행 증거는 `EXAMPLE_MATRIX.md`와 각 JSON receipt를 참조합니다.

## 입력 방법

검증된 `WORLD_ENGINE_PRESENTATION_PROMPT_V2` 예제 파일을 입력하는 방식이 가장 재현하기 쉽습니다. 파일에는 자연어 `prompt`, 기존 `WORLD_ENGINE_DATA_PROMPT_V1` 형식의 `data`, 지리 범위 `region`, 선택한 연출 `presentation`이 함께 있습니다. 기존 `data` 형식과 Scene JSON은 그대로 보존합니다.

| 필드 | 역할 |
|---|---|
| `prompt` | 길이·제공된 장소 참조·지원되는 연출 의도. 원문과 추출 위치를 기록합니다. |
| `data` | 실제 날짜·위치·좌표·경로·영역·출처의 기준입니다. 자연어가 이를 조용히 덮어쓰지 않습니다. |
| `region` | `center: [경도, 위도]`, `bbox: [서, 남, 동, 북]`, `crs: "EPSG:4326"`, `sourceId: "AUTO"`. 실제 소스 범위를 따로 검증합니다. |
| `presentation` | 장면별 카메라·색상·위치 강조와 실제 컷 전환의 명시적 설정입니다. |

기존 데이터에 `renderSettings.sourceRegionId`가 남아 있으면 새 `region.legacyProfileId`에 같은 기존 프로필을 명시해야 합니다. 서로 다른 소스를 조용히 선택하지 않습니다. 새 좌표 기반 예제는 이 기존 소스 선택값을 포함하지 않고 실제 범위 검증을 사용합니다.

자유 문장만 제공해 좌표나 검증 자료가 부족하면 `NEEDS_INPUT`을 반환합니다. 모르는 지명·자료가 없는 전선·실제 연결망을 임의 생성하지 않습니다. 입력한 날짜·시간·연결 방향이 자료와 충돌하면 `CONFLICT`, 좌표가 잘못되면 `INVALID`, 연결되지 않은 기능이면 `UNSUPPORTED`입니다.

## 실제 검사된 예제

**유럽 항공 연결:** `examples/AVIATION_EUROPE_NL.json`

> 첨부한 HAMBURG, BERLIN, MUNICH 좌표와 두 방향 연결 자료로 6초 항공 연결 영상을 만들어줘. 첫 장면은 카메라를 이동하고 줌아웃한 뒤 줌인해줘. 두 번째 장면은 제공한 역방향 경로를 따라 카메라가 이동해줘. 제공한 도시를 강조하고 두 장면을 전환해줘. 이 연결은 실제 항공편이 아닌 가상 예시야.

첫 장면은 제공한 키프레임, 두 번째 장면은 제공한 역방향 경로 추적을 선택합니다. 좌표와 경로는 함께 있는 `data`에 있습니다. 이 예제는 실제 항공 운항 증거가 아닙니다.

**남미 연결:** `examples/TRADE_SOUTH_AMERICA_NL.json`

> Create a 6 second illustrative trade connection using the attached VALPARAISO, SANTIAGO and CONCEPCION coordinates. Pan and zoom out, then zoom in during the first scene. Follow the supplied reverse route with the camera in the second scene. Highlight the supplied cities and cut between the two scenes. This is an abstract city connection, not an observed or navigable shipping service.

**가상 영역 변화:** `examples/FICTIONAL_AFRICA_NL.json`

> 제공한 가상 영토 자료만 사용해 6초 지도 영상을 만들어줘. 첫 장면에서는 영역 확장과 영토 색상 변화를, 두 번째 장면에서는 같은 영역의 축소를 보여줘. 카메라를 이동하고 줌아웃한 뒤 줌인해줘. 제공한 WINDHOEK 위치를 강조하고 두 장면을 전환해줘. 실제 역사나 실제 점령 주장이 아닌 가상 설정이야.

영역 자체는 제공된 작은/큰 폴리곤이며, 색상은 실제 state ID에 연결됩니다. 보기 좋게 만들기 위해 임의 영토를 만들지 않습니다. 추가 지역 예제는 `NEW_REGION_JAPAN_NL.json`, `NEW_REGION_AUSTRALIA_NL.json`입니다. 국가마다 렌더러 코드를 바꾸는 방식이 아닙니다.

## 지원 연출

| 자연어 의도 | 실제 소비되는 설정 |
|---|---|
| 카메라 이동, `move/pan camera` | `camera.mode: "KEYFRAMES"`와 제공된 중심점 |
| 줌인·줌아웃, `zoom in/out` | 제공된 키프레임 `zoom`. 원래 승인된 상세도 제한을 넘지 않습니다. |
| 경로 따라가기, `follow the supplied route` | `camera.mode: "ROUTE_FOLLOW"`, 실제 `routeId` |
| 영토·영역 확장/축소와 색상 변화 | 기존 Area V3 상태·폴리곤·시간축, state ID별 `territoryColors` |
| 도시·사건 위치 강조 | 제공된 `locationId`의 기존 마커 pulse. 임의 위치가 생기지 않습니다. |
| 장면 전환, `cut between scenes` | 실제 장면 경계의 `{type: "CUT", frame: ...}` |
| 제공된 이전 상태를 다음 장면에서 유지 | `initialStateVisibility: "PRESERVE_PROVIDED"`. 인접 장면의 실제 영역·전선·색상·출처가 일치하는지 검사합니다. 기본 `REVEAL`은 유지됩니다. |

장면마다 다른 연출은 문장에 **첫 장면 / 두 번째 장면 / first scene / second scene / 정확한 sceneId**를 명시하고 문장·세미콜론·줄바꿈으로 구분합니다. 명시적 `sceneOverrides`가 정확한 재현용 설정입니다. 장소 이름은 첨부한 location ID/label과 연결되며, `from A to B` 또는 `A에서 B로`는 제공한 방향의 경로가 있어야 합니다.

## 현재 제한

- 새 무료 소프트웨어 프리뷰 경로는 **최대 240프레임**, 30fps 기준 8초까지입니다. 기존 장편 코드는 보존되지만 이 프리뷰의 장편 실행 성공을 의미하지 않습니다.
- 키프레임 줌은 `0 < zoom <= 1`이며 마지막 키프레임이 가장 가까운 배율이어야 합니다. `ROUTE_FOLLOW`와 키프레임 전용 필드를 혼용하지 않습니다.
- 회전·orbit, 3D, dissolve/fade, 폭발, 실시간 데이터, TTS·BGM·내레이션은 이 새 경로에 연결되지 않았습니다.
- 지명·라벨·설명 문구를 화면에 쓰는 기능은 지원하지 않습니다. facts의 label은 추적용 메타데이터이며, 표시 요청은 `UNSUPPORTED_VISIBLE_LABELS`로 차단합니다.
- 극지 투영, 날짜변경선 횡단 및 실제 지도 소스 범위 밖 요청은 지원 여부를 명시적으로 판정합니다. 소스가 없는 지형·수심을 생성하지 않습니다.
- 출처가 있는 근사 부분 전선과 완전한 점령 영역은 다릅니다. 기존 부분 전선의 `LINE_METRIC` 소비자 미연결과 실제 자료 부족을 서로 구분합니다.

이 가이드의 지원 표시는 입력·코드 연결 범위입니다. 실제 Studio 영상 생성, 전체 프레임 검수와 사용자 영상 승인은 별도의 결과이며, 기술 검사만으로 품질 PASS나 FINAL 승격을 선언하지 않습니다.
