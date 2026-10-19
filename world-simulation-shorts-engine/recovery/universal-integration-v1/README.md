# WORLD ENGINE 통합 후보 V1 — CPU 검증 완료, 필수 통합은 부분 차단

기준 감사 151개 ID와 미연결 53개를 모두 검토하고 새 버전의 입력·표현·Studio 연결을 구현했다. 기존 FINAL/Candidate·렌더러·데이터·운영 이미지는 수정하지 않았다. **한국전쟁 80초 전체 구현/영상 품질 PASS가 아니다.**

## 완료한 안전한 연결

- `WORLD_ENGINE_STUDIO_PROMPT_V2`의 엄격한 파서·JSON Schema를 추가했다. V1 정규화는 원본에 그대로 위임하며 frozen V4 `videoPlan`은 변경하지 않는다.
- 실제 기존 Area 팩터리가 소비하는 영토 opacity·전선 폭·halo 반경·gain, 기존 V5 확장의 접근 frame 수를 별도 표현 계층으로 전달한다. 원래 Geometry·마스크·카메라 최소 범위를 보존한다.
- 독립 Studio entry에서 기존 HTTPS·관리자 인증·CSRF·Origin·사전검사·동의·idempotency를 재사용한다. V2를 구 렌더러로 조용히 대체하지 않는다.
- 입력 전체에서 만든 capture signature를 분리된 private cache/작업 ID에 연결했다. 기존 완료 job/claim을 삭제하거나 재사용하지 않는다. 상태 조회는 검증된 job→capture index로 해당 범위를 찾는다.
- 기존 detached worker·NVIDIA admission·공통 GPU lease·VRAM 감시·FFmpeg·SFX·저장 경로를 버전별 source-bound wrapper로 연결했다. worker의 원본 오디오 helper 경로를 보장했다. 이 경로의 실제 GPU 실행은 미검증이다.
- 실제 기존 선택 함수를 2,400프레임 전체에서 CPU로 실행해 trace를 남겼다. 실제 WebGL draw/readPixels/MP4 증거로 바꾸어 표기하지 않았다.
- 필수 source/data/image와 비공개 5초 사용자 품질 승인 gate가 없으면 80초 실행을 차단한다. 승인값은 prompt에 넣을 수 없다. 기존 GPU 비용·시간·재시도 검사는 유지한다.

## 판정 결과

151개: SUPPORTING **87**, BLOCKED **22**, UNVERIFIED **27**, NOT_APPLICABLE **15**, APPLIED **0**. APPLIED는 대상 실제 출력까지 증명해야 하므로 이번 CPU 단계에서 만들지 않았다. `FEATURE_DECISIONS_151`과 `UNWIRED_REVIEW_53`은 원본 ID·축·근거를 보존한다. 53개를 모두 공개 API로 강제 노출하지 않았다.

2,400프레임은 초기 무이벤트60, 기존 도식 영역1,490, 부분 전선 고정850으로 선택된다. 전선 고정850프레임에 양측 점령 영역을 추정해 채우지 않는다. 연속 전선 morph, 역사적 부대 이동, 양측 점령 전체 자료는 제공되지 않았다.

## 남은 핵심 차단

1. 검증된 양측 점령 Polygon, 국가별 부대 시점·역할·위치/route, 연속 전선 상태가 없다. 현대 가상5초 fixture를 한국전쟁 사실로 복사할 수 없다.
2. 고급5초 scalar frontier의 실제 지형 조명, closer zoom/roll, 전체 Detail Adapter는 이번 다섯 설정으로 연결되지 않는다. 보존된 엔진을 강제로 대체하지 않았다.
3. V2의 구간 SFX 수정은 metadata를 유지하는 revision bridge가 아직 없어 명시적으로 차단한다. 기존 V1 entry의 기능은 보존됐다.
4. 새 코드는 현재 운영 이미지8ef393에 없다. 새 GPU 이미지 digest는 없다. 현재 gCube 화면에 V2를 붙여넣으면 지원된다고 주장하지 않는다.
5. 실제5초/80초 신규 MP4, NVIDIA draw/readPixels, 외부 Dropbox 다운로드·시각 품질은 이번에 검증하지 않았다. 실제66430/80초 영상도 접근 불가다.

## 입력·자료 읽기

- `PROMPT_V2_COOKBOOK.md`, `STUDIO_PROMPT_V2.schema.json`: 정확한 필드와 미지원 명령.
- `fixtures/V2_80S_PROMPT.json`: **새 entry의 입력 검증용** 실제 V2 JSON. CPU에서 frozen backend로 검증했다. 입력이 valid여도 ready/renderAllowed는 false다.
- `fixtures/SCENE_TEMPLATE_REFERENCE.json`: 기존 raw Scene의 URL·SHA. 이 참조 객체 자체를 Scene 입력으로 넣지 않는다.
- `reports/FEATURE_DECISIONS_151.json/.csv`, `reports/UNWIRED_REVIEW_53.json/.csv`: 전수 판정표.
- `reports/TIMELINE_80S_COVERAGE.json/.csv`:12장 전체 자료·기능 coverage.
- `reports/FRAME_SELECTION_TRACE_2400.ndjson`: CPU 선택 증거. 실제 렌더 frame이 아니다.
- `reports/DATA_PROVENANCE.md`, `reports/HISTORICAL_BLOCKERS.json`: 역사 자료와 ASTRA 범위·라이선스·NoData 한계.
- `reports/TEST_RESULTS.json`: 집중 CPU 검사132개 PASS, SKIP0. 명시한 factory/backend spy는 실제 GPU가 아니다.

## 범용성과 실제 지원 범위

알고리즘에 국가 좌표·전쟁 날짜를 분기하지 않았다. 남반구·서반구 합성 입력으로 같은 표현/카메라 API를 검사했다. 합성 입력은 실제 역사 결과로 표기하지 않는다. 현재 Studio V2의 배포 가능한 데이터 카탈로그가 임의 국가·주제를 지원한다는 뜻은 아니다. 새 검증 Scene/자료 공급·admission 연결은 별도 필요하다.

ASTRA 원본3종은 서로 다른 지역 샘플이다. 원본24개 해시 검증·수집을 반복하지 않고 기존 receipt와 관련 manifest를 재사용했다. 실제 지원 밖은 기존 재질로 fallback하며 고도/수심을 만들어 채우지 않는다.

## 저장·다음 단계

작업 브랜치: `development/universal-integration-v1-20261019`. 중요한 CPU 체크포인트와 공개 산출물을 별도 commit→push한다. 원격 commit/다운로드 증거는 별도 publication receipt를 따른다.

현재 **gCube에서 변경할 설정은 없다. GPU를 배포하거나 제작 시작을 누르지 않는다.** 먼저 자료·연결 차단을 해결한 후 신규 immutable image를 검증하고, 실제 현재 요금·최대 비용·시간·재시도 상한을 확인해 5초 GPU 실행을 별도 승인해야 한다. 실제5초 레퍼런스 비교·사용자 품질 승인 전80초 제작과 FINAL 승격을 금지한다.

전체 판정: **UNIVERSAL_INTEGRATION_PARTIAL_BLOCKED**. 다음 GPU 단계 상태: **USER_APPROVAL_REQUIRED**(현재 자료/연결 차단이 남아 있으므로 유료 실행 승인을 바로 요청하지 않음).
