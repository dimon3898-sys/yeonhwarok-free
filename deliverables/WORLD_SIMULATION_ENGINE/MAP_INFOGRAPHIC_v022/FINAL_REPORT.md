# WORLD ENGINE v022 — 구현·검증·게시 완료

v022 구현과 실제 컨테이너 검증을 완료하고 immutable 신규 이미지를 공개 게시했습니다. 실제 gcube Workload는 조작하지 않았습니다. 아래 기술 검증 PASS는 실제 NVIDIA 영상 품질 합격과 구분합니다.

1. **실제 구현**

   검증 GIS registry, 국가 Boundary, Polygon/MultiPolygon Fill·hole, native 사건 geometry의 CLOSED→OPEN 전이, 공통 Text Hierarchy/Layout, Persistent Marker, intro와 steady state 분리를 구현했습니다. 실제 geometry 기반 Local-Close와 Script→실측 TTS→semantic timeline→visual frame plan은 별도 Production family입니다. QA의 운하 폐쇄/개방은 `가정 시나리오`를 표시하고 Egypt 국가 면은 사건 범위와 구분합니다. Point를 선/면으로 만들거나 출처 없는 사건·수치를 추가하지 않았습니다.

2. **CODE / DATA 변경**

   CODE는 infographic contract/planner/adapter/backend/QC, semantic timeline, explicit geometry framing 및 전용 preflight입니다. `qa_planner.py`와 `pipeline_stability.py`는 새 family 선택과 기존 Diagnostic 연결만 추가합니다. DATA는 versioned registry/schema, 최소 canal subset, source/license receipts 및 실제 Noto Bold700입니다. 이미지 source는 `bbb3d15f057797c7894c796d1eb444e9990d90dc`, branch는 `fix/v022-map-infographic`입니다. 정확한 포함 파일은 frozen source manifest로 관리합니다. 최종 문서 commit은 이미지 source와 분리합니다.

3. **재사용 및 보호**

   기존 spherical projector·Adaptive Wide solver, v020 glyph/marker intro, v018 지역 LOD, v019 재질, 기존 TTS provider·audio mixer·ducking·FFmpeg subtitle를 재사용합니다. 720개 camera pose/target/FOV/timing과 기존 24초 camera-only fixture는 동일합니다. OFF는 같은 입력의 inherited v021 plan을 유지합니다. 원래 rendering/audio와 GPU/WebGL/profile/proxy, JPEG/FFmpeg, Diagnostic ZIP, Checkpoint/Retry 기반은 보존했습니다. 공개 parent OCI layer의 보호 소스 27개와 실제 bytes를 대조해 모두 일치했습니다.

4. **GIS / 라이선스**

   Registry 542개/6개 출처, 기존 291 Point의 원본 좌표 불일치0입니다. 새 GIS는 Natural Earth의 Suez river/lake-centerline 2feature만 추가했습니다. 26vertex/3native part와 원래 gap을 보존하고 연결선을 만들지 않았습니다. `10m`은 1:10,000,000 지도 축척입니다. Natural Earth public domain, OurAirports PDDL, searoute Apache-2.0, Noto SIL OFL과 기존 texture CC BY 고지를 유지했습니다. 참고 영상의 그래픽·문구·색상·자산을 복제하지 않았습니다.

5. **Regression**

   PASS **1,061** / FAIL **0** / ERROR **0** / SKIP **0**. Core824(기존767+신규57), 독립 proxy/GPU logic206, diagnostic31의 정확한 실행 ID와 frozen inventory를 검증했습니다. 별도 isolated31/35/57 재실행은 중복으로 집계하지 않았습니다. [실제 CI](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37935004783/job/113835034826)는 2026-10-09 13:49:38 UTC 성공 종료입니다.

6. **Container 검증**

   Docker build, protected source/hash, assets/license111, HTTP hash19, packages·UID1000 write paths, native720 QA/OFF/ON, 실제 ESpeak Production253 frames, CPU Canvas16checks/10captures, JPEG·FFmpeg·concat·audio·QC·retry가 PASS입니다. Legacy/v021/v022 health·owner login·각61초 유지 및 actual entrypoint의 noNVIDIA fail-closed가 PASS입니다. 공개 익명 Docker pull 후 OCI revision과 세 모드 로그인·61초 유지도 PASS입니다. Canvas/합성 MP4는 GPU 영상 증거로 사용하지 않았습니다. 자세한 count 중 public notice에 없는 항목은 성공한 frozen helper의 필수 assertion inventory로 출처를 명시했습니다.

7. **새 Container Image**

   `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v022-map-infographic-bbb3d15f0577`

   미존재 tag와 최신 source HEAD를 확인한 후 게시했습니다. 기존 안정 tag와 `latest`는 덮어쓰지 않았습니다. 이미지의 `WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION=v022`로 새 24초 HIGH 요청은 `MAP_INFOGRAPHIC_QA_V022`를 선택합니다. 명시적 `SECOND_EVENT_ADAPTIVE_WIDE_TEST`는 보호된 기존 경로입니다.

8. **실제 digest**

   `sha256:e5de0f00022715dd2b1653c684213cf23359f337fca160afff3215b865104fed`

   Anonymous manifest/config byte hash, linux/amd64 digest, OCI source/revision 및 default selector를 독립 검증했습니다. 실행 image는 확인된 digest로 고정할 수 있습니다. Config digest는 `sha256:5eefe6a0586f9bf0af59ff1bf79ff280a673c26f969434e26379dab7a994fdc5`입니다. 증거는 `RELEASE_VERIFICATION.json`, `FINAL_CI_RECEIPT.json`, `PUBLIC_IMAGE_VERIFICATION.json`입니다.

9. **실제 GPU에서 남은 검증 — NOT_RUN**

   RTX4080S 실제 map frames/MP4, overlay shader·depth/LOD 상호작용, 텍스트·Boundary·Fill·Marker의 실제 지도 가독성, 최종 시각·AAC 청취, VRAM·frame/render time은 NOT_RUN입니다. 기존 첨부 CURRENT의 생성 image/commit도 미확정으로 유지했습니다. REFERENCE/CURRENT 전체 decode와 normalized frame 비교, CPU overlay captures는 보존했지만 새 GPU BEFORE/AFTER로 대체하지 않았습니다. 새 actual Diagnostic ZIP 역시 다음 GPU 출력에서 확보해야 합니다.

10. **다음 RTX4080S 테스트**

    사용자 승인 후 한 세션에서 MASTER 순서로 실제 NVIDIA admission → 보호 24초 camera-only → 같은 camera의 infographic OFF/ON → sourced measured Production(다른 실제 위치 포함)을 검증합니다. `NVIDIA_DRIVER_CAPABILITIES=all`, `WORLD_ENGINE_RENDER_MODE=gpu-required`를 유지하고 speech clock은 GPU host에서 다시 실측합니다. 각 MP4와 Diagnostic ZIP을 휴대폰에 다운로드한 뒤 Workload를 중지합니다. 75/80초 GPU 렌더·PWA·웹 디자인은 이번 작업에 포함하지 않았습니다. 상세 순서는 `GPU_TEST_METHOD.md`에 있습니다.

Rollback baseline은 기존 v021 `sha256:2f68a880afdc56a5d3b9dc5ab52c2a87100316048d5d863e712654fee789a9dc`입니다. 기존 프로젝트와 preset/version을 유지합니다. 구현·CODE/DATA·재사용 상세는 `IMPLEMENTATION.md`, asset/license 원본은 `data/infographic/v022/SOURCES.json` 및 release manifest를 참조하세요.
