# WORLD ENGINE 통합 completion V2 — 검수 결과

**판정: 부분 통합 완료. 전체 통합 PASS·80초 제작 허용은 아님. `USER_REVIEW_REQUIRED`.**

V1 원격 `61c7fc3`에서 이어 새 브랜치 `development/universal-integration-completion-20261019`에 저장했다. 기존 소스·FINAL·Candidate·Scene·Asset 변경은 **0건**이다. GPU 실행·영상 렌더링·gCube 배포·과금·FINAL 승격은 하지 않았다.

## 실제 연결한 범위

- 기존 V5 컴파일러·평가기·native factory를 새 Studio completion 선택 경로에 연결했다. 실제 12장면·2,400개 CPU 카메라 상태와 장면 경계 연속성을 확인했다. 최초 접근을 보존하고 이후 11장면 추적·10장면 turn을 선택한다. 레이아웃·draw는 명시적인 CPU spy이며 렌더링 증거가 아니다.
- 기존 Area·Front 소비자를 전역 frame과 제공된 원본 전선에 결합했다. 원본 Geometry·영토 속도·전선 엔진은 보존했다. 현 역사 입력에는 동일 ID의 연속 좌표 변화가 **0프레임**이므로 실제 전선 이동 연출이 개선됐다고 주장하지 않는다.
- 기존 Event V1·Flow V2·Area V3의 canonical plan 및 실제 소비자를 자료 역할·SHA·payload 검증과 연결했다. 현재 80초 입력의 추가 배열은 비어 있으며, 역사적 이동 객체·부대가 화면에 추가됐다는 뜻은 아니다. 추가 Area가 기존 전선을 가릴 수 있으면 그리기 전에 차단한다.
- 입력 → private submission → capture signature → 기존 독립 실행 관리자 → 원본 bounded encoder·SFX·내보내기 경로의 metadata 전달과 SFX-only revision bridge를 연결했다. 임의 카메라·영토 부분 수정은 미지원으로 유지한다.
- 원본 자료 4개 JSON의 실제 바이트뿐 아니라 평가할 plan·front 객체도 대조한다. root와 12개 장면의 승인된 이미지 digest 재바인딩만 허용하고, 장 제목·Geometry 변조는 거부한다.
- CI에서 확인한 기반 이미지의 원본 Scene 누락을 해결했다. 저장된 commit의 JSON·GeoJSON 13개만 추가하며, 기존 파일이 다르면 덮어쓰지 않는다.

정확한 입력과 호출 경로는 [STUDIO_INPUT_AND_LIMITS](STUDIO_INPUT_AND_LIMITS.md), [CALL_GRAPH](CALL_GRAPH.md)에 있다.

## 151개·53개 전수 추적

| 범위 | SUPPORTING | BLOCKED | UNVERIFIED | NOT_APPLICABLE | APPLIED |
|---|---:|---:|---:|---:|---:|
| 전체 151개 | 103 | 18 | 15 | 15 | 0 |
| 기존 미연결 53개 | 19 | 18 | 5 | 11 | 0 |

`SUPPORTING`은 소스·계약·보조 기능 근거다. 103개가 모두 새 Studio 버튼으로 노출되거나 실제 영상에 적용됐다는 의미가 아니다. 기능별 CPU 근거는 **52개**, renderer consumer CPU 계측은 **32개**다. GPU 근거는 **151개 모두 NOT_VERIFIED**다. 각 축과 SHA 근거는 [151개 표](FEATURE_LEDGER_151.csv), [53개 표](UNWIRED_LEDGER_53.csv), [연결 receipt](CONNECTION_RECEIPTS.json)에서 확인할 수 있다.

## 80초 제작 준비 상태

80초·30fps·1080×1920·2,400프레임·12장면 입력은 실제 기존 검증기를 통과했다. 소스 선택은 **60프레임 사건 Geometry 없음 / 1,490프레임 도식 held-core / 850프레임 근사·부분 사료 전선만 표시**다. 부분 전선에서 상대 영토를 추정해 채우지 않는다.

