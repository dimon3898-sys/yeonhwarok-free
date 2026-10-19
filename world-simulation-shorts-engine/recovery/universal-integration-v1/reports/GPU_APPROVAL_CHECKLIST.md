# GPU 실행·5초 품질 승인 체크리스트

이 문서는 새 후보의 실행 **선행 조건**을 정의한다. 이번 CPU 작업에서 GPU를 실행하거나 사용자 품질 승인서를 발행하지 않는다. `quality_gate.py`의 `allowed: true`도 NVIDIA admission·기존 인증·개별 작업 동의·비용 정책을 대체하지 않는다.

## 현재 판정

| 항목 | 현재 근거와 판정 |
| --- | --- |
| CPU 계약·프레임 계획 | CPU 검증 결과로만 기록한다. 실제 프레임 출력·NVIDIA PASS가 아니다. |
| 새 통합 모듈의 운영 이미지 포함 | 새 코드가 이전 이미지에 포함된 것으로 간주하지 않는다. 이미지 source closure·고정 digest 검증이 필요하다. |
| 한국전쟁 필수 데이터 | 완전한 양측 점령 영역·역사적 부대/표식 위치 등 미확보 항목은 별도 데이터 보고서의 차단 사유를 유지한다. 사용자 품질 승인으로 자료 부족을 덮어쓸 수 없다. |
| 실제 통합 5초 영상 | 이번 작업에서 생성하지 않는다. 새 경로의 NVIDIA 출력 근거는 미확보다. |
| 5초 레퍼런스 비교·사용자 승인 | 새 통합 후보에 연결된 승인 receipt가 없으면 미완료다. 이전 Candidate 승인은 새 Scene·소스·이미지에 자동 승계하지 않는다. |
| 80초 실행 | 위 조건이 충족되기 전 `FULL_VIDEO` gate가 차단한다. |
| 유료 작업 | 이번 작업에서는 금지한다. 무료 검증 결과가 비용 승인을 생성하지 않는다. |

## 실제 실행 전 순서

1. 실제 Scene과 필수 모듈·역사 데이터의 차단 항목을 해결한다. 검증되지 않은 영토·부대·이동 경로를 새로 만들어 채우지 않는다.
2. 새 코드 및 부모 소스의 SHA-256 closure를 확인한다. 실행 이미지의 immutable digest와 그 이미지에 새 패키지가 포함됐다는 검증을 연결한다.
3. 기존 Studio 관리자 인증·Origin·CSRF·작업 동의·GPU 중복 방지 및 NVIDIA admission을 유지한다.
4. 실제 운영자가 확인한 요금·최대 비용·실행시간·재시도 상한·만료시각을 기존 비공개 정책으로 검증한다. `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON`의 기존 검증기를 그대로 사용한다.
5. 사용자에게 **별도 유료 GPU 승인**을 받은 후에만 `REFERENCE_5S`를 검토한다. 영상 길이 5초는 GPU 실행시간 5초를 뜻하지 않는다. 실제 작업시간과 비용은 측정 전까지 미확정이다.
6. 실제 NVIDIA 환경에서 새 통합 5초·1080×1920·30fps·150프레임을 생성하고 전체 MP4를 디코딩한다. 기준 레퍼런스와 비교하고 사용자가 실제 영상을 검수한다.
7. 사용자가 승인한 경우에만 신뢰된 서버/운영자 경로가 승인 근거를 비공개 상태에 기록한다. 프롬프트·Scene JSON·브라우저의 임의 `qualityApproved` 값은 승인 근거가 아니다.
8. 동일 Scene·소스·이미지·길이에 연결된 receipt와 실제 데이터 차단 해소를 검증한 후 `FULL_VIDEO`를 검토한다. 그 뒤에도 기존 비용·GPU admission·작업별 동의 검사는 필수다.

과거 사용자가 언급한 RTX 5090 시간당 910~1,300원은 **현재 검증된 요금 견적이 아니다**. 이번 작업은 시간당 요금, 실제 5초 렌더링 벽시계 시간, 80초 제작비·완료시간을 확정하지 않는다. 엔진 timeout은 gCube 과금 종료와 별개다.

## 서버 전용 gate 호출 계약

`evaluate_render_gate(context, *, phase, operator_policy=None, policy_validator=None, receipt_path=None, trusted_receipt_root=None, trusted_uid=None, now=None)`는 결과만 반환한다. 렌더·배포·claim 생성·파일 수정은 수행하지 않는다.

`context`는 신뢰된 백엔드가 실제 검증 결과에서 구성한다. 클라이언트 입력에서 그대로 복사하면 안 된다.

