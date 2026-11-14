# WORLD ENGINE — 범용 생성기 최상위 제작·개발·검증·배포 MASTER

사용자 확정: 2026-11-14 (Asia/Seoul). 이번 공통 입력 확장부터 이후 WORLD ENGINE 작업에 적용한다. 기존 증거와 유효 PASS는 보존한다.

## 1. 목표와 책임

하나의 검증된 범용 GPU 실행 이미지 버전과 외부 JSON·역사 데이터로 다양한 영상을 반복 제작한다. 기술 총괄은 실행 전에 구조적 충돌, 이미지 기능 누락, 입력 불일치, 분할 초기화, 검증 중복, 비용 발생을 먼저 확인하고 예방한다. 새 생성기를 만들지 않는다.

공통 이미지에는 GPU 환경, Chromium/WebGL2/EGL/Vulkan, 정식 Controller/Worker/Capture, 지도·역사·연속 영토·카메라·라벨·효과 엔진, 프레임/MP4 출력과 진단을 둔다. 주제·국가·연도·사건·좌표·도형·지도 범위·카메라·라벨·효과 타이밍·장면·출력 규격은 버전 및 무결성이 검증된 외부 입력으로 둔다. 외부 데이터는 코드 실행, 임의 모듈 로딩, 임의 파일/URL 접근 권한을 얻지 않는다.

## 2. 이미지 운영

운영 기준은 검증된 공통 이미지 하나이며 이전 성공 이미지는 복구용으로 유지한다. 새 역사 주제, 연도, 좌표, 카메라 속도, 이미 지원되는 효과/길이 때문에 빌드하지 않는다. 공통 엔진 코드, 실제 공통 기능 누락, 보안/GPU 환경, 입력 호환 계약 변경에만 필요성을 입증한 뒤 새 공통 버전을 준비한다. 이미지 자체는 불변이므로 코드 갱신 시 새 digest가 필요하며, 주제별 이미지와 구분한다.

## 3. 시작 게이트

원격 HEAD → 작업 브랜치/미커밋 상태/동시 작업 → CHECKPOINT → 기존 PASS와 마지막 실제 GPU 성공 → 운영 이미지 digest/입력 계약 → 최초 미완료 단계를 확인한다. 최신 커밋은 보존한다. 유효한 완료 단계는 SKIP한다. 기존 PASS를 재검증하려면 무효화된 항목·구체적 증거·영향 파일/기능·최소 검사를 먼저 기록한다.

선행 FAIL/BLOCKED에 의존하는 후속 작업은 중지한다. 독립적인 무료 조사·설계는 계속할 수 있다. 도구 실패는 체크포인트를 보존하며 작업 처음부터 재시작하지 않는다.

## 4. 사전 위험 질문

1. 현재 범용 생성기로 가능한가?
2. 구현된 기능이 있는가?
3. 운영 이미지에 포함됐는가?
4. 실제 GPU 성공 경로와 호환되는가?
5. JSON만 바꾸면 되는가?
6. 공통 코드 수정이 필요한가?
7. 빌드가 정말 필요한가?
8. 기존 성공 기능의 영향은 무엇인가?
9. 다른 역사 주제에서도 재사용 가능한가?
10. GPU 실행 전 무료로 확인할 수 있는 것은 무엇인가?

증거와 추정을 구분해 답한 뒤 구현/빌드를 시작한다.

## 5. 증거 상태

`CODE_COMPLETE`, `UNIT_TEST_PASS`, `INTEGRATION_TEST_PASS`, `IMAGE_INCLUDED`, `INPUT_COMPATIBLE`, `GPU_RENDER_PASS`, `MP4_VERIFIED`, `PRODUCTION_READY`를 따로 관리한다. 코드 PASS가 이미지 포함을, 이미지 포함이 GPU 성공을, 프레임 생성이 최종 MP4 검증을 의미하지 않는다. Mock·계약 시험은 실제 실행 receipt와 구별한다.

## 6. 성공 경로 보호와 GPU 연결

실제 성공 당시 tag/digest/source commit, GPU와 driver, Chromium 인수, EGL/Vulkan 환경, Controller/Worker/Capture, 프레임과 MP4 증거를 수정 불가 기준 자료로 보존한다. 미회수 값은 추정하지 않는다. 현재 노드 정상 여부는 별도다.

이미지 시작 → 장치/driver → EGL/Vulkan 준비 → Controller → Worker → Capture → WebGL2 → 첫 프레임 → 전체 프레임 → MP4를 하나의 환경 전달 계약으로 관리한다. 환경변수, UID/GID, 파일 권한, 허용 descriptor 경로, NVIDIA library/ICD, 선택 backend, 실제 Pod digest를 확인한다. 소프트웨어 렌더링을 GPU 성공으로 오인하지 않는다. 초기화 오류를 영상 길이 탓으로 단정하지 않는다.

