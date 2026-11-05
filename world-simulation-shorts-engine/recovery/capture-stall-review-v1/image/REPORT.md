# WORLD ENGINE — 이미지 게시·gCube 저장 결과 (2026-11-05)

기존 CPU PASS 20개를 재실행하지 않고, 검증된 기록 보존 변경 9개 파일만 기존 품질 이미지에 추가했다. 새 이미지 1회 빌드·완전 백업·GHCR 게시와 gCube 설정 저장을 완료했다. GPU는 시작하지 않았다.

## 신규 성과

- 새 이미지: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:capture-retention-v1-42002690934`
- digest: `sha256:534e5afd33e73b9d3f3e49db3f4a7dc63a1ee25a91457611f2d4b4fcb00e1e4c`
- 이미지의 변경 파일 9개, UID1000의 시작 manifest 및 runtime source 계약 PASS. 기존 127개 층 보존 + 추가 1개 층이다.
- 완전 이미지 백업 806,385,501바이트를 새 GitHub Release에 보관했다. CI에서 모든 archive layer hash와 config/manifest를 대조하고, 업로드 후 GitHub 자산 size/digest를 확인했다. 이 Work에서 백업을 재다운로드해 복원 실행한 것은 아니다.
- 게시된 태그와 digest, 백업의 image/config identity 일치. 기존 quality 태그의 digest 불변.
- gCube #5373에서 이미지 검증 완료 후 이미지 태그와 이미지 digest 환경변수 두 항목만 변경했다. 이미지 검증이 자동 설정한 포트8000은 기존8080으로 복원했다. 저장소 `/world-storage`, GPU·레플리카, 명령, 나머지 환경변수, 공유 메모리3GB 유지.
- 저장 후 관리 화면에서 새 태그, 종료, 노드 ID —, 이전 배포 시각 유지 확인. 실제 컨테이너 기동·런타임 digest 확인·마운트 외부 회수는 미실행이다.

## 실제 변경 파일

이번 단계에는 렌더러나 runtime 소스를 추가 변경하지 않았다.

- `image/build_once.py`: 기존 registry·Docker·백업 helper를 재사용하는 1회 빌드/게시 절차.
- `image/installed_probe.py`: 부모와 새 이미지의 제한된 파일·시작 계약 확인. 브라우저·GPU·FFmpeg 실행 없음.
- `image/BASE_PINS.json`: 보존할 부모 이미지 파일 해시.
- `.github/workflows/world-engine-active-retention-image-once.yml`: 정확한 부모 commit·branch·message·실행1회·공개 저장소·표준CPU runner 조건.
- `image/PREPARATION.json`, `image/PREPARE_RESULT.json`, `image/GCUBE_BEFORE.json`, `image/GCUBE_SETTINGS.json`, `executions/20261105-image-42002690934/`, `CHECKPOINT.json`, `NEXT_GATE.json`, `SHA256SUMS`: 증거와 이어가기 기록.

## 검증 결과

- [빌드 실행](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/42002690934): SUCCESS, 재시도0.
- [완전 이미지 백업](https://github.com/dimon3898-sys/yeonhwarok-free/releases/tag/capture-retention-image-backup-42002690934).
- 기존 소스/CPU 20개 PASS 재사용. 이미지 포장·설치 검사는 새 산출물의 첫 검증이다.
- CI 증거8개를 로그 원본 base64에서 회수해 SHA256과 Release 자산 size/digest를 대조했다.
- 빌드1, 게시1, gCube 저장1, GPU기동0, 렌더링0, 과거PASS재실행0.
- main과 기존 품질 브랜치, 이전 이미지·태그·MP4·Scene은 수정하지 않았다.

## 남은 차단 원인과 다음 행동

다음 단계는 새로 승인된 유료 GPU 세션이다. 제안 범위는 RTX4080 Super×1, 최대30분, 비용상한500원, 재시도0이다. 아직 승인되지 않았다. 실제 저장소 회수 확인에 실패하면 렌더링하지 않고 중지한다. 통과하면 기존 품질10초 작업1회를 실행한다.

기존 1/300 정체의 원인과 실제 해결 여부, 레퍼런스 수준 MP4 완성은 아직 미확정이다. 삭제된 private 파일·stdout/stderr를 다시 찾거나 기본10초·라벨·지도 기능을 재개발하지 않는다.
