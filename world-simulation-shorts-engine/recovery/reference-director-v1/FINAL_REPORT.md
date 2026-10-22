# Reference 64306 실행 결과

**판정: `CAPABILITY_EXTENSION_REQUIRED / DATA_DETAIL_BLOCKED`. 실제 재현 영상 및 영상 품질 PASS는 없습니다.**

기준은 `82854af429d09aebb4b31c2f168e2f0ddc9560c9`, 새 브랜치는 `development/reference-director-v1-20261022`입니다. README → MASTER → 분석 문서·목표 JSON·전체 CSV 순서로 확인했습니다. 첨부 문서는 실행 요구와 측정 근거로 구분했으며, 미바인딩 목표를 기존 실행 가능한 Scene으로 오인하지 않았습니다.

## 확인된 원인

1. **공통 지도 회전 연결이 없습니다.** `renderer.mjs:561`의 `updateCamera`는 bounds만 받습니다. 같은 파일의 flat terrain fragment `:132`는 회전 없는 UV→경위도 샘플링입니다. 지도/GIS/경계와 지형을 함께 회전시키는 공개 forward/inverse 훅이 없습니다. 기존 framebuffer 복사·회전 경로는 이번 MASTER가 금지하므로 재사용하지 않았습니다. 보호 파일을 수정하거나 비공개 내부 상태를 monkey patch하지 않았습니다.
2. **초근접 자료가 없습니다.** 기존의 국가·두 장소 데이터는 부분 연결할 수 있으나, 핵심 장소의 검증된 Point·정밀 Polygon·순서 있는 실제 경계 LineString·상세 지도 소스는 부족합니다. 문맥 채색/국경 스타일 선택도 미바인딩입니다. 없는 지형·국경·정밀도를 만들어 채우지 않았습니다.
3. **기존 V2 소비 경로가 이번 연출과 다릅니다.** 현재 경로는 Area/Flow와 마커 중심이며 location/metric 텍스트 소비가 꺼져 있습니다. 모든 영역·마커를 safe 안에 강제하는 규칙도 이번의 viewport clip/context cull과 다릅니다. 이 차이를 문서화하고 별도 연출 계약으로 구현했으며 기존 기본값은 바꾸지 않았습니다.

## 실제 구현·검증

- 카메라 수학: 화면 앵커/두 점/실제 폴리곤 맞춤, C1 중심·log scale·연속 각도, 회전한 네 viewport 모서리 역투영, 전체 전역 경로의 소스 검사, 180/180/186프레임 창 계약.
- 이벤트: 투명 구멍 핀 스타일, 한 번의 팝인, grapheme 공개, 원본 지리 선 길이에 따른 reveal, 지리 중점 metric 배치, 역할·시점별 가시성. 실제 native-map consumer와의 연결은 미완료입니다.
- 읽기 전용 Studio preflight: 기존 관리자 인증·Origin·CSRF를 재사용합니다. 새 요청은 실제 HTTP에서 검사되지만 미충족 제작은 409로 차단하며 제출·claim·worker를 만들지 않습니다. 기존 UI·운영 이미지는 변경하지 않았습니다.
- 미바인딩 546프레임의 authoring 이벤트를 컴파일하고 입력 대응 CSV 4,914행을 작성했습니다. 실제 camera·projection·pixel bbox는 `null` 또는 빈 칸이며 `NOT_EXECUTED_BLOCKED`입니다. 완성된 Scene/camera track으로 표시하지 않았습니다.
- 독립 검수에서 새 모듈의 metric 법선 반전·source arclength 혼용·projection 입력 오류를 재현하여 수정했습니다. 원본 입력·기존 코드나 테스트 기준을 바꿔 통과시키지 않았습니다.

## 테스트와 원본 확인

