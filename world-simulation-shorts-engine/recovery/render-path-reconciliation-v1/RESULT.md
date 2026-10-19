# WORLD ENGINE 5초 Candidate 원인·제작 경로 대조 결과

상태: **USER_REVIEW_REQUIRED · VISUAL_NEEDS_REWORK · NVIDIA_GPU_PENDING**

## 확인된 원인

- 공통 기존 native/V4 엔진은 양쪽에서 실제 호출됩니다. 고급 65422는 현대 가상 Scene의 상보 scalar 영토·연속 전선·NE1 재질·presentation roll·국기 8개를 직접 합성했습니다. source `2c097df`, MP4 `f3de1bdf…eed2ef6`입니다. 당시 보존 증거는 기술 PASS이며 사용자 최종 품질 승인은 기록하지 않습니다.
- 실제 확보한 새 파일 SHA `3899d87c…de83f66`는 source `e236131` checkout에서 Area·ASTRA·V5 경로로 생성됐습니다. 선택값 scalar/national은 null이고 Event/Flow 배열도 비어 있습니다. 역사 catalog에는 상보 점령장·역사 군대 위치 source가 없습니다. 코드나 이미지에 모듈이 포함된 사실로 실행을 주장할 수 없습니다.
- 새 파일의 48개 bounds variant는 실제 최대 **0.602065px** 이동입니다. 확대 변화는 수치 오차 수준이고 actual V5 turn은 없습니다. 수치 차이를 가독성 있는 카메라 연출로 사용한 판정을 교정했습니다.
- 고정 Area snapshot의 crossfade와 원래 hold가 실행됩니다. 원본 전역 시간축·상태를 보존하며 preview 초기화·은밀한 basic-V4 fallback은 관측되지 않았습니다. 첫50프레임의 과거 도식 문맥은 원래 schedule의 별도 snapshot 날짜와 함께 유지됩니다.
- **66461.mp4 원본/동일성 SHA는 미확보**입니다. 위 실제 확보 파일과 동일하다고 단정하지 않습니다. 66430 원본도 없어 실제80초 영상 직접 비교는 하지 않았습니다. reference65379는958프레임 전체, 이전·알려진 새5초는 각150프레임 전체 비디오 및 존재하는 오디오를 디코딩했습니다. 오디오는 수치 분석이며 주관적 청취 품질 PASS는 없습니다.

## 직접 수정·검증한 부분

1. 독립 source-bound native capability guard를 기존 Studio source admission 뒤에 연결했습니다. 현재 producer가 제공하지 않는 scalar 교체 합성 슬롯·internalBoundarySegments·동일 프레임 pre-territory texture·native role coverage 선택은 **GPU 관리자 실행 전에 차단**합니다. 기존 compile 성공→첫 draw 실패를 CPU로 재현했습니다. 이 조건부 결함을 null 선택 영상의 발생 원인으로 혼동하지 않습니다.
2. 별도 픽셀 기준 카메라 분석과 관측 구간 선택을 추가했습니다. 기존 카메라·selector·Scene을 변경하지 않았습니다. 실제 관측200프레임의150프레임 창51개 모두1px 미만이며 `NO_OBSERVED_VISIBLE_CAMERA_WINDOW`입니다. 알 수 없는 구간의 카메라를 만들거나 움직인다고 표시하지 않습니다.
3. 실제 factory 생성·draw·세 global 프레임의 단계 전후 readPixels를 기록했습니다. ASTRA·V5·Area 소비자가 모두150번 실행됐습니다. import·mock 성공만으로 픽셀 실행을 보고하지 않습니다.
4. 새 무료 CI의 NumPy 의존성 미선언을 격리 환경에서 재현하고 선언했습니다. 검사 stdout/stderr를 안전하게 보존합니다. 최초 CI 원격 stderr는 미확보여서 최초 실패와 동일 원인이라고 단정하지 않습니다. 후속 CI 전체 성공입니다.

## 새 실제5초 영상

1080×1920 /30fps /150프레임 /H.264 /SFX 포함, 원본80초2400프레임 중 **[1400,1550)**만 캡처했습니다.