| 필드 | 규격 |
| --- | --- |
| `sourceCommit` | 실제 소스 40자리 Git commit |
| `sourceManifestSHA256` | 선택 소스 manifest의 실제 SHA-256 |
| `sourceClosureManifestSHA256` | 새 모듈과 부모 의존성 closure manifest의 실제 SHA-256 |
| `sceneSHA256` | 실제 전체 대상 Scene의 SHA-256 |
| `imageDigest` | 검증된 `sha256:<64자리>` 이미지 digest |
| `sourceClosureVerified` | 신뢰된 closure 검증 결과. 누락·false는 차단 |
| `imagePackageIncluded` | 해당 이미지에 새 모듈이 포함됐다는 검증 결과. 이전 이미지·미빌드 이미지는 true로 표시하지 않음 |
| `durationSeconds`, `fps` | `REFERENCE_5S`: 정수 5와 30. `FULL_VIDEO`: 정수 80/120/180/300/600과 30 |
| `requiredModules` | 비어 있지 않은 `{기능ID: 상태}`. `READY` 또는 실제 비필수 기능의 `NOT_REQUIRED`만 허용. 최소 한 기능은 `READY`여야 함 |
| `dataBlockers` | 실제 미해결 필수 자료 오류 코드 배열. 항목이 하나라도 있으면 차단 |
| `referenceSHA256` | 실제 비교 레퍼런스 SHA-256 |
| `candidateSHA256` | `FULL_VIDEO`에 필수. 실제 승인된 새 5초 MP4 SHA-256 |

`policy_validator`는 기존 `StudioController._policy`로 비공개 정책을 검증하는 서버 함수다. 클라이언트 callback이나 임의 bool은 인정하지 않는다. 기존 정책의 6개 필드(`validUntil`, `maxWallSeconds`, `maxRetries`, `maxCostAmount`, `currency`, `gpuHourlyRate`)를 검증한 매핑이 필요하다. 기존 정책은 그대로 보존한다.

## 품질 승인 receipt 보안·정합

receipt의 schema는 `WORLD_ENGINE_5S_USER_QUALITY_APPROVAL_V1`이다. 이 작업은 receipt의 발급 API나 임의 승인 UI를 만들지 않는다. 실제 사용자 승인이 없는 유효 receipt를 결과물에 포함하지 않는다.

- 지정된 비공개 운영자 디렉터리는 해당 UID 소유의 `0700`이어야 한다. 공유 Dropbox 마운트를 비공개 승인 권한 저장소로 취급하지 않는다.
- receipt는 동일 UID 소유·`0600`·single-link regular file이어야 한다. 경로 전체의 symlink, 상위 경로 탈출, hard link, FIFO, 공개 권한, 중복 JSON 키·비정상 수치는 거부한다.
- 디렉터리 FD와 `O_NOFOLLOW`로 읽고 파일 변경 여부를 재확인한다. 실패 시 기존 권한을 강제로 고치거나 데이터를 삭제하지 않는다.
- `sourceCommit`, 소스·closure·Scene SHA, image digest, reference·candidate SHA와 `targetDurationSeconds`, `targetFps`를 모두 대상 작업과 일치시킨다.
- `userReview`가 `PASS`여야 한다. 시간대가 포함된 `reviewedAt`, `validUntil`을 검사하고 미래 승인·만료 승인을 거부한다.
- candidate에는 실제 5초·1080×1920·30fps·150프레임, NVIDIA 검증 및 전체 디코딩 근거 SHA가 필요하다. CPU/SwiftShader는 인정하지 않는다.
- reference comparison에는 동일 reference/candidate SHA와 완료된 비교 근거 SHA가 필요하다.
- 모듈 미연결·자료 부족·이미지 미포함은 receipt가 유효해도 계속 차단한다.

비공개 파일 소유권은 **신뢰된 운영자 기록의 저장 경계**다. 그 자체가 사용자가 영상을 봤다는 사실을 만들어 내지는 않는다. 실제 확인된 GPU·비교·사용자 승인 근거가 있을 때만 운영자 경로가 기록해야 한다.

## CPU 검증

`python -B -m unittest discover -s world-simulation-shorts-engine/recovery/universal-integration-v1/tests -p test_quality_gate.py`

**45개 CPU 테스트 PASS.** 테스트의 media hash·가격·receipt는 전부 명시적 합성 Fixture다. 기존 operator policy validator를 호출하여 만료·비용 부족·알 수 없는 필드 거부를 확인했다. 누락/위조 형식 승인, 잘못된 Scene·소스·이미지·기간 바인딩, symlink·hard link·권한·UID, CPU 후보와 자료 차단 유지도 검증했다.

테스트 결과는 실제 NVIDIA 렌더 성공, 실제 요금 확인, 실제 사용자 품질 승인 또는 80초 제작 허용을 뜻하지 않는다.

## 사용자의 최소 다음 행동

현재는 인계 결과와 남은 자료·통합 차단 목록을 검수하면 된다. gCube 재배포·터미널 명령·토큰 재입력·80초 제작 시작을 요구하지 않는다. 무료로 해결할 수 있는 차단 항목이 정리되고 실제 5초 실행 후보가 준비된 뒤에만, 정확한 실제 요금과 상한을 제시하여 별도 유료 GPU 승인을 받아야 한다.
