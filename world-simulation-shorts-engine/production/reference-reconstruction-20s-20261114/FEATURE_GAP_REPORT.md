# 기능·자료 격차: 구현하지 않고 보고

기준 `417ba2e`. 비용은 확인된 가격이 없으면 UNKNOWN이다. 난이도는 코드 범위에 근거한 기술 추정이며 일정 약속이 아니다. 기존 PASS를 무효화하거나 재실행한 항목은 없다.

## P0 — 연속 역사600프레임 GPU 정식 연결

- 레퍼런스 구간: 전체 연출을 새20초 입력으로 내보내는 전달 단계. 영상 효과 자체가 아닌 실행 연결 문제.
- 불가능 근거: `recovery/codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs:68`는6/10초만 허용. generated capture도 같은 제한. generated NVIDIA runtime:31은240프레임 한도. `controller/nvidia_controller.py:306`은180/300만 허용. `universal-presentation-v2/studio_adapter.py:131`은240(조건부300), :276–287은 HISTORICAL 상태를 차단한다.
- 부족 코드: 신규 HISTORICAL_CONTINUOUS_V1와 최신 지도/영토/camera의 GPU variant 반영, source pins·manifest·duration/size·controller/worker/receipt의 일치. 기존 CPU 600 지원만으로 해결되지 않는다.
- 최소 후속 구현: 먼저 기존 정식20초(10초×2) controller normalizer와 source seals를 감사하여 재사용 가능 여부 확정. 불가능하면 기존 NVIDIA adapter에 명시적600프레임 프로파일을 추가하고 prompt→controller→worker→renderer→receipt 전 구간을 연결. 기존 consent/cost/private-source/history gates 유지. generated파일만 손으로 고쳐 gate를 피하지 않는다.
- 수정 후보: 위4파일 및 `backend/profile_contract.mjs`, `backend/build_variants.py`, `backend/GENERATED_SOURCE_MANIFEST.json`, `RUNTIME_SOURCE_MANIFEST.json`, `controller/nvidia_worker.py`와 배포 packaging. 실제 후속 범위는 source closure 감사 뒤 축소.
- 기존 PASS 영향: 기존6초/10초 결과는 보존. 새 duration/profile, 최신 runtime source seals, 새 입력 연결만 신규 검사. 기존 PASS 전체 rerun 불필요.
- 난이도: 중~높음(여러 계약 연결). 실행비용: 무료개발/CPU검사 가능 범위는 환경 의존, 실제 GPU 가격 UNKNOWN. 단순 이미지 재빌드만으로 해결 불가.
- 미구현 차이: 정확한 설계와 CPU schema가 있어도 Studio에서 실제20초 렌더 시작 불가. **READY_FOR_USER_GPU_START 금지**.
- 대체: 기존10초×2 조합은 참조 가능하나 이 연속 역사profile의 source/경계상태 continuity admission 검증 전 사용할 수 없음. CPU 전체MP4 우회 제작은 하지 않는다.
- 이번 작업: 설계·읽기전용 경로감사만. 새 공통기능 개발/빌드/GPU시작0.

## P1 — 레퍼런스형 장면 리듬을 자동 프로파일로 입력

- 발생:30–175 pullback,175–283 push-in,283–330 read,330–452 detail push,452–575 close read.
- 현 상황: geographic per-frame camera와 scene/territory 시간표의 runtime계약은 있다. 하지만 `presentation_prompt.mjs:289,350`은 CONTINUOUS 자동설정에 authored camera/timing을 섞으면 거부하며 `history_continuous_v1.mjs:10–35`는 사건수 기반 균등cycle을 만든다.
- 최소 구현: 후속에서 기존 automatic profile의 명시적 pace/camera 의도 필드를 설계·검증하여 현재 modules에 전달. 새 renderer 필요 없음.
- 수정 후보: presentation_prompt/schema, history_continuous_v1, territory_camera_v1. 프롬프트의 설정을 조용히 무시하지 않아야 함.
- 영향: 새 옵션 경계와 각 source-density/camera 안전성만 검사. 이전 default PASS 유지.
- 난이도: 중간. GPU 비용0(개발); 완료시간 UNKNOWN.
- 미구현 차이/대체: 자동baseline의3회 접근+hold를 사용하거나, 기존 정식 runtime request를 명시적으로 구성하여 카메라·시간표를 설계할 수 있다. 후자는 Studio 입력으로 이미 연결됐다는 뜻이 아니다. 이번 산출물은 실행 계약을 속이지 않고 이 구분을 표시한다.

## P1 — 초근접 지도 source

- 발생:330–574, 특히452 이후 건물·해안·수면 texture.
- 부족: 현재 NASA BMNG 1분(21600×10800 원본) 및 native pyramid에는 건물 수준 정보가 없다. 원본레퍼런스 source UNKNOWN.
- 최소 해결: 선택한 역사주제에 적합한 고해상도 실자료를 source catalog의 기존규격(CRS, bounds, pixel spacing, NoData, license, SHA256)으로 추가·승인. 업스케일·가짜지형 생성 금지.
- 수정 후보: REGION_SOURCE_CATALOG와 source assets/descriptors; 필요하면 현재 geographic terrain loader의 LOD 수용범위만 최소확장.
- 영향: 추가source admission만 검사. 기존BMNG PASS 유지.
- 난이도: 자료권리·coverage에 따라 중~높음, 비용 UNKNOWN.
- 대체: 진짜 디테일이 유지되는 광역·지역 구도까지 제한. 이번설계에는 이를 적용. 레퍼런스 동등근접화질 PASS 불가.

## P2 — 특정 정적 경계선의 지속 발광

- 발생:459–574의국지 노란선, 약490이후85m라벨.
- 부족: 기존 continuous `FRONTIER_LIGHT_V1`은 움직이는band를 강조하고 정착시 소멸; 원본의 특정 선분에 해당하는 실제 역사데이터는 없음.
- 최소 해결: 출처있는LineString 및 사건구간을 기존 boundary trace/event line·Area V3에 결합하는 지원계약 검토. 임의직선을 역사국경으로 만들지 않는다.
- 수정후보: presentation_plan의 source-bound line effect와 territory_effects/runtime 연결. 기존 line 기능으로 충족되면 확장 불필요.
- 영향: 새 line binding·timing만. 난이도 낮음~중간(자료확보는 별도). 비용 UNKNOWN.
- 대체: 변화중실제boundary band 강조, 결과의 added색 유지, 안정된역사기간라벨. 이번영상은 이 대체를 사용한다.

## P3 — 정확한 청색 label bloom·원본 shader 복제

- 발생:289–362,311–362. 기존 label/pin/GRAPHEME_POP은 재사용 가능하지만 정확한 원본색·bloom은 UNKNOWN.
- 최소 구현: 필요할 때 기존 label style에 제한된 source-independent 시각설정 추가. 원본프로그램 추정으로 API를 만들지 않는다.
- 영향: 새스타일배치/가독성만. 난이도 낮음, 비용 UNKNOWN.
- 대체: 검증된 기존 label style. 이번에는 불필요한도시·핀을 추가하지 않는다.

새주제의 실제 경계·시기 자료 검증은 TOPIC_SELECTION에서 별도로 확정한다. 공통 GPU연결 차단은 주제를 바꾸는 것만으로 해결되지 않는다.
