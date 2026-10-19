# 실제 Studio 입력과 현재 제한

새 completion 후보의 **정규화 가능한 입력**과 **지금 제작을 허용하는 입력**은 다르다. 아래 파일은 실제 원본 검증기를 거쳐 확인된 입력이지만 `renderReady:false`다. 기존 운영 이미지나 현재 gCube가 새 후보로 교체됐다는 의미는 아니다. GPU 실행·비용·배포 승인은 별도다.

## ChatGPT가 먼저 읽을 파일

| 파일 | 용도 |
|---|---|
| [정확한 80초 prompt](../fixtures/STUDIO_V2_80S_PROMPT.json) | 새 completion runtime용 inner JSON. 검증된 파일을 그대로 사용. |
| [실제 정규화된 80초 submission](../fixtures/VALIDATED_80S_SUBMISSION.json) | frozen `videoPlan` + sibling metadata. Studio의 Scene 첨부칸에 그대로 넣는 raw Scene 파일은 아님. |
| [입력 schema](../STUDIO_PROMPT_V2.schema.json) | strict V2 prompt·completion 필드와 조건. |
| [Event/Flow/Area schema](../EVENT_FLOW_REQUEST.schema.json) | canonical plan·자료 참조 계약. 추가 Core compiler 검증 필요. |
| [실행 예제 및 오류](../PROMPT_V2_COOKBOOK.md) | 기본값·범위·정확한 호출·미지원 명령. |
| [정확한 입력 CPU 검증](EXACT_INPUT_VALIDATION.json) | prompt·submission SHA, 2,400프레임·12장면, `gpuExecuted:false`. |

정확한 prompt receipt의 parser는 `ACTUAL_FROZEN_STUDIO_V4_PLUS_COMPLETION_V2`다. 입력 검증에 사용한 기존 immutable 이미지 참조는 **계약 검증용 바인딩**이며 새 후보 코드가 그 기존 이미지 안에 있다는 주장이 아니다. 새 이미지 tag·digest·독립 pull은 최종 이미지 보고서를 사용한다.

## 모바일에서의 최소 입력 절차

다음은 **후보 이미지 검증·필요 승인 이후**의 입력 방법이다. 현재 사용자에게 GPU 배포나 제작 시작을 요구하는 절차가 아니다.

1. 인증된 새 completion Studio에 로그인한다.
2. 길이 **80초**, 프로필 **V4 · 근사·부분 역사 자료**를 선택한다.
3. `STUDIO_V2_80S_PROMPT.json` 전체를 제작 프롬프트에 붙여넣고 Scene 파일은 첨부하지 않는다.
4. 이 정확한 파일에는 `sfx:{"enabled":true,"gain":0.65}`가 들어 있다. **효과음 ON·음량 65%**로 화면도 맞춘다. 기존 UI 기본값은 70%이므로 그대로 두면 `STUDIO_V2_SFX_CONFLICT`로 거부한다.
5. 사전검사를 실행해 결과를 확인한다. 필요한 gate가 남으면 제작 시작이 허용되지 않아야 한다.

화면의 효과음 설정만 쓰려면 prompt의 `sfx` 항목을 생략할 수 있다. 이것도 지원되는 계약이지만 원본 파일과 다른 입력·SHA가 되므로 위 정확한 fixture를 그대로 실행했다는 증거로 사용하지 않는다. 효과음 설정 충돌을 조용히 덮어쓰지 않는다.

## 지원되는 명시적 계약

inner prompt의 기존 필드는 `schema`, `preset`, `title`, `durationSeconds`, `profile`, `visualProfile`, `sfx`이며 새 경로에 `completion`을 추가한다. 알 수 없는 필드는 거부한다. 자유 문장을 역사 조사나 새로운 Scene으로 해석하는 AI가 아니다.

| 범위 | 실제 지원 | 제한 |
|---|---|---|
| 고정 자료 preset | `VERIFIED_FRONT_V4_80S` + `V4_ARCHIVAL_80S` | completion은 현재 정수 80초만 지원. raw Scene 첨부와 동시 선택 금지. |
| 영상 규격 | 1080×1920, 9:16, 30fps, 2,400프레임, 12장면 | 기존 source-bound Scene 검증 유지. |
| 기존 presentation | 영토 opacity, front core 폭·halo 반경·gain, camera 접근 frames | 정확히 다섯 필드만 지원. 범위는 schema 참조. 자료 없는 영역·전선을 생성하지 않음. |
| completion 정책 | `QUALIFIED_SOURCE_ONLY` | 전체 양측 점령·정밀 일일 전선·부대 위치를 확보한 것으로 격상하지 않음. |
| 카메라 | `V5_EVENT_TRACKING` 또는 `PRESERVE_PARENT` | 원본 V5/native factory 재사용. 임의 roll·자세·좌표·강제 근접 zoom 지원 아님. 사용되지 않는 설정은 충돌 오류. |
| 움직이는 전선 | `AUTHORED_FRONT_MOTION_V2` | 실제 제공된 front observation과 동기화. 없는 front·해안 장식선 생성 금지. terrain-aware scalar frontier 계약 부족은 별도 blocker. |
| Event·Flow·Area | 자료가 결합된 canonical plan 배열 | source ID·SHA만 적으면 신뢰하지 않음. server catalog의 실제 payload·역할과 일치해야 함. final route는 HIDDEN. |
| SFX | 원본 사건 cue·ON/OFF·gain·선택적 WAV | 기존 라이선스·시간축 검증. TTS·자막·BGM 없음. |
| 구간 수정 | 기존 SFX-only 수정·전체 영상 재합성 계약 | `videoPlan`·integration·completion identity 보존. 임의 시각 구간 수정은 미지원. |

