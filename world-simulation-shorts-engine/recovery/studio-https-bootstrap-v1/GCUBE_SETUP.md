# gCube 설정과 모바일 HTTPS 등록

이 문서는 새 후보의 무료 CPU 검증 절차와 실제 GPU 실행을 구분합니다. 이 작업에서는 gCube 배포·유료 렌더링을 하지 않습니다. #5373의 과거 최초 종료 로그는 확보되지 않았으므로 그 최초 원인까지 확정한 것은 아닙니다.

## 배포 설정

검증 완료된 새 태그/digest는 최종 `RESULT.md`와 `runs/*/pull.json`을 확인합니다. 기존 이미지는 보존합니다.

- GPU: RTX 4080 SUPER 16GB. 기존 정상 GPU 설정을 재사용합니다.
- 서비스 포트: **8080**, Command: **비움**. 이미지의 별도 HTTPS bootstrap ENTRYPOINT를 사용합니다.
- 공유 메모리: **2GB**.
- 기존 Dropbox 마운트: **/world-storage**. 데이터나 권한을 초기화하지 않습니다.
- `WORLD_ENGINE_RENDER_MODE=gpu-required`
- `WORLD_ENGINE_STARTUP_MODE=normal` — 기존 진단 전용 설정과 구분합니다.
- `NVIDIA_DRIVER_CAPABILITIES=graphics,utility,compute,video` — 기존 정상 GPU 런타임 설정을 보존합니다.
- `WORLD_ENGINE_STUDIO_PORT=8080`
- `WORLD_ENGINE_STUDIO_OWNER_CODE`: **기존 관리자 코드 Secret 그대로**. 새 코드 생성·재설정이나 채팅 입력이 필요하지 않습니다. 미설정이며 기존 private owner 파일도 없으면 시작을 차단합니다.
- `WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST`: **이번에 배포하는 새 이미지의 `sha256:...` 값**. 전체 GHCR 주소나 부모 이미지 digest를 넣지 않습니다. 이 환경변수는 Scene/실행 이미지 바인딩 값이며, 환경변수 값만으로 실제 OCI 이미지 신원을 증명하는 것은 아닙니다.
- `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN`: 첫 배포에서는 없어도 됩니다. 임의 주소를 넣지 않습니다. 이미 실제 주소를 설정한 경우 보존합니다.
- `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON`: 기존 실제 운영 정책을 보존합니다. `gpuHourlyRate`, `currency`, `maxCostAmount`, `maxWallSeconds`, `maxRetries`, 시간대가 포함된 `validUntil`이 필요합니다. 임의 요금·비용·승인을 만들지 않습니다. 누락·오류·만료이면 웹 UI는 유지되지만 제작은 차단됩니다.

GPU API 토큰·이메일·워크로드 번호는 이 수동 배포 Studio의 HTTPS 부트스트랩에 필요하지 않습니다. 기존 Secret을 삭제하지 않습니다. 사용자는 배포·과금 종료를 직접 관리합니다. Studio의 시간 제한은 플랫폼 과금 종료 기능이 아닙니다.

## 처음 등록

1. 사용자가 승인 후 워크로드를 배포하고, gCube가 발급한 **포트8080의 실제 HTTPS 서비스 주소**를 엽니다.
2. 초기 설정 화면에서 그 HTTPS Origin을 직접 입력합니다. 경로·쿼리·끝의 `/`는 제외합니다. 주소창의 실제 출처와 일치해야 합니다.
3. **기존 관리자 접근 코드**로 확인합니다. 이 단계는 주소를 저장하거나 렌더링하지 않습니다.
4. 표시된 주소를 다시 확인하고 명시적으로 등록합니다. 일회용 확인이 끝나면 설정/운영 세션은 모두 폐기됩니다.
5. “Studio 로그인”으로 이동하여 기존 관리자 코드로 새로 로그인합니다. 기존 입력·SFX·진행·부분 수정·결과 화면을 사용합니다.
6. 실제 GPU 검사, 데이터/Scene SHA, 유효한 운영 정책과 비용/시간/재시도 한도, 명시적 제작 동의가 모두 충족돼야 제작을 시작합니다. HTTP200이나 초기 설정 완료만으로 GPU/영상 제작 성공이 아닙니다.

## 주소 변경과 영속성

확정 주소를 바꾸려면 **기존 등록 주소에서 로그인한 상태로 `/setup`**에 접근하고, 관리자 코드를 다시 확인하여 실제 새 Origin을 명시적으로 등록합니다. 요청은 기존 Origin에 고정하여 검증하고, 저장 후 모든 세션을 폐기합니다. 새 주소에서 다시 로그인합니다.

주소와 인증 상태는 기존 private0700 POSIX 경로의0600 파일에만 보존합니다. Dropbox에 관리자 코드·세션·Origin 상태를 내보내지 않습니다. 동일 컨테이너 재시작/동일 private 볼륨에서는 등록 주소가 유지됩니다. **gCube가 컨테이너/워크로드를 새로 만드는 경우 writable layer 영속성은 확인되지 않았습니다.** 재생성 후 같은 주소를 유지하려면 확인된 실제 Origin을 gCube의 기존 `WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN` 설정에도 저장하거나, 별도 승인된 private POSIX 영구 볼륨을 사용해야 합니다. 새로운 임시 컨테이너는 인증된 초기 설정을 다시 할 수 있습니다. 충돌하는 기존 private 설정을 덮어쓰지 않습니다. 환경변수 주소와 이미 확인·등록한 private 주소가 다르면 등록된 주소의 UI는 유지하고 `STUDIO_CONFIGURED_ORIGIN_CONFLICT`로 제작을 차단합니다. gCube의 실제 환경변수 주소도 새 등록 주소와 일치시킨 뒤 재시작해야 합니다.

## 상태·실패

- `/healthz`: 웹 서비스가 살아 있는지만 표시합니다. SETUP/CONFIGURED와 관계없이 `renderAllowed=false`, `gpuRenderingVerified=false`입니다.
- 기존 포트8000의 GPU admission/진단 서비스는 변경하지 않습니다.
- GPU admission이 실패/종료돼도 웹 UI가 유지됩니다. 오류는 stdout에 기록하며 자동 GPU 재시도·자동 렌더링은 하지 않습니다.
- 관리자 코드 누락, private 경로 안전성 실패, 소스 무결성 실패는 fail closed입니다.
- 잘못된 Host/Origin/forwarded header, 인증 실패, CSRF 실패는 제작/설정 요청을 거부합니다. 이를 해결하려고 인증·CSRF 검사를 끄면 안 됩니다.
- 예전 작업·claim·캐시·완성 영상은 삭제하거나 초기화하지 않습니다.

실제 NVIDIA, gCube 프록시/healthcheck, Dropbox 외부 동기화, 80초 제작 및 영상 품질은 별도 승인된 실제 GPU 실행에서 확인할 항목입니다.
