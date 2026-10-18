# 사용자 승인 후 재개 지점

이 파일은 실행 준비 절차이며 현재 GPU 실행·배포 중지에 대한 승인이 아니다. SSH 복구를 재개하지 않는다. 기존 #5373·claim·맞춤 입력·캐시·승인은 그대로 둔다.

## 1. 승인 전에 확보할 항목

1. 새로 선택할 실제 RTX4080SUPER 노드의 시급·통화·세금/반올림/네트워크/저장소 과금 조건을 gCube 견적 화면에서 확인한다. 무료 공식 API 조회만으로 일치하는 견적을 확보하지 못했다. 예시 단가를 넣지 않는다.
2. 기존 `WORLD_ENGINE_STUDIO_OWNER_CODE`를 승인된 Secret 저장 경로에서 안전하게 재사용할 수 있는지 확인한다. 채팅/GitHub에 값을 쓰지 않는다.
3. 새 작업의 최대 비용, 10,800초 시간 상한을 사용할지, retry 상한, timezone을 포함한 승인 만료를 확정한다. 기존 승인/claim을 고치지 않는다. `gpuHourlyRate`, `currency`, `maxCostAmount`, `maxWallSeconds`, `maxRetries`, `validUntil`이 모두 실제 승인과 일치해야 한다. 180분은 예상 시간이 아니며 과금 자동 종료도 아니다.
4. 기존 배포 중지 시 미확인 private 맞춤 입력·캐시·앵커가 유실될 수 있음을 별도로 판단한다. 이 사전점검은 무손실 중지 PASS가 아니다. 중지·삭제는 별도 사용자 결정 전 실행하지 않는다.
5. 신규 후보는 GitHub 기본 V4 프리셋을 사용하는 새 영상이다. 이전 사용자의 실제 PLAN/AUDIO와 byte-identical 재현이 필요하면 먼저 그 원본 확보가 필요하다.

## 2. 승인 후 새 GPU 환경의 설정

