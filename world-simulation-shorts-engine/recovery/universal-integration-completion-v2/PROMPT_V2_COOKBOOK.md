# Studio V2 completion 실행 입력 계약

이 문서는 **새 독립 completion 후보 경로**의 실행 입력이다. 기존 운영 이미지나 이전 V2 코드가 아래 `completion` 필드를 지원한다는 뜻이 아니다. 실제 후보 이미지 포함 여부는 배포 manifest와 전체 결과 보고서를 확인한다. 코드·CPU 검증은 실제 NVIDIA 영상 품질 승인과 별개다.

기존 V1과 이전 V2 입력은 변경하지 않는다. `completion`이 없으면 저장된 이전 V2 정규화 함수에 그대로 위임한다. `completion`이 있으면 이전 함수의 고정 Scene·자료·오디오 검증을 그대로 수행하고, 기존 `integration` 옆에 `completionV2`를 추가한다. 원본 `videoPlan`, 역사 자료, 영토 상태와 사건 날짜를 변경하지 않는다.

## 모바일에서 붙여넣을 프롬프트

새 completion 실행 경로에서 길이 **80초**, 자료 프로필 **V4_ARCHIVAL_80S**를 선택하고 Scene 파일을 첨부하지 않는다. 다음 JSON 전체가 제작 프롬프트다. 효과음은 화면 설정으로 지정하므로 프롬프트에서 `sfx`를 생략한다.

```json
{
  "schema": "WORLD_ENGINE_STUDIO_PROMPT_V2",
  "preset": "VERIFIED_FRONT_V4_80S",
  "title": "한국전쟁 전선 변화 — 부분·근사 역사 자료",
  "durationSeconds": 80,
  "profile": "V4_ARCHIVAL_80S",
  "visualProfile": {
    "territoryOpacity": 0.62,
    "frontCoreWidthPixels": 4.8,
    "frontGlowRadiusPixels": 10,
    "frontGlowGain": 0.42,
    "cameraApproachFrames": 48
  },
  "completion": {
    "schema": "WORLD_ENGINE_UNIVERSAL_COMPLETION_V2",
    "profile": "VISUAL_UNIFIED_COMPLETION_V2",
    "dataPolicy": "QUALIFIED_SOURCE_ONLY",
    "camera": {
      "mode": "V5_EVENT_TRACKING",
      "settleFrames": 18,
      "holdFrames": 24
    },
    "frontier": {
      "profile": "AUTHORED_FRONT_MOTION_V2",
      "enabled": true,
      "motionResponse": true,
      "settledStrength": 0.2,
      "settleFrames": 18
    },
    "eventFlow": {
      "schema": "WORLD_ENGINE_COMPLETION_EVENT_FLOW_V1",
      "events": [],
      "flows": [],
      "areas": []
    }
  }
}
```

이 입력이 문법적으로 유효해도 80초 작업 시작이 허용되는 것은 아니다. 원본 자료·구현 경로·보안·GPU 운영 정책과 **5초 실제 비교 및 사용자 품질 승인 gate**가 별도로 적용된다. 승인 값을 프롬프트에 넣어 통과할 수 없다. `title`은 제작 메타데이터이며 지도 위에 설명 문구를 추가하는 명령이 아니다.

현재 프리셋에는 도식 상태와 일부 공식 근사 전선이 있다. 완전한 양측 점령 영역, 역사적 부대·국기 위치, 검증된 이동 경로가 모두 확보된 상태가 아니다. 위 `eventFlow` 배열이 비어 있는 이유는 데이터가 없는 표식·이동을 만들지 않기 위해서다. 기존 Scene의 Area·Front Line·사건 시간축은 그대로 유지된다. 빈 배열을 Event/Flow 기능이 영상에 적용됐다는 증거로 보고하지 않는다.

## 실제 지원 필드

