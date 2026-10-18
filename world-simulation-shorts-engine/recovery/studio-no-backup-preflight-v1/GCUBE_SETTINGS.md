# 이번 실행에서 필요한 gCube 입력값

비용 승인이 아직 없으므로 지금 **배포/제작 시작을 누르지 않는다**. 기존 Dropbox Secret이나 백업 데이터를 삭제하지 않는다.

## 컨테이너 이미지

이미지 입력란:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:studio-proxy-v1-4589328-39085567166-1
```

기존에 지원된 백업 추가 전 정상 Studio 경로를 이번 실행에만 재사용한다. 새로운 백업 이미지에서 검사를 끄는 설정이 아니다.

## 일반 환경변수

```text
WORLD_ENGINE_RENDER_MODE=gpu-required
WORLD_ENGINE_STARTUP_MODE=normal
WORLD_ENGINE_STUDIO_PORT=8080
WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST=sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da
WORLD_ENGINE_STUDIO_STATE_ROOT=/var/lib/world-engine-private/engine/studio-no-backup-80s-v1
```

기존 `WORLD_ENGINE_STUDIO_OWNER_CODE`와 NVIDIA 설정을 유지한다. 새 Dropbox 토큰/암호화 키 입력은 필요하지 않다. 기존 `WORLD_ENGINE_STUDIO_BACKUP_*` 설정/Secret은 삭제하지 않으며 이 이전 이미지의 정상 Studio 경로에서는 사용되지 않는다. 지원되지 않는 `BACKUP_MODE=off` 같은 변수는 추가하지 않는다.

## 운영 승인 정책

`WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON`의 새 정책에서 고정 가능한 값:

```json
{"maxWallSeconds":14400,"maxRetries":0}
```

**위 두 필드만 붙여 넣으면 안 된다.** 실제 정책에는 다음 네 필드도 모두 필요하다. 현재 확정하지 않았으며 임의 값을 만들지 않는다.

| 필드 | 입력할 실제 값 |
| --- | --- |
| `gpuHourlyRate` | 선택한 gCube 노드에 표시된 실제 시간당 요금 |
| `currency` | 실제 요금 통화, 예를 들어 원화이면 `KRW` |
| `maxCostAmount` | 사용자가 별도로 승인한 금액. 4시간×해당 시간당 요금 이상이어야 함 |
| `validUntil` | 사용자가 승인한 실제 만료시각. 시간대 포함 ISO8601, 작업 완료를 허용하는 충분한 유효시간 |

요금 조회에서 RTX4080SUPER16GB catalogue는 tier2 시간당252–360원, tier3 154–220원이었으나 둘 다 availability=false였다. 이 범위만으로 선택 노드의 실제 요금/총액/승인을 확정하지 않는다. 배포 준비·대기·저장소 등 추가 비용과 과금 종료 시각도 확인해야 한다.

기존 private `operator_policy.json`은 다른 환경변수 정책으로 덮어쓰지 않는다. 위의 기존 지원 `WORLD_ENGINE_STUDIO_STATE_ROOT`는 이번 재제작용 별도 private 디렉터리다. 상위 `/var/lib/world-engine-private/engine`은 기존 이미지가 준비한다. 새 디렉터리와 파일은 기존 0700/0600·UID1000 검사로 생성되며 기존 상태·정책·작업·claim은 그대로 보존된다. 기존 `WORLD_ENGINE_STUDIO_OWNER_CODE` 환경변수는 유지해야 동일 관리자 자격을 사용할 수 있다. 지정한 새 디렉터리가 이미 존재하고 다른 정책을 담고 있다면 안전하게 차단한다. 삭제/덮어쓰기하지 않는다.

## 나머지 화면

- GPU: RTX4080SUPER16GB. 실제 가용 여부와 요금 확인 후 별도 승인.
- 서비스 포트: `8080`.
- Command: **비움**.
- 공유 메모리: `2GB`.
- 기존 결과물 저장소 마운트: `/world-storage` 유지.
- private Studio 상태를 `/world-storage`로 옮기지 않는다.
- 별도 private 상태에서는 예전 세션/등록이 재사용되지 않는다. 실제 현재 주소가 환경변수로 정확하게 설정되어 있으면 유지한다. 새 주소가 발급되면 그 주소의 `/setup`에서 기존 관리자 코드로 확인·등록한다. 종료된 과거 주소나 임의 Origin을 넣지 않는다.
- 기존 `WORLD_ENGINE_STORAGE_MODE=ephemeral`, `WORLD_ENGINE_STORAGE_PATH=/data`는 Scene 자동 백업을 켜고 끄는 변수가 아니다. 이 값만 바꿔 영구 백업이 된다고 판단하지 않는다.

장면별 MP4와 SHA는 기존 동작대로 `/world-storage`에 즉시 내보낸다. 새 private Scene·캐시의 컨테이너 교체 후 보존/자동 복구는 보장하지 않는다.

240분은 애플리케이션 작업 상한이며 gCube 과금 자동 종료가 아니다. 승인 후 실제 작업을 완료하면 MP4 다운로드와 SHA 일치를 확인하고 사용자가 워크로드를 수동 중지한다. 이번 사전검수에서는 GPU·새 MP4·외부 다운로드 검증을 실행하지 않았다.
