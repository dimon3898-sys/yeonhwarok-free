# 300/300 이후 실패 — 수정 이미지 사용자 실행 안내

2026-11-08. 새 이미지 게시·백업 및 gCube #5373 저장/재조회 완료. 현재 종료·노드 미할당이다. Work의 GPU 기동·렌더링·배포 중지는0회다. 실제 v13 MP4 성공은 아직 미검증이다.

## 바뀐 점

FRAME_EVIDENCE 전용 읽기 경계만 수정했다. 기존 입력 JSON·Scene·GeoJSON·지형·렌더러·인코더·합성기는 유지했다. 크기 경계 및 보호 검사10개 PASS, 새 이미지 설치 무결성/모듈 연결 PASS. 원본 실패 파일의 실제 크기는 확인 불가이므로 실패 해소를 실제 GPU PASS로 선언하지 않는다.

```text
이미지: ghcr.io/dimon3898-sys/world-simulation-shorts-engine:capture-json-v13-42442147946
digest: sha256:c43c8514e471a68d0c150f01358a7fff0ee5d059e0b3da5b699bcf354b202da4
GPU: TIER2 RTX5090 ×1 /32GB
포트:8080 / Storage:/world-storage / Command:빈 값 / 공유 메모리:3GB
```

이미지와 digest 환경변수2개만 바꿨다. 나머지13개 환경변수와 기존 인증·정책·GPU 설정을 보존했다. 새 ENTRYPOINT도 기존 tini→bootstrap 구조이며 필수 manifest 해시만 갱신했다. 사용자가 설정을 다시 입력할 필요는 없다.

## 다운로드와 실행

- [gCube #5373 배포 화면](https://gcube.ai/demand/ns74a360e2/workload/5373)
- [1구간 JSON](https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_01.json)
- [2구간 JSON](https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_02.json)

```text
https://gcube.ai/demand/ns74a360e2/workload/5373
https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_01.json
https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_02.json
```

1. gCube #5373에서 저장된 태그가 capture-json-v13-42442147946, GPU가 RTX5090×1인지 확인하고 사용자가 **배포**한다. 재고/가격 조건이 달라졌으면 임의로 다른GPU를 선택하지 않는다.
2. Running 이후 표시되는 **HTTP8080 서비스 주소**로 Studio에 접속한다. 이전 :24999 주소를 고정 재사용하지 않는다. 기존 인증을 사용한다.
3. GPU/WebGL2/Vulkan 하드웨어 조건, 영구 저장소 사전검사 PASS를 확인한다. FAIL/BLOCKED면 제작을 시작하지 않는다.
4. 동일한 **PART_01 JSON**을 새 작업으로 선택하고 사전검사한다.10초/300프레임/2장면이 맞고 전체 PASS일 때 사용자가 제작 시작을 한 번 누른다. 기존 FAILED 작업의 새로고침은 재실행이 아니다. 기본6초 예제나 PART_02를 먼저 실행하지 않는다.
5. COMPLETED/COMPLETE가 되면 WORLD_ENGINE_STUDIO_VIDEO.mp4, QUALITY_SUMMARY.json, SHA256SUMS를 다운로드하고 실제10초 재생을 확인한다.300/300표시만으로 최종 성공을 판단하지 않는다.
6. PART_01 다운로드 성공 후에만 PART_02를 같은 순서로 실행하고 결과를 보존한다. 동시에 두 작업을 실행하지 않는다.
7. 두 MP4와 증거를 다운로드한 뒤 사용자가 gCube **배포 중지**를 누르고 종료/노드 해제를 확인한다. CPU 합성을 위해 GPU를 켜둘 필요는 없다.
8. 두 실제 정식 MP4만 기존 WORLD ENGINE CPU CLI 합성기에 넣어20초/600프레임으로 연결한다. [기존 사용자 안내의 CPU CLI 절](../korean-war-20s-rtx5090-v12/USER_RUNBOOK.md#기존-합성기--사용자-pc의-cpu-cli)을 그대로 사용한다. 그 문서의 이전 이미지 태그·미검증 저장소 문구는 이번 안내로 대체한다. Python3/Git/FFmpeg가 있는 PC/WSL이 필요하다. 휴대폰 Studio의 두 작업 자동 합성 UI는 미연결이며, CLI환경이 없으면 합성을 BLOCKED로 남긴다. 다른 편집기로 대체하지 않는다.

오류가 나면 자동·수동 재시도 없이 작업ID,PART번호,오류코드,단계,프레임/장면수,시각과 화면을 보존한다. 진단 파일과 외부 저장소 capture-checkpoint-<job>/CAPTURE_CHECKPOINT.json, capture-diagnostic-<job>/CAPTURE_DIAGNOSTIC.json 및 SHA256SUMS를 보관한 뒤 사용자가 배포를 중지한다. 기존 작업의 실제 외부 체크포인트·진단 회수는 확인됐다. 전체 private 원문/MP4가 자동 영구 보존된다는 뜻은 아니다.

## 보존 및 미지원

기존 v11 이미지·원본 입력·과거 PASS와 실패 증거를 보존했다. [새 이미지 백업](https://github.com/dimon3898-sys/yeonhwarok-free/releases/tag/capture-json-image-backup-42442147946), [무료 빌드 결과](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/42442147946).

HISTORICAL 차단과 Studio 자동20초 합성 UI 미연결은 유지된다. GENERAL의 검증된 현대 지도/지형만 쓰며1950년 전선을 임의 생성하지 않는다. 최종20초 MP4와64306.mp4 대비 시각 품질은 실제 출력 후 검증한다.
