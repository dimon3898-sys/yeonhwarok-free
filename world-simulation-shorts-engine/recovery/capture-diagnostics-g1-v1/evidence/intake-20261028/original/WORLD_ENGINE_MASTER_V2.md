# WORLD ENGINE — 보존형 복구·출시 설계 MASTER v2
작성 기준: 2026-10-28 / Asia/Seoul
문서 상태: 설계 완료. 아래 통제와 진단 개선은 아직 운영 코드에 적용되지 않았다.
현재 제품 상태: GPU 첫 프레임 경로 FAIL, 6초 MP4 미완성.

## 1. 목표와 한계
기존 WORLD ENGINE을 폐기하거나 새 렌더러로 다시 만들지 않는다. 검증된 자산·Scene·렌더러·Studio 인증·해시 수정·게시 이미지는 보존한다. 바꾸는 대상은 실패 진단, 검증 범위, 배포 승인 및 결과 보존 절차다.

목표는 “앞으로 오류가 절대 없음”이 아니다. 이미 알려진 결함의 재발을 자동 검사로 막고, 새 실패가 생겨도 실패 연산·증거·복구 위치를 잃지 않도록 하는 것이다. 실제 결과 없는 PASS, 완료 시각 보장, 성공 확률의 임의 제시는 금지한다.

최종 제품 목표는 RTX 4080 SUPER에서 1080×1920·30fps·180프레임·6초·무음 MP4를 생성하고, 기술 검증과 별도로 영상 품질을 확인하는 것이다. 이후 국가·주제·사건을 Scene/데이터로 교체하는 범용 제작으로 확장한다. 80초 확장·새 UI·신규 생성기 기능은 이 성공보다 앞서 진행하지 않는다.

## 2. 보존 기준점 — 이미 완료된 것을 다시 만들지 않는다
- 저장소: https://github.com/dimon3898-sys/yeonhwarok-free
- 코드 수정: b8648e468d7c5780001511aa7dab7a5c297f97e1
- CPU 검증 기록: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/40660455589
- 출시 소스 기준 커밋: 478c6c33648e94f662673cab533bf14b74133f91
- 이미지 게시 기록: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/40664470151
- 이미지 태그: ghcr.io/dimon3898-sys/world-simulation-shorts-engine:capture-pin-v1-478c6c33648e-40664470151
- 이미지 digest: sha256:bedf23b0315666ea702f719a509147d6c97dc27f7b529de918e2708f8928997f
- 실제 파생 런타임 경로: /opt/world-engine-handoffs/studio-page-stage-v1/repo
- gCube #5373 / RTX 4080 SUPER ×1 / HTTP 8080 / 공유 메모리 3GB / Dropbox 마운트 /world-storage
- 마지막 실패 작업: studio-56ad1bf48706ff64201eda263de11d35
- 최신 확보 진단: /WORLD_ENGINE/capture-diagnostic-studio-56ad1bf48706ff64201eda263de11d35/CAPTURE_DIAGNOSTIC.json
- GPU 중지: 사용자 보고 있음. 이번 설계 작업에서 공급자 상태·과금 종료를 직접 확인한 것은 아님.

이 이미지는 “게시 및 사전검사 기준점”이다. GPU 영상 생성 성공 이미지 또는 정상 렌더러 복귀점이라고 부르지 않는다.
기존 PASS는 해당 소스·이미지·입력·환경에 한정한다. 변경되지 않은 부분의 증거를 재사용한다. 소스·의존성·환경 변경으로 무효화된 검사와 필수 실행 안전 검사는 필요한 범위에서 다시 한다. 무조건적인 재검사 금지와 무조건적인 전체 재검사는 모두 금지한다.

