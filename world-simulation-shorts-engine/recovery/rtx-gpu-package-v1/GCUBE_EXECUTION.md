# gCube 실행 절차 — 이번 작업에서는 실행하지 않음

먼저 `GCUBE_SETTINGS.md`의 장치·라이브러리·메모리·포트·영속 볼륨 설정을 적용할 준비를 합니다. 현재 gCube GPU와 계정 접속은 검증하지 않았습니다. 과거 감사에 확인된 API/SSH 구조를 재사용하며, 관리 API를 원격 명령 실행 API라고 가정하지 않습니다.

## 사용자가 준비할 설정

1. 후속 승인 후 새 패키지를 build하고 별도 registry/tag에 push합니다. 실제 manifest digest를 기록하고 그 digest를 가리키는 전체 image reference를 선택합니다. 기존 `7e32…` 이미지/tag는 덮어쓰지 않습니다. gCube UI의 digest 입력·private registry 인증·pull 성공은 실제 배포 시 확인해야 합니다.
2. 한 개의 RTX 4080 SUPER 16 GB, provider NVIDIA graphics/utility 주입, GPU device access를 선택합니다. 4090/5090도 런처에서 허용합니다. 이미지 안에서 kernel driver를 설치하지 않습니다.
3. `/dev/shm` 2 GiB를 설정하고 `/world-storage`에 전용 영속 볼륨을 연결합니다. container RAM 설정과 실제 mount/rename/권한/재시작 보존을 확인합니다. VRAM 기본 예산 8 GiB와 container RAM은 별도 항목입니다.
4. 원격 명령에는 실제로 지원되는 SSH 또는 provider의 command override 경로가 필요합니다. Codex 현재 환경은 gCube SSH/VPN/자격증명이 설정된 상태가 아닙니다. 기존 CLI의 공인 SSH TCP 경로와 로그 WSS를 명령 API로 바꾸어 해석하지 않습니다. credential은 repository/이미지/보고서에 넣지 않습니다.

## 별도 실행 진입점

아래는 향후 승인된 GPU host의 Docker 명령 예시입니다. 이번 준비 작업은 이 명령을 실행하지 않습니다. `NEW_IMAGE_AT_VERIFIED_DIGEST`는 실제 새 이미지 digest로 교체해야 합니다.

```sh
docker run --rm --gpus '"device=0"' --shm-size=2g --memory=8g \
  --mount type=volume,source=world-engine-rtx-results,target=/world-storage \
  -e NVIDIA_DRIVER_CAPABILITIES=graphics,utility \
  -e WORLD_ENGINE_RENDER_MODE=gpu-required \
  NEW_IMAGE_AT_VERIFIED_DIGEST --check
```

기본 command override를 비우면 같은 GPU admission 후 health-only 서버가 시작됩니다. `/healthz`만 지원하며 자동 영상 렌더링·원격 셸·임의 명령·파일 배포 API가 아닙니다.

검증 통과 후 승인된 기존 장면 실행은 같은 설정으로 인자를 `--render-65422`로 바꿉니다. 새로운 GPU 기능이나 ASTRA 재질 구현을 시작하는 명령이 아닙니다. gCube command field가 entrypoint 인자로 전달되는지 실제 플랫폼에서 확인합니다. SSH가 검증된 경우 실행 중인 컨테이너에서 **동일한 bootstrap**을 새로 호출할 수 있습니다:

```sh
/usr/bin/python3 /opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/bootstrap.py --render-65422
```

매 실행은 staged source와 native dependencies, 실제 GPU/WebGL2를 다시 확인합니다. 실패 시 CPU로 전환하지 않습니다. 한 allocation에서 동시에 두 capture를 실행하면 kernel capture guard가 거부합니다. interrupt 후 재개는 소스·driver·browser·GPU fingerprint가 같은 저장 프레임만 검증하여 재사용합니다.

## Codex가 후속 승인 후 자동화할 수 있는 범위

정확한 image/source hash 확인, package 준비·CPU 검사, 검증된 접속 경로에서 `--check`/명시적 capture 호출, private 진단 수집, 기존 입력·기능 보호 확인, 결과 SHA와 ffprobe 검사·허용 결과물 저장을 자동화할 수 있습니다. 실제 접속과 GPU 확인 전 성공을 선언하지 않습니다. 현재 패키지는 인증된 HTTPS render-job 서버를 새로 구현하지 않으므로, 접속 제한을 우회하는 방식으로 자동 실행하지 않습니다.

결과 위치는 `/world-storage/rtx-gpu-package-v1/captures/<source-and-hardware-signature>/`입니다. `public-review`에는 새 MP4·checkpoint PNG·SHA256SUMS만 있습니다. diagnostics/frames/rows/report/source/manifest는 공개하지 않습니다. 모바일 공개 URL 생성과 HTTP 200·다운로드 SHA 검사는 실제 새 proof 이후의 승인된 작업이며 이번 준비 단계에 영상이나 공개 URL을 만들지 않습니다.
