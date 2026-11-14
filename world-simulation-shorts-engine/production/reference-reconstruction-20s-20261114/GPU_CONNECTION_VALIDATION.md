# 신규 600프레임 GPU 연결 검증

상태: PASS_FREE_SOURCE_CONTRACT_SCOPE. 실제 NVIDIA 실행·화질은 PENDING_GPU.

- 이전 Work의 GPU 계약 17개, Worker 5개, Controller 저장·캐시 복원 4항목, 모바일 6개 결과를 원본 그대로 보존했다. 재실행하지 않았다.
- 실제 Controller에 누락된 실패 입력 11종을 추가 검사했다. duration/FPS 불일치, 역사 자료·카메라·지도 누락, 도형 참조 변경, 범위 초과, 180/300 강제 변환, 미허용 profile·사용자 해시 주입을 오류 코드와 함께 거부했다.
- runtime 변조 7종을 추가 검사했다. 지도 source 누락, 입력 해시, profile, 범위, 역사 증거, 두 가지 단축 변환을 거부했다.
- 새 manifest 473파일은 현재 bytes/SHA와 일치한다. generated 3개는 기존 검증 bytes와 동일하다. Worker가 참조하는 generated NVIDIA runtime 경로를 보존했다.
- backend 정책·launch 검사를 추가했다. 승인·비용·잠금·시작 함수는 기존 구조를 유지하고 profile selector 및 20초 값만 전달한다.
- 원본 입력 파일 SHA와 의미 해시는 구분한다. 정확한 FINAL_20S_INPUT.json SHA는 이 보고서·배포 preflight에 봉인한다. 실행 PLAN의 originalInputSHA256은 authored prompt의 canonical SHA이며, historicalAdmission·runtimeWireSHA256·plan SHA로 실행 기록에 연결된다.
- 실행 기록은 PLAN.json(소스 manifest·image digest·profile·카메라/영토/지도/라벨), state.json(jobId·상태·실패 원인·출력), CAPTURE_RECEIPT.json(입력 runtime 해시·프레임·미디어), MEDIA_VERIFICATION.json의 결합이다. 이번 검사에서는 실제 GPU 성공 Receipt를 발급하지 않았다.

마지막 검증 이미지 quality-v2의 소스 계약은 새 profile과 달라 재사용 실행 불가다. immutable parent sha256:ed2ff287e7617b201876059210603e4f507632ca7143ae1768414364faf848ce 위에 127개 변경 소스만 추가한다. 4개 비추적 지도 파일은 parent와 동일 해시이며 이미지에서 실제 상속 bytes를 검사한다. 새 이미지의 전체 source closure·동일 Controller→Worker 전달은 이미지 안에서 무료 검사해야 한다.
