# 새 HTTPS 프록시 후보의 gCube 입력값

이 작업에서 Codex는 워크로드를 배포하거나 유료 GPU를 실행하지 않았다. 아래는 사용자 승인 후 수동 실행 절차다. 기존 Secret·Dropbox 데이터·claim을 삭제하거나 초기화하지 않는다.

1. 신규 이미지 주소를 다음 태그로 선택한다. 기존 이미지 대신 별도 후보이며 원본은 보존한다.

   `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:studio-proxy-v1-4589328-39085567166-1`

   immutable 참조를 지원하면 `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da`를 사용한다.

2. 서비스 포트 **8080**, **Command 비움**, 공유 메모리 **2GB**, 기존 Dropbox **/world-storage** 마운트를 유지한다. 기존 NVIDIA graphics/utility 설정과 RTX4080SUPER 실행 설정을 재사용한다.

3. 기존 설정을 보존하되 실행 이미지 바인딩 값은 새 이미지에 맞춘다.

   ```text
   WORLD_ENGINE_RENDER_MODE=gpu-required
   WORLD_ENGINE_STARTUP_MODE=normal
   WORLD_ENGINE_STUDIO_PORT=8080
   WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST=sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da
   ```

   `WORLD_ENGINE_STUDIO_OWNER_CODE`는 기존 관리자 Secret 그대로 사용한다. 채팅이나 공개 코드에 쓰지 않는다. 새 관리자 코드를 만들거나 기존 private 파일을 지우지 않는다. 이 이미지에는 Secret이 내장돼 있지 않다.

4. `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN`은 아직 주소가 발급되지 않았다면 없어도 된다. 이미 등록된 실제 주소가 있는 경우 보존한다. 임의 주소나 종료된 과거 서비스 주소를 넣지 않는다. API 토큰은 이 수동 배포 Studio 웹 서버에 필요하지 않으며 기존 Secret은 삭제하지 않는다.

5. 배포 후 **그 실행에서 발급된 실제 포트8080 HTTPS 서비스 주소**에 `/setup`을 붙여 연다. 화면에 등록할 Origin에는 `https://호스트:외부포트`만 입력한다. 경로·쿼리는 넣지 않고 외부 포트는 생략하지 않는다. 관리자 인증→표시 주소 명시적 확인→등록→기존 코드로 새 Studio 로그인을 수행한다. 예전 `ae20158c…:24999`는 2026-10-18 10:01 KST에404였으므로 현재 유효성을 가정하지 않는다.

6. 운영 정책이 미설정이면 로그인 후에도 **제작은 차단**된다. 실제 승인한 `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON`의 요금·통화·최대 비용·시간·재시도·승인 만료시각을 설정해야 한다. 임의 정책을 넣지 않는다. UI 실행 성공과 GPU/영상 제작 허용은 별개다. Studio 타임아웃은 gCube 과금 종료가 아니므로 사용자가 워크로드 종료를 관리한다.

등록 정보는 기존 안전한 private 경로를 재사용한다. 동일 private 상태를 보존한 컨테이너 재시작은 검사했지만, 워크로드 재생성 시 writable layer 영속성은 확인하지 않았다. 새 private 상태면 인증된 설정을 다시 수행한다. 기존 환경변수 Origin과 private 등록 주소가 다르면 충돌을 숨기지 않고 제작을 차단한다. 자세한 주소 변경 정책은 기존 `../studio-https-bootstrap-v1/GCUBE_SETUP.md`를 따른다.

## 여전히 주소 확인이 실패하면

새 후보는 단일 내부 XFP `http`만, 정확한 외부 Host/포트·XFH·Origin 고정 조건에서 지원한다. 내부 Host 재작성, XFP 체인, 포트 누락을 추정으로 허용하지 않는다. 실제 gCube가 어떤 형태를 전달하는지 아직 관측하지 못했다.

워크로드가 실행 중일 때 기존 공식 읽기 전용 `gcube workload logs 5373` 또는 gCube 로그 화면에서 `STUDIO_PROXY_ENVELOPE_REJECTED`, `WORLD_ENGINE_PROXY_REQUEST_DIAGNOSTIC_V1` 기록을 확보한다. 기록은 헤더 개수·프로토콜 분류·known-origin 일치 boolean과 오류 코드뿐이다. Secret/전체 환경변수/관리자 코드를 붙여넣지 않는다. 이 기록을 기준으로 다른 원인이 확인될 때만 다음 최소 수정을 수행한다.

관리자 인증·Origin·CSRF 검사를 해제하거나 임의 Host/Forwarded를 신뢰해서는 안 된다. gCube 실행 중 실제 등록·로그인 성공을 확인하기 전에는 최종 복구 PASS로 판정하지 않는다.