## 7. 범용 입력과 분할

공통 스키마는 프로젝트·주제 식별, 규격, 글로벌 타임라인, 지도, 역사 이벤트, 영토, 카메라, 라벨, 효과, 출력 설정을 다룬다. 특정 국가/연도 전용 필드나 하드코딩을 추가하지 않는다. 새 공통 필드에는 버전과 하위 호환을 관리한다. 외부 자료의 사실 검토와 SHA 무결성은 별개다. 사용자가 VERIFIED라고 쓴 것만으로 역사 자료를 승인하지 않는다.

길이는 지원 범위 내에서 데이터로 제어한다. 정식 분할은 글로벌 프레임·카메라·투영·영토·라벨·효과 진행·유지 시간·속도를 보존한다. 분할마다 초기화하지 않는다. 승인 없는 삭제/압축/가속 금지. 분할 계약 PASS가 GPU 성공을 뜻하지 않는다.

## 8. 품질

레퍼런스 64306.mp4의 지도/지형 디테일, 영토 경계 움직임, 카메라 이동·확대 리듬, 장면 유지, 라벨 가독성, 강조 타이밍, 연속성과 편안한 속도를 기준으로 한다. 짧다고 연출을 압축하지 않는다. 실제 MP4 확인 없이 시각 품질 PASS를 선언하지 않는다.

## 9. 빌드 게이트

현재 이미지에서 불가능한 이유, 기존 공통 코드/외부 입력 대안, 필요한 정확한 코드 변경, 주제 독립성, 성공 경로 보존, 무료 변경 범위 검증, 하위 호환성을 기록한다. 모두 충족하면 기존 정식 Dockerfile·생성·manifest·startup·게시 경로로 범용 후보를 만든다. 정확한 소스 커밋·manifest·원격 digest를 연결하고 이전 이미지를 보존한다.

## 10. 유료 실행 게이트

매 실행 전 목적, 이미지/digest, GPU 모델, 최대 시간/비용, 재시도, 성공 기준, 실패 종료 조건을 제시하고 별도 승인을 받는다. 초기화 실패 시 전체 영상으로 넘어가지 않는다. 원인 분석 없는 반복 실행 금지. 종료 후 실제 중지 상태를 확인한다.

## 11. 결함 처리

원본 오류 → 실패 단계 → 기존 성공 비교 → 원인/증상 구분 → 공통 기능 영향 → 최소 수정 → 변경 범위 무료 검증 → 실제 결함을 검출하는 재발 검사 → CHECKPOINT → GitHub 증거 저장 순서를 따른다. 미해결이면 BLOCKED를 유지한다.

## 12. 자동 진행과 중지

사용자 개입이 필요 없는 조사·비교·입력 생성·스키마 검사·무료 CPU 검사·기록·저장은 연속 진행한다. 유료 실행, 계정 승인, 중요한 설계 조건 변경, 기존 PASS 무효화, 해결되지 않은 선행 BLOCKED, 데이터 손실 위험은 해당 게이트에서 중지한다. 사용자 승인이 이미 있는 범위는 반복 질문하지 않는다.

## 13. 저장과 최종 흐름

저장소 `dimon3898-sys/yeonhwarok-free`, 브랜치 `fix/reference-6s-formal-admission-20261113`. main 수정/reset/force push/기존 증거 삭제 금지. CHECKPOINT에는 현재 단계, 완료, 유효 PASS, 신규 검사, 최초 미완료, 차단, 운영 이미지, 스키마, GPU 승인, 다음 행동을 기록한다.

제작 흐름: 입력 분석 → 기능 대응 → 이미지 호환 → 영상 데이터 → 무료 검사 → 배포 준비 → GPU 승인 → 정식 렌더 → MP4/시각 검증 → 결과 보존. 각 단계의 증거를 다음 단계의 선행 조건으로 쓴다.

## 14. 현재 몽골 작업

