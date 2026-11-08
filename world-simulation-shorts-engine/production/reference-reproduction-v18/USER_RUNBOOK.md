# 한국전쟁 20초 — 인수 후 현재 실행 기준

**현재 GPU 실행은 보류한다.** 표현 입력은 준비됐지만 새 표면 자료 승인과 실제 영상 품질은 미완료다.

## 보존한 배포 이미지

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:worker-launch-v16-42446481907
sha256:1ab43dd68e5ccdd364b6ec97d61d2f877070213cc42101412f45e17c54871e4b
```

빌드 성공: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/42446481907

백업: https://github.com/dimon3898-sys/yeonhwarok-free/releases/tag/worker-launch-image-backup-42446481907

이전 저장 증거는 RTX5090×1, HTTP8080, Storage `/world-storage`, 빈 Command,
공유 메모리 3GB다. 이번 Work는 gCube 현재 화면을 재조회하지 않았고 설정도 바꾸지 않았다.
현재 종료 상태나 실제 마운트 정상 여부를 새로 확인한 것으로 해석하지 않는다.

## 최신 입력 후보 — 기존 JSON을 덮어쓰지 않음

두 파일은 `ad4441661c250826b150fbef01ab1a8e557c572a`에 고정한다.

- PART01: https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/ad4441661c250826b150fbef01ab1a8e557c572a/world-simulation-shorts-engine/production/reference-reproduction-v18/ready-a4/KOREAN_WAR_REFERENCE_CANDIDATE_PART_01.json
- PART02: https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/ad4441661c250826b150fbef01ab1a8e557c572a/world-simulation-shorts-engine/production/reference-reproduction-v18/ready-a4/KOREAN_WAR_REFERENCE_CANDIDATE_PART_02.json

```text
PART01 SHA256 ffcbf85fa99a82a903f49e3cedbdecf69c5cac90b968e8780560637f20623792
PART02 SHA256 3f569901e1ff0ed45f7dd3cabe17d89ad0666179981ef98e59051d1a3dde6611
```

각각 GENERAL, 10초, 30fps, 1080×1920, 300프레임, 2장면이다.
실제 GPU 영상 품질 PASS나 실행 준비 전체 완료를 뜻하지 않는다.
앞으로 데이터 연결 변경이 생기면 이미지와 입력 호환성을 다시 한정 확인해야 한다.

## 차단 해소 후 사용자가 실행할 순서

1. https://gcube.ai/demand/ns74a360e2/workload/5373 에서 최종 확정 이미지·RTX5090·저장 설정을 확인하고 직접 배포한다.
2. 새 HTTP8080 주소로 Studio에 접속한다. NVIDIA/WebGL2/Vulkan 및 실제 Storage 사전검사 통과를 확인한다.
3. PART01을 올려 10초·300프레임·2장면을 확인한 후 한 번 제작한다.
4. COMPLETED/COMPLETE와 실제 MP4·QUALITY_SUMMARY.json·SHA256SUMS 다운로드를 확인한다. 첫 구간 실패 시 둘째 구간을 실행하지 않는다.
5. PART02도 같은 순서로 제작·다운로드한다. 두 작업을 동시에 시작하지 않는다.
6. 원본 두 개와 증거가 저장됐으면 사용자가 배포를 중지하고 종료·노드 해제를 확인한다.
7. 기존 WORLD ENGINE 합성기로 20초를 연결하고 600프레임·전체 디코드·순서·실제 시각 품질을 확인한다.

기존 CPU 합성 절차는 `../korean-war-20s-rtx5090-v12/USER_RUNBOOK.md`의
“기존 합성기 — 사용자 PC의 CPU CLI” 절에 있다. 그 문서의 예전 이미지 값은 사용하지 않는다.
합성 명령은 아래와 같고, 실제 두 파일의 해시가 담긴 `KW20_SEGMENTS.json`이 먼저 필요하다.

```bash
python3 world-simulation-shorts-engine/recovery/universal-auto-video-v2/compose.py --plan world-simulation-shorts-engine/production/korean-war-20s-deployment-v11/COMPOSE_PLAN.json --segments KW20_SEGMENTS.json --destination KW20_COMPOSE_5090_01
```

모바일 자동 합성 UI는 미연결이다. 실제 두 MP4가 있어야 기존 CPU 합성을 수행할 수 있다.

## 오류 보존

반복 시작하지 말고 작업ID·오류코드·단계·프레임·마지막 갱신 시각과 진단 다운로드를 보존한다.
기존 `ActiveCheckpointMirror`는 `/world-storage/capture-checkpoint-<작업ID>/CAPTURE_CHECKPOINT.json`에
제한된 진행·오류 스냅샷을 기록한다. 전체 private 파일 백업은 아니다. 실제 마운트는 실행 때 확인한다.
사용자가 증거를 내려받은 뒤 배포를 중지한다. 삭제된 Pod의 복구 불가 원문 회수는 반복하지 않는다.