- 실제 새 SwiftShader draw/readPixels150프레임이며 source `e677862dc81b223d0ebb8c7cf9c7d5cd790574d0`입니다.
- Git 원격 동기화의 sparse-checkout이 새 manifest를 일시 제외해 마지막 source 검사에 실패했습니다. 원본15파일+manifest를 해당 commit의 정확한 바이트로 복구하고 부모82개도 재검증했습니다. 완료150 PNG를 모두 보존·검증해 인코딩만 수행했으며 **재렌더0**입니다. 이후 sparse 범위에 신규 namespace를 추가해 원격동기화 시 제외되지 않도록 했습니다.
- 150프레임 RGBA·PNG가 기존 알려진 출력과 모두 동일합니다. 새 영상은 실행 관측·보존 검증용이며 **고급 연출이 복원된 개선 영상이 아닙니다**.
- 실제 캡처/실패398.433초 + encode-only 복구14.828초 =413.261초입니다. 개입 대기·후속 SFX 시간은 이 합계에서 제외하며 NVIDIA 성능으로 환산하지 않습니다.
- MP4 SHA-256: `3899d87cbacfbb54f9a094ac0a37755b7a3dd5ba941634e37f4555d01de83f66`
- 단색 도식·직선 경계·표식 보호 사각형·고정 문구·군대 자료 부재·hold가 남아 **VISUAL_NEEDS_REWORK**입니다.

## 무료 검사·저장·후보 이미지

- 집중 CPU **59 PASS /0 FAIL /0 SKIP**: Python54 +Node5. 별도151개 ledger 구조 검사9개. 기존104/168/233 전체 검사를 반복하지 않았습니다.
- 새 source15 +보존 parent82개 SHA 통과. 원본 FINAL·Candidate·Scene·Asset·렌더러·Camera·Area·Flow·Event·Planner 변경0건입니다. 실제 관측을 NVIDIA `APPLIED`로 올리지 않았습니다.
- 151개: SUPPORTING104 /BLOCKED18 /UNVERIFIED14 /해당 없음15. APPLIED0 /NVIDIA 증거0입니다.
- 브랜치: `development/5s-render-reconciliation-20261020`
- 구현 source: `e677862dc81b223d0ebb8c7cf9c7d5cd790574d0`
- 이미지 build source: `f8b17ec3b2e0e8100b7e29980fecd1fdd8517218`. 양쪽 runtime15파일과 manifest는 동일합니다. 새 이미지에서 영상은 실행하지 않았습니다.
- Manifest SHA: `0487f40289d31e3ad5c9896781e945fa5f28f17a9c930e501e207e5a4bd8abc8`
- 태그: `reconcile-v1-f8b17ec3b2-39317457661-1`
- 이미지: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:1bb399679bfaf1f3d6d57df67c139974e8c63862f07142e950b9b6d150281c9f`
- 무료 빌드·등록·독립 digest pull·컨테이너 Studio import·native guard·관리자 누락 차단 PASS. 기존 capture proof와 새 layer proof는 별도 기록합니다.
- CI: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39317457661

## 남은 부분·사용자 최소 행동

상보 영토·고급 terrain-aware scalar light·역사 군대 표식의 복원은 완료하지 못했습니다. 확인된 양측 점령 데이터·역할/시점별 군대 좌표·동일 프레임 native 합성 계약이 필요합니다. 임의 적군 영역·부대 위치·추정 전선을 만들지 않았습니다. 안전한 기존 대안과 필요한 정확한 필드는 `EXACT_MISSING_ITEMS.md`에 있습니다.

**66461.mp4 원본 한 개 또는 그 파일의 SHA-256만 제공하면 파일 동일성과 실제 생성 경로를 확정할 수 있습니다.** 지금 gCube 배포·환경변수 변경·렌더링 시작은 필요하지 않습니다. 기존5200원 등 과거 승인을 사용하지 않았고 유료GPU·전체80초 렌더링·FINAL 승격은 실행하지 않았습니다.
