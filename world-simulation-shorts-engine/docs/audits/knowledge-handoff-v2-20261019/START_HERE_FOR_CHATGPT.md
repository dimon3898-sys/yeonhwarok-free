# WORLD ENGINE 지식 인계 V2 — 먼저 읽기

이 문서는 현재 Studio가 실제 수용하는 입력과 저장된 독립 기능을 구분한다. 기능 이름이 저장소에 있다는 이유로 프롬프트에서 호출 가능하다고 쓰지 않는다. 이번 작업은 문서 감사이며, 구현·렌더·이미지 교체·배포를 수행하지 않았다.

## 고정 기준

- 저장소: `dimon3898-sys/yeonhwarok-free`
- 조사 소스: `c0f2868e9cab8a269c2bd8552dc09920e5e53863`
- 문서 브랜치: `audit/world-engine-knowledge-handoff-v2-20261019`
- 운영 태그: `studio-proxy-v1-4589328-39085567166-1`
- 운영 digest: `sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da`
- 이미지 실제 소스: `83bf1e0c7fc5955d9ff1d06441264f4c0d5a702b`. 태그의 `4589328`을 이미지 전체 소스 commit으로 해석하지 않는다.
- 태그·digest manifest를 이번에 각각 HTTP 200으로 확인했다. Docker 독립 pull은 기존 immutable 증거를 재사용했다. 실제 운영 컨테이너의 현재 입력·출력·환경 설정을 읽었다는 뜻은 아니다.

## 현재 가능한 입력

휴대폰에서 **80초 / V4 · 근사·부분 역사 자료**를 선택하고 프롬프트 칸에 다음 JSON 자체를 넣을 수 있다. 이는 CPU의 실제 frozen backend에서 검증했으며 제작 시작을 실행하지 않았다.

```json
{"schema":"WORLD_ENGINE_STUDIO_PROMPT_V1","preset":"VERIFIED_FRONT_V4_80S","durationSeconds":80}
```

`durationSeconds`는 정수 80이다. 별도의 Scene을 첨부하지 않는 preset 예제다. Scene 첨부가 있으면 프롬프트 해석보다 우선한다. 이 예제는 기존 80초·2,400프레임·12장면 계획을 선택하며 새 역사·영토·부대 위치를 생성하지 않는다.

현재 inner prompt의 허용 필드는 `schema`, `preset`, `title`, `durationSeconds`, `profile`, `sceneJson`, `sfx`뿐이다. `title`은 작업 메타데이터이며 영상 자막 제어가 아니다. HTTP envelope와 프롬프트 칸의 JSON은 다르다. 자세한 구분·최대 지원 필드 예제·실패 코드는 [PROMPT_COOKBOOK.md](PROMPT_COOKBOOK.md)를 따른다.

화면의 SFX ON/OFF·음량이 프롬프트 내부 SFX 전체를 교체한다. 화면 기본은 70%, normalizer 기본은 65%다. 프롬프트에 넣은 custom cues/WAV가 현 UI에서 적용된다고 쓰면 안 된다. 구간 수정은 SFX 전용이다.

## 현재 불가능하거나 별도 연결이 필요한 것

- 자유 문장만으로 임의 주제를 조사하고 역사 Scene을 생성하는 기능은 현재 Studio에 연결되지 않는다.
- `renderIntent`, `map`, `territory`, `camera`, `militaryUnits`, `events`, `timeline`, `qualityGate`를 inner prompt에 추가하면 `STUDIO_PROMPT_FIELD_UNSUPPORTED`다.
- V4 원본 Scene에 카메라·재질·전선·부대 설정을 임의 추가하거나 바꾸면 frozen-plan 검증에서 거절한다. JSON 필드가 존재하는 것과 사용자가 수정 가능한 것은 다르다.
- 120/180/300/600초는 검증된 `UNIVERSAL_V3` 계획이 있어야 한다. V4 preset 숫자만 바꿔 늘릴 수 없다. 장편 NVIDIA 실행 성공을 이번에 검증하지 않았다.
- 독립 Event/Flow/Wave·Metric 연출, national unit tablets, scalar 영토 확장·moving frontier의 전체 연출은 현재 WAR 장편 프롬프트로 켤 수 없다.
- TTS/BGM/자막 코드는 기존 경로에 있으나 현재 Studio에는 연결되지 않는다. 현재 Studio는 자체 SFX·FFmpeg 경로를 선택한다.
- 후기 Dropbox OAuth/offline/durability 기능은 저장돼 있으나 이 운영 이미지와 분리된 계층이다. 기존 Secret을 삭제하거나 재인증할 근거는 아니다.

## 고급 5초 연출과 80초의 차이

현재 이미지에는 Reference V2의 고급 모듈이 포함된다. 그러나 장편은 그 5초 browser boot·scalar 영토·국가 표식·카메라 트랙을 실행하지 않는다. `front_adapter`는 ASTRA/source 재질, Area V3, 보수적 chapter 카메라와 native graphics를 선택한다. 따라서 코드 미포함으로 일괄 진단하면 틀린다.

