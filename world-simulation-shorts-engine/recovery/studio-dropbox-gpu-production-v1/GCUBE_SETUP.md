# GPU production candidate: gCube settings

이 문서는 무료 준비 결과와 향후 사용자가 승인할 유료 실행을 구분합니다. 이번 작업에서 gCube 배포·렌더링·중지·삭제를 하지 않습니다. 기존 FINAL·Camera·Area·Flow·Event·Planner·영상·claim·백업은 보존합니다.

## 1. 이미지와 기본 설정

이 프로필의 `RESULT.md`와 독립 pull 기록에서 **새로 검증한 태그와 digest**를 확인합니다. 기존 이미지 태그를 덮어쓰지 않습니다. 이미지가 실제로 발행되기 전에는 digest를 추측해서 입력하지 않습니다.

| gCube 항목 | 입력값 |
| --- | --- |
| GPU | RTX 4080 SUPER 16GB × 1; 실제 선택 노드 요금 확인 |
| 서비스 포트 | `8080` |
| Command | 비움; 새 이미지의 기존 Studio 연결 ENTRYPOINT 사용 |
| 공유 메모리 | `2GB` |
| 기존 결과물 마운트 | `/world-storage` |
| NVIDIA graphics 설정 | 실제 정상 실행에서 사용한 기존 설정 유지; 최소 `graphics,utility` 필요 |

`/world-storage`는 기존 공개 결과물용입니다. 개인 Scene·캐시·인증·Secret 저장소로 간주하지 않습니다. Dropbox API의 암호화 백업은 이 마운트와 독립적입니다.

## 2. 환경변수

gCube의 워크로드 설정에서 다음 일반 환경변수를 연결합니다. 아직 배포·제작 시작을 누르지 않습니다.

| 정확한 변수명 | 정확한 값 또는 값의 출처 |
| --- | --- |
| `WORLD_ENGINE_RENDER_MODE` | `gpu-required` |
| `WORLD_ENGINE_STARTUP_MODE` | `normal` |
| `WORLD_ENGINE_STUDIO_PORT` | `8080` |
| `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST` | `RESULT.md`의 새 이미지 `sha256:...` 값; 전체 GHCR 주소 아님 |
| `WORLD_ENGINE_STUDIO_BACKUP_MODE` | `dropbox-api` |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_AUTH_MODE` | `offline` |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_PREFIX` | `/WORLD_ENGINE_STUDIO_BACKUPS_V1` |
| `WORLD_ENGINE_STUDIO_BACKUP_PROOF_ID` | `08398705cd4ffb90a7f68a26ee6f65a121c5efa62ad4f854c1aa50ea371b55a7` |
| `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN` | 실제 새 HTTPS 주소가 발급되기 전 생략; 이후 기존 관리자 인증 `/setup`으로 실제 Origin 등록 |
| `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON` | 아래 실제 비용·시간 승인 정책 |

기존 private 기본 경로는 `/var/lib/world-engine-private/engine/production-studio-mvp-v1`입니다. 일반 신규 작업에서 `WORLD_ENGINE_STUDIO_STATE_ROOT`를 변경할 필요가 없습니다. `/world-storage`로 강제 변경하지 않습니다. `WORLD_ENGINE_STORAGE_MODE`와 `WORLD_ENGINE_STORAGE_PATH`는 이전 런처 설정이며 Studio의 Scene·캐시 영구 보존을 제어하지 않습니다.

`GCUBE_ACCESS_TOKEN`, `GCUBE_API_TOKEN`, `GCUBE_EMAIL`, `GCUBE_WORKLOAD_SER`는 사용자가 수동 배포한 Studio에서 제작하기 위한 필수 입력값이 아닙니다. 기존 Secret을 삭제할 필요도 없습니다.

## 3. 기존 Secret 연결

다음 **기존 동일 값**을 gCube의 승인된 Secret 주입 수단으로 연결합니다. 재로그인·토큰 재발급·키 교체는 요구하지 않습니다.