기존 600프레임과 106개 도형은 보존한다. 사용자 승인대로 [0,180), [180,360), [360,540)만 출력하고 [540,600)은 제외한다. 재분배/가속/새 장면 금지. 이전 성공 이미지의 HISTORICAL 미지원은 확인된 사실이다. 최신 공통 코드를 기준으로 외부 역사·영토 데이터와 글로벌 구간을 정식 지원하도록 최소 확장하는 것은 이번 MASTER에서 승인됐다. 몽골 전용 생성기/이미지는 만들지 않는다. 범용 이미지 빌드는 실제 필요성과 무료 검증이 충족된 경우에만 진행한다. 현재 유료 GPU 승인 없음.
'''
cat > world-simulation-shorts-engine/recovery/universal-input-contract-v2/PRE_IMPLEMENTATION_REVIEW.md <<'EOF'
# 공통 입력 확장 — 구현 전 위험 및 변경 범위

기준 HEAD: 66e94bb19fbb8bdd32f42b5f051f4e190bae74d5. 사용자 MASTER 2026-11-14로 이전 scope-decision 차단은 해소됐다. 기존 GPU 성공/실패 증거와 기존 600 설계는 보존한다.

| 사전 질문 | 실제 근거와 판단 |
|---|---|
| 기존 엔진 처리 가능? | 지도/카메라/106개 continuous/effect 평가 기능은 이미 있다. 새 renderer가 필요하지 않다. |
| 기존 기능 존재? | history_authored_v1.mjs, presentation_runtime.mjs, HISTORY_SOURCE_CATALOG.json에 기존 연결이 있다. |
| 운영 이미지 포함? | 이전 성공 이미지에는 새 history 모듈이 없고, history20 이미지는 V1/600 경로만 포함한다. 현재 전체 범용 PRODUCTION_READY 이미지는 입증되지 않았다. |
| GPU 성공 경로 호환? | NVIDIA launch/lease/native guard/FFmpeg는 보존한다. 현재 노드 WebGL 장애는 독립 BLOCKED다. |
| JSON만으로 가능? | 불가. V1 compiler, Controller/Worker, backend 계약이 600/HISTORICAL 또는 6·10/nonhistorical로 고정돼 있다. |
| 공통 수정? | 버전 있는 외부 검토 자료 loader, 글로벌 frame window, 명시적 historical profile 전달이 필요하다. |
| 빌드 필요? | 위 공통 계약이 기존 이미지에 없어 향후 하나의 공통 버전 갱신은 필요하다. 검증 전 빌드하지 않는다. 신규 주제 자료는 이후 빌드 없이 교체한다. |
| 기존 기능 영향? | 새 명시적 V2 분기만 추가하고 기존 V1/6·10 경로를 보존한다. shared request validation/adapter derivation 변경은 해당 연결만 검사한다. |
| 재사용? | 국가명/연도/도형 개수를 코드에 넣지 않는다. server-approved 외부 catalog와 내용 해시로 dataset을 선택한다. |
| 무료 확인? | dataset hash/path/권한/심사 경계, 스키마/거부 조건, 글로벌 frame 및 상태 전달, Controller/Worker/capture 계약, generated/manifest, 실제 이미지 CPU 검사. |

## 보안·재현성 결정

- 데이터 파일은 코드와 분리하고 외부 immutable content-addressed package로 제공한다. 입력에는 dataset ID/version/hash만 둔다.
- 사실 검토는 기존 evidence owner를 유지한다. 별도 operator-configured catalog hash로 승인된 외부 자료만 로드한다. 사용자 JSON의 VERIFIED 주장, 임의 path/URL/module은 승인 권한이 없다.
- 새 V2의 출력 window는 기존 전체 source scene/presentation을 보존하고 capture가 해당 글로벌 frame을 평가한다. 라벨 종료/효과 진행 상태를 각 6초 경계로 재작성하지 않는다.
- 현재 지원 규격 1080×1920·30fps 및 실행 길이 6/10/20초를 명시한다. 검증되지 않은 규격/길이를 무제한 지원한다고 선언하지 않는다.
- 기존 V1 schema와 image/published evidence는 유지한다. 새 V2가 기존 이미지에서 작동한다고 표시하지 않는다.

## 재검증 범위 사전 기록

기존 reference/design/history/106 geometry/실제 GPU/MP4 PASS는 무효화되지 않았으며 재실행하지 않는다. 새 공통 분기로 변경될 adapter, request/profile validation, capture frame mapping, receipt 및 generated manifest의 이전 hash 기반 연결 증거는 **새 코드에 그대로 적용할 수 없다**. 따라서 신규 V2 요청과 변조 거부, 기존 분기 상수/선택 기본값 보존, source 대비 window 평가만 검사한다. 기존 전체 6초·10초·600프레임 suite/MP4 재생성은 금지한다. 변경된 일반 함수가 기존 의미를 바꾸는 결함이 발견되면 별도 최소 영향 기록 후 그 부분만 확인한다.

## 명시적 미해결 항목

현재 gCube 노드의 EGL/WebGL2 원인은 미확정이며 이번 입력 계약 개발과 독립이다. 무료 계약 PASS나 새 이미지 게시로 GPU_RENDER_PASS/PRODUCTION_READY를 선언하지 않는다. 실제 Pod image digest/환경 readback도 별도 게이트다.