기존 5초는 현대 가상 시나리오의 보완적인 승자/패자 영역이다. 80초는 제공된 역사 도식 상태와 근사·부분 원문 전선이다. 역사 부대 좌표는 비어 있고, 후기 archival 구간은 검증되지 않은 영토 채우기를 의도적으로 비운다. V3 자체 백색·금빛 전선과 카메라 확장은 존재하므로 전선·카메라 전체가 없다고 쓰는 것도 틀린다.

[END_TO_END_RUNTIME_TRACE.md](END_TO_END_RUNTIME_TRACE.md), [VISUAL_GAP_REFERENCE_VS_80S.md](VISUAL_GAP_REFERENCE_VS_80S.md), [BLOCKERS_AND_MINIMAL_INTEGRATION_PLAN.md](BLOCKERS_AND_MINIMAL_INTEGRATION_PLAN.md)에 경로·근거·후속 최소 연결안을 분리했다. 후속 구현은 이번 감사에서 실행하지 않았다.

## ChatGPT가 따라야 할 판단 순서

1. `CAPABILITY_CATALOG.json`의 해당 feature와 **8축**을 확인한다. `BUILT_IN_IMAGE=YES`만으로 호출 가능이라고 쓰지 않는다.
2. prompt schema의 allowlist와 `PROMPT_LINT_RULES.json`을 확인한다. 미지원 명령을 실행 가능한 예제로 만들지 않는다.
3. 직접 Scene은 `SCENE_JSON_CONTRACT.schema.json`과 실제 source/frozen backend 검증을 함께 적용한다. Schema PASS는 GPU admission이나 영상 품질 PASS가 아니다.
4. 근거는 `SOURCE_EVIDENCE_INDEX.csv`의 source commit·파일·줄·검사 결과로 확인한다. 경로는 저장소 루트 기준이다.
5. `OUTPUT_VERIFIED=NOT_VERIFIED`는 실제 영상 증거가 없다는 뜻이다. 과거 FINAL receipt, import 성공, WebGL admission을 현재 결과물 검증으로 대체하지 않는다.

분류 `PROMPT_CALLABLE`은 실제 필드·제한된 수정 명령으로 호출됨, `SCENE_ONLY`는 검증된 Scene/고정 profile/시스템 실행에 묶임, `NOT_WIRED`는 코드 연결 필요, `NOT_IMPLEMENTED`는 조사 범위에서 구현 없음, `NOT_VERIFIED`는 증거 부족이다. 시스템 기능의 `SCENE_ONLY`는 사용자 편집 필드가 있음을 뜻하지 않는다. 축별 YES는 정적 경로 증거일 수 있으며 이번 실행 관측과 구분한다.

## 파일 읽는 순서와 미확인 범위

먼저 이 파일과 Cookbook을 읽고, JSON/CSV로 기능·허용 입력을 검색한다. Scene 계약, Runtime Trace, 이미지 계보 순으로 연결을 확인한다. `SOURCE_TREE_INVENTORY.csv`는 4,681개 추적 경로의 메타데이터 목록이며 모든 파일 본문을 전수 의미 분석했다는 선언이 아니다. 조사 범위와 사각지대는 `AUDIT_VALIDATION_RESULTS.json`을 따른다.

첨부 레퍼런스 31.813초와 65422 Candidate 5초는 CPU 전체 디코딩했다. 실제 66430/80초 MP4와 비공개 운영 정규화 입력은 접근하지 못했다. 따라서 80초의 정적 반복·청록 화면·실제 성능·최종 시각 품질은 미검증이다. 공개 ZIP에는 문서와 안전한 예제만 넣고 영상·원본 데이터·Secret·비공개 진단 원문은 넣지 않았다.

## 인계 요약

[확인된 기능] Camera/Event/Flow/Area, ASTRA, 영토·전선, 표식, Planner, SFX·레거시 오디오, Studio·저장·복구를 증거와 8축으로 정리했다.

[현재 Studio에서 실제 호출 가능] 고정 V4 80초 preset, 검증된 장편 Scene, 화면 SFX 설정 및 SFX 구간 수정. 실제 렌더 성공은 이번에 미검증.

[Scene 전용] source-bound V3/V4 타임라인·카메라·Area와 내부 시스템 경로. 임의 Scene 편집 허용을 뜻하지 않는다.

[미연결/미구현] 고급 5초 전체 연출, 독립 Flow/Wave/Metric의 장편 선택, 역사 national unit 위치, 시각 구간 수정, 자유 자연어 조사·생성은 현재 Studio에서 사용 불가.

[80초 실패 원인 확정/미확정] 실행 graph·preset·data 차이는 소스로 확정. 실제 80초 픽셀·운영 입력·품질 실패 단계는 미확정.

[ChatGPT에 전달할 파일] 전체 ZIP을 전달하고 이 파일부터 읽도록 한다. 실행 예제는 Cookbook과 machine-readable 계약을 함께 사용한다.

[사용자 할 일] 문서를 검수한다. 실제 화면 비교를 추가하려면 기존 80초 완성 MP4와 민감정보를 제외한 receipt/Scene 식별자가 필요하다. 이번에는 재렌더·GPU·이미지 교체를 실행할 필요가 없다.

최종 상태: **USER_REVIEW_REQUIRED**.
