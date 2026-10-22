# 범용 소스 Scene V2 — 실제 지원 범위

기존 Scene, G1, 운영 이미지 또는 API를 바꾸지 않는 선택형 확장이다.
`WORLD_ENGINE_UNIVERSAL_SOURCE_SCENE_V2`만 새 정규화기로 전달하고 다른 입력은
기존 Studio Controller에 위임한다. 자유 자연어를 해석하는 기능은 추가하지 않았다.

## 입력과 권한

정확한 실행 예제는 `fixtures/DEMO_SOURCE_SCENE.json`이다. 인천 자료의 차단 예제는
`fixtures/INCHEON_SOURCE_SCENE_BLOCKED.json`이다. 두 파일은 같은 필드 구조를 사용한다.

| 필드 | 현재 처리 |
|---|---|
| schema / scenario_id / event_id | 버전 및 등록된 데이터 패키지와 일치 검사 |
| title | 사용자 문자열, 렌더 화면의 임의 제목 오버레이로 사용하지 않음 |
| durationSeconds / fps / resolution / startFrame | 이 무료 검증 경로는 2~240프레임, 30fps, 1080×1920. 전역 프레임 오프셋 유지 |
| time_interval | 사건 날짜와 표시 시간을 분리. 등록된 원본과 일치해야 함 |
| source_bundle_id / source_refs | 서버가 고정한 INDEX·파일 SHA로만 데이터 선택 |
| geometry | 현재 지리 렌더는 EPSG:4326 및 검증된 identity 정합만 가능. PDF 페이지 좌표는 관측 자료로 전달하고 지도 렌더 차단 |
| actors | 등록 actor_id 순서 유지. RGB 색상 0~1만 변경 가능 |
| control_states | 프레임별 명시적 owner/unknown/contested 자료. 기존 SourceRegistry·GEOS·Area 검증기 재사용 |
| frontline_geometries | 같은 프레임의 검증된 owner 경계에서 기존 공급자가 만든 sharedFront만 소비. 별도 가짜 전선 입력 금지 |
| event_location / camera | 등록된 사건점·기존 Camera V5 계획만 선택. 클라이언트의 임의 승인·좌표 교체 불가 |
| transition / confidence | 등록 소스 샘플의 시간·불확실성 계약 유지. 누락 상태를 보간해 만들지 않음 |
| visual_annotations / audio_cue_slots | 확장 슬롯. 현재 비어 있어야 하며 값이 있으면 명시적 BLOCKED. 사용자 지정 자막·SFX 연결 완료 아님 |

INDEX 위치·SHA, 원본 파일, 라이선스 승인, 실행 허용은 서버 설정이다. 입력 JSON에서
승인 플래그를 보내거나 파일 경로를 바꾸어 우회할 수 없다. 알 수 없는 필드는 오류다.
브라우저 JSON의 `18.0`과 `18`은 같은 숫자로 처리하지만 bool과 숫자, 근사 좌표는 구분한다.

## 실제 호출 경로

기존 Studio HTTP 인증·Origin·CSRF → 새 Controller 선택 → `source_contract.normalize_submission`
→ 고정 source INDEX / SHA → 기존 `control_provider.SourceRegistry`와 `compile_control_state`
→ 프레임별 한 control field → 분리 worker → `capture_source.mjs`
→ 기존 Camera V5 / native map factory / Area V3 / Marker / Glyph → 실제 WebGL2 draw/readPixels
→ PNG → FFmpeg → 완전 디코딩 검사 → 작업 상태.

실행은 서버의 `allow_software_source_review=True`, 명시적 동의, ready preflight를 모두 요구한다.
이 옵션은 로컬 검증에서만 활성화했다. 기존 gCube 이미지나 운영 서비스를 변경·배포하지 않았다.
기존 G1의 opt-in은 활성화하지 않았으며 G1 렌더를 다시 실행하지 않았다.

작업 ID·claim·소스·입력 SHA를 별도 namespace에 기록한다. 인증된 브라우저가 닫혀도 detached
worker는 계속되고, 새 Controller의 동일 submission 시작 요청은 기존 작업을 반환한다.
900초 상한·재시도 0회이며 실패 claim을 지워 재실행하지 않는다. 수정된 코드·입력은 새 작업이다.

## 좌표·카메라·재질 한계

원본 V5를 Chromium에서 다시 계산한 실제 카메라를 사용한다. Node 사전 계산과의 합의는
실측한 산술 차이만 수용하도록 ≤256 ULP **및** ≤10⁻⁹ canonical pixel을 동시에 요구한다.
이 규칙은 LOCAL 입장 조건이나 GIS 정밀도를 변경하지 않는다. DEMO의 camera source clock은
forward / hold / reverse이며 사건의 전역 시간은 계속 증가한다. 역방향 재생의 원본 도함수
연속성을 주장하지 않는다.

DEMO는 기존 native global fallback을 사용하며 ASTRA 범위 밖에 가짜 고도·수심을 만들지 않는다.
기존 G1 V4의 지역 래스터를 지원 범위 밖으로 늘리거나 clamp 결과를 세계지도라고 사용하지 않는다.
G1의 상세 재질·국기·회전·scalar 스타일과 이 DEMO의 시각적 동등성을 주장하지 않는다.
기존 승인 Layout 버전 태그는 이름에 지역명이 있어도 API 계약이므로 그대로 보존한다.

## 역사 자료와 DEMO 구분

인천 패키지는 원문 PDF의 8개 진지선·29개 cubic 명령을 페이지 좌표 그대로 Scene에 전달한다.
지도 좌표 변환, 독립 기준점, 양측 통제면이 없으므로 render-ready가 아니다.
현재 pixel consumer 자체도 SYNTHETIC_TEST 전용이다. 자료가 보강되더라도 검증된 역사 consumer
입장 검사를 별도로 구현·검증하기 전까지 PRODUCTION을 허용하지 않는다.

다른 지역 DEMO의 0.25도 격자 영역은 현대 Natural Earth 육지 안에 작성한 가상 관측 구역이다.
실제 점령선·국경·오염 사건·해안선을 뜻하지 않는다. 자료 파일에 이미 기록한 각 프레임만 그리며
합성 예제를 G2 역사 PASS 또는 G3 인천 영상으로 계산하지 않는다.

## 복원과 이식

`fixtures/SOURCE_BUNDLE.zip`과 `SOURCE_CATALOG_PIN.json`이 중립 입력을 보존한다.
`tools/source_fixture_store.py`는 원본 ZIP·모든 entry·INDEX SHA와 경로를 검사하고 복원한다.
변경된 기존 파일, symlink, 경로 이탈, 과대 패키지는 거부한다. GPU 전용 메모리 배치는 고정하지 않았다.
이 검증은 CPU/SwiftShader이며 NVIDIA 업로드·성능·gCube 운용·사용자 품질 승인을 대신하지 않는다.
