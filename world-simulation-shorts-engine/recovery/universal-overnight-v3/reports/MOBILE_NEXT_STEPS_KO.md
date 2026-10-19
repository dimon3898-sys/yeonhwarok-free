# 휴대폰 다음 행동

지금은 새 GPU를 배포하거나 기존 워크로드를 재시작하지 않습니다. 먼저 공개 검수 폴더의 **5초 MP4와 비교 PNG**를 휴대폰에서 확인합니다. 소프트웨어 렌더 결과는 보고서에서 `SOFTWARE_VALIDATION`으로 구분합니다. 실제 NVIDIA 검증이나 최종 영상 품질 합격을 뜻하지 않습니다.

## 내일 할 일

1. 최종 보고서의 **5초 MP4 다운로드**를 누릅니다.
2. 영토 색상, 전선, 카메라, 지형·바다를 확인합니다. 효과음이 포함된 파일은 동기화도 확인합니다.
3. 이 대화에 검수 결과를 남깁니다. 현재 단계에는 터미널·토큰 복사·Scene 재작성·유료 GPU 실행이 필요하지 않습니다.

검증된 MP4가 생성되지 않았다면, 실패 보고서의 실제 원인과 마지막 저장 지점을 먼저 확인합니다. 파일이 없는 상태를 영상 검수 완료로 처리하지 않습니다.

## 이후 별도 비용 승인을 받았을 때의 GPU 후보

다음 값은 배포를 지시하는 것이 아니라, 검증된 후보의 연결 계약을 기록한 것입니다. **CI 이미지 등록과 독립 pull 확인 전에는 사용할 수 없습니다.**

- 후보 이미지: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:7d45f95a7dd30a8e66a8cf6ef521e8ed38981e1fd07bd992eee4aea0ba78a645`
- gCube 서비스 포트: `8080`
- Command: **비움**. 이미지의 기존 안전한 bootstrap을 사용합니다.
- 동작: `OVERNIGHT_SAFE_V3`의 **연속 5초·150프레임 Preview 전용**. 80초 전체 제작은 차단됩니다.

| 설정 | 실제 지원되는 입력·처리 |
|---|---|
| `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST` | `sha256:7d45f95a7dd30a8e66a8cf6ef521e8ed38981e1fd07bd992eee4aea0ba78a645` — 실제 이미지와 같은 immutable digest만 사용 |
| `WORLD_ENGINE_OVERNIGHT_IMAGE_PROOF_JSON` | 해당 이미지의 독립 pull 검증 후 생성된 **`IMAGE_PROOF.json` 전체 JSON**. 이전 Completion 이미지 proof를 재사용하지 않음 |
| `WORLD_ENGINE_STUDIO_PORT` | `8080` |
| `WORLD_ENGINE_RENDER_MODE` | `gpu-required`. 소프트웨어 검증을 허용하는 운영 설정은 없음 |
| `WORLD_ENGINE_STARTUP_MODE` | `normal` |
| `WORLD_ENGINE_STUDIO_OWNER_CODE` | 기존 관리자 인증 설정 유지. 보고서·채팅에 값을 붙여넣지 않음 |
| `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN` | 실제 발급된 HTTPS Origin 유지. 주소가 바뀌면 기존 `/setup`의 관리자 인증·주소 등록 절차 사용 |
| `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON` | 실제 GPU 단가·최대 비용·실행시간·재시도 상한·승인 만료시각을 새 승인 범위에 맞춰 설정. 과거 80초 승인 금액을 재사용하지 않음 |
| `WORLD_ENGINE_STUDIO_STATE_ROOT` | 기존 안전한 로컬 private 경로 유지. `/world-storage`로 강제 변경하지 않음 |

새 image proof는 비밀 토큰이 아니라 소스·이미지 결합 검증 기록입니다. `sourceManifestSHA256`, `sourceCommit`, `imageDigest`가 실제 후보와 일치해야 하며, bootstrap이 기존 인증 구조를 통해 private 파일로 보존합니다. 누락·불일치하면 제작이 차단됩니다. 기존 Secret과 이전 이미지 proof는 삭제하지 않습니다.

현재 단가·승인 금액·만료시각은 이 문서에서 임의로 정하지 않습니다. 컨테이너의 시간 제한은 gCube의 과금 종료와 별개이며, 워크로드 시작·정지는 사용자가 승인 후 수동으로 관리합니다.

## 승인 후 Studio에서 사용할 입력

1. 실제 gCube HTTPS 주소의 Studio에 기존 관리자 계정으로 로그인합니다.
2. `STUDIO_OVERNIGHT_5S_PROMPT.json`의 내용을 **제작 프롬프트**에 붙여넣습니다. Scene JSON을 새로 만들지 않습니다.
3. 원본 Scene 길이는 **80초**로 유지됩니다. 출력은 그 시간축에서 선택한 **5초 Preview**이며, 시작 버튼도 **5초 Preview 제작**으로 표시됩니다.
4. **사전검사** 결과에서 자료·이미지 proof·GPU·저장소·비용 정책을 확인합니다. 모든 검사가 통과하고 해당 유료 Preview가 별도로 승인된 경우에만 동의 후 **5초 Preview 제작**을 누릅니다.
5. 브라우저를 닫아도 분리된 작업은 유지됩니다. 다시 접속해 같은 작업 ID의 상태를 확인합니다. 실패 시 새 작업을 반복 생성하거나 기존 claim을 삭제하지 않습니다.

프롬프트의 `overnight.operation`은 `PREVIEW_5S`입니다. `FULL_80S`, 임의 회전·Detail 설정, 소프트웨어 GPU 우회 입력은 거부됩니다. 기존 자료에 없는 국가별 부대 위치나 점령 영역도 생성하지 않습니다.

완료 MP4는 기존 `/world-storage` 내 새 버전 폴더로 내보내고 SHA를 다시 확인합니다. Studio 결과 화면에서 실제 폴더와 다운로드를 확인합니다. 마운트 저장 성공과 Dropbox 외부 다운로드 성공은 각각 검증해야 합니다. PNG 체크포인트와 내부 기록은 해당 작업의 private capture에 보존됩니다.

**현재 상태: 사용자 소프트웨어 영상 검수 대기. 유료 GPU 실행·80초 렌더·FINAL 승격 없음.**
