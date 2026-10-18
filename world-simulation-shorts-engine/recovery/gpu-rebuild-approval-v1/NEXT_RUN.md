# 새 80초 제작의 재개 지점

현재 상태는 **USER_APPROVAL_REQUIRED**다. 기존 서버 전용 미확인 Scene·캐시·체크포인트의 유실 수용은 이미 승인됐다. 같은 결정을 다시 요구하지 않는다. 새 GPU 비용·배포·렌더링은 아직 승인되지 않았다.

## 지금 사용자가 할 수 있는 기존 서버 중지

gCube → 워크로드 → #5373 `world-engine-test` 확인 → **배포중지** → 확인 → 상태 **종료** 확인. 영구 삭제를 선택하거나 Dropbox 저장소를 삭제하지 않는다. 상태 종료가 확인돼야 공식 과금 종료 조건에 도달했다고 판단할 수 있다. Codex는 이 중지를 실행하지 않았다.

## 비용 승인 전 확정할 내용

- 공식 조회 시 가용 tier2 RTX4080SUPER의 시간당 카탈로그 범위는 **252~360원**,180분 계산 범위는 **756~1,080원**이다. 선택 노드와 최신 가용성·실제 과금 조건은 배포 화면에서 다시 확인한다.
- **사용자 최대 총비용은 아직 미승인**이다.180분 제작 상한과 세팅·유휴·전달 검증 시간을 포함하는 플랫폼 사용시간을 구분한다. 카탈로그 1,080원을 자동 중지되는 총과금 상한으로 보지 않는다.
- 실제 `gpuHourlyRate`, `currency`, 사용자 승인 `maxCostAmount`, `maxWallSeconds`, `maxRetries`, `validUntil`을 확정한다. 권장 제작 시간 상한은10,800초이나 완료 보장이 아니다. 최초 작업은 승인 없는 유료 재시도를 허용하지 않는다.
- 기존 `WORLD_ENGINE_STUDIO_OWNER_CODE`를 승인된 Secret 경로에서 안전하게 재사용할 수 있는지 확인한다. 값은 채팅/GitHub에 기록하지 않는다.
- 실제 견적과 최대 비용·시간·재시도·만료에 대한 사용자 승인이 오기 전 GPU를 새로 배포하거나 제작 시작을 누르지 않는다.

## 승인 후 새 환경 설정

기존 검증 이미지:

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da
```

digest 참조를 지원하지 않으면 기존 고유 태그 `studio-proxy-v1-4589328-39085567166-1`를 쓰고 같은 digest인지 확인한다.

| 항목 | 값/조건 |
| --- | --- |
| GPU | RTX4080SUPER 16GB ×1, 선택 노드 견적 재확인 |
| Command | 비움 |
| 서비스 포트 | 8080 |
| 공유 메모리 | 2GiB |
| `NVIDIA_DRIVER_CAPABILITIES` | `graphics,utility` |
| `WORLD_ENGINE_RENDER_MODE` | `gpu-required` |
| `WORLD_ENGINE_STARTUP_MODE` | `normal` |
| `WORLD_ENGINE_STUDIO_PORT` | `8080` |
| `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST` | `sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da` |
| `WORLD_ENGINE_STUDIO_OWNER_CODE` | 기존 승인된 관리자 Secret, 공개·가짜 값 금지 |
| `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON` | 실제 단가·통화·비용·시간·재시도·만료가 포함된 새 승인 정책 |
| `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN` | 새 실제 주소 발급 전 생략 가능. 발급 후 관리자 인증 `/setup`으로 등록. 과거 주소를 새 환경에 복사하지 않는다. |
| Dropbox | 기존 `/world-storage` 연결, 기존 데이터 보존 |
| private 상태/캐시 | 기존 기본 `/var/lib/world-engine-private/engine/production-studio-mvp-v1`, UID/GID1000와 private POSIX 규칙 준수. Dropbox를 private 캐시·인증 폴더로 사용하지 않는다. |

`GCUBE_ACCESS_TOKEN`/`GCUBE_API_TOKEN`은 수동 배포 Studio의 실제 제작 필수 값이 아니다. 기존 Secret은 그대로 보존한다. 새 SSH 연결은 선행조건이 아니다. GPU 드라이버·VRAM·WebGL2·저장 공간·마운트 검사는 실제 새 환경에서 기존 admission으로 통과해야 한다.

## 승인 후 제작

1. 사용자가 새 GPU를 수동 배포하고 실제 HTTPS 주소에서 관리자 인증·Origin/CSRF 등록을 완료한다.
2. 기준 커밋0625c85의 `production-studio-mvp-v1/examples/STUDIO_PROMPT_V4_80S.json`을 입력한다. preset `VERIFIED_FRONT_V4_80S`, profile `V4_ARCHIVAL_80S`를 유지한다.
3. 저장된 `verified-front-data-v4-recovery/VIDEO_PLAN_80S.json` 원문 SHA는 `2632f9106962bb126bf333422bce2be5094d4af7b25c5701acdf4455a2829dc6`다. 실제 이미지 바인딩은 기존 검증 adapter를 사용한다.
4. Preflight에서 원본·Scene·2,400프레임·12장면·소스 SHA·영토/전선·SFX·GPU·공간·Dropbox·정책·중복 claim을 확인한다. 새 작업 ID로 시작하며 기존 claim이나 기록을 삭제해 충돌을 우회하지 않는다.
5. 사용자 승인 범위 안에서만 제작 시작1회. 기존 독립 관리자·분할 렌더링·캐시·FFmpeg·SFX·Dropbox를 그대로 재사용한다.
6. 완성 후 전체 디코딩·80초/2,400프레임/1080×1920/30fps/H.264·SFX·SHA·Dropbox 외부 다운로드를 검증하고 사용자 영상 검수에서 멈춘다. 실제 시간·단계별 병목을 기록한다.
7. 완료/실패 여부와 별도로 플랫폼을 사용자가 중지해야 추가 과금을 멈출 수 있다. 결과 보존 확인 후 사용자가 중지한다. FINAL 승격은 하지 않는다.

기존 완료 기능 재개발, SSH 복구 반복, 새 역사 자료 조사,5초 샘플 반복은 이 재개 경로에 포함되지 않는다.
