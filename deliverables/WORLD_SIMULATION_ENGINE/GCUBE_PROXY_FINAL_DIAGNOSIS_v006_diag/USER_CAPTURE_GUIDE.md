# 실제 gcube 헤더를 확인하는 단 한 번의 진단

진단 이미지: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v006-diag`

기존 Workload를 Codex가 생성·수정·시작하지 않았습니다. VM을 유지하면서
이미지만 교체할 수 있는지는 확인되지 않았으므로 가능하다고 단정하지 않습니다.

포트 8000, Container Command 빈칸, Istio ON, 기존 ephemeral 설정을 유지합니다.
`WORLD_ENGINE_OWNER_CODE`에는 대화에 노출되지 않은 새 16자 이상 비밀번호를
입력합니다. 이미지에는 비밀번호가 들어 있지 않습니다.

공식 서비스 주소를 열면 다음 중 하나가 표시됩니다.

- 프록시 검증 실패: 실제 400/403 상태를 유지하며 `FAILED_VALIDATION_RULE`과
  마스킹된 진단 결과를 바로 표시합니다. 로그인이나 보호 API는 허용하지 않습니다.
- 프록시 검증 통과: 로그인 화면이 표시됩니다. 새 owner-code로 로그인하면
  마스킹된 진단 결과를 확인할 수 있습니다.

화면의 **진단 결과 복사** 내용을 전달한 뒤 Workload를 중지합니다.
브라우저를 닫는 것만으로 GPU VM 과금이 멈추지는 않습니다.

`PROXY_ONLY`, `GPU: NOT_RUN`, `engine_ready: false`, `rendering: DISABLED`는
이 진단 이미지의 정상 상태입니다. GPU 성공/실패나 렌더 준비 완료를 뜻하지
않습니다. 영상 생성이나 GPU 검사는 이 이미지에서 실행되지 않습니다.

IP와 Workload 주소는 마스킹되며, 비교 ID로만 같은 값인지 확인할 수 있습니다.
owner-code, Cookie, Authorization, Token, Session과 요청 본문은 진단 결과에
포함하지 않습니다. 별도의 터미널·Docker·Git 명령은 필요하지 않습니다.

기존 프록시 오류의 정확한 규칙을 확인한 뒤에만 원인 수정을 진행합니다.
T4 NVIDIA Graphics Capability 지원 여부는 아직 미확인입니다.