## 3. 지금 확정된 사실과 미확정 사실
### 확정된 사실
1. 캡처 variant pin 누락 수정과 CPU 검증은 이전 증거가 있다. 이번에는 기존 빌드 작업의 성공 상태만 읽었고 다시 실행하지 않았다. [S5, S6]
2. 최신 진단은 PAGE_EVALUATE_FIRST_NATIVE_DRAW, 0프레임, capture.code=null, cleanupVerified=true를 기록한다. missingEvidence.capture=false이므로 내보내기 시점에는 내부 receipt를 읽었다. 현재 그 원본이 남아 있다는 뜻은 아니다. [S1, S7]
3. FIRST_NATIVE_DRAW 블록은 런타임 생성·모듈 로딩·네이티브 검증을 함께 포함한다. 이 이름만으로 GPU 드라이버 오류나 실제 draw 호출 실패라고 확정할 수 없다. nvidiaVerified=false도 검증 완료 증거가 없다는 뜻이다. [S2, S3, S4]
4. safe_code는 메시지 전체가 고정 허용 코드와 정확히 일치할 때만 통과시킨다. page.evaluate 접두어가 붙은 메시지는 코드가 null로 변환된다. [S1]
5. 빌드 워크플로는 이미지 내부 Python 무결성 검사와, 러너 Node의 verifyGeneratedSources 실행을 한다. 후자를 “이미지 내부 JS 실행 검증”이라고 부르면 안 된다. Chromium/NVIDIA 드로우는 이 검사의 범위가 아니다. [S5, D1]

### 이번에 추가로 실행한 조사
GitHub에서 읽은 safe_capture_export.py를 변경 없이 로컬에 복사하고 Git blob SHA(6950a1b77a85c9edf49b2fd7c8c9675d1effbed3)가 일치함을 확인했다. 합성 receipt 6조건으로 기존 exporter를 실행했다. 알려진 코드 단독은 보존되지만, page.evaluate 접두어가 붙으면 null로 바뀌었다. native_guard의 일부 코드도 현 허용 목록에 없어 null이 된다. receipt 누락 표시와 cleanup 차단은 유지된다. [S8]
이것은 진단 정보 손실의 재현이지 실제 GPU 고장 원인의 재현·수정·렌더링 PASS가 아니다.

### 미확정 사실
실제 첫 실패 예외, 실패한 가장 안쪽 연산, GPU/브라우저/Scene 중 인과 원인, 종료 후 컨테이너의 원본 receipt 생존 여부는 미확정이다. Dropbox 검색 결과가 없다는 이유로 원본이 생성되지 않았다고 말하지 않는다.

## 4. 단일 작업 체계
Astra Work를 실행 조정 담당 1개로 정한다. Codex는 필요한 코드 변경에만 사용하고, GitHub Actions를 CPU 실행 검증 대상으로 사용한다. 동일 파일을 여러 에이전트가 동시에 수정하지 않는다. ChatGPT는 증거·변경 범위·사용자 승인을 검토한다. 이는 역할 설계이며, 이 문서로 원격 작업이 자동 시작된 것은 아니다.

CHECKPOINT.json을 상태의 기준으로 사용한다. 채팅의 PASS 문구가 아니라 commit, imageDigest, 입력 Scene 해시, 환경 식별값, 검사 범위, 증거 URI, 다음 소유자를 기록한다. 상태는 PASS / FAIL / BLOCKED / NOT_RUN / INVALIDATED로 구분한다. 모르는 값은 null과 사유로 남기며 임의 값으로 채우지 않는다.

실행 담당은 매번 기준점을 먼저 읽고 미완료 항목만 처리한다. 권한 부족이나 차단이 있으면 실제 실패한 도구·권한과 보존 결과를 기록한다. 안전 정책 차단을 다른 도구로 우회하지 않는다. “직접 할 수 있다”는 말은 실제 호출 성공으로 확인된 능력에만 쓴다.

## 5. 기존 엔진 위에 추가할 구조
기존 흐름을 유지한다.

주제/Scene → 입력·자산 검증 → 기존 계획 컴파일러 → 기존 브라우저 런타임 → 기존 GPU 드로우 → 캡처/인코딩 → 결과 보존 → 영상 품질 검수

주변에 세 가지 통제를 보강한다.
- Release Lock: 소스 커밋·파생 생성 절차·이미지 digest·manifest·실행 파일 버전을 연결한다.
- Evidence Recorder: 각 작업의 시작/종료/실패를 구조화하고 보존을 검증한다.
- Gate Controller: 검증 범위·실패 상태·승인 범위를 보고 다음 동작을 허용하거나 차단한다.

