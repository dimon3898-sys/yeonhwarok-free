# 실제 80초 작업 복구 절차

대상: gCube5373 / `studio-bcd340f797498d7c9fea8181921f91b9`.

## 지금 필요한 조치

재배포·컨테이너 교체·private 작업 디렉터리 초기화 전에 보존 자료를 확보한다. 사용자 보고의12/12·2400/2400은 완료 카운트이고, 이번 무료 조회에서는 캐시 파일을 직접 읽지 못했다.

기존 `GCUBE_ACCESS_TOKEN` 인증은 성공했다. 2026-10-18 **11:41:15 KST**에 Pod Running을 확인했지만 기존 SSH 등록이 없어 읽기 전용 파일 검사를 중단했다. 인증 토큰을 다시 만들거나 채팅에 보낼 필요는 없다. 현재 Pod에 접근 가능한 공식 연결 경로가 먼저 필요하다.

공식 gcube-cli0.4.2의 `gcube workload ssh 5373 --info`는 기존 등록 조회이고, 등록이 없으면 일반 `gcube workload ssh 5373` 사용을 안내한다. 일반 명령은 SSH 등록/접속과 접속 IP 설정을 수행할 수 있으므로 이번 읽기 전용 조사에서는 실행하지 않았다. `--show-password`, `--delete`, IP 변경·기존 등록 삭제를 사용하지 않는다. 허용된 실행자의 연결을 등록한 다음 읽기 전용 검사만 다시 수행해야 한다. 단순히 다른 장치의 IP에 연결을 등록했다고 CI 실행자도 접속 가능하다고 가정하지 않는다.

워크로드 배포·정지는 사용자가 관리한다. GPU 재배포를 복구 선행조건으로 사용하지 않는다. 기존 컨테이너에서 CPU 합성을 하더라도 GPU 호스트가 켜져 있으면 플랫폼 과금이 계속될 수 있다. `gpuExecuted=false`는 그 과금 종료를 의미하지 않는다. 이번 도구는 유료 호스트 사용을 새로 승인하거나 비용 상한을 늘리지 않는다.

## 보존 대상

실제 `WORLD_ENGINE_STUDIO_STATE_ROOT`를 먼저 확인한다. 기본값은 `/var/lib/world-engine-private/engine/production-studio-mvp-v1`이고 운영 controller는 그 아래 `production`을 사용한다. 단독 runtime 기본 경로 `/production-studio-v1`와 혼동하지 않는다.

- `production/<studio-job-id>/STATE.json`, `PLAN.json`, `AUDIO.json`, `APPROVAL.json`, `supervisor.log`, 기존 `media/`.
- `production/render-v4/video-v2-<plan hash24>/JOB.json`, `PLAN.json` 및 private 장면 체크포인트 앵커. UNIVERSAL_V3이면 `render-v3`.
- `production/render-v4/cache/<scene cache key>/SUCCESS.json`, `attempt-*/COMPLETE.json`과 장면 MP4/영수증.
- 기존 `jobs`, `approvals`, `requests`, `runs`, `recoveries`, `ACTIVE.json`, `active.json`은 그대로 보존.
- Dropbox의 `world-engine-export-<id>/scene-recovery-<id>/segment.mp4`, `SHA256SUMS`. 별도의 private `SCENE_CHECKPOINT_ANCHOR.json`도 필요하다. 공유 SHA 파일만으로 NVIDIA 출처를 인증할 수 없다.
- 무음 완성본이 있으면 `world-engine-export-<id>/video-<id>/WORLD_ENGINE_AUTO_VIDEO.mp4`와 기존 private export receipt. 최종본이 이미 있으면 `studio-<id>/WORLD_ENGINE_STUDIO_VIDEO.mp4`와 기존 receipt.

관리자 코드·세션·토큰·전체 환경변수는 공개 폴더나 이 GitHub 저장소로 복사하지 않는다. 작업 자료를 다른 CPU 환경으로 이동할 때는 private 메타데이터를 공개 결과물과 분리하고 원본 해시·소유권·0600/0700 권한을 유지한다. 원본 앵커가 가리키는 경로를 임의 JSON 편집으로 위조하지 않는다. 현재 도구는 원본 private 레이아웃을 전제로 하며, 임의의 Dropbox MP4만으로 계획을 재구성하거나 앵커를 새로 만들어 주지 않는다.

## 합성 전용 도구

새 코드만 별도 위치에서 실행한다. 기존 이미지·렌더러·FINAL을 덮어쓰지 않는다. 기존 이미지 안에서 추가 경로 `/opt/world-engine-studio-cpu-recovery`를 사용할 경우, 원본 CPU 라이브러리는 기존 `/opt/rtx-package/repo/...`와 `/opt/world-engine-production-studio`에서 SHA 고정으로 재사용한다. 새 GPU 이미지를 배포할 필요는 없다. 도구는 로컬 UID/GID1000 private 연산용이며 무인증 웹 API를 추가하지 않는다.

읽기 전용 검사와 승인 초안 생성:

