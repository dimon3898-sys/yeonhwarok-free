# G2_GATE_DECISION

**G2: NEEDS_REWORK / G3: BLOCKED / 새 Studio 6초 MP4: NOT CREATED**

| 게이트 | 판정 | 근거 |
|---|---|---|
| PHASE 0 | PASS | 보호 SHA 기준 확보, 기존 전체 180프레임 실제 decode·소스/코드 원인 확정 |
| PHASE 1 | PASS — 부분 렌더 검증 범위 | 실제 동일 NE1 원본과 source-native crop, 기존 runtime 유지, f0/f90/f179 확인·동일 프레임 결정성 |
| PHASE 2 CPU | PASS | 기존 52 + 신규 49, skip 0 |
| PHASE 2 범용 지역 | FAIL | Namibia 4 draw PASS, Nepal Layout 초기화 FAIL·draw 0 |
| PHASE 2 전체 | FAIL | 필수 두 지역 통과 미충족 |
| PHASE 3 | BLOCKED | 게이트 실패 시 즉시 중단 지시 적용. 실제 Studio job/180프레임 MP4 미실행 |
| PHASE 4 | 실패 보고·증거 보존만 | 새 영상 품질 검수 완료로 표시하지 않음 |

최종 조건의 “실제 Studio 180프레임 산출물 확보”와 “두 지역 범용성 통과”가 충족되지 않았다. 기술 검사 또는 일부 깨끗한 화면만으로 G2 PASS를 선언하지 않는다.

## 보존·비용

기준 원격 `0069e9a`, PHASE 0 체크포인트 `35347aa`, 구현 체크포인트 `da58b4f`. 기존 G1/FINAL/렌더러/카메라/Area/Flow/Event 및 보호 307파일은 변경하지 않았다. 기존 namespace 143파일과 기존 캐시 223파일 보존 검사도 통과했다.

이번 작업에서 유료 GPU·유료 API·GPU 배포·원격 워크로드 변경·80초 제작·FINAL 승격을 실행하지 않았다. 무료 CPU/SwiftShader만 사용했다. 기존에 사용자가 운영 중인 gCube의 과금 상태를 조회하거나 0원이라고 판정하지 않았다.

## 다음 실행 지점

Nepal에서 드러난 Scene 정보 활성 상태와 기존 Layout 입장 조건의 정합을 먼저 확인해야 한다. 기존 보호 검사를 제거하거나 실패 지역을 교체하지 않는다. 수정이 필요하면 새 연결/입력 계층의 최소 변경으로 집중 재검증하고 PHASE 2를 통과해야 한다. 그 후에만 원래 조건의 Studio 180프레임을 시작할 수 있다.

사용자가 gCube 환경변수·Secret·GPU 설정을 바꿀 필요는 없다. 이번 부분 복구 PNG와 실패 근거를 검토하면 된다. 역사 G3·유료 실행·80초·FINAL은 별도 승인 없이 진행하지 않는다.