기존 controller/supervisor/인증·CSRF·승인·lease를 교체하지 않고 확장한다. 새 대형 플랫폼, 데이터베이스, 원격 관리 서비스, 별도 렌더러는 현재 범위 밖이다. UI와 GPU 작업을 별도 서비스로 분리하는 확장도 6초 성공 후 평가한다.

## 6. 최우선 수정: 오류가 사라지는 경로
### 오류의 구조화
브라우저 내부에서 알려진 domain error를 고정 코드로 분류하고, page.evaluate가 문자열을 덧붙이기 전에 JSON 직렬화 가능한 결과로 전달한다. Node에서 다시 스키마 검증한다. 문자열 전체를 오류 코드로 사용하거나 임의 정규식으로 비밀정보를 걸러냈다고 가정하지 않는다. [D1, D2]

첫 실패와 정리 실패를 별도 기록한다. 정리 과정의 예외가 원래 실패를 덮어쓰지 않도록 한다. timeout·page crash·프로세스 종료처럼 반환 자체가 실패하면 부모 프로세스가 마지막 확인 연산과 실패 유형을 기록한다.

최소 안전 필드:
runId, releaseId/imageDigest, sceneSHA256, operationId, lastCompletedOperation, failureKind, errorCode, recognized, exceptionType, sourceId/line/column(검증된 소스 식별자만), frameIndex, renderedFrames, nativeProofCompleted, cleanupStatus, evidenceStatus.

operationId는 최소한 입력/캔버스, 런타임 생성, WebGL 컨텍스트, 실제 렌더러 식별, 지도·텍스처 준비, native_guard import, draw, readPixels, proof 검증, PNG, encoder, export를 구분한다. 렌더러의 실제 호출 순서를 유지하며 계측 위치가 부족하면 필요한 함수 경계만 추가한다. 단순히 상위 단계 이름만 더 늘리는 수정은 불충분하다.

알 수 없는 예외도 UNCLASSIFIED_EXCEPTION 같은 고정 분류와 안전한 위치·단계를 남긴다. code:null만 내보내고 완료로 처리하지 않는다. 모든 임의 예외를 한 번에 근본 원인으로 변환할 수 있다고 약속하지 않는다.

### 보안과 관측성을 동시에 유지
Owner-code, 토큰, 쿠키, Authorization, 전체 환경변수, 전체 URL 쿼리, 요청/응답 본문을 기록하지 않는다. 임의 원본 에러·stack·trace를 공유 Dropbox나 CI 공개 artifact로 내보내지 않는다. 상대 소스 ID·숫자·고정 enum 중심으로 내보내고, 상세 정보가 꼭 필요하면 먼저 제거·제한·접근 통제를 검증한다. 인증 화면의 스크린샷/trace는 자동 수집하지 않는다. [D2]

공개 안전 진단과 원본 private receipt를 구분한다. 기존 private/public 디렉터리 분리와 cleanup 검증을 무력화하지 않는다. private receipt를 복사하기 위해 심볼릭 링크·권한·원본 검사 조건을 풀지 않는다.

### 사후 finally만 의존하지 않음
부모가 각 주요 연산 직전/직후의 제한된 안전 checkpoint를 기록한다. 최종 진단과 결과 목록은 임시 파일 작성·flush·원자적 교체 등으로 완료 상태를 표시한다. 전원 단절·공급자 강제 삭제까지 완벽히 보장할 수는 없으므로 마지막 확인 시각과 증거 누락을 별도 표시한다.

## 7. 실패 경로를 먼저 검증
기존 전체 엔진 테스트가 아니라 새 진단 계약의 실패 테스트를 추가한다.
- 브라우저에서 알려진 오류를 던져 코드와 내부 단계가 최종 안전 파일까지 동일하게 남는지 검사한다.
- TypeError/알 수 없는 오류, 모듈 import 실패, 자산 HTTP 실패, context 생성 실패, draw 실패, readback 실패를 구분한다.
- page crash/timeout/종료 상황에서 마지막 완료 연산이 남는지 검사한다.
- 정리 실패가 최초 실패를 덮어쓰지 않는지 검사한다.
- 저장 권한 거부·공간 부족·크기 제한 초과·연결 실패·업로드 확인 실패를 명시적으로 구분한다.
- 합성 비밀값을 넣어 안전 진단 및 CI artifact에 유출되지 않는지 검사한다. 보안 검증도 실패하면 출시를 막는다.
- GPU 없이 시험한 mock/소프트웨어 렌더러 결과에는 CPU_ONLY를 기록한다. NVIDIA 강제 조건을 꺼서 통과시키지 않는다.

