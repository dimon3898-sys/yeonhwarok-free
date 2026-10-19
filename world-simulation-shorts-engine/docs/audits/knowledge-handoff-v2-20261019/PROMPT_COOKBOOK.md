# Studio 실행 프롬프트 계약과 검증 예제

검사 기준: `c0f2868e9cab8a269c2bd8552dc09920e5e53863`. 운영 이미지: `sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da`. 이 문서는 실제 현재 파서의 계약이다. GPU 렌더링·유료 실행·새 이미지 빌드는 하지 않았다. `CONTRACT_TEST_RESULTS.json`은 기존 집중 검사 33개와 실제 frozen backend 예제 42개의 실행 결과를 구분한다.

## 먼저 알아야 할 입력 구분

- **휴대폰 제작 프롬프트 칸**에는 아래 `WORLD_ENGINE_STUDIO_PROMPT_V1` 객체 자체를 JSON 텍스트로 붙여넣는다.
- **HTTP 제출 envelope**는 `{"prompt":"<그 JSON 텍스트>","durationSeconds":80,"profile":"V4_ARCHIVAL_80S","sfx":{"enabled":true,"gain":0.65}}`다. 이 envelope를 프롬프트 칸에 다시 붙여넣지 않는다.
- **Scene JSON 첨부**는 원본 영상 계획 객체다. 제출 envelope나 이 문서의 JSON Schema 파일을 첨부하는 방식이 아니다. 실제 규격은 `SCENE_JSON_CONTRACT.schema.json`과 frozen backend 검증을 함께 적용한다.
- `WORLD_ENGINE_STUDIO_SUBMISSION_V1`은 정규화 **출력** schema다. 프롬프트 입력 schema가 아니다.

## 1. 검증된 최소 80초 프롬프트

화면에서 80초, `V4 · 근사·부분 역사 자료`를 선택한다. 별도 Scene 첨부 없이 다음 전체를 붙여넣을 수 있다.

```json
{
  "schema": "WORLD_ENGINE_STUDIO_PROMPT_V1",
  "preset": "VERIFIED_FRONT_V4_80S",
  "durationSeconds": 80
}
```

이 예제는 실제 frozen V3/V4 backend의 source binding과 plan validation을 통과했다. 80초·2,400프레임·12장면을 선택한다. 자료의 근사·부분 성격은 그대로다. 프롬프트로 정밀 역사 전선을 새로 만들지 않는다. `durationSeconds`를 `80.0`이 아닌 **정수 80**으로 쓴다. 현재 기본 계획의 값이 80.0이어서 UI 외부에서 `schema`와 `preset`만 보낸 경우에는 `STUDIO_DURATION_UNSUPPORTED`가 발생한다. UI는 별도 정수 80을 보내 이 문제를 피한다.

효과음은 **화면의 ON/OFF·음량 값**이 우선이다. 기본 화면은 ON·70%이며, API normalizer 자체 기본 gain은 65%다. 두 기본값을 혼동하지 않는다.

## 2. 실제 지원 필드를 모두 명시한 preset + SFX 예제

아래는 최소 크기 제한이나 모든 사건을 채운 최대 데이터를 뜻하지 않는다. 상호 배타적인 `sceneJson`을 제외한 **지원 preset 필드 전체와 6개 SFX 종류**를 사용한 검증 예제다.

```json
{
  "schema": "WORLD_ENGINE_STUDIO_PROMPT_V1",
  "preset": "VERIFIED_FRONT_V4_80S",
  "title": "한국전쟁 전선 변화 — 공식 지도 기반 부분·근사 자료",
  "durationSeconds": 80,
  "profile": "V4_ARCHIVAL_80S",
  "sfx": {
    "enabled": true,
    "gain": 0.65,
    "exportWav": true,
    "cues": [
      {
        "eventId": "OUTBREAK",
        "frame": 0,
        "type": "CLICK",
        "gain": 0.8
      },
      {
        "eventId": "OUTBREAK",
        "frame": 30,
        "type": "MECHANICAL_TICK",
        "gain": 0.8
      },
      {
        "eventId": "OUTBREAK",
        "frame": 60,
        "type": "OCCUPATION_COMPLETE",
        "gain": 0.8
      },
      {
        "eventId": "OUTBREAK",
        "frame": 90,
        "type": "MARKER_POP",
        "gain": 0.8
      },
      {
        "eventId": "OUTBREAK",
        "frame": 120,
        "type": "CAMERA_WHOOSH",
        "gain": 0.8
      },
      {
        "eventId": "OUTBREAK",
        "frame": 150,
        "type": "EVENT_TRANSITION",
        "gain": 0.8
      }
    ]
  }
}
```

