# MOVING FRONTIER GLOW FIX — 5S CANDIDATE

판정은 **기술 PASS / 전선 강조 IMPROVED / USER_VIDEO_REVIEW_REQUIRED**다. 레퍼런스 동급 및 사용자 최종 승인은 주장하지 않는다.

보호 기준은 기존 개발 브랜치의 `8e2b994755330907ceed9b9bfcc922e9b113138d`다. 첨부 65416 Candidate SHA `4f1b676baef6a4ba6fefbfd58a5d6b2e235fb57ada7d11cfd2baf827ec79f12e`와 65379 레퍼런스 SHA `5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6`는 영구 저장 원본과 일치한다. 기존 Source·FINAL·Candidate·데이터 변경은 0건이다. 현대 가상 시나리오를 유지하며 역사 데이터나 국가 역할을 다시 작성하지 않았다.

원인은 실제 렌더러의 warm 중심색, 얇은 1.8px 설정, 낮은 halo 강도 및 기존 화면 변환/압축에서의 약화였다. 동기화·위치·레이어 오류는 발견하지 못했다. 기존 GPU V4와 frontier V3, AREA/Control, Camera V5, Projection 및 모든 재질/아이콘 코드를 그대로 재사용했다. 새 엔진이나 별도의 전선 경로는 만들지 않았다.

변경은 private Scene의 frontierProfile뿐이다. 중심을 near-white/설정 폭 2.5px로, 주변광을 절제된 금빛/σ3.5/support10으로 조정했다. 실제 경계 변위에 반응하는 기존 energy oracle을 사용하며 window12/정지 strength.08로 감쇠한다. Terrain relief의 luminanceAnchor/minimumLightingFactor/enable은 그대로다. 영토 속도·모양·카메라·육지·바다·금빛 지형 조명·군대 디자인·Planner는 동일하다.

실제 1080×1920 RAW 프레임 0/74/149에서 중심광 FWHM 중앙값은 **2.62–2.70px**, 전체 강조 FWHM은 **3.08–3.11px**이며 기존 전체 강조는 **2.25–2.40px**다. 배경 대비 밝기 증가량의 비율은 **1.42–1.44배**다. 중심 위치 최대 표본 오차는 0.355px다. 이는 실제 RAW 측정이며 H.264 전체 프레임의 픽셀 폭이나 물리적인 조도 인증으로 주장하지 않는다.

첫 보호 마스크는 기존 shader의 field/quad-gradient 거리를 Euclidean polyline 거리로 잘못 해석해 모서리 246픽셀을 실패로 표시했다. 그 FAIL, Source A 코드, 모든 좌표 진단을 보존했다. 검증 모델만 기존 float32 field/2×2 derivatives/정확한 bilinear contributor에 맞췄고, renderer·profile·허용 support10·tolerance를 바꾸지 않았다. 교정된 실제 RAW 검사에서 빛 범위 밖과 군대 표식 영역은 모두 BIT_EXACT다. 상세 근거는 `FRONTIER_GLOW_PIXEL_MEASUREMENTS_V2.json` 및 `MEASUREMENT_EVIDENCE_INDEX.json`이다.

집중 Node 검사는 4/4 PASS다. 실제 150프레임의 Camera/Control/Material/Badge 입력 동일성 및 별도 private 실제 정지 Fixture에서 12프레임 후 strength.08까지 단조 감쇠를 검증했다. 이 공개 5초 구간은 150프레임 전부 계속 전진하므로 영상 끝에서 임의로 정지시키거나 fade를 꾸미지 않았다.

새 MP4는 `WORLD_ENGINE_MOVING_FRONTIER_GLOW_FIX_5S.mp4`, 1080×1920/30fps/150프레임/5.000초/H.264/무음이며 SHA는 `f3de1bdf9244171a47c6e5eccca6aae1370f58d8bf4721a7658b6bca2eed2ef6`다. 기존 영상과 새 영상을 각각 150프레임 실제 디코딩했다. Root와 독립 검수자는 전체 chronological contact 및 같은 프레임 0/38/75/112/149의 기존-left/신규-right 비교 5장을 직접 봤다. 밝은 중심광과 은은한 주변광, 영토 진행과의 일치, 색상 구분·표식 가독성 개선을 확인했다. 실시간 재생·실물 휴대폰 검수나 완전한 레퍼런스 동등성은 주장하지 않는다.

전체 출력 GL 오류·검은/빈 프레임·모서리 실패·Safe Area 위반·critical collision은 0이다. 영상 텍스트·화살표·이동선·장식용 전선은 없다. 기존의 거친 지형/바다와 64-knot 경계 단순화는 보호 범위로 유지했다. 오프라인 전체 캡처/인코딩 wall time은 251.184초, 실제 backend는 SwiftShader다. 실시간 30fps GPU 성능으로 주장하지 않는다.

새 브랜치는 `development/moving-frontier-glow-fix-20261014`다. Safety `0ffe37c`, 구현 A `4465bcb`, 렌더 Source B `2c097df`, 원본 Proof `9a8ddbb`를 각각 push/원격 일치 확인 후 다음 단계로 진행했다. Source/Fixture/Asset/Dependency/Import/Hash/재현 문서는 새 namespace에 저장했다. Required temp-only는 0이다. 기존 MP4를 재인코딩하거나 새 원본 MP4를 다시 튜닝하지 않았다.

Public Review는 원본 MP4, 비교 PNG 5개, SHA256SUMS의 정확히 7개다. Scene/Source/Diagnostic/Internal Plan은 공개 폴더에 포함하지 않는다. 실제 immutable HTTPS GET/HTTP status/원본·Git·다운로드 byte와 SHA 검증은 `evidence/HTTP_DOWNLOAD_VERIFY.json`, 저장·원격 확인은 private `PERSISTENCE_VERIFICATION.json`/`REMOTE_VERIFICATION.json`에 기록한다.

검수 이미지 입력 크기 오류는 저장된 Source를 보존하고 새 검수 컨텍스트/작은 이미지 입력으로 복구했다. Selected model is at capacity 오류나 자동 모델 변경은 발생/실행한 것으로 주장하지 않는다. 재개 시 Source commit에 묶인 유효 프레임만 재사용한다. 결과 제출 후 USER_VIDEO_REVIEW_REQUIRED에서 멈추며 14초 확장·FINAL 승격·다음 기능은 실행하지 않는다.
