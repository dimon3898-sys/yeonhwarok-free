# Event V1 · Flow V2 · Area V3 연결

새 지도 엔진을 만들지 않고 기존 계약·컴파일러·평가자·GPU pass를 선택하는 얇은 연결 계층을 추가했다. **CPU 연결 검증이며 실제 GPU 출력은 미검증**이다. 한국전쟁 데이터에 없는 이동 경로·부대 위치·점령 영역을 추가하지 않았다.

## 입력과 권한 경계

`completion.eventFlow`는 `WORLD_ENGINE_COMPLETION_EVENT_FLOW_V1`의 엄격한 버전 입력이다. `events`, `flows`, `areas` 배열은 각각 최대 32개다. 현재 역사 입력에 추가로 검증된 Event/Flow 자료가 없으면 세 배열을 비워 둔다. 빈 선택은 GPU 리소스를 만들지 않는 명시적 no-op이며, 실제 적용을 주장하지 않는다.

| 배열 | 정확한 항목 필드 | 보존된 계약 |
| --- | --- | --- |
| `events` | `id`, `startFrame`, `plan`, `sourceBindings` | `EVENT_TIMELINE_V1` canonical plan |
| `flows` | `id`, `plan`, `sourceBindings`, `routeVisibility`; 선택 `arrivalAreaId` | `FLOW_PLAN_V2` canonical plan |
| `areas` | `id`, `plan`, `sourceBindings` | `AREA_PLAN_V3` canonical plan |

`plan`은 기존 compiler의 실제 출력이어야 한다. 기존 compiler로 다시 만들고 전체 의미를 비교한다. 알 수 없는 중첩 필드나 무시되는 가짜 카메라 옵션을 받아들이지 않는다. 일반 JSON 저장소의 key 정렬은 허용하며, 기존 evaluator를 호출하기 전 원래 canonical 순서로 복원한다.

`event_flow_contract.py:normalize_event_flow`는 로컬 Node CPU compiler를 bounded subprocess로 호출한다. 4 MiB 입력·8 MiB 출력·20초 제한이며 shell을 사용하지 않는다. `EVENT_FLOW_REQUEST.schema.json` 검증과 실제 legacy-core canonical 검증을 함께 사용해야 한다. JSON Schema 단독 검증은 원본 plan의 의미 정합을 대체하지 않는다.

각 `sourceBindings`는 `{role, sourceId, sha256}`다. 사용자 입력의 `VERIFIED` 문자열은 권한이 아니다. 서버가 원본 SHA를 확인하여 읽은 immutable catalog의 source ID·SHA·역할·검증 상태·**정확한 payload**와 일치해야 한다.

| 선택 | 필수 역할과 비교 payload |
| --- | --- |
| Event line | `GEOMETRY`: 원본 line geometry |
| Event metric | `METRIC`: 고정 값·단위·anchor·source가 포함된 metric |
| Flow | `GEOMETRY`: route geometry; `OBJECT_GRAPHIC`: 실제 공급된 graphic; `FLOW_PLAN`: role·시간·도착을 포함한 canonical plan 전체 |
| Area | `AREA_INTENT`: source·geometry·state를 포함한 canonical Area intent 전체 |

서버용 trusted catalog record는 `{sourceId, sha256, role, verificationStatus, payload}`다. 원본 파일 SHA와 추출 payload의 관계는 서버 source manifest가 보증한다. `canonicalSourceJSON`/`canonicalSourceSHA`는 정렬된 UTF-8 JSON SHA를 제공하며 Python `ensure_ascii=False, sort_keys=True, separators=(',', ':')`와 일치한다. 브라우저나 프롬프트가 trusted catalog를 만들면 안 된다.

Python 서버의 실제 source admission은 `validate_event_flow(request, fps=..., total_frames=..., trusted_sources=...)`다. 로컬 Node `--admit`가 `compileCompletionEventFlow`를 `allowSynthetic=false`로 호출하고, plan 원문을 출력하지 않는 bounded CPU receipt만 반환한다. 기본 geometry·graphic 일치만으로 다른 세력이나 시대의 객체를 표시하지 못하도록 Flow의 `object_role`과 timing까지 `FLOW_PLAN` payload에 묶는다.

## 실제 재사용 owner와 호출

