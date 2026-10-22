# 연구 네트워크 — 초안과 실제 적용 상태

이번 무료 공개 자료 조사에서는 공식 `request_permissions`가 `network.enabled=true`를 turn 범위로 반환했습니다. 해당 반환은 환경 설정의 도메인 정책이 실제 게시됐다는 의미가 아닙니다.

실제 요청에서는 기존 HTTP/HTTPS 프록시와 CA/TLS 검증을 그대로 사용했습니다. Wikipedia 지명 페이지, IGN 공식 포털, Overpass 상태 페이지 및 GitHub API는 CONNECT 단계의 **403 Forbidden**으로 응답했고 원문을 받지 못했습니다. 허용된 GitHub 웹·raw 문서 요청은 HTTP200 또는 실제 파일404를 반환했습니다. 따라서 일반 JSON 파싱 오류나 지도 파일 손상으로 원인을 오인하지 않았습니다.

주 실행 담당이 공식 환경 설정 도구로 **네트워크 전용 초안**을 안전하게 저장한 결과는 다음과 같습니다.

- 기존 custom 허용 도메인 12개 보존.
- 연구에 필요한 정확한 도메인 5개 추가: `en.wikipedia.org`, `www.ign.es`, `overpass-api.de`, `www.openstreetmap.org`, `ejercito.defensa.gob.es`.
- 기존 Secret, 환경변수, 설치 설정 보존. 가짜 GPU 인증 값 입력 없음.
- 도구 응답은 `requires_publish=true`. 실제 실행 환경에 적용됐다는 확인은 아직 없음.
- 정책 게시·적용 전에는 차단된 출처를 다시 요청하지 않음. 동일한403을 반복하거나 다른 프록시·외부 CI 경유로 우회하지 않음.

앞의 3개 도메인은 실제403을 기록했습니다. OpenStreetMap copyright/ODbL 페이지와 스페인 육군의 공식 지명 설명은 필요한 다음 검증 경로이며, 아직 실제 내용을 읽은 것으로 취급하지 않습니다. 허용 도메인 추가 자체가 상세 자료의 존재·coverage·사용 허가를 인증하지도 않습니다.

다음 연구 재개 조건은 환경 설정의 초안이 **Publish되어 실제 실행 환경에 반영된 상태**를 확인하는 것입니다. 자동 게시 도구가 없거나 제품에서 사용자의 게시 조작을 요구한다면 그 절차를 우회하지 않습니다. [Publish]가 비활성화된 경우 원인을 확인하지 않은 채 Secret을 삭제하거나 가짜 값을 채우지 않습니다.

게시·적용 후 실제 네트워크를 재검증하고, 후보 장소 식별 → 원본 지리 데이터 → 소스의 라이선스·날짜·좌표계·native 해상도·SHA 순서로 다시 진행할 수 있습니다. 이 상태에서는 정밀 자료 gate가 `DATA_DETAIL_BLOCKED`이고, 실제 Studio reference MP4 제작은 허용되지 않습니다. 독립적인 CPU·SwiftShader renderer 검증은 계속 진행할 수 있습니다.

실제 시도와 확인한 문서의 바이트·SHA는 `reports/DATA_ACQUISITION_LEDGER.json`, 입력 gate는 `reports/DATA_DETAIL_GATE.json`에 보존합니다.
