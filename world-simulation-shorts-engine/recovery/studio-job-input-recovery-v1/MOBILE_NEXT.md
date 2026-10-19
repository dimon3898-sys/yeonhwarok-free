# 현재 Studio에서 80초 입력 불러오기

기존 80초 입력은 원본 `production-studio-mvp-v1/examples/STUDIO_PROMPT_V4_80S.json`에 보존돼 있다. 별도 Scene JSON 업로드 없이 이 구조화 프롬프트의 `VERIFIED_FRONT_V4_80S`를 사용하면 이미지에 포함된 고정 V4 자료를 불러온다. 80초·2,400프레임·12장면이며 기존 근사/부분 역사 자료의 한계를 유지한다.

원본 다운로드는 HTTP200·308바이트·SHA256 `68bf6157f03c5fdafbf5f5734a1890e4a8c6c9adb0198333ff411cad2069797d`가 확인됐다.

[기존 입력 JSON](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/c5f39f3fa2bf9cf558d2c0e4268211a4679c14e2/world-simulation-shorts-engine/recovery/production-studio-mvp-v1/examples/STUDIO_PROMPT_V4_80S.json)

## 오류와 기존 작업

`STUDIO_JOB_NOT_FOUND`는 현재 private 상태의 `production/jobs/<요청ID>.json`이 없거나 ID가 일치하지 않을 때 발생한다. 브라우저는 로그인 직후 `localStorage['world-studio-job']`의 이전 ID를 자동 조회한다. 기존 상태 경로/컨테이너를 교체했다면 이전 ID만 브라우저에 남을 수 있지만, 오류만으로 모든 작업이 없다고 단정하지 않는다.

기존 서비스에는 인증된 작업 목록 API가 없다. 이번 읽기 전용 원격 조회는 작업 목록/디스크에 접근하지 않으며 존재하지 않는 작업을 만들어 복구하지 않는다. 현재 root에 다른 작업이 있는지는 아직 확인하지 못했다.

기존 **로그아웃 → 관리자 로그인**은 브라우저의 이전 작업 ID만 제거하며 서버의 작업·claim·Scene·캐시·영상은 삭제하지 않는다. 같은 입력에 대한 중복 방지 기록 `runs/<submissionSHA>.json`도 그대로다. 명시적 제작 시작을 나중에 승인하더라도 같은 입력의 기존 기록이 있으면 새 GPU 작업 대신 그 기록을 반환한다.

## 휴대폰에서 수행할 무료 사전검사

1. Studio에서 **로그아웃 → 같은 관리자 코드로 로그인**한다. 이 동작은 렌더링 중단/시작/서버 기록 삭제를 수행하지 않는다.
2. **80초 / V4 · 근사·부분 역사 자료**, 효과음 ON·65%를 선택한다.
3. 기존 JSON을 **제작 프롬프트**에 붙여넣고 Scene JSON 첨부는 비워 둔다.
4. **사전검사**만 누른다. **제작 동의**는 체크하지 않고 **제작 시작/재개**를 누르지 않는다.
5. `CURRENT_GPU_HEALTH: PASS`와 `WORK_CLAIM: PASS`, 나머지 검사 결과를 확인한다. 실패한 항목이 있으면 오류 코드를 보존하며 제작은 시작하지 않는다.

`CURRENT_GPU_HEALTH`는 기존 localhost8000 health에서 `gpuRenderingVerified=true`, `testOnly=false`, `renderMode=gpu-required`, `model=RTX 5090`을 요구한다. 기존 시작 시 검증된 NVIDIA WebGL2 결과를 읽으므로 새 GPU draw나 80초 영상 작업을 생성하지 않는다. 실제 장면별 admission은 향후 승인된 렌더링 시 다시 검사한다.

공개 포트8080 `/healthz`의 `gpuRenderingVerified=false`, `renderAllowed=false`는 웹 서비스용 고정 응답이다. 이 응답만으로 GPU 실패/성공을 판정하지 않는다. 관리자 로그인 성공도 GPU PASS의 증거가 아니다.

사전검사 버튼은 `/api/preflight`와 준비된 입력의 `/api/submissions` 저장만 수행한다. GPU 작업 생성은 별도 동의와 `/api/start`가 있어야 한다. 이 작업에서는 `/api/start`, `/resume`, 워크로드 변경·SSH·GPU 재배포를 실행하지 않는다.

## 검증 범위

원본 입력 계약·기존 프리셋 바인딩 CI 증거를 재사용했다. 로컬 sparse checkout의 전체 Scene body를 새로 다운로드하거나 역사 자료를 생성하지 않았다. 이번 로컬 전체 백엔드 실행은 필수 parent JSON 미추출로 완료하지 않았으며 새 PASS로 표시하지 않는다. 현재 서버의 실제 프리셋·source closure·GPU·중복 claim은 인증된 사전검사에서 검사해야 한다.

기존 FINAL·Scene·Asset·렌더러는 수정하지 않는다. 새 이미지도 필요하지 않다. 사용자 승인 전 80초 제작은 시작하지 않는다.