합성 테스트는 로그 보존 계약만 증명한다. 실제 NVIDIA 픽셀과 영상 품질을 증명하지 않는다.

## 8. 이미지·환경 오류의 재발 방지
### 한 번 만든 후보를 같은 digest로 시험·게시·배포
새 후보를 패키징한 뒤 그 이미지 내부에서 실행 파일 위치, Node/Chromium/Playwright 버전, JS import, manifest, 서비스 라우트의 CPU로 검증 가능한 부분을 확인한다. /usr/bin/node 같은 경로를 추정하지 말고 이미지의 실제 경로와 PATH를 확인한다.

CPU 전용 환경에서 GPU 의존 ENTRYPOINT가 차단되는 경우를 성공으로 위장하지 않는다. 기본 ENTRYPOINT 계약 검사와 CPU 테스트용 harness를 구분하고, 실제 하드웨어 시작 검사는 GPU gate에 남긴다. CPU 환경의 가짜 자격증명은 실제 Owner-code와 분리한다.

검사 후 운영 이미지를 다시 빌드하지 않고 검사한 동일 이미지를 게시·배포한다. 실패 후보만 폐기 대상으로 표시하되 기존 사용자 이미지나 백업은 삭제하지 않는다. 이미 패키징된 기준 이미지의 JS 소스 파일이 repository의 오래된 generated 파일과 다를 수 있으므로, 파생 생성 절차·최종 manifest를 기준으로 연결을 확인한다.

### 해시를 사람이 따로 맞추지 않음
캡처 변경 → generated variant manifest → runtime manifest → bootstrap pin → startup manifest 순으로 하나의 생성 절차가 계산한다. 352개는 현 기준 이미지의 파일 수이며 임의 누락으로 숫자만 맞추지 않는다. 새로운 런타임 파일이 필요하면 등록과 계약 변경을 명시한다. 테스트 파일은 런타임 closure 밖에 둘 수 있다.

### 디스크·비용 사전점검
이미지 pull 전에 해당 Docker 데몬의 저장소, 남은 공간, 권한, 이미지 압축 해제·작업 복사·새 레이어의 최대 사용량 근거를 확인한다. 10GB 같은 임의 임계값만으로 충분하다고 보장하지 않는다. 부족하면 같은 pull/환경 교체를 반복하지 않는다. 공유 캐시·백업에 대한 일괄 prune은 금지한다.

GitHub Actions를 무조건 무료라고 부르지 않는다. 저장소 공개 여부, runner 종류, 무료 한도, artifact 저장량과 과금 차단 설정을 확인한 범위만 무과금 실행한다. 확인되지 않으면 비용 상태 UNKNOWN으로 두고 자동 유료 실행을 하지 않는다. [D4]

## 9. 증거 보존과 출시 판정
CHECKPOINT.json, RELEASE_LOCK.json, TEST_RESULTS.json, DIAGNOSTIC_SAFE.json, 필요한 안전 로그, SHA256SUMS를 실행 ID별로 묶는다. 구현 시 파일 이름은 기존 계약과 충돌하지 않게 버전 관리한다.

CI 결과는 workflow artifact로 남기고 artifact digest와 실제 파일 SHA256을 검증한다. 보존 기간을 명시하고 자동 만료 전에 필요한 작은 증거를 승인된 저장소에 보관한다. GitHub cache와 artifact를 동일시하지 않는다. [D3]

GPU 출력은 기존 Dropbox 경로 정책을 사용한다. /world-storage 로컬 파일 생성은 Dropbox 서버 저장 확인과 다르다. 원격 API로 파일을 다시 읽고 크기·SHA256을 확인한 뒤 STORAGE_PASS로 판정한다. 안전 로그 업로드의 제한된 재시도는 렌더링 재시도와 별개로 다루되 무제한 대기는 금지한다.