| 기능 | 기존 파일·함수 | 새 consumer 연결 |
| --- | --- | --- |
| Event line/hold/metric/hold | `web/map_infographic_v1/event_timeline_v1.mjs`: `compileEventPlan`, `evaluateEventFrame` | 정확한 로컬 frame으로 원본 evaluator 호출 |
| Event arc-length | `event_line_v1.mjs`: `compileGeographicLinePrimitive`, `evaluateGeographicLineReveal` | 실제 부모 `project` 재사용 |
| Event line GPU | `event_line_pass_v1.mjs`: `createEventLinePass` | 원래 pass의 `draw` 소비 |
| Metric glyph/layout | `event_metric_v1.mjs`: `compileMetricAnnotation`; `event_layout_adapter_v1.mjs`: `chooseMetricPlacement`, `chooseRelatedMetricPlacement` | 기존 Gate1Bold 40px 측정·layout·full reservation 유지 |
| Metric GPU | `event_metric_pass_v1.mjs`: `createEventMetricPass` | 실제 측정 atlas를 원래 pass에 전달 |
| Route/object/heading/pulse/hold | `flow_core_v2.mjs`: `compileFlowPlan`, `compileFlowRoute`, `evaluateFlowFrame` | 기존 arc-length·가감속·heading·endpoint timing 그대로 사용 |
| Flow GPU | `flow_graphic_pass_v2.mjs`: `createFlowGraphicPass` | 기존 native canvas와 원래 pass의 `draw` 소비 |
| Area reveal/grow/contract/move/front/state/time/hold | `area_core_v3.mjs`: `compileAreaPlan`, `evaluateAreaFrame` | 공급된 원본 intent·operations만 사용 |
| Area GPU | `area_overlay_pass_v3.mjs`: `createAreaOverlayPass` | 원본 geometry·project·safe area·reservations 전달 |
| Marker·text occlusion | `event_occlusion_policy_v1.mjs`: `classifyEventLineProtection` | 기존 Marker mask와 strict text reservation 유지 |

Native Marker를 새로 설계·생성하지 않는다. 부모의 native Marker·Label·실제 date/metric reservation을 `completionProtectedGraphics`로 수집한다. 영토나 부대의 위치를 지명 Marker에서 추론하지 않는다.

## 부모 pipeline의 정확한 hook

1. 기존 `window.longVideoProof.pipeline.drawFrame(globalFrame)`를 먼저 완료한다.
2. 캡처의 `readPixels()`/PNG 이전에 `createCompletionEventFlowPass(...).drawFrame(globalFrame, context)`를 호출한다.
3. `context`는 부모의 실제 `project`, `cameraState`, `scalePlan`, `heightSource`, `safeArea`, `protectedGraphics`다. 추가 Area draw에는 실제 native frame의 `boundarySegments`와 서버 측 `nativeBoundarySourceVerified:true`가 반드시 필요하다. 카메라를 새로 만들거나 위치를 변경하지 않는다.
4. 부모의 `camera.protectedGraphics`와 `area.date.event/geometry.reservation`을 모두 보존한다. 명시적으로 추가된 다른 군대 Marker owner의 예약도 합쳐야 한다.
5. 새 pass 내부 순서는 **Area → Event geographic line → Flow object/endpoint → measured metric glyph**다. Metric의 전체 측정 슬롯을 먼저 예약하여 다른 pass가 덮지 못하게 한다.
6. 원본 GL-state capture/restore를 재사용한다. 완성 화면을 복사하거나 이미지로 덮어씌우지 않으며, 부모 캔버스를 clear·resize하지 않는다.

부모 V4 factory의 내부 native renderer는 공개되지 않는다. 따라서 Event line/metric용으로 동일한 기존 WebGL2 context에서 pass 전용 Three owner를 만들고, 기존 Event pass를 그대로 사용한다. 지도 renderer 전체를 복제하지 않는다. Flow·Area pass는 원래의 공유-context owner와 state restoration을 그대로 사용한다.

브라우저 새 alias는 `/completion-v2/event_flow_binding.mjs`다. 원본 모듈은 기존 `/modules/<파일명>.mjs`와 `/three.js`를 사용한다. Node CPU에서는 같은 보존 파일을 직접 import한다. source closure에는 이 직접·간접 의존성이 포함되어야 한다.