```bash
python3 -B /opt/world-engine-studio-cpu-recovery/recover.py prepare \
  --parent-job-id studio-bcd340f797498d7c9fea8181921f91b9 \
  --control-root /var/lib/world-engine-private/engine/production-studio-mvp-v1/production \
  --export-root /world-storage
```

위 경로는 기본값 예다. 실제 배포가 다른 private root를 사용하면 그 확인된 경로를 사용한다. `prepare`는 작업을 시작하지 않는다. 실행 중인 Studio/native PID, 미해결 claim, 손상·누락 자료가 있으면 차단한다.

초안은 `approved=false`, 만료/통화 미설정 상태다. 실제 검사에서 얻은 plan·원래 승인 SHA와 부모 job ID를 묶은 **별도 CPU-only 승인 파일**이 있어야 한다. 최대10800초, 추가 GPU 비용0, GPU 허용false, 자동 재시도0이며 원래 GPU 승인을 갱신하지 않는다. 무료 CPU 환경에서만 새 비용0 범위를 충족할 수 있다. 실제 GPU 호스트 시간을 사용하는 별도 작업은 승인된 비용 범위를 따로 확인한다. 예시 통화·요금·승인 만료를 지어내서 입력하지 않는다.

검증된 CPU 승인 파일이 있는 경우에만 다음 진입점을 사용한다:

```bash
python3 -B /opt/world-engine-studio-cpu-recovery/recover.py recover \
  --parent-job-id studio-bcd340f797498d7c9fea8181921f91b9 \
  --control-root /var/lib/world-engine-private/engine/production-studio-mvp-v1/production \
  --export-root /world-storage \
  --grant /confirmed/private/CPU_AUTHORIZATION.json \
  --request-id recovery-bcd340f7-cpu-v1
```

`/confirmed/private/...`는 실제 private 승인 파일 경로로 바꿔야 하는 자리 표시자다. 요청 ID는 ASCII이며 동일 요청을 다시 실행해도 완료 결과를 검증해 재사용한다. 기존 모바일 ‘재개’ 버튼으로 이 만료된 작업의 승인 한도를 늘리지 않는다. 기존 버튼은 원래 승인과 GPU health를 그대로 검사하므로 CPU-only 도구와 다른 경로다.

도구 선택 순서는 검증된 기존 silent export → 전체 private 장면 cache → independently anchored Dropbox scene checkpoint다. 무음 완성본이 있으면 장면 복사·재합성을 건너뛴다. 그 외에는 모든 범위·SHA·출처를 확인하고 새 private 파일로 복사한 후 기존 composer/SFX/stream-copy mux/export를 호출한다. 어느 경우에도 GPU 렌더러·원래 coordinator start/resume를 호출하지 않는다. 불완전한 자료는 GPU 재렌더링으로 자동 대체하지 않는다.

원래 작업은 FAILED 상태로 보존하고 새 `cpu-recoveries/cpu-recovery-<id>/STATE.json`에 복구 결과를 기록한다. 같은 완료 요청은 결과를 다시 해시 확인한 후 재사용한다. 실패 claim은 자동 초기화하지 않는다. 최종 Dropbox는 새 버전이며 기존 영상은 유지한다.

## 다음 신규 작업의180분 정책

기존 정책 검사 자체는10800초를 지원한다. 기존 GPU 요금·통화·최대 비용·재시도 상한은 그대로 두고, 실제 승인된 만료가3시간을 충분히 포함하는지 확인해야 한다. 최대 비용은 적어도 `실제 시간당 요금 × 3`을 감당해야 하며 부족하면 이 도구가 비용을 임의로 늘리지 않고 차단한다.

`policy.py stage --control-root <실제 production root> --candidate <실제 승인한 private 정책 파일>`은10800초 정책을 **비활성 revision**으로 저장하고 기존 정책 원문 bytes를 별도 보존한다. 이후 `policy.py activate --control-root <동일 root> --revision-id <출력된 revisionId> --confirm-future-policy`가 명시적 활성화다. 기존 작업의 APPROVAL·deadline·retry 기록은 바뀌지 않는다.

gCube의 기존 `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON` 환경변수와 private 정책이 서로 다르면 기존 bootstrap이 충돌을 차단한다. 현재 정책을 활성화한 후 다음 재시작 설정에도 **같은 실제 승인 정책**을 반영해야 한다. 환경변수 값만 바꿔 기존 private 파일을 강제로 덮어쓰지 않는다. 이번 작업에서는 실제 정책 파일에 접근하지 못했으므로 원격180분 적용 완료로 표시하지 않았다.

## 확인할 최종 결과

새 복구 기록에는 실제 verified copy, composition, silent export, SFX·최종 합성·저장·검증 시간이 남는다. 원래 STATE/JOB의 timing·events와 함께 병목을 판정한다. 합성 fixture의 실행시간을1080×1920 제작시간으로 환산하지 않는다.

최종 MP4는80초·2400프레임·1080×1920·30fps·H.264와 전체 디코딩/SHA를 확인한다. 마운트 내 readback과 Dropbox 외부 동기화·다운로드는 별개다. 실제 외부 다운로드 후 원본 SHA가 일치해야 전달 완료이며, 파일이 있다는 이유로 영상 품질이나 FINAL PASS를 선언하지 않는다.
