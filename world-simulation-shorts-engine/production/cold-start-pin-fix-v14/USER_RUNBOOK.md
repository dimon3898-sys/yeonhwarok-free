# v14 시작 오류 수정 — 사용자 실행 안내

2026-11-08. 이 문서는 v13 이미지 실행 안내를 대체한다. v13에는 Work가 시작 해시 갱신을 누락한 결함이 있었으며 배포 준비 판정을 취소했다. v14는 이를 수정하고 실제 ENTRYPOINT CPU 검사를 거쳤다. GPU에서 Studio와 MP4가 성공했다는 의미는 아니다.

```text
Workload:#5373 / world-engine-test
이미지:ghcr.io/dimon3898-sys/world-simulation-shorts-engine:cold-start-v14-42443683657
digest:sha256:a1eb4f0f1671d1cec1fb7e310c65b8479b0aa5e1e7bf11b00a1e3f9a1f78d3a7
GPU:TIER2 RTX5090 ×1 /32GB
HTTP:8080 / Storage:/world-storage / Command:빈 값 / 공유 메모리:3GB
현재:종료·노드 미할당 / Work GPU 기동·렌더링·배포 중지:0회
```

이미지와 digest 환경변수2개만 저장하고 재조회했다. 나머지13개 환경변수, 인증, 비용·시간·재시도 정책, GPU와 포트·저장소 설정은 보존했다. 사용자가 직접 설정을 고칠 필요는 없다. 기존 JSON 크기 수정도 v14에 유지된다.

- [gCube 배포 화면](https://gcube.ai/demand/ns74a360e2/workload/5373)
- [1구간 JSON](https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_01.json)
- [2구간 JSON](https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_02.json)

```text
https://gcube.ai/demand/ns74a360e2/workload/5373
https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_01.json
https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_02.json
```

1. 저장 이미지가 cold-start-v14-42443683657, GPU가 RTX5090×1인지 확인하고 사용자가 **배포**한다. 재고·가격이 달라졌으면 임의 GPU 변경을 하지 않는다.
2. Running이 된 뒤 새 **HTTP8080 서비스 주소**로 Studio에 접속한다. 이전 서비스 포트/주소를 고정 재사용하지 않는다. 기존 인증을 사용한다.
3. GPU/WebGL2/Vulkan 진단과 영구 저장소 사전검사를 확인한다. FAIL/BLOCKED가 있으면 제작을 시작하지 않는다. 다시 CrashLoopBackOff면 아래 오류 절차를 따른다.
4. 기존 **PART_01 JSON**을 새 작업으로 선택하고 사전검사한다.10초·300프레임·2장면이고 전체 PASS일 때 사용자가 제작 시작을 한 번 누른다. 과거 FAILED 작업 새로고침은 재실행이 아니다.
5. COMPLETED/COMPLETE 확인 후 WORLD_ENGINE_STUDIO_VIDEO.mp4, QUALITY_SUMMARY.json, SHA256SUMS를 다운로드한다. 실제10초 재생도 확인한다.300/300표시만으로 성공을 판정하지 않는다.
6. PART_01 다운로드 성공 뒤에만 PART_02를 같은 순서로 진행한다. 두 작업을 동시에 돌리지 않는다.
7. 두 MP4와 증거를 보관하면 사용자가 **배포 중지**하고 종료·노드 해제를 확인한다. CPU 합성을 위해 GPU를 유지하지 않는다.
8. 실제 정식 MP4 두 개만 [기존 WORLD ENGINE CPU 합성 안내](../korean-war-20s-rtx5090-v12/USER_RUNBOOK.md#기존-합성기--사용자-pc의-cpu-cli)에 따라 연결한다. 링크 문서의 옛 이미지 안내는 쓰지 않고 CPU CLI 절만 적용한다. Python3/Git/FFmpeg가 있는 PC 또는 WSL이 필요하다. 휴대폰 Studio의 자동20초 합성 UI는 미연결이다. CLI 환경이 없으면 두 MP4를 보존하고 합성 BLOCKED로 남긴다.

## 오류 발생 시

반복 배포·재렌더링을 하지 않는다. CrashLoop이면 파드ID,노드ID,이미지태그,오류,이벤트 시각과 화면을 저장하고 사용자가 배포를 중지한다. Studio 작업 오류이면 추가로 작업ID,PART번호,단계,프레임/장면수와 진단 파일을 저장한다. 외부 저장소의 capture-checkpoint/capture-diagnostic 파일 및 SHA256SUMS도 보관한다. 전체 private 원문이나 MP4가 항상 자동 영구 보존된다는 뜻은 아니다. 삭제한 컨테이너의 private 원문/stdout 회수는 반복하지 않는다.

## 확인 범위

새 이미지의 시작 해시 검증, 실제 ENTRYPOINT CPU 경로, 백업·GHCR digest 및 gCube 저장값은 확인했다. ENTRYPOINT 시험은 실제 인증 없이 의도한 Owner 필수 설정 단계에서 정지했으며 Studio/GPU를 실행하지 않았다. 원래 인증 보호를 우회하거나 지우지 않았다.

HISTORICAL 차단, Studio 자동 합성 UI 미연결은 그대로다. 실제5090 시작·10초 MP4·최종20초·레퍼런스64306.mp4 대비 품질은 사용자 출력 후 확인한다.

[무료 CI 증거](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/42443683657) · [새 이미지 백업](https://github.com/dimon3898-sys/yeonhwarok-free/releases/tag/cold-start-image-backup-42443683657)