| 위치 | 기본값·허용값 | 실제 의미 |
|---|---|---|
| `durationSeconds` | 정수 `80` | 고정 V4 자료 프리셋. `80.0`·문자열·다른 길이는 거부. 다른 길이의 기존 범용 V1 경로는 보존. |
| `visualProfile.territoryOpacity` | 0.62, 0.24–0.8 | 기존 검증된 영토 면의 불투명도. 자료 없는 상대 점령 영역을 채우지 않음. |
| `visualProfile.frontCoreWidthPixels` | 4.8, 2.5–7px | 실제 자료 Front Line 중심 폭. |
| `visualProfile.frontGlowRadiusPixels` | 10, 3–16px | 실제 Front Line 주변광 반경. |
| `visualProfile.frontGlowGain` | 0.42, 0.1–0.65 | 실제 Front Line 주변광 기여도. |
| `visualProfile.cameraApproachFrames` | 48, 정수 12–120 | 기존 카메라 접근 기간. V5 추적 모드에도 30fps 기준 접근 초로 전달. |
| `completion.dataPolicy` | `QUALIFIED_SOURCE_ONLY` | 자료 역할·범위·불확실성 유지. 다른 정책 거부. |
| `completion.camera.mode` | `V5_EVENT_TRACKING` 또는 `PRESERVE_PARENT` | 원본 V5 컴파일·평가기를 사용하는 추적 어댑터 또는 기존 카메라 유지. |
| `completion.camera.settleFrames` | 18, 정수 6–60 | V5 추적 안정화 구간. |
| `completion.camera.holdFrames` | 24, 정수 0–120 | 추적 후 최소 유지 구간. 나머지 장면 시간은 최종 포즈 유지. |
| `completion.frontier.profile` | `AUTHORED_FRONT_MOTION_V2` | 제공된 실제 전선과 결합한 움직임 반응. 임의 전선 생성 없음. |
| `completion.frontier.enabled` | `true` | `false`이면 기존 전선 owner 유지. 사용하지 않는 움직임 설정 동시 지정 금지. |
| `completion.frontier.motionResponse` | `true` | 움직임 반응 사용. `false`이면 `settleFrames`·`settledStrength` 지정 금지. |
| `completion.frontier.settledStrength` | 0.2, 0–1 | 정지 후 발광 기여도. |
| `completion.frontier.settleFrames` | 18, 정수 1–120 | 정지 후 자연스러운 감소 구간. |

`completion.camera: {"mode":"PRESERVE_PARENT"}`는 허용된다. 그 안에 `settleFrames`·`holdFrames`를 함께 넣으면 무시하지 않고 `STUDIO_COMPLETION_CAMERA_SETTING_CONFLICT`로 거부한다. 추적 모드에서 장면 시간·safe area·연속성을 만족하지 못하면 readiness를 차단하며 기존 카메라로 조용히 대체하지 않는다.

`completion.frontier: {"enabled":false}` 또는 `{"motionResponse":false}`도 명시적 선택이다. 비활성 모드가 소비하지 않는 안정화 설정은 `STUDIO_COMPLETION_FRONTIER_SETTING_CONFLICT`다. 이 표현이 원본 고급 scalar 점령 셰이더와 같거나 지형 인식 황금 조명이 완성됐다는 뜻은 아니다. 해당 계약이 맞지 않는 기능은 별도 BLOCKED 항목으로 유지한다.

## 검증된 Event·Flow·Area 추가

`completion.eventFlow`는 `EVENT_FLOW_REQUEST.schema.json`과 기존 Core 컴파일러의 canonical plan 검증을 함께 통과해야 한다. 배열별 최대 32개다.

- `events`: `{id, startFrame, plan, sourceBindings}`. 기존 Event V1 canonical timeline 사용.
- `flows`: `{id, plan, sourceBindings, routeVisibility, arrivalAreaId?}`. 기존 Flow V2 canonical plan 사용. 최종 제작에서는 `routeVisibility:"HIDDEN"`만 허용해 장식 경로·화살표를 추가하지 않는다.
- `areas`: `{id, plan, sourceBindings}`. 기존 Area V3 canonical plan 사용.
- `sourceBindings`: `{role,sourceId,sha256}` 참조. 역할은 해당 계약의 `GEOMETRY`, `METRIC`, `OBJECT_GRAPHIC`, `FLOW_PLAN`, `AREA_INTENT` 중 허용된 항목만 사용. Flow는 geometry·object graphic뿐 아니라 역할·시각을 뒷받침하는 `FLOW_PLAN` 자료 참조도 필요하다.