실패: 제한 시간 내 안전 증거 보존 시도 → 자식 프로세스 정리 → 공급자 Stop → 공급자 종료 확인 → 과금 상태 확인 순으로 정리한다. 증거 업로드 문제 때문에 유료 GPU를 계속 켜 두지 않는다. 로그 손실이 생기면 명시적으로 기록한다.
성공: MP4 및 증거 보존 → 기술 검증 → GPU 종료 확인 → 비용 없는 환경에서 영상 품질 검수한다. 품질 검수하려고 GPU를 켜 둘 이유는 없다.

cleanupVerified=true는 자식 정리의 증거이지 gCube Finished나 과금 종료 증거가 아니다. 공급자 종료 확인, 과금 종료 확인, 사용자 보고를 서로 구분한다.

## 10. 단계와 진입 조건
| Gate | 목적 | 통과 조건 | 현재 상태 |
|---|---|---|---|
| G0 | 기존 성과 보존 | 기존 증거/커밋/이미지/실패 작업 식별 | 증거 인수 완료, 기존 제품 PASS 범위 보존 |
| G1 | 진단 손실 수정 | 합성 실패가 최종 안전 파일까지 보존되고 비밀 유출 없음 | 결함 재현 완료, 수정은 NOT_RUN |
| G2 | 동일 후보 이미지 검증 | 실제 이미지 내 CPU 계약·실행 경로·무결성·증거 보존 확인 | NOT_RUN |
| G3 | 실제 GPU 원인 규명/실행 | 별도 단회 승인, 정확한 후보와 입력, 정지 담당, 안전 증거 확보 | BLOCKED |
| G4 | 실제 원인 수정 확인 | 최초 예외 또는 재현 증거에 근거한 최소 수정 및 영향 검증 | NOT_RUN |
| G5 | 6초 결과 완성 | 180프레임/해상도/fps/길이/무음/전체 decode/저장/종료/품질 | NOT_RUN |

G1/G2는 원인 규명에 필요한 진단 수리다. 렌더링 오류를 해결했다고 선언하는 단계가 아니다. G3에서 원인이 확인되면 G4에서 해결하고, 변경으로 무효화된 G1/G2 범위만 재검증한다. G3에서 실제 6초 렌더링까지 성공하더라도 G5의 기술·저장·품질 조건을 생략하지 않는다.

CPU에서 재현하지 못하는 하드웨어 문제는 실제 GPU 실험이 필요할 수 있다. 이는 추측 수정이 아니라 승인된 원인 규명 실험이다. 기존 기록을 확보할 수 없다는 이유만으로 자동 실행하지 않는다. G1/G2가 완료되고 무엇을 측정할지·실패 시 남을 증거·최대 횟수·정지 방법이 검증된 경우에만 별도 승인 요청한다.

기존 6초/180프레임 승인 계약을 임의로 1프레임 요청으로 바꾸지 않는다. 기존 runThreeNativeDraws의 최초 안정성 검증을 그대로 관문으로 사용한다. 그 증거가 없으면 인코더/후속 프레임으로 진행하지 않는다. 다른 probe 모드는 별도 계약·검증 없이 도입하지 않는다. [S2, S3]

## 11. 유료 GPU 승인 계약
현재 추가 GPU 실행 승인은 없다. 과거의 “실행”을 재사용하지 않는다.
승인에는 imageDigest, Scene 해시, workload, GPU, 실행 목적, 시작 허용 시각/만료, 최대 배포/렌더 횟수, 금액/시간 한도, stop 담당이 결합돼야 한다. 같은 요청의 중복 클릭·도구 재시도로 두 번째 렌더링이 생기지 않게 기존 lease와 작업 ID를 유지한다.

실패하면 자동 렌더 재시도는 0회다. 같은 이미지·입력·환경에서 같은 실패가 났고 새 정보가 없으면 재실행 금지다. 재시도하려면 수정 또는 검증할 가설과 관측 방법의 차이를 기록해야 한다.

