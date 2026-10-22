# G2 Final Recovery — technical verification and user review

기준 `3913ad8e90885c769cdccc91f396072d83e356f2`. 새 작업 브랜치 `development/g2-final-recovery-20261022`. 기존 G1·FINAL·이전 복구 결과는 수정하지 않았다.

Nepal의 원래 Location Layout 실패를 범용 opt-in 입력 확장으로 해결했다. 기존 Layout 함수와 폰트·지리 앵커·충돌 보호를 그대로 사용하고, 네 기본 후보가 실패할 때만 제한된 gap 후보를 탐색한다. 정책이 없으면 기존 결과를 그대로 반환한다.

기존 101개와 추가 42개 검사, Namibia/Nepal/한반도/Germany/Chile 실제 draw 20회가 통과했다. 이후 실제 인증·Origin·CSRF·claim·detached worker를 거치는 Studio 작업 `studio-ed20f92b16cf939f72cc078c24f217c7`으로 1080×1920/30fps/180프레임/6초 H.264 무음 MP4를 생성했다. CPU SwiftShader 실행이며 NVIDIA 또는 운영 OCI 이미지 실행을 의미하지 않는다.

주요 자료:

- `ROOT_CAUSE_REPORT.md`, `LAYOUT_FIX_REPORT.md`: 원인·수정·호환성.
- `REGRESSION_TEST_REPORT.md`: 기존 101개·추가 42개 및 실제 5지역 검사.
- `FRAME_AUDIT.md`, `reports/RECOVERY_FRAME_AUDIT.json`: 완성 MP4 전체 180프레임·카메라·영역·전선·원본 상태 비교.
- `G2_GATE_DECISION.md`, `reports/GATES.json`: 최종 기술 게이트와 사용자 품질 승인 상태.
- `public-review/G2_FINAL_DEMO_6S.mp4`: 실제 Studio 출력 그대로.
- `public-review/BEFORE_AFTER_CONTACT_SHEET.png`: 같은 프레임의 기존/새 MP4 실제 디코딩 비교.
- `public-review/ALL_FRAMES_*.png`: 모든 180프레임의 축소 개요. 전체 해상도 정밀 검수와 구분한다.
- `public-review/FLAGGED_F133_ACTUAL_CROPS.png`: 변경하지 않은 고정 경계 탐지 기준에서 표시된 f133과 실제 원본 지형 비교.
- `SHA256SUMS`: 전달 파일 SHA. 실제 다운로드 검증은 `reports/DOWNLOAD_VERIFICATION.json`.

재현은 기존 저장소 전체의 기준 checkout과 이 브랜치 파일을 함께 사용한다. 기존 source package·core renderer를 ZIP에 복제하지 않는다. 원래 main Scene/자산과 이전 복구 source bundle은 기준 커밋에 보존돼 있다. 새 범용 지역 입력은 `fixtures/GENERIC_REGION_INPUTS.zip`, 새 정책은 `fixtures/LAYOUT_PROFILE.json`에 있다. 컴파일된 private probe package·raw PNG는 저장된 입력과 스크립트로 재생성할 수 있다. owner code·세션·private job 파일은 공개 자료에 넣지 않는다.

기존 DEMO의 native `ZONE`은 화면에 그리지 않지만 활성 입장 역할과 실제 폰트 기반 배치 검사는 유지한다. 실제 보이는 그래픽은 원래 marker와 SYNTHETIC caption이다. 측정한 `ZONE` 위치를 실제 표시한 것처럼 보고하지 않는다.

G3 역사 제작·유료 GPU·80초·FINAL 승격은 금지 상태를 유지한다. 기술 검증이 끝나도 영상 품질은 사용자의 실제 MP4 검수 전까지 승인하지 않는다.