| Secret 이름 | 값 |
| --- | --- |
| `WORLD_ENGINE_STUDIO_OWNER_CODE` | 기존 관리자 코드 |
| `WORLD_ENGINE_STUDIO_BACKUP_KEY` | GitHub에 보관한 기존 암호화 키 값 그대로 |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY` | 기존 Dropbox 앱의 App key |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET` | 기존 Dropbox 앱의 App secret |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN` | 이미 승인·저장한 Refresh Token |

GitHub Repository Secret이 gCube로 자동 전달되지는 않습니다. GitHub Secret 조회 API는 저장한 원문을 반환하지 않습니다. 따라서 채팅으로 값을 요구하거나 공개 파일로 추출하지 않습니다. gCube의 전용 Secret 입력·마운트 기능이 현재 계정에서 제공되는지 확인되지 않았다면 제공된다고 가정하지 않습니다. Secret을 안전하게 연결할 수 없는 상태에서는 제작을 차단하고, 해당 계정의 공식 Secret 주입 경로를 먼저 확정해야 합니다.

공식 문서 버전 `Data-Alliance/gai-platform-docs@6338ac39d1b964226b1d7b378c0fa8e4af6cb201`의 [워크로드 등록](https://github.com/Data-Alliance/gai-platform-docs/blob/6338ac39d1b964226b1d7b378c0fa8e4af6cb201/docs/user-guide/workload/register-workload.ko.md)에서 확인된 일반 설정 경로는 **Workload Mode → 새 워크로드 등록 → 컨테이너 설정 → 컨테이너 환경변수**입니다. 이 표의 비밀 아닌 변수는 그곳에 입력할 수 있습니다. [공식 CLI](https://github.com/Data-Alliance/gai-platform-docs/blob/6338ac39d1b964226b1d7b378c0fa8e4af6cb201/docs/user-guide/gcube-cli/cli-workload.ko.md)와 [저장소 관리](https://github.com/Data-Alliance/gai-platform-docs/blob/6338ac39d1b964226b1d7b378c0fa8e4af6cb201/docs/user-guide/sign-up/storage-management.ko.md)에도 전용 workload SecretRef 계약은 확인되지 않았습니다. `+ 인증 정보 등록`은 이미지 레지스트리용이며 Dropbox Secret 주입 버튼으로 안내하지 않습니다. 사용자는 gCube에 **환경변수가 접근 제한·마스킹된 Secret으로 보관되는지, 또는 UID1000/0600 비공개 Secret 파일 마운트를 지원하는지** 확인해야 합니다. 이 확인 전에는 기존 Secret을 일반 YAML/API로 자동 전송하지 않습니다.

재사용한 공식 `gcube-cli 0.4.2`의 `commands/workload.py`는 일반 `containerEnvs`의 키/값만 전달하고, `api/workload.py`의 describe용 YAML 생성은 그 값을 직렬화합니다. 이 코드에서 workload용 Secret 참조·비공개 Secret 파일 주입 계약은 확인되지 않았습니다. 따라서 일반 환경변수 YAML을 안전한 Secret 저장소라고 판정하지 않으며, Secret이 연결된 workload의 전체 describe 응답·YAML·환경변수를 로그나 공개 보고서로 출력하지 않습니다. registry 인증용 `gcube credential`을 Dropbox Secret 저장 기능으로 혼동하지 않습니다.

기존 런타임은 Dropbox 네 Secret 각각에 대해 `<위 이름>_FILE` 형식도 지원합니다. 이 형식에는 값 대신 실제 비공개 파일의 절대 경로를 입력합니다. 파일은 링크가 아닌 일반 파일, 단일 링크, `0600`, 런타임 UID/GID `1000:1000`, 부모 디렉터리 `0700`이어야 하며 `/world-storage`에 두지 않습니다. raw 값과 `_FILE`을 동시에 제공하면 파일 입력이 우선하므로 충돌하는 두 입력을 새로 만들지 않습니다. 실제 마운트 경로를 확인하지 않고 예시 경로를 입력하지 않습니다.

새 입력 어댑터는 기존 키의 Base64 표현만 정규화하며 32바이트 키 자체는 유지합니다. Secret 값, Refresh Token, 키를 이미지·Scene·GitHub 코드·로그·URL에 넣지 않습니다. 기존 Access Token Secret은 보존하지만 offline 경로에서는 사용하지 않습니다.

## 4. 240분 지원과 비용 승인

기존 Studio 및 coordinator 검증기는 `maxWallSeconds=14400`을 이미 지원합니다. Camera·렌더러·전선 변경은 필요하지 않습니다. 기존 60분/180분 작업의 승인이나 claim을 늘리지 않고 **다음 새 작업**에만 새 정책을 적용합니다. 180분 전용 `studio-80s-recovery-v1/policy.py` 도구를 240분 설정에 사용하지 않습니다.

필수 정책 필드는 다음 여섯 개입니다. 다음은 값의 의미를 표시하는 **입력 계약이며 실행 가능한 승인값이 아닙니다**.

| 필드 | 넣을 값 |
| --- | --- |
| `maxWallSeconds` | 정수 `14400` |
| `maxRetries` | 정수 `0`; 별도 승인 없는 유료 재시도 방지 |
| `gpuHourlyRate` | 실제 선택 노드의 확인된 시간당 요금 |
| `currency` | 실제 요금의 3자리 통화 코드 |
| `maxCostAmount` | 사용자가 승인한 금액; 최소 `실제 시간당 요금 × 4`를 감당해야 함 |
| `validUntil` | 사용자가 승인한 실제 만료시각; 시간대 포함 ISO8601, 의도한 실행시간 충분히 확보 |

기존 private 정책과 환경변수 정책이 다르면 원본 bootstrap은 충돌을 차단합니다. 기존 파일을 삭제하거나 덮어써서 우회하지 않습니다. 새 환경에서는 새 실제 승인 정책을 사용합니다. 같은 private 상태를 재사용하는 경우 기존 비파괴 정책 변경 절차를 별도로 검증해야 합니다.

기존 공식 조회 증거는 `gpu-rebuild-approval-v1/RESULT.json`입니다. **2026-10-18 12:47:11 KST**의 가용 tier2 RTX4080SUPER 카탈로그는 시간당 **252~360원**이었고, 단순 4시간 계산은 **1,008~1,440원**입니다. 이는 현재 선택 노드의 확정 견적·승인된 비용이 아닙니다. 배포 화면의 실제 단가·통화·과금 조건을 확인해야 하며, 세금/반올림·저장소/네트워크·준비/유휴시간 비용은 확정되지 않았습니다.

Studio 타임아웃은 gCube 과금 자동 종료가 아닙니다. 240분은 완료시간 예측도 아닙니다. 전체 계정 청구액의 강제 상한을 확보했다고 보고하지 않습니다. 사용자는 결과 보존 확인 후 gCube를 수동 정지해야 하며, 이번 준비 작업은 유료 실행 승인을 대신하지 않습니다.

## 5. 백업 proof와 컨테이너 재시작

승인된 proof는 실제 Dropbox 전송·복구 경로의 검증이며 특정 production 이미지와의 동일성 증명이 아닙니다. 원본 검증기는 의도적으로 합성 proof의 `sha256:` + `b` 64개 이미지 바인딩을 확인합니다. 따라서 새 후보 이미지라는 이유만으로 같은 외부 백업 검사를 반복할 필요가 없습니다. 같은 키·앱 폴더에서 유효기간 내 기존 proof를 인증해 사용합니다.

이 proof의 기록된 만료는 **2026-10-25 17:37:59 KST**입니다. 런타임은 실제 시각과 암호화된 원격 receipt를 다시 검사하며, 만료·다른 키·다른 prefix·손상 시 제작을 차단합니다. 만료 뒤에는 기존 인증으로 무료 CPU proof만 갱신할 수 있고, 불필요한 Dropbox 재로그인은 요구하지 않습니다.

실제 제작 체크포인트는 별도입니다. 동일 원본 Scene SHA와 **해당 제작에 사용한 원본 이미지 digest**에 고정됩니다. 새 이미지 digest를 과거 production 체크포인트에 임의로 대입하지 않습니다. 합성 CPU proof 체크포인트를 실제 제작 체크포인트로 사용하지 않습니다.

컨테이너 교체 후 private 상태가 사라졌으면, 인증된 production 체크포인트를 선택하여 다음 선택적 변수로 복구합니다.

| 변수 | 실제 입력값 |
| --- | --- |
| `WORLD_ENGINE_STUDIO_RESTORE_CHECKPOINT_ID` | 보존된 인증 체크포인트의 ID |
| `WORLD_ENGINE_STUDIO_RESTORE_PLAN_SHA256` | 해당 원본 Scene의 SHA-256 |
| `WORLD_ENGINE_STUDIO_STATE_ROOT` | 기존 root와 겹치지 않는 새로운 비공개 POSIX 디렉터리 |
| `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST` | 해당 production 체크포인트와 같은 원본 이미지 digest |

기존 bootstrap은 UID/GID1000으로 다운로드·복호화·SHA·MP4 검사 후 입력과 검증된 완료 장면 캐시만 복구합니다. 이전 승인·관리자 세션·실행 PID·claim을 실행 권한으로 복구하지 않습니다. 새 유효 정책과 인증된 명시적 시작이 필요하며 컨테이너 재시작 자체로 GPU 작업을 자동 시작하지 않습니다.

중단된 불완전 복구 root는 보존·거부하며 다른 새 root에서 명시적으로 재시도합니다. 기존 root나 claim을 삭제해 우회하지 않습니다. CPU 컨테이너 재생성 테스트와 실제 gCube 컨테이너 재시작 성공은 구분합니다. 기존 이미지의 Docker health 시작 유예는 20분, 복구 subprocess 상한은 600초이며, gCube 자체 startup probe/재시작 정책의 동일 유예 지원은 실제 플랫폼 설정 확인이 필요합니다.

## 6. 80초 재제작 순서

1. 무료 테스트·독립 이미지 pull·복구 검증 결과를 확인합니다.
2. 실제 선택 노드 단가와 최대 비용·시간·승인 만료를 사용자가 승인합니다.
3. 같은 Dropbox Secret과 위 설정을 안전하게 연결합니다.
4. 사용자 승인 후에만 수동 배포하고 실제 HTTPS 주소의 `/setup`에서 기존 관리자 인증으로 등록합니다.
5. 기존 `VERIFIED_FRONT_V4_80S` / `V4_ARCHIVAL_80S` 입력을 사용합니다. 80초·30fps·2,400프레임·12장면, 1080×1920·H.264와 기존 SFX·연출 경로를 유지합니다.
6. Preflight의 실제 GPU·자료 SHA·저장·proof·운영 정책·중복 작업 검사가 모두 통과한 뒤 한 번 시작합니다. 장면별 백업 실패는 다음 장면을 차단해야 합니다.
7. 완성 후 전체 디코딩·SHA·Dropbox 외부 다운로드를 확인하고 최종 영상을 검수합니다. 결과 보존을 확인한 뒤 사용자가 gCube를 수동 정지합니다.

이번 무료 준비만으로 실제 NVIDIA 렌더링·80초 제작시간·모바일 영상 품질을 PASS 또는 FINAL로 선언하지 않습니다.
