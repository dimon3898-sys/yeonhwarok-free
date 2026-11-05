# 2026-11-05 현재 렌더 정체 회수·수정 기록

현재 작업 `studio-3575e3b2e0c90037eadcad96e5738e86`은 두 번째 프레임(DRAW, index1)에서 `UP2_ACTUAL_FEATURE_PIXELS_MISSING`로 실패했다. 삭제된 11월3일 작업의 원인을 소급 확정하지 않는다.

## 확보한 증거

- 캡처 실패: 12:30:18.321 UTC. 브라우저 정상 종료 및 실패 receipt: 12:30:18.404 UTC.
- UI/worker는 1/300, RUNNING을 유지하다 12:40:05.433 UTC에 전체 제한 시간으로 FAILED가 됐다.
- 실제 내부 경로는 worker 인자로 확인했다. 기존 작업 디렉터리를 추측하지 않았다.
- 자동 mirror는 `ACTIVE_CHECKPOINT_TIMEOUT`. 해당 외부 폴더가 비어 있음을 확인했다.
- 종료 전에 진단 9종을 읽고 민감한 이름의 키를 제외한 내용·원본 파일 크기/SHA256을 `RECOVERED_CURRENT_JOB.json`으로 보존했다. 이 파일은 원본 바이트 전체의 복제본이 아니다.
- 종료 전 최종 state와 supervisor 결과, 프로세스 목록을 별도로 보존했다. deadline 후 cleanupVerified=true, 추적한 자식 프로세스 남음0. 별도 확인한 프로세스 목록에 node/Chromium/FFmpeg 없음.
- `FRAME_000.png` 2,764,419 bytes, 컨테이너 SHA256 `8c1ae24af68e3e711b81b0ee553d1ae670ddc6bd2834cc22e7a2a138f7d2954c`. Dropbox에 동일 크기 파일 존재 확인. 원격 바이너리 SHA256 대조는 하지 않았다.
- Dropbox 경로: `/WORLD_ENGINE/capture-checkpoint-studio-3575e3b2e0c90037eadcad96e5738e86/`. 두 진단 JSON은 연결 도구로 다시 읽어 별도 회수했다. 원문 stdout 파일 2개는 각각0 bytes였고, 구조화된 브라우저 기록과 capture receipt의 오류 stack은 회수했다.
- gCube 중지 이벤트: 21:41:44 KST. 최종 상태 종료, 노드ID 없음. 에이전트 GPU 시작0·재렌더0·재시도0.

## 원인과 실제 코드 변경

| 파일 | 변경 |
|---|---|
| `universal-presentation-v2/presentation_runtime.mjs` | AREA의 극소 alpha가 RGBA8 반올림 한계 이하일 때 changed-pixel을 강제하지 않음. draw/geometry 검사는 유지. |
| `codex-to-gcube-handoff-v1/presentation_runtime_vulkan.generated.mjs` | 같은 검사 수정. 렌더링 수식·카메라·라벨·Scene 그대로. |
| `codex-to-gcube-handoff-v1/controller/lease_supervisor.py` | 구조화된 terminal FAILED를 받은 즉시 원래 lease를 유지한 채 기존 descendant cleanup 진입. |
| `codex-to-gcube-handoff-v1/controller/capture_diagnostics_safe.py` | 비동기 저장 helper 한 개의 제한을1초→15초로 분리. 샘플 주기1초, 실패 후 재시도 없음, 캡처600초 제한 그대로. |
| `codex-to-gcube-handoff-v1/controller/safe_capture_export.py` | active exporter 내부 제한도15초까지 허용. private 권한·고정 schema·원자적 교체·읽기 확인 유지. |

동반 변경: GENERATED_SOURCE_MANIFEST, RUNTIME_SOURCE_MANIFEST, bootstrap 소스 pin, STARTUP_MANIFEST. 기존356개 소스 행 수 유지. 새 검사5개, CHECKPOINT/NEXT_GATE 및 이번 증거 파일 추가. 기존 성공 영상과 QUALITY_LABELS_10S.json(SHA256 `281250a9f3c866d4d0a424da0d06a6e9a3cf4e2ab31660b879657e7ab0b3a24e`)은 변경하지 않았다.

## 최소 검증 범위와 결과

이전 A6 PASS는 sparse 프레임 및 layout 범위였다. 이번 실제 frame1 실패는 그 검사가 포함하지 않은 구간이다. 기존 PASS 전체를 다시 실행하지 않았다. 새 수정으로 바뀐 failure cleanup과 storage budget만 별도로 검사했다.

[무료 CPU CI42031019500](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/42031019500), source `754b09262140b0ad5a48238843e0f98aaa8c4735`: SUCCESS, 첫 실행.

- 실제 software baseline frame1에서 같은 오류 재현.
- frame1 alpha=0.0018600464694684042, featureChangedPixels=0. `0.5/255` 이하의 변화가 RGBA8에서 사라지는 경계 조건.
- 후보: frames0/1/2 및 segment 진입150/151/152 완료, glError0. frame2에서176,764개 feature 픽셀 변화. frame0 PNG는 baseline과 후보 동일 SHA256.
- 실제 UID1000 CPU 프로세스: FAILED 뒤 살아 있는 자식2개 정리,0.3899초, lease 조기 해제 없음.
-1.3초 지연 helper의 고정 schema 쓰기·읽기 확인.15초 한도 후 kill/reap 및 재시도 없음.
- 별도 신규 로컬 UID0 검사: exporter 내부 fsync에1.3초 지연을 주어1.3035초 후 쓰기·읽기 확인. 실제 FUSE latency 검증으로 확대 해석하지 않는다.
- 변경 소스 pin9개 일치. 새 GPU0, 전체 MP4 렌더0, 이미지 빌드0, 이미지 게시0.

[영구 CPU 증거 ZIP](https://github.com/dimon3898-sys/yeonhwarok-free/releases/tag/incident-frame1-cpu-42031019500)

## 남은 차단과 다음 행동

현재 gCube에는 이전 capture-retention 이미지가 설정되어 있다. 수정 소스는 아직 배포하지 않았다. 다음 단계는 `IMAGE_FIX_PLAN.json`의9개 overlay로 새 immutable 이미지1회 게시 및 image/digest 설정 적용이다. 기존 게시1회 계획을 재사용해 자동 실행하지 않는다. GPU는 계속 종료 상태로 둔다.

새 이미지에서 자동 기록의 실제 gCube→Dropbox 회수, NVIDIA300프레임 완주·전체 디코딩·최종 외부 MP4·레퍼런스 품질은 아직 미검증이다. 유료 GPU 시작은 별도 승인이 필요하다. 이번 CPU PASS를 최종10초 MP4 성공으로 표시하지 않는다.
