# WORLD ENGINE GPU 장애 기술 지식베이스 v1

2026-11-01 연구. **연구 완료 / GPU 복구 원인 미확정.** 운영 코드·이미지·gCube 설정 변경, GPU·렌더링, 기존 PASS 재실행은 모두 0회다. 문서는 별도 연구 브랜치에만 추가한다.

최신 실패 `studio-7d7a08be1d09817c903f41484bce3f33`의 실제 저장 진단에서도 `UP2_WEBGL2_REQUIRED`, `PAGE_EVALUATE_FIRST_NATIVE_DRAW`, `renderedFrames:0`을 확보했다. Chromium 옵션 복원 뒤 보고된 실패는 이전과 같은 WebGL2 생성 단계다. 다만 안전 진단에 실제 image digest와 최종 argv가 없어, **해당 작업의 실행 이미지·옵션까지 입증한 결과는 아니다.**

## 기술 판단

| 판단 | 근거 | 다음 결정 |
|---|---|---|
| **확인됨:** DOM canvas의 WebGL2 context 확보 실패 | [최신 안전 원문](evidence/latest-job/CAPTURE_DIAGNOSTIC.json), [실제 코드 경로](system/SYSTEM_ARCHITECTURE.md) | GPU/ANGLE/native 초기화 증거로 범위를 한정한다. |
| **유력한 조사 계층:** 실제 캡처의 Chromium GPU 프로세스→ANGLE→Vulkan/NVIDIA 그래픽 경로 | page import 이후 context 생성에서 실패. CPU·사전검사는 실제 capture를 실행하지 않으며 startup health 조건도 다름 | 장치·ICD·권한·sandbox·실제 argv 중 어디가 실패했는지 구분해야 한다. 특정 원인은 아직 선택할 수 없다. |
| **확인됨:** 현재 safe export만으로 실패 환경 전체를 재구성할 수 없음 | 원본 receipt의 dependencies/browserProfile와 private GPU_ALLOCATION 등이 safe export에 없음. 비JSON child 출력도 보존되지 않음 | [같은 작업의 기존 private 증거](ROOT_CAUSE_AND_PLAN.md)를 먼저 찾고, 없으면 보존 경로를 갖추기 전 재현하지 않는다. |
| **확인됨:** 복원한 옵션 한 줄은 완료된 변경이며 WebGL2 복구 PASS가 아님 | [기존 CHECKPOINT][checkpoint], 최신 동일 context 오류 | 재복원·동일 이미지 재빌드·다른 옵션 일괄 변경을 반복하지 않는다. |

WebGL2 생성은 라벨 pass, 첫 native draw, PNG 캡처, FFmpeg spawn보다 앞이다. **이 실패의 직접 원인으로 라벨·Namibia PNG·인코더를 다시 수정할 근거는 없다.** 그 단계의 향후 정상 동작까지 검증했다는 뜻은 아니다.

## 문서 선택

| 판단 목적 | 문서 |
|---|---|
| JSON부터 MP4 다운로드까지 실제 파일·함수·오류 전파 | [시스템 구조](system/SYSTEM_ARCHITECTURE.md), [소스 27개 색인](system/SOURCE_INDEX.json) |
| 과거 성공과 최신 실패의 관측값·설정값 구분 | [환경 비교표](ENVIRONMENT_COMPARISON.md) |
| 원인 후보의 확신 수준·판별·최소 복구 경로 | [근본 원인 평가와 실행 계획](ROOT_CAUSE_AND_PLAN.md) |
| Chromium/Playwright/ANGLE/WebGL2 조건과 적용 버전 | [브라우저 근거집](browser/BROWSER_GPU_KNOWLEDGE.md), [공식 출처](browser/OFFICIAL_BROWSER_SOURCES.json) |
| NVIDIA 주입·ICD·사용자·권한·환경 전달 | [NVIDIA/Vulkan 근거집](nvidia/NVIDIA_VULKAN_KNOWLEDGE.md), [공식 출처](nvidia/sources.json) |
| 이미 해결한 문제·반복하지 않을 작업·FFmpeg 경계 | [복구 이력과 인코딩](history/HISTORY_AND_ENCODING.md), [FFmpeg 공식 출처](history/official-sources.json) |
| 향후 실행 전 최소 조건과 무결성 주의 | [실행 전 기준](PRE_GPU_GATES.md) |
| 연구 범위·기준·미확정 사항 | [연구 CHECKPOINT](CHECKPOINT.json), [새 파일 SHA256](SHA256SUMS) |

## 기준과 증거 수준

- 운영 소스 열람 기준: `296402e71257c7847d0045215ca0cdaf3dd700d2`, `recovery/webgl-surface-restore-20261101`. 이미지 빌드 소스는 그 부모인 `b130ea8917d9b5ff7c2102a2f7beb9231fd79d74`다. 이후 커밋은 성과 보존이다.
- 마지막 확인된 저장 이미지: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:surface-restore-v1-41288263483`, digest `sha256:c9fa126b0bf0d06c109bbe45f9fe14b5cc71de4282a4a57455b3b5f19d3366b5`.
- 실제 성공: `studio-03d9b670cd764ce5823ea4720af1b410`, 180프레임. [기존 성공 근거에서 가져온 안전 요약](evidence/reused/SUCCESS_ENVIRONMENT.json). 원본 receipt를 새로 실행하거나 이전 PASS를 재검증하지 않았다.
- 최신 실패: 해당 job 이름의 Dropbox 폴더에서 안전 JSON과 SHA256SUMS 두 파일을 확보했다. [수집 기록](evidence/latest-job/INTAKE.json). 792 bytes, SHA256 `0f61c08da02b98fba68f08f9964c416a3d0d9adf9553e6113fcfc1e75df8baed`. 새 증거의 바이트 동일성만 확인했다.
- 마지막 관측 gCube 상태는 2026-11-01 17:23:58.647 KST의 Finished/노드 미할당이다. 이후 최신 실패 파일이 17:41:45 KST에 저장됐다. 따라서 **현재 live 배포/과금 상태는 이 과거 종료 기록으로 확정하지 않는다.** 이번 연구는 gCube를 조작하거나 Studio에 접속하지 않았다.

공식 문서의 일반 조건은 특정 작업의 원인 증명이 아니다. 고정 버전 소스와 rolling 문서를 구분했으며, 최신 실패의 미확보 값을 과거 성공 값으로 채우지 않았다. 각 출처 JSON은 URL, 적용 버전, 프로젝트 연결 및 한계를 담는다.

## 다음 최소 행동

같은 job의 기존 `CAPTURE_RECEIPT.json`, `GPU_ALLOCATION.json`, supervisor 결과가 정상 관리/저장 경로에 남아 있다면 안전 필드만 확보한다. 그 자료가 없다면 현재 저장 방식의 누락을 먼저 해결할 별도 작업이 필요하다. **새 진단기·이미지 재빌드가 기본 해법은 아니다.** 기존 경로에서 충분한 증거를 보존할 수 있는지 확인한 다음에만, 별도 승인된 GPU 실행 여부와 범위를 결정한다. [구체적인 분기와 최소 변경 조건](ROOT_CAUSE_AND_PLAN.md).

[checkpoint]: https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/webgl-surface-restore-v1/CHECKPOINT.json