기존 7,200초/10,000원 정책은 허용 상한이지 목표 사용량·현재 승인·공급자 강제 차단 보장이 아니다. 현재 요금이나 무료 한도를 추정하지 않는다. 원격 정지 도구가 없으면 사용자 수동 정지 가능 상태가 선행 조건이다. 실제 정지 제어를 할 수 없는데 자동 과금 종료를 약속하지 않는다.

## 12. 재발 방지 검수표
- 연결 주소: 과거 확인된 /login과 쿼리 없는 origin을 구분한다. 새 배포 주소는 공급자 화면/응답으로 확인한다. 관리자·로그인 URL은 복사용 코드블록으로 제공한다. ?utm_source 사례만으로 과거 모든 HTTP 오류의 원인을 확정하지 않는다.
- 포트: 입력 예시(placeholder)와 저장값을 구분한다. 8080과 8000은 실제 필드·프로세스 바인딩 증거 없이 수정하지 않는다.
- 해시: 파일 변경 시 연결된 manifest를 자동 생성한다. 무결성 검사를 비활성화하지 않는다.
- 실행 파일: 이미지 안에서 발견한 경로를 사용한다. runner 경로와 컨테이너 경로를 혼동하지 않는다.
- 디스크: 환경 교체 횟수를 늘리지 말고 데몬 저장소의 실제 공간 문제를 해결한다.
- 진단: 실패 원인이 모르는 상태임을 보존한다. generic code만 남는 진단을 완료로 표시하지 않는다.
- 권한: 접속·검색·수정·실행·Stop을 실제 도구별로 확인한다. 사용할 수 없는 Astra/Codex 세션을 실행했다고 말하지 않는다.
- 상태 보고: “확인된 결과 / 미확인 / 이번 변경 / 다음 담당 / 사용자 행동”만 짧게 보고한다. PASS에는 범위와 증거를 붙인다.

## 13. 이번 응답에서 실제 수행한 일 / 하지 않은 일
수행: 기준 소스 읽기, 기존 CI 결과 조회, 최신 Dropbox 진단 읽기, 원본 blob 해시 대조, 합성 6조건 exporter 재현, 이 설계·체크포인트·Astra 지시서 작성.
하지 않음: GitHub 코드 수정/커밋, CI 신규 실행, 이미지 빌드/게시, gCube 설정 변경/배포, GPU 실행, 원격 Astra 작업 시작.

즉시 다음 작업은 G1이다. 진단 손실이라는 확인된 결함만 먼저 고친다. 아직 확인되지 않은 GPU 고장 원인을 추측해서 렌더러를 수정하지 않는다.

## 14. 근거
- [S1] https://github.com/dimon3898-sys/yeonhwarok-free/blob/478c6c33648e94f662673cab533bf14b74133f91/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/controller/safe_capture_export.py
- [S2] https://github.com/dimon3898-sys/yeonhwarok-free/blob/478c6c33648e94f662673cab533bf14b74133f91/world-simulation-shorts-engine/recovery/capture-page-evaluation-evidence-v1/candidate_capture_vulkan.mjs
- [S3] https://github.com/dimon3898-sys/yeonhwarok-free/blob/478c6c33648e94f662673cab533bf14b74133f91/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/backend/native_guard.mjs
- [S4] https://github.com/dimon3898-sys/yeonhwarok-free/blob/478c6c33648e94f662673cab533bf14b74133f91/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs
- [S5] https://github.com/dimon3898-sys/yeonhwarok-free/blob/478c6c33648e94f662673cab533bf14b74133f91/.github/workflows/world-engine-capture-pin-image.yml
- [S6] https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/40664470151
- [S7] /WORLD_ENGINE/capture-diagnostic-studio-56ad1bf48706ff64201eda263de11d35/CAPTURE_DIAGNOSTIC.json
- [S8] evidence/diagnostic_loss_reproduction.json
- [D1] https://playwright.dev/docs/evaluating
- [D2] https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet
- [D3] https://docs.github.com/en/actions/tutorials/store-and-share-data
- [D4] https://docs.github.com/en/actions/concepts/billing-and-usage