| 검증 | 실제 결과 |
| --- | --- |
| 기존 회귀 검사 | **503 PASS / 0 FAIL / 0 SKIP**; 성공 재실행 중복은 집계하지 않음 |
| 새 카메라 수학 | **19 PASS**; 이전 17개 실행 로그 보존, 최종 19개로 한 번 집계 |
| 새 이벤트 규칙 | **24 PASS**; source arclength/metric normal 독립 검수의 재현·회귀 포함 |
| 새 Studio preflight | **12 PASS**, 실제 localhost HTTP 인증·Origin·CSRF 포함; native render 아님 |
| 실제 데이터 무결성 | **4 PASS**; 국가·위치·7개 등록 지도 소스의 실제 bytes/hash/license 대조 |
| 부분 트랙/제작 차단 | **4 PASS**; 최종 코드·부분 입력으로 546행/4,914행 재계산 일치 |
| 원본 MP4 | 파일 SHA 일치, 실제 BGR 픽셀 SHA **635/635 일치**, PTS 일치 |
| 명세 자료 | 원본 635행/계획 546행/카메라 575행/핀 228행/경계 118행 확인 |
| 실제 레퍼런스 static draw/MP4 | **미실행** — 필수 capability/data 게이트 실패 |

새 집중 검사 합계는 **63 PASS**입니다(19+24+12+4+4). 별도로 실제 Chromium에서 핀 2종과 글리프 3개를 래스터화하여 투명 구멍·크기·ink 중앙/하단 정렬을 검사했습니다. `evidence/EVENT_COMPONENT_DRAW.png`는 컴포넌트 증거이며 지도/Studio 출력이 아닙니다. 파란 텍스트 halo·개별 글자 GPU pop·native 지도 투영과의 합성은 아직 픽셀 consumer로 구현되지 않았습니다.

기본 sandbox의 localhost/Chromium 실행 제한은 코드 결함으로 취급하지 않았습니다. 공식 도구의 승인된 실행 경로로 필요한 검사만 재개했고, 실패 시도와 변경 없는 재실행 로그를 남겼습니다.

## 보호·비용

보호 307개 원본 SHA, 기준의 전체 6,746개 Git 파일, 기존 3개 worktree, 4개 캐시 경로의 1,059개 메타데이터를 취득·재검증했습니다. 최종 결과는 `reports/PROTECTION_FINAL.json`에 보존합니다. 캐시 메타데이터 검사는 캐시 내용 전체의 재해시와 구분합니다. 이 작업은 기존 캐시에 쓰지 않았습니다.

원본 영상과 디코딩 원본 이미지는 비공개 분석 위치에 유지합니다. 공개 패키지에 포함하지 않았습니다. 원본 UI·자막·워터마크를 새 영상으로 합성하지 않았습니다. 공개 파일의 명시적 Secret 패턴 최종 검사 결과는 `reports/SECRET_SCAN_FINAL.json`에 있고 앞선 검사 기록도 보존합니다.

유료 GPU/API 사용, 배포, 80초 렌더링, FINAL 승격: **전부 미실행**. NVIDIA 또는 실제 Android 기기의 품질 검증은 하지 않았습니다.

## 제출되지 않은 영상과 다음 조건

`REF64306_A_CONTEXT_6S.mp4`, `REF64306_B_FOCUS_6S.mp4`, `REF64306_C_BOUNDARY_METRIC_6P2S.mp4`와 원본/렌더 비교 PNG는 없습니다. 필수 조건이 실패한 뒤 대체 영상이나 placeholder를 만들지 않았습니다. 실제 지도 12개 시점과 두 가상 fixture의 native draw도 미실행입니다.

재개에는 **한 파일의 opt-in 공통 회전·역투영 훅에 대한 한정된 변경 승인**과 **검증된 상세 지리·지도 자료**가 필요합니다. 정확한 함수·최소 변경은 `CAPABILITY_GAP_AND_PATCH_MAP.md`, 누락 필드와 허용 형식은 `REFERENCE_DIRECTOR_INPUT.json`의 `gate.missingBindings`, 재개 순서는 `REMAINING_LIMITS.md`에 있습니다. 현재 새 프로필을 운영 Studio에 배포하거나 렌더링을 시작할 설정 변경은 권하지 않습니다.

**USER_REVIEW_REQUIRED** — G3는 계속 BLOCKED이며 사용자 승인 전 FINAL 승격하지 않습니다.
