# 한국전쟁 샘플 — v16 PID 저장 순서 수정 후 사용자 실행

고객지원 답변을 기다려야만 진행할 수 있는 상태는 아니다. 실제 코드에서
작업 시작 시 PID가 사라지는 결함을 무료 재현했고, 최소 수정 후 새 검사
6개를 통과했다. 새 이미지의 설치·시작 경로 검증, 게시·백업과 gCube 설정
저장·재조회도 완료했다. 기존 10초 성공 PASS를 다시 실행하지 않았다.

이번 158프레임 사건의 원본 state/launch가 없어 이 결함이 유일한 원인이었는지는
미확정이다. v16의 실제 RTX5090 MP4와 최종20초 품질은 아직 검증하지 않았다.
전체 제작 완료 또는 GPU 성공 PASS를 선언하는 문서가 아니다.

## 저장된 이미지 — 사용자가 수정할 값 없음

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:worker-launch-v16-42446481907
sha256:1ab43dd68e5ccdd364b6ec97d61d2f877070213cc42101412f45e17c54871e4b
```

RTX5090×1,HTTP8080,Storage `/world-storage`,빈 Command,공유 메모리3GB,
기존 인증·정책·나머지13개 환경변수는 그대로다. 새 image digest 두 값만 함께
갱신했다. 현재 종료·노드 미할당이며 Work의 배포 시작·중지·렌더링은0회다.

## 기존 입력 그대로 사용

- [1구간 JSON](https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_01.json)
- [2구간 JSON](https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_02.json)
- [gCube #5373](https://gcube.ai/demand/ns74a360e2/workload/5373)

```text
https://gcube.ai/demand/ns74a360e2/workload/5373
https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_01.json
https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_02.json
```

각 입력은 기존1080×1920·30fps·10초·300프레임·2장면·GENERAL·무음이다.
HISTORICAL과 미검증 전선·영토 변화를 활성화하지 않는다.

## 사용자가 직접 실행할 순서

1. gCube #5373에서 종료 상태,RTX5090×1,위 v16 이미지가 표시되는지 확인한다.
   실제 실행을 하기로 한 경우 사용자가 **배포**를 누른다. 설정 수정은 필요 없다.
2. 실행 후 상세의 HTTP8080 서비스 링크로 Studio에 접속한다. 서비스 주소는
   새 배포 화면에서 확인한다. 예전 주소를 추측해 입력하지 않는다.
3. 기존 인증으로 접속하고 NVIDIA/WebGL2/Vulkan·Storage 사전검사가 통과해야 한다.
   PART_01을 선택해 사전검사 결과10초·300프레임·2장면을 확인한다.
4. 사용자가 제작 시작을 한 번 누른다. 완료 전에는 PART_02나 재시작을 누르지 않는다.
5. COMPLETED/COMPLETE,300/300,2/2를 확인하고 MP4·QUALITY_SUMMARY.json·SHA256SUMS를
   다운로드한다. 300프레임 표시만으로 MP4 성공을 판정하지 않는다.
6. 첫 구간 MP4가 실제 출력·다운로드된 다음 PART_02를 같은 순서로 실행·다운로드한다.
7. 두 원본 MP4와 증거를 보존한 뒤 사용자가 gCube 배포를 중지하고 종료·노드 해제를
   확인한다. CPU 합성을 위해 GPU를 켜둘 필요는 없다.
8. 기존 WORLD ENGINE 합성기로 두 정식 MP4를 연결한다. 명령과 파일 순서는
   [기존 CPU 합성 안내](../korean-war-20s-rtx5090-v12/USER_RUNBOOK.md#기존-합성기--사용자-pc의-cpu-cli)를 그대로 사용한다.
   이 링크의 예전 이미지 안내는 사용하지 않는다. Studio의 모바일 자동 합성 UI는
   미연결이므로 CLI 환경이 없으면 두 원본을 보존하고 합성은 BLOCKED로 남긴다.

## 오류가 다시 나오면

자동 재시도나 재렌더링은 하지 않는다. 작업ID,오류코드,단계,프레임,경과시간,
화면과 마지막 갱신 시각을 저장한다. 기존 진단 다운로드가 제공되면 보관하고,
Dropbox의 `capture-checkpoint-<작업ID>/CAPTURE_CHECKPOINT.json`을 보존한다.
원본 state/launch/worker exit 정보가 없으면 원인 확정이 제한되므로, 터미널이
열리는 경우 기존 진단 정보 확보 후 사용자가 중지한다. 원시 로그·인증값을
공개 게시하지 않는다. 삭제된 Pod 파일 회수를 반복하거나 GPU를 다시 켜지 않는다.

기존 체크포인트는 제한된 진행 기록이다. private state/launch 전체의 영구
백업이나 정리 완료 증거를 대신하지 않는다. 이번에 새 진단기를 개발하지 않았다.

[수정 증거](REPAIR_NOTE.md) · [무료 패키징 Actions](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/42446481907)
· [이미지 백업](https://github.com/dimon3898-sys/yeonhwarok-free/releases/tag/worker-launch-image-backup-42446481907)
