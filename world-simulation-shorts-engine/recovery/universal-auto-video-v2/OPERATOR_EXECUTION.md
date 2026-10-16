# 80초 실행 연결 절차 — 사용자 승인 후 운영자용

현재 단계에서는 유료 GPU 작업을 실행하지 않는다. 사용자는 중간 샘플이나 GPU
터미널을 검수할 필요가 없도록 설계했으나, gCube 계정 연결은 아직 설정되지 않았다.
이 문서는 승인 후 trusted control-plane worker가 공식 SSH 경로로 실행할 고정
명령을 설명한다. 공개 렌더 API 또는 임의 shell command 입력은 제공하지 않는다.

## 배포 설정과 보존

새 후보의 immutable digest는 최종 `IMAGE.json`을 따른다. 부모 이미지·완성 영상·
65422 claim을 덮어쓰지 않는다. RTX 4080 SUPER 16GB, 공유 메모리 2GB,
`NVIDIA_DRIVER_CAPABILITIES=graphics,utility,compute`,
`WORLD_ENGINE_RENDER_MODE=gpu-required`, `WORLD_ENGINE_STARTUP_MODE=normal`,
`WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST=sha256:<실제 후보 digest>`를 사용한다.
기존 normal 서비스와 기본 ENTRYPOINT/CMD를 유지한다. command override로
기존 `--render-65422` 또는 진단 전용 모드를 실행하지 않는다.

Dropbox는 기존 `/world-storage`에 둔다. private job/cache는
`/var/lib/world-engine-private/engine/universal-video-v2`의 UID/GID1000·0700
POSIX 디렉터리를 사용한다. 컨테이너 교체 후 자동 복구를 원하면 이 private 경로도
적합한 영구 POSIX 저장소로 보존해야 한다. Dropbox 공유 JSON만으로 NVIDIA
실행 provenance를 재인증하지 않는다. 알려지지 않은 mount 권한은 변경하지 않는다.

## 계정 연결과 비용 승인

운영자가 보안 설정에 gCube token/account/workload 식별자, 공식 API host와
SSH host/port/source-IP 허용 및 검증된 host key를 제공한다. 토큰이나 private key를
채팅·GitHub·Scene JSON·이미지에 넣지 않는다. 실제 단가·통화·최대 비용·wall time·
재시도 상한·승인 만료가 확정되기 전에는 실행하지 않는다.

`OPERATIONS_AUDIT.md`에 근거한 공식 CLI의 인증된 SSH 명령 실행을 사용한다.
현재 계정에서 연결·가격·STOP schedule 권한을 확인하지 않았으며, 자동 배포·
완료 시 과금 종료를 구현 완료로 표시하지 않는다. schedule PUT은 기존 목록을
대체하므로 원래 항목을 먼저 보존한다. 프로세스 timeout은 GPU 과금 종료가 아니다.

## 고정 실행 경로

아래 GPU 시작 명령은 아직 실행하지 않았다. trusted worker가 UID/GID1000으로 사유 작업
디렉터리를 생성하고 실제 후보 digest를 환경에 설정한다. 우선 저장된
`FIRST_PRODUCTION_80S_PLAN.json`을 `/PRIVATE/VIDEO_PLAN.json`으로 byte 그대로
복사한다. 파일 SHA는 `ca3498ee4221408f3a0cdc47d66e8704786a6312a98db19c4b98e49927c653d3`,
canonical plan SHA는 `69060bf9269fa091c7e070572f61efe00affa061c56827c9902942d0d4ea0f7b`다.
계획의 native payload는 이미지 내부 fixture 경로를 사용하므로 private 경로로
이동해도 원본 binding을 유지한다. `/PRIVATE`는 UID/GID1000·0700이며 파일은0600이어야 한다.

새로 계획을 생성해야 할 경우에만 다음 CPU 준비 명령을 사용한다. 저장된 plan의
검증이나 기존 데이터 조사를 반복하는 필수 단계가 아니다.

```bash
/usr/bin/python3 -B /opt/world-engine-universal-v2/prepare_video.py '한국전쟁의 전선 변화를 80초 영상으로 만들어줘.' --output /PRIVATE/VIDEO_PLAN.json --image-digest sha256:ACTUAL_IMAGE_DIGEST
```

준비 명령은 실제 2,400프레임·1080×1920·30FPS 계획과 native payload를 만들고 canonical
plan SHA를 출력한다. 원본 5개 도식 상태를 유지하며 미검증 부대 위치를 추가하지 않는다.
새로 생성한 plan의 SHA가 달라지면 해당 새 SHA에 대한 별도 승인이 필요하다.
이 단계는 GPU를 실행하지 않는다.

검증된 plan SHA와 실제 image digest에 대해 `ORCHESTRATION_AND_RECOVERY.md`의
정확한 authorization schema로 승인 파일을 작성한다. template의 비용·만료 placeholder는
유효 승인이 아니다. 승인 파일을 생성한 뒤에만 다음 고정 진입점을 실행한다.

```bash
/usr/bin/python3 -B /opt/world-engine-universal-v2/orchestrator.py start --plan /PRIVATE/VIDEO_PLAN.json --approval /PRIVATE/OPERATOR_APPROVAL.json
/usr/bin/python3 -B /opt/world-engine-universal-v2/orchestrator.py status --plan /PRIVATE/VIDEO_PLAN.json
```

`start`는 실제 PID와 job ID를 기록하고 터미널과 독립 실행한다. 상태 확인은 재실행이
아니다. 컨테이너 재시작·실패 이후에는 원인과 기존 worker 종료 여부를 확인한 뒤
명시적으로 `start ... --resume`한다. 기존 claim·실패 attempt·완료 scene을 지우지 않는다.

## 완료 검증과 전달

coordinator가 장면별 capture→검증 cache→비공개 Dropbox checkpoint→합성→전체 decode
→공개 결과 export 순서로 진행한다. Public Review는 MP4·SHA256SUMS·안전한
QUALITY_SUMMARY.json만 포함한다. 내부 로그·원본 데이터·진단은 별도 private 경로에 둔다.

최종 기술 검사와 mount readback만으로 외부 전달을 완료했다고 판정하지 않는다.
실제 Dropbox 공유 URL을 확보한 뒤 기존 HTTPS 검증 경로로 HTTP200과 다운로드 SHA를
확인하고 전체 MP4를 재생·비교한다. 사용자에게 80초 완성본만 검수 요청한다.
외부 보존과 private 회수 기준을 확보한 뒤 공식 STOP과 실제 stopped 상태를 확인한다.
사용자 실제 영상 승인 전 FINAL 승격은 없다.
