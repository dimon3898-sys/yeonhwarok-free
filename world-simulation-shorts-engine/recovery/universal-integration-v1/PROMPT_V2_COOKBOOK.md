# 실행 입력 V2 계약

이 문서는 새 독립 통합 경로의 입력 계약이다. 기존 운영 이미지의 V1 파서는 이 V2 프롬프트를 지원하지 않는다. 새 코드의 CPU 계약 검증과 실제 NVIDIA 영상 품질 승인은 별개다. 기존 이미지에서 V2를 붙여넣고 실행하도록 안내하지 않는다.

V2는 보호된 V4 자료 프리셋을 기존 V1 정규화 함수와 실제 원본 검증기에 전달한 뒤, 변경하지 않은 `videoPlan` 옆에 `integration` 설정을 추가한다. 실제 지리·역사 자료, 사건 시각, 부대 위치, 점령 영역을 프롬프트로 만들지 않는다. 현 자료는 부분·근사 역사 자료이며 정확한 전체 점령 지도라는 의미가 아니다.

## 모바일 입력 예제

새 통합 실행 경로에서 길이 **80초**, 자료 프로필 **V4_ARCHIVAL_80S**를 선택하고 Scene 파일을 첨부하지 않은 상태로 다음 JSON 전체를 제작 프롬프트에 붙여넣는다. 효과음은 화면의 ON/OFF·음량으로 지정한다. 이 예제 자체는 제작 승인 또는 GPU 실행 승인이 아니다.

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
  }
}
```

`title`은 화면 제목 메타데이터다. 지도 위에 설명 텍스트를 추가하는 명령이 아니다. `visualProfile`을 생략하면 위 다섯 기본값을 사용한다. `durationSeconds`는 정수 `80`이어야 하며 문자열 `"80"`, 소수 표기 `80.0`, 다른 길이는 이 보호 프리셋에서 거부한다. 다른 길이의 범용 V1 Scene 경로를 삭제하거나 변경하지 않는다.

## 실제 소비되는 설정

| 필드 | 기본값 | 허용 범위 | 실제 연결 및 제한 |
|---|---:|---:|---|
| `territoryOpacity` | 0.62 | 0.24–0.8 | 기존 Production Area 점령 면 합성. 검증된 면이 없는 구간에 새 점령 영역을 생성하지 않는다. |
| `frontCoreWidthPixels` | 4.8 | 2.5–7px | 자료에 있는 Front Line 중심 폭. 해안선이나 임의 장식선을 새 전선으로 만들지 않는다. |
| `frontGlowRadiusPixels` | 10 | 3–16px | 기존 실제 Front Line 주변광 반경. |
| `frontGlowGain` | 0.42 | 0.1–0.65 | 실제 Front Line 주변광 기여도. |
| `cameraApproachFrames` | 48 | 정수 12–120프레임 | 기존 보수적 native camera 접근 구간. 30fps에서 0.4–4초. 임의 줌·roll·카메라 경로 생성 명령이 아니다. |

고급 5초 Candidate의 모든 셰이더·아이콘·카메라를 이 다섯 설정으로 옮겼다는 뜻은 아니다. 데이터 계약과 보호 코드가 맞는 연결만 사용하며, 미연결 기능 및 역사 자료 부족은 전체 기능 판정표에 별도로 기록한다. 실제 효과의 크기·가독성은 렌더링 전까지 미검증이다.

## 효과음 입력과 충돌 처리

화면은 바깥 요청에 `sfx`를 보낸다. V2에서는 프롬프트와 화면의 효과음 설정이 다르면 `STUDIO_V2_SFX_CONFLICT`로 거부한다. 어느 설정이 적용됐는지 숨기지 않는다. 모바일에서는 위 예제처럼 프롬프트에서 `sfx`를 생략하고 화면 설정만 사용한다.

프로그램에서 화면을 거치지 않고 정규화할 때는 기존 효과음 계약을 그대로 사용할 수 있다.

```json
{
  "schema": "WORLD_ENGINE_STUDIO_PROMPT_V2",
  "preset": "VERIFIED_FRONT_V4_80S",
  "durationSeconds": 80,
  "sfx": {
    "enabled": true,
    "gain": 0.5,
    "exportWav": false
  }
}
```

효과음 큐의 사건 ID와 프레임은 기존 Scene의 실제 사건 범위와 일치해야 한다. 외부 음원·TTS·BGM은 이 계약에서 추가하지 않는다. 생략 시 기존 사건 전환 큐를 사용하고, `cues: []`는 큐 없음이다. 동일 사건·프레임·종류 중복은 거부한다.

## 지원하지 않는 입력

다음은 인식한 척하거나 무시하지 않는다. 최상위 또는 `visualProfile`에 넣으면 명시적으로 거부한다.

- 자유 문장만으로 사건 조사·역사 좌표·점령선·부대 위치 생성.
- `camera`, `cameraRollDegrees`, 임의 경로·자세·줌 좌표.
- `militaryUnits`, `unitMarkerScale`, 국기·군대 표식 자동 배치.
- `route`, 검증되지 않은 이동 경로·전선 확장.
- `approval`, `imageDigest`, `profileSha256`, 소스 해시나 GPU 승인 우회 값.
- V2 프리셋과 구체적인 `sceneJson` 첨부의 동시 선택.
- 120·180·300·600초를 V4 80초 프리셋으로 자동 늘리기.
- 역사 자료가 없는 구간의 상대 세력 점령 영역 역산·채우기.

허용되지 않은 필드는 `STUDIO_PROMPT_FIELD_UNSUPPORTED` 또는 `STUDIO_V2_VISUAL_FIELD_UNSUPPORTED`를 반환한다. 범위·자료형 오류는 `STUDIO_V2_VISUAL_VALUE_INVALID`다. 기존 데이터 검증 실패는 기존 `STUDIO_RENDER_PLAN_REJECTED`를 유지한다.

## 실제 호출 형태

```python
normalized = contract_v2.normalize_submission(
    {"prompt": json.dumps(v2_prompt),
     "durationSeconds": 80,
     "profile": "V4_ARCHIVAL_80S"},
    image_digest=verified_image_digest,
    backend=preserved_studio_runtime,
    parent_normalize=preserved_studio_contracts.normalize_submission,
)
```

`normalized["videoPlan"]`은 기존 V1 검증 결과와 동일하다. 추가 결과는 다음 sibling 설정이며, 서명·해시는 사용자 입력으로 받지 않는다. 독립 Studio/runtime이 검증된 소스에서 결합한다.

```json
{
  "integration": {
    "schema": "WORLD_ENGINE_UNIVERSAL_INTEGRATION_V1",
    "profile": "VISUAL_UNIFIED_V1",
    "visualProfile": {
      "territoryOpacity": 0.62,
      "frontCoreWidthPixels": 4.8,
      "frontGlowRadiusPixels": 10,
      "frontGlowGain": 0.42,
      "cameraApproachFrames": 48
    }
  }
}
```

V1 입력은 새 계약이 결과·기본값을 바꾸지 않고 기존 정규화 함수에 원본 요청 그대로 위임한다. V2 설정이 선택됐는데 새 실행 경로를 사용할 수 없는 경우 기존 영상 경로로 조용히 되돌리지 않는다.

## 검증 범위와 실행 차단

테스트는 `tests/test_contract_v2.py`에 있다. 이번 실행은 22개 PASS다. 기존 테스트 double을 재사용한 입력·스키마 검사 21개와 실제 frozen V3/V4 원본 검증기 검사 1개를 구분한다. 테스트는 GPU admission, claim 쓰기, 작업 시작 또는 렌더링을 실행하지 않는다. 실제 원본 closure가 없는 환경에서는 원본 검증 검사를 SKIP로 기록한다.

5초 실제 레퍼런스 비교와 사용자 품질 승인이 확보되기 전 80초 실행은 별도 실행 gate에서 차단해야 한다. 프롬프트에 임의 승인 값을 추가해 이 절차를 통과할 수 없다. 이 문서는 5초 또는 80초 NVIDIA 영상 품질 PASS나 기존 FINAL 승격을 선언하지 않는다.