`completion` 생략 시 저장된 이전 V2 정규화 동작을 유지한다. 기존 V1의 별도 검증된 Scene을 사용하는 120·180·300·600초 계약과 소스는 삭제하거나 재작성하지 않았다. 그러나 새 completion 80초 preset을 선택한 채 길이만 변경해 장편을 만들 수는 없다. 이전 장편 호환성을 실제 NVIDIA 600초 렌더 성공으로 보고하지 않는다. 새 entry에서 구형 입력으로 80초 quality gate를 우회할 수도 없다.

## 현재 한국전쟁 입력에 없는 것

현재 `eventFlow.events`, `flows`, `areas` 추가 배열은 비어 있다. 원본 Scene의 Area·Front·사건은 유지되지만 새 추가 Event/Flow를 실제로 요청했다는 의미는 아니다.

- 검증된 역사적 국가별 부대·국기 위치와 이동 route가 없다. 도시 marker에서 추론하지 않는다.
- 일부 근사 전선은 전체 양측 점령 polygon이 아니다. 한쪽 held-core의 나머지를 상대 점령으로 채우지 않는다.
- 사료의 작전 화살표를 실제 전선 또는 실제 이동 경로로 바꾸지 않는다.
- 소련 지상군 등 검증되지 않은 참전 역할·위치를 만들지 않는다.
- source endpoint 간 인포그래픽 전환은 관측된 매일의 전선 위치와 구분한다.
- ASTRA의 지역 sample 밖에는 보존된 fallback을 사용한다. 없는 고도·수심을 생성하지 않는다.

관련 최소 자료 요구사항은 [MINIMUM_MISSING_DATA.json](MINIMUM_MISSING_DATA.json)에 있다. 검증되지 않은 자료를 추가해 필수 모듈 gate를 통과시키지 않는다.

## 수정 요청과 결과 보존

“25초부터 35초 효과음 음량 40%”처럼 기존 SFX 요청만 처리한다. `revision_bridge`는 원본 SFX 수정 결과에서 `videoPlan`, `integration`, `completionV2`, 모든 장면 재사용과 GPU 불필요를 확인한다. 원본 완성본·claim·cache를 삭제하거나 새 후보의 것으로 취급하지 않는다.

“25초부터 35초 카메라를 확대해줘”, 영토·전선·군대 위치 수정은 `STUDIO_VISUAL_REVISION_UNSUPPORTED`다. 지원하지 않는 요청을 효과음 수정으로 축소해 성공 처리하지 않는다. SFX 수정도 검증된 완료 parent와 올바른 저장·실행 gate가 있어야 실제 수행할 수 있다.

## 차단과 승인 경계

- 문법·자료·source 무결성이 유효해도 이미지 포함·필수 모듈·운영 정책·실제 5초 비교/사용자 품질 승인 gate가 남아 있으면 `ready:false`다.
- 현재 부족한 국가별 역사 표식과 terrain-aware scalar frontier 계약을 숨기지 않는다. 전체 기능 연결 PASS나 APPLIED를 선언하지 않는다.
- CPU·Node·localhost HTTP 테스트는 실제 NVIDIA 업로드·draw·readPixels·영상 효과·성능 검증이 아니다.
- 새 5초 실제 후보와 reference 비교 및 사용자 승인 전 80초 렌더를 시작하지 않는다.
- 현재 80초 완성 MP4·mobile 외부 다운로드·Dropbox SHA 검증 결과를 새로 확보했다고 주장하지 않는다.
- 사용자 검수 전 FINAL 승격, 자동 유료 GPU 실행, gCube 자동 배포·정지는 수행하지 않는다.

사용자는 이 CPU 통합 작업을 위해 PC·터미널·Docker·Secret 재입력을 할 필요가 없다. 다음 실제 실행은 최종 보고서의 필수 blocker와 승인 항목을 확인한 뒤 진행한다.