직접 `{"prompt": "<위 JSON 전체>"}`를 normalizer에 전달한 검사에서는 gain 0.65, 6개 큐, WAV 요청이 그대로 선택됐다. **현재 모바일 화면은 `sfx={enabled,gain}`를 따로 보내므로 위 `cues`와 `exportWav`는 화면에서 실행되지 않는다.** 이는 병합이 아니라 전체 교체다. 화면 사용자는 ON/OFF·음량만 설정하고, 큐/WAV를 프롬프트로 제어했다고 주장하면 안 된다. 이 감사에서는 UI나 API를 새로 확장하지 않았다.

`title`은 작업 메타데이터다. 화면에 글자나 자막을 그리는 명령이 아니다. SFX 큐는 실제 plan의 eventId와 해당 반열린 frame 범위에 묶인다. 예제의 `OUTBREAK`는 이 공개 preset의 기존 사건 ID다. 다른 Scene에는 해당 Scene에서 검증된 ID를 사용해야 한다.

## 3. 검증된 Scene JSON 직접 입력

실제 검증된 원본 V3/V4 계획 파일을 첨부하고 UI의 길이·profile을 그 계획과 맞춘다. 첨부가 있으면 프롬프트는 해석하지 않는다. 따라서 “카메라 확대” 같은 문장을 함께 적어도 Scene은 바뀌지 않는다.

V4 경로는 허용된 immutable image binding 외에 원본 계획 전체와 정확히 일치해야 한다. 임의 `camera`, `territory`, profile 숫자를 추가한 Scene은 이 경로로 허용되지 않는다. `UNIVERSAL_V3`도 source hash·파생 chapter/geometry/work-scene metadata를 실제 validator가 검증하므로 임의 GeoJSON/자유로운 Scene 객체가 곧 실행 가능한 것은 아니다. 120·180·300·600초는 그 길이에 맞는 검증된 **UNIVERSAL_V3 계획**을 공급해야 한다. V4 80초 preset의 길이만 바꾸면 늘어나지 않는다.

기존 공개 저장본 [검증된 V4 80초 Scene JSON](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/c0f2868e9cab8a269c2bd8552dc09920e5e53863/world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery/VIDEO_PLAN_80S.json)을 파일로 사용할 수 있다. 파일 SHA는 `SCENE_TEMPLATE_INDEX.json`에 있다. 데이터·기존 Scene을 새로 만들거나 수정하지 않는다.

직접 API envelope 구조 예시는 다음과 같다. `<검증된 원본 계획 객체>`는 설명용 자리표시자이며 그대로 실행하는 JSON이 아니다. 실행 가능한 자료 파일과 hash는 별도 Scene 계약/자료 manifest를 따른다.

```text
{"sceneJson": <검증된 원본 계획 객체>, "durationSeconds": 80, "profile": "V4_ARCHIVAL_80S", "prompt": "외부 메모, 적용하지 않음"}
```

## 4. 시간 구간 SFX 수정 예제

**완료된 작업**의 시간 구간 25초 이상 35초 미만에 다음 중 하나를 넣는다.

```text
효과음 꺼줘
```

```text
효과음 음량 40%
```

```text
SFX ON
```

세 예제 모두 실제 원본 plan에서 CPU 실행했다. 결과는 `SFX_ONLY_RECOMPOSE`, `requiresGpu=false`, 영상 계획 불변, 12개 영상 장면 재사용이다. 이는 합성 계획 검증이며 실제 완성 MP4의 새 생성/다운로드 검증은 아니다. 범위는 정확한 프레임 경계여야 하므로 30fps에서 25.01초는 허용되지 않는다. 선택 구간 안에서 시작한 큐만 바꾸며 잔향·근접 큐 제한 영향은 인접 오디오 범위로 보고된다.