기존 검증 이미지를 사용한다. 이번 작업에서는 재빌드할 필요를 발견하지 못했다.

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da
```

digest 입력을 지원하지 않으면 이미 보존된 고유 태그 `studio-proxy-v1-4589328-39085567166-1`와 같은 digest임을 확인한다. 기존 이미지를 덮어쓰지 않는다.

| 설정 | 값/조건 |
| --- | --- |
| GPU | 실제 RTX4080SUPER 16GB. 기존 하드웨어 admission을 새 환경에서도 통과해야 한다. |
| Command | 비움: 검증된 이미지 ENTRYPOINT/CMD 사용 |
| 서비스 포트 | 8080 |
| 공유 메모리 | 2GiB 권장, 기존 admission 유지 |
| `NVIDIA_DRIVER_CAPABILITIES` | `graphics,utility` |
| `WORLD_ENGINE_RENDER_MODE` | `gpu-required` |
| `WORLD_ENGINE_STARTUP_MODE` | `normal` |
| `WORLD_ENGINE_STUDIO_PORT` | `8080` |
| `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST` | `sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da` |
| `WORLD_ENGINE_STUDIO_OWNER_CODE` | 기존 승인된 관리자 Secret, 공개 값·가짜 값 없음 |
| `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON` | 위 1단계에서 실제 승인된 새 정책. 미설정/만료/비용 부족이면 제작 차단 |
| `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN` | 새 HTTPS 주소가 발급되기 전에는 생략 가능. 이전 환경의 주소를 새 환경에 복사하지 않는다. |
| Dropbox | 기존 `/world-storage` 마운트, 기존 파일 보존 |
| private 상태/캐시 | 기본 `/var/lib/world-engine-private/engine/production-studio-mvp-v1`; UID/GID1000, private POSIX 규칙 준수. Dropbox를 private cache/auth 저장소로 잘못 사용하지 않는다. |

GPU 기본 작업 예산 8GiB는 실제 free VRAM에서 2GiB 여유를 남기는 admission을 충족해야 한다. 코드의 80초 private 디스크 최소 사전검사값 2GiB는 실제 최대 사용량 보장이 아니다. 충분한 공간을 제공하고 기존 저장 공간 사전검사를 통과한다. 새 NVIDIA 드라이버, EGL/Vulkan, WebGL2 draw/readPixels를 CPU 증거로 대체하지 않는다.

가능하고 승인된 경우 private 루트에 POSIX 권한을 지원하는 별도 영속 볼륨을 사용해 새 캐시 유실 위험을 낮춘다. 해당 계정의 지원·보존 정책과 권한 검사가 확인되지 않았다면 있다고 가정하지 않는다. Dropbox에는 기존 adapter로 내보내고 외부 동기화를 따로 검증한다.

`GCUBE_ACCESS_TOKEN`/`GCUBE_API_TOKEN`은 사용자가 수동 배포한 Studio에서 제작하는 데 필수 입력이 아니다. 기존 Secret은 삭제하지 않는다. 새 SSH 등록도 선행조건이 아니다.

## 3. HTTPS·입력·실행

1. 새 환경에서 발급된 **실제** 포트8080 HTTPS 서비스 주소의 `/setup`을 연다. 관리자 인증과 Origin/CSRF 검증을 통과해 Origin을 명시적으로 등록하고 로그인한다. 임의 주소·과거 종료 주소·인증 우회는 금지한다.
2. GitHub의 `production-studio-mvp-v1/examples/STUDIO_PROMPT_V4_80S.json`을 제작 입력으로 사용한다. preset `VERIFIED_FRONT_V4_80S`, profile `V4_ARCHIVAL_80S`. 사용자가 원한 기존 AUDIO를 확보하지 못했다면 저장 프리셋의 SFX 설정을 쓰는 새 후보임을 유지한다.
3. 저장된 원문 `verified-front-data-v4-recovery/VIDEO_PLAN_80S.json` SHA는 `2632f9106962bb126bf333422bce2be5094d4af7b25c5701acdf4455a2829dc6`이다. 런타임 이미지 바인딩은 기존 adapter가 검증하여 처리한다. 장면·전선 좌표를 임의 수정하지 않는다.
4. Preflight에서 원본 SHA/12장면/2,400프레임/영토·전선/좌표·NoData/GPU·VRAM/공간/저장소/SFX/정책/중복 claim을 모두 검사한다. 새로운 고유 작업 ID를 사용하고 기존 캐시/claim을 삭제해 충돌을 피하지 않는다.
5. **유료 실행 승인 후에만** 제작 시작 1회. 기존 터미널 독립 관리자와 장면별 처리·캐시를 그대로 사용한다. 승인 없는 유료 재시도는 하지 않는다. 실제 단계 시간과 자원 사용을 기록한다.
6. 완성 후 MP4 전체 디코딩,80초/2,400프레임/1080×1920/30fps/H.264/SFX,장면 경계,PNG,SHA,Dropbox 외부 다운로드를 검증한다. 마운트 readback만으로 외부 전달 PASS로 처리하지 않는다.
7. 결과 보존과 검증 상태를 확인하고 사용자가 플랫폼 중지를 직접 결정한다. 제작 프로세스 종료·timeout과 gCube 과금 중지는 별개다. 완성본은 사용자 영상 검수 대기, FINAL 승격 금지.

## 남은 차단과 판정

필수 원본의 확인된 누락은 없다. 남은 것은 실제 단가·유료 비용 승인, 기존 관리자 Secret의 안전한 가용성, 새 환경의 마운트·NVIDIA admission·HTTPS 등록, 실제 완성 영상 검증이다. 완료시간과 총비용은 아직 확정할 수 없다.

**USER_APPROVAL_REQUIRED — GPU 배포·제작·기존 배포 중지는 이 문서 작성만으로 실행하지 않는다.**