새 이미지 등록 후 같은 prompt를 실제 검증기로 다시 처리한 [후보 입력](../fixtures/CANDIDATE_80S_SUBMISSION.json)과 [이미지·자료 결합 receipt](CANDIDATE_INPUT_VALIDATION.json)도 보존했다. 원래 Scene은 그대로이며 허용된 13개 이미지 digest 경로만 새 후보에 결합했다.

기존 5개 도식 상태와 8개 부분 전선은 `FACT_BASED_VISUAL_GRADE`의 한정된 인포그래픽 자료로 인정한다. 전체 양측 점령선·관측된 일일 전선·국가별 부대 위치를 확보한 것은 아니다. ASTRA는 기존 지역 샘플과 실제 마스크·범위 밖 fallback을 유지한다. 장면 05·07의 정확한 날짜 근거는 부분 검증 상태를 유지한다.

[프레임 CSV](FRAME_SELECTION_TRACE_2400.csv), [12장면 기능표](CHAPTER_FEATURE_COVERAGE.json), [자료·불확실성](HISTORY_ADMISSION.md)에 근거를 보존했다. SFX는 48kHz 기준 3,840,000샘플·프레임당 1,600샘플의 CPU 시간축 정합을 확인했으며 실제 WAV·AAC·MP4를 생성하지 않았다.

## 남은 차단 사항

- **18개 BLOCKED:** 역사적 부대·이동·운송 자료/연결 11개, 추가 Detail·roll·scalar 영토·지형 인식 전선 조명 계약 7개다. 정확한 목록과 최소 입력은 판정표와 [누락 자료 사양](MINIMUM_MISSING_DATA.json)에 있다. 제한된 기존 도식 영상의 자료 자체를 전부 부정하는 blocker는 아니지만, 요청된 고급 전체 프로필의 완성을 의미하지도 않는다. 현재 full completion 제작 gate는 차단을 유지한다.
- **15개 UNVERIFIED:** 지도·ASTRA·SFX의 실제 출력 9개, 조건부 추가 Detail 1개, 비활성 백업 4개, 기존 실제 80초 입출력 1개다. 새 GPU 영상 증거로 대체하지 않았다.
- 기준 65379 파일은 보존되어 있으나 이전 66430 실제 영상은 없다. 이번 작업에서 직접 픽셀·시간축 비교는 수행하지 않았다.
- 새 프로필의 **150프레임 전용 preview 실행 범위 연결은 아직 미구현**이다. 80초를 통째로 실행해 5초 검수를 대신하지 않는다. 자세한 선행 조건은 [5초 준비 점검표](GPU_5S_READINESS.md)에 있다.

## 무료 검증·후보 이미지

집중 CPU **157 PASS / 0 SKIP**. 기존 전체 테스트와 ASTRA 원본 재조사는 반복하지 않았다. Secret Scan **0건**. 필수 temp-only 파일 **0개**.

무료 공개 GitHub Actions에서 실제 컨테이너 소스 검증·fail-closed 시작 검사·빌드·GHCR 등록·독립 runner digest pull을 완료했다. [CI 증거](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39262218752)

- 소스 commit: `c5167ac6f61d4d32008b22a28a45ac05c8032670`
- 태그: `completion-v2-c5167ac6f6-39262218752-1`
- 이미지: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:a956c93e4b23bc1f73990d94948c85e4db0c2f18f0bdef301f61ad7882be4886`
- source manifest SHA: `99caa40a2c7566982f5c5502ce4d5ce95e35367dc5809c8e7013ca4e83c7b3e9`

이는 **후보 소스 포함·CPU 무결성 검증**이다. 현재 gCube 교체·NVIDIA 실행·모바일 영상 품질 PASS가 아니다.

## 다음 행동

이번 결과와 미연결 목록을 검수하면 된다. 지금은 gCube 배포·제작 시작·Secret 재입력 작업이 없다. 필수 미연결 계약과 자료, 5초 preview 경로를 해결한 뒤 별도 비용 승인으로 5초 실제 비교와 사용자 품질 검수를 진행해야 한다. 그 전까지 80초 렌더와 FINAL 승격은 차단한다.