## 전선 없는 이동 객체와 도착 → 영역 관계

Production Flow에는 `routeVisibility: HIDDEN`만 허용한다. 기존 `evaluateFlowFrame`에서 나온 route·object 위치·heading·pulse·hold는 수정하지 않는다. draw control에서 `routeFraction=0`, `routeActive=false`, `directionalActive=false`만 설정한다.

이는 실제 기존 API가 지원하는 동작이다. `event_line_pass_v1.mjs`의 `draw`는 `visibleFraction=0`일 때 reveal path가 두 점 미만이므로 `drawn:false`를 반환한다. Flow 객체·endpoint는 원래 `flow_graphic_pass_v2.mjs`가 계속 그린다. 새 Route Engine·화살표·장식 경로는 추가하지 않는다. GPU에서 실제 경로 픽셀이 없는지는 후속 5초 출력으로 다시 확인해야 한다.

`arrivalAreaId`는 이미 source-bound인 Area 항목을 참조한다. 해당 Area plan의 `startFrame`이 원본 Flow `arrivalFrame`과 정확히 같아야 한다. 도착 순간 1회 causal cue만 기록한다. 영역을 만들거나 시작 시간을 몰래 바꾸거나, 도착을 점령 사실로 해석하지 않는다.

## 명시적 차단

- 검증된 역사적 route·부대/객체 위치·graphic payload가 없으면 해당 역사 Flow를 선택하지 않는다.
- 임의 source hash, payload 불일치, 합성 Fixture의 production 진입, 알 수 없는 plan 필드·중복 ID·timeline 범위 초과는 차단한다.
- 부모 Detail Lock 이전 Event/Flow/Area는 기존 계약에 따라 차단한다. Safe Area 밖 Event geometry는 기존 readiness가 거부한다.
- 기존 V4 진단은 `camera.boundarySegments`를 생략하므로 거기서 빈 배열을 만들어 쓰면 안 된다. 새 camera wrapper가 보존한 동일 global frame의 실제 native boundary support가 없으면 추가 Area draw를 차단한다.
- Production propagation/impact는 실제 육지·바다 exclusion mask 계약이 이 얇은 계층에 연결되지 않았으므로 `COMPLETION_PROPAGATION_MEDIUM_MASK_BINDING_REQUIRED`로 차단한다. 기존 Tsunami 기능이 없다는 의미가 아니다.
- 현재 자료는 완전한 양측 점령 상태나 역사적 국기·부대 이동을 제공하지 않는다. 이 모듈은 그 미확보 항목을 생성하지 않는다.
- 실제 브라우저의 원본 font·GL·pass draw, 픽셀 보호, 모바일 품질은 **GPU 미검증**이다.

## CPU 증거

`node world-simulation-shorts-engine/recovery/universal-integration-completion-v2/tests/test_event_flow_binding.mjs`

**28개 CPU 테스트 PASS.** 남반구·서반구의 명시적 합성 Fixture를 사용했다. 기존 Event/Flow/Area compiler·evaluator를 실제로 호출했고, 원본 Flow의 위치·heading·pulse·hold 결과와 비교했다. Area의 reveal/grow/contract/move/front/state/time/hold 전체를 평가했다. 자료 hash·payload·역할·검증 상태, unknown field, canonical 저장 순서, arrival frame, safe area, Marker/text 예약, Python→Node 계약, 소비자 호출 순서도 검사했다. 실제 보존 geometry catalog를 사용한 Event source admission 성공과, catalog 누락·payload 교체 거부를 실제 Python→Node 경로로 확인했다. 실제 native boundary support 없는 추가 Area draw 거부도 검사했다.

GPU pass factory의 실제 `draw` 인자 연결은 **명시적 CPU spy instrumentation**으로 검증했다. spy는 production에서 허용하지 않는다. 이는 원본 GL shader 실행이나 픽셀 결과가 아니다. Synthetic Fixture의 좌표·수치·객체는 역사 자료가 아니며 Production 데이터 catalog에 등록하지 않는다.

별도 Python 검증에서 Draft 2020-12 schema 자체와 합성 request를 검증했고, 실제 Python→Node canonical compiler bridge가 PASS했다. 실제 GPU 실행·비용·사용자 품질 승인·FINAL 승격은 수행하지 않았다.
