# 정식 20초 GPU 연결 감사

기존 한국전쟁 v11의 10초×2는 GENERAL 입력의 controller→source admission 증거다. 역사 자료를 GENERAL로 바꿀 근거가 아니며, 본 106개 연속 영토·600 pose의 세그먼트 연결 증거는 없다. 기존 compositor와 경계 기록은 보존한다. 이 입력은 한 번의 연속 600프레임 NVIDIA 프로파일로 연결한다. 새 렌더러나 분할 우회 캡처는 만들지 않는다.

소스상 연결은 Studio request→NvidiaPresentationController→source normalizer→NVIDIA prepared sources→plan→기존 승인/비용/공통 lease→nvidia_worker→lease_supervisor→capture_nvidia→generated capture/runtime→receipt다. 600 추가만으로는 부족하다. common.py의 duration/plan, profile_contract.mjs의 HISTORICAL 차단, worker receipt/ledger, supervisor progress cap도 함께 연결해야 한다.

현재 GENERATED_SOURCE_MANIFEST의 원본 SHA와 최신 CPU 원본은 불일치한다(GPU_ROUTE_AUDIT.json). 기존 이미지가 최신 CPU 지도·연속 영토·카메라를 포함한다는 가정은 무효다. 기존6/10 영상 결과 PASS는 무효화하지 않는다. 재검증 범위는 새600 연결과 기존6/10 계약 불변성·필수 수정 보존이다.

입력 방식 A: 명시 authored 역사 입력을 기존 runtime request로 변환한다. 자동 director와 혼합하지 않는다. 서버 소유 검증 역사 기록과 기존 보간 artifact를 해시로 결합하고, 사용자가 지정한 시간·camera·label을 그대로 검증·전달한다. 미지원 필드는 거부한다. 기존 역사 canonical facts·기간·geometry 검증을 유지한다. 코드에 몽골 좌표나 날짜를 하드코딩하지 않고 등록된 source data로 분리한다.

참조: korean-war-20s-generator-audit-v10/ROUTE_AUDIT.md, korean-war-20s-deployment-v11/executions/20261107-42345505600/FORMAL_INPUT_CONNECTION.json, 기존 COMPOSE_PLAN.json. GPU 실행 증거는 모두 PENDING_GPU다.