Canonical plan은 기존 Core에서 만든 정확한 결과여야 한다. 모르는 nested 필드를 추가하면 재컴파일·canonical 비교에서 거부한다. 사용자가 hash를 적었다는 이유로 자료를 신뢰하지 않는다. 서버가 소유한 immutable source catalog의 SHA와 **실제 payload**가 맞아야 제작 경로가 허용된다. `VERIFIED:true`와 같은 자기 선언은 지원하지 않는다. 검증된 역사 경로·표식이 없는 현재 입력에 synthetic 좌표를 넣지 않는다.

## 효과음과 부분 수정

효과음 입력은 기존 계약을 재사용한다. 프롬프트와 화면에서 서로 다른 `sfx`를 지정하면 `STUDIO_V2_SFX_CONFLICT`로 거부한다. 모바일에서는 프롬프트에서 `sfx`를 생략하는 것이 가장 간단하다.

완성 영상의 시간 구간 수정은 현재 **SFX만** 지원한다. 예: `효과음 음량 40%`, `효과음 끄기`. 새 `revision_bridge.plan_revision`은 기존 원본 수정 함수를 호출하고 `videoPlan`, `integration`, `completionV2`가 전부 유지되는지 검사한다. 기존 장면 전부 재사용·GPU 불필요가 확인돼야 새 수정 입력을 저장한다. metadata 누락·변경은 차단한다.

“25초부터 35초 카메라 확대”처럼 시각 변경을 요청하면 기존 `STUDIO_VISUAL_REVISION_UNSUPPORTED`를 유지한다. 시각 수정이 구현된 것처럼 효과음 수정으로 처리하지 않는다. 기존 완성본·claim·캐시는 삭제하지 않는다.

## 명시적으로 지원하지 않는 명령

- 자유 문장만으로 역사 조사·전선 좌표·점령 사건·부대 위치 만들기.
- 임의 카메라 자세·roll·강제 근접 zoom 좌표와 카메라 엔진 교체.
- 도시 marker에서 군대 위치를 추론하거나 상대 점령 영역을 complement로 채우기.
- 자료 없는 군대·국기·소련 지상군 추가.
- `approval`, `imageDigest`, `sourceManifestSha256`, 신뢰 상태를 사용자 입력으로 선언하기.
- 정밀 쓰나미·유체·군사 전술·선박·항공 물리 simulation.
- TTS·자막·BGM 생성 또는 gCube 자동 배포·정지.
- 임의 시각 구간 수정, V4 프리셋을 자동 120~600초로 늘리기.

지원하지 않는 필드는 무시하지 않고 원본 V2 오류 또는 `STUDIO_COMPLETION_*` 오류로 반환한다. 전체 기능별 상태는 151개 기능 판정표와 53개 미연결 검토표를 사용한다. 화면에 나타나지 않는 내부 기능을 사용자 knob로 노출하지 않는다.

## 프로그램 호출

```python
submission = completion_contract.normalize_submission(
    {"prompt": json.dumps(v2_prompt),
     "durationSeconds": 80,
     "profile": "V4_ARCHIVAL_80S"},
    image_digest=verified_immutable_image_digest,
    backend=preserved_studio_runtime,
    parent_normalize=preserved_studio_contracts.normalize_submission,
)

revision = revision_bridge.plan_revision(
    submission, 25, 35, "효과음 음량 40%",
    parent_revision=preserved_studio_contracts.plan_revision,
)
```

`normalize_completion`은 metadata를 독립적으로 검증하는 함수다. 원본 source SHA 검증·실제 payload admission·GPU 승인 gate는 runtime에서 별도로 수행한다. CPU Node 호출은 기존 Event/Flow/Area Core의 구조·canonical 검증이며 WebGL 또는 GPU 렌더링이 아니다.
