# Dropbox CPU proof startup correction

기존 계정 인증·Secret·키·백업을 재사용한다. 새 인증·토큰 재발급·GPU·이미지 빌드는 없다.

## 기존 실제 기록

실행 `39110576350`, attempt 1의 공개 proof는 `DURABILITY_OFFLINE_STARTUP_FAILED`를 기록했다. workflow가 초록색이어도 이 proof는 BLOCKED이며 실제 백업·복구 성공이 아니다.

기존 `studio-dropbox-offline-v1/ci.py`는 Python `-c`에서 `runpy.run_path(offline_entry.py)`를 실행하지만 모듈 디렉터리를 import 경로에 추가하지 않는다. 따라서 `offline_manifest` import가 실패하며 entry의 안전한 오류 처리에서 일반 시작 오류, 종료 코드 2로 바뀐다. 기존 정상 entrypoint의 직접 스크립트 실행과는 다른 경로다.

기존 로그 아카이브 다운로드는 현재 Codex 네트워크의 403으로 접근하지 못했다. 보존된 실제 proof와 원본 코드, 독립 CPU 재현을 사용한다. 이 프로필은 같은 immutable 이미지에서 수정 전 종료 2와 고정 workdir 적용 후 CLI import 성공을 다시 확인한 뒤에만 실제 외부 검증을 허용한다.

## 최소 수정

`adapter.py`가 SHA 고정 원본 bootstrap과 정확히 같은 외부 proof 명령에만 Docker 인자 `--workdir=/opt/world-engine-studio-dropbox-offline`를 추가한다. 다른 명령이나 실행 이미지에는 적용하지 않는다. 보안·UID·읽기 전용 마운트·capability·GPU 금지 조건을 유지한다.

기존 frozen 파일을 수정하지 않는다. 새 proof adapter는 기존 `proof_ci.py`와 `ci.py`를 SHA로 확인하고 재사용한다. 업로드·다운로드·암호화·fresh-process restore·OAuth 자동 갱신·Secret 파일 취급은 원래 구현이다.

첫 실제 수정 검증 `39111545470`에서 시작 재현 검사는 PASS했고, 다음 단계에서 `DURABILITY_KEY_32_BYTES_REQUIRED`를 확인했다. 브라우저가 저장한 표준 Base64 표현과 frozen reader가 요구하는 canonical URL-safe Base64 표현의 불일치다. 키의 raw32 형식을 요구하는 문제가 아니다.

`key_encoding.py`는 기존 Secret의 프로세스 내부 복사본을 엄격히 디코딩해 정확히 32바이트임을 확인하고, **동일 바이트**를 패딩을 유지한 URL-safe Base64로 표현한다. 그 표현만 기존 helper의 이번 실행용 private 파일에 전달한다. GitHub Secret 원문·암호화 키 바이트·기존 백업은 변경하지 않는다. raw32·hex64·패딩 누락·비정규 문자열은 추측해 처리하지 않는다.

이 정규화는 이번 CPU proof 입력 경계에 적용된다. 기존 GPU 생산 이미지의 bootstrap은 이번 작업에서 변경하지 않았다. 향후 생산 실행에도 동일 바이트 보존 입력 어댑터를 연결해야 하며, 이 proof 성공만으로 GPU 시작 성공을 선언하지 않는다.

## 검증과 저장

- 보호 기준: `1cd8ea4565238bd7d4c8c72c6374f78557b2dc1d`.
- 새 브랜치: `development/dropbox-startup-fix-20261018`.
- 새 workflow: `.github/workflows/studio-dropbox-startup-fix-v1.yml`.
- 새 파일과 workflow만 변경을 허용한다. 기존 FINAL·Candidate·렌더러·기존 백업 파일·키는 변경하지 않는다.
- 고정 기존 이미지 하나만 pull하고 원본 payload·protected parent manifest를 확인한다. 같은 이미지의 이미 완료된 parent/dependency 감사와 전체 테스트는 반복하지 않는다.
- 집중 stdlib 검사 11개, 기본 규칙 그대로인 SHA 고정 gitleaks 검사, 자격증명 없는 CPU 시작 재현을 사용한다.
- `workflow_dispatch`에서만 기존 Repository Secrets 네 개를 일시적인 UID 1000 / 0600 파일로 마운트한다. 이 실행의 새 임시 파일만 제거한다.
- 기존 Dropbox 객체에는 overwrite/delete를 하지 않는다. 기존 백업 구현의 고유 합성 검증 객체·receipt만 추가한다.
- 공개 결과는 `runs/<runId>-<attempt>/proof.json`과 SHA256SUMS뿐이다. 원문 로그·Secret·provider body는 기록하지 않는다.

실제 외부 검증이 PASS일 때만 `proofId`, `checkpointId`, 만료시각과 실제 offline refresh·metadata·external recovery 확인을 내보낸다. GPU·production rendering·production approval은 항상 false다. 이 proof 성공은 FINAL 승격이나 유료 GPU 실행 승인이 아니다.

## 재현 방법 — Codex/CI용

집중 테스트는 `python3 -B -m unittest discover -s <이 디렉터리>/tests -v`이다. 새 무료 workflow를 해당 브랜치로 한 번 dispatch하면 preflight → scan → immutable pull → CPU 시작 재현 → 실제 외부 백업·복구 → 안전한 proof 저장을 수행한다. 사용자에게 터미널 실행이나 재로그인을 요구하지 않는다.

이전 mobile Candidate의 파일과 workflow는 보존한다. 이번 수정 프로필의 결과는 별도 경로에 기록하며, 원래 실패 proof를 덮어쓰거나 삭제하지 않는다.