구조화 SFX 수정도 지원한다. HTTP 요청에는 `startSeconds`, `endSeconds`, `prompt`가 필요하고, 아래 객체 전체를 `prompt` 문자열로 전달한다.

```json
{
  "schema": "WORLD_ENGINE_STUDIO_REVISION_V1",
  "sfx": {"gain": 0.4}
}
```

`exportWav`를 이 구간 수정 객체에 추가하면 `STUDIO_REVISION_SFX_INVALID`다. 카메라·영토·전선·표식의 구간 수정은 현재 Studio MVP에 구현되어 있지 않다.

## 5. 지원하지 않는 명령

| 입력 | 현재 결과 |
|---|---|
| “한국전쟁을 조사해서 80초로 만들어줘” 자유 문장 | `STUDIO_STRUCTURED_PROMPT_REQUIRED`; 역사 조사 AI 호출 없음 |
| inner prompt에 `renderIntent`, `map`, `territory`, `camera`, `militaryUnits`, `events`, `timeline`, `qualityGate` | 각각 실제 검사에서 `STUDIO_PROMPT_FIELD_UNSUPPORTED` |
| 위 필드를 제출 envelope 최상위에 추가 | `STUDIO_SUBMISSION_INVALID` |
| “레퍼런스급”, “황금빛 지형”, “군대 아이콘 추가”, “전선을 더 밝게” | 현재 Studio 자연어 시각 제어 명령 없음 |
| “25초부터 35초까지 카메라를 확대하고 천천히 이동” | `STUDIO_VISUAL_REVISION_UNSUPPORTED` |
| preset 80초를 120초로 선택만 변경 | `STUDIO_DURATION_CONFLICT`; 역사/장면 자동 늘이기 없음 |
| 없는 eventId 또는 OUTBREAK frame=200 SFX | `STUDIO_SFX_INVALID`; 이벤트/위치 임의 생성 없음 |
| 다른 prompt schema 버전 사용 | 새 버전 처리 안 함; raw Scene으로 간주한 뒤 검증 거절 |
| `qualityGate: PASS` 또는 프롬프트 내 비용 승인 | 지원 필드 아님; 품질/비용 승인을 프롬프트로 우회 불가 |

## 6. 검증과 실행의 경계

사전검사는 입력을 읽고 검증한다. 정상일 때 UI는 submission을 저장하지만 영상을 시작하지 않는다. 제작 시작은 별도 동의·idempotency key·관리자 인증·CSRF·Origin·운영 정책·GPU admission·claim 검사 후에만 호출된다. 이 감사의 parser 검사에서는 시작/재시도/렌더/claim 쓰기를 호출하지 않았다.

JSON Schema 검사만으로 source closure, V4 동일성, GPU 상태, 영상 품질을 PASS로 판단할 수 없다. Schema의 `x-runtime-checks`와 실제 함수 검증이 필수다. 현재 Studio에서 호출되지 않는 독립 5초 기능은 프롬프트에 이름을 적어 활성화할 수 없다.

## 소스 근거

- `recovery/production-studio-mvp-v1/studio_contracts.py:151–217` — exact allowlist, preset/Scene 선택, 우선순위, 길이/출력 규격.
- `recovery/production-studio-mvp-v1/studio_contracts.py:233–343` — SFX 전용 수정, frame 범위, visual revision 거절.
- `recovery/production-studio-mvp-v1/studio_audio.py:111–153` — 실제 event-bound SFX 종류·gain·큐 규격.
- `recovery/production-studio-mvp-v1/web/app.js:16` — UI가 보내는 실제 envelope와 SFX 우선순위.
- `recovery/production-studio-mvp-v1/web/app.js:55–61` — 사전검사/시작/수정 단계 구분.
- `recovery/production-studio-mvp-v1/web/index.html:7–15` — UI 길이·profile·70% 기본값·수정 제한.
- `recovery/production-studio-mvp-v1/server.py:326–355` — 실제 HTTP route와 수정 요청 필드 제한.
- `recovery/production-studio-mvp-v1/studio_runtime.py:98–169` — frozen backend 검증·image binding·V4 exact parent.

위 경로는 모두 기준 commit에 대한 인용이며 문서 생성 시 기존 파일은 변경하지 않았다.
