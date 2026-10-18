# Mobile-first Dropbox setup — 계정 권한 승인 대기

기록: 2026-10-18 Asia/Seoul.

## 자동 완료한 작업

- 독립 브랜치: `development/dropbox-mobile-connect-v1-20261018`.
- 설계 체크포인트: `8791bc3`; 구현 체크포인트: `5d78ea1ecc33e3989cd4a142ec7e44683aaf657e`.
- Android 브라우저용 S256 PKCE offline 인증 화면, 동일 HTTPS callback·state 만료·재사용 차단, callback query 즉시 제거 구현.
- Refresh Token을 사용자에게 표시하거나 복사를 요구하지 않고, 브라우저 메모리에서 GitHub public key로 봉인 암호화하여 Secret API로 전달하는 경로 구현.
- 기존 키·App secret 보존, 같은 앱·계정인지 확인할 수 없는 기존 인증 교체 차단. 새 연결은 비공개 식별 표식을 먼저 저장하여 부분 실패 후 같은 계정으로 재개.
- 기존 자동 갱신·App Folder 백업·암호화·마지막 체크포인트 복구를 그대로 재사용. 새 백업 엔진·GPU 이미지·렌더러는 만들지 않음.
- 기존 immutable 이미지의 독립 pull과 보호 검사, GPU 없는 실제 백업·복구 검증 workflow 구현. 실제 GitHub API dispatch 성공 확인.

## 실제 검증 결과

| 검사 | 결과 |
| --- | --- |
| Core OAuth·Secret·보호 계약 | 36 tests PASS |
| Proof-only 실행·보안 계약 | 16 tests PASS |
| 실제 모바일 Chromium UI | 412×915, 126 assertions PASS, 합성 provider만 사용 |
| 실제 브라우저 sealed-box → 네이티브 복호화 | PASS; 변조 거부·평문 배열 초기화 PASS |
| 무료 CI push 실행 | [39102014929](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39102014929) PASS |
| 실제 API dispatch 및 무료 CI | [39102070071](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39102070071) PASS |
| 기존 FINAL·Candidate·렌더러·기존 웹사이트 변경 | 0 |
| 새 Docker 빌드·이미지 등록·GPU·유료 작업 | 0 |
| Required temp-only source files | 0 |

Secret Scan은 기본 gitleaks 규칙을 유지했다. 공식 npm 배포본과 바이트·SHA가 동일한 libsodium 함수명 5건이 generic-api-key 오탐이었다. 정확한 파일 SHA·규칙·5개 match를 대조해 분류했으며, 다른 finding은 허용하지 않는다. 실제 Secret 노출은 0건이다. 파일 제외나 탐지 임계값 변경은 없다.

보안 검토에서 발견한 기존 앱·계정 인증 덮어쓰기 위험과 실패 후 동작하지 않는 새로고침 버튼을 수정했다. 동일 앱·계정의 검증 표식이 없는 기존 연결은 자동 이관하지 않으며, 기존 인증과 데이터를 보존한다.

## 실제 Dropbox 연결·복구 상태

원격에 보존된 실제 결과: `runs/39102070071-1/proof.json`.

```json
{
  "status": "BLOCKED",
  "reasonCode": "MOBILE_DROPBOX_SECRETS_NOT_BOUND",
  "offlineTokenRefreshVerified": false,
  "metadataReadVerified": false,
  "externalStorageRecoveryVerified": false,
  "gpuExecuted": false,
  "productionRenderingStarted": false
}
```

필요한 인증 Secret 중 하나 이상이 연결되지 않아 실제 Dropbox 요청은 실행하지 않았다. CI 성공을 실제 연결·복구 성공으로 표시하지 않는다. 브라우저 UI의 PASS는 합성 응답을 사용한 검사이며 실계정 PASS가 아니다.

기존 이미지 재사용: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0`.

## 현재 멈춘 실제 원인

현재 GitHub 연동은 새 저장소 생성 요청 `POST /user/repos`에 `403 Resource not accessible by integration`을 반환했다. 확인 전 `world-engine-connect` 조회는 404였으며, 새 저장소가 생성됐다고 보고하지 않는다.

기존 `yeonhwarok-free` Pages는 다른 ‘연화록’ 서비스를 제공한다. 그 사이트를 OAuth 페이지로 교체하거나 main·Pages 설정을 변경하지 않았다. 별도 HTTPS 호스팅 권한이 없으므로 아직 사용자에게 접속 가능한 연결 URL은 없다. `web/config.js`는 비활성 상태이며, 임의 주소나 인증정보를 채워 넣지 않았다.

Dropbox 공식 JS SDK의 브라우저 PKCE·offline 교환은 확인했다. GitHub API의 브라우저 CORS preflight도 HTTP 204로 확인했다. Dropbox token endpoint의 직접 CORS 요청은 환경 프록시 CONNECT 403으로 미검증이다. 이를 Dropbox 계정 오류로 판단하지 않는다.

## 지금 사용자에게 반드시 필요한 행동

Android에서 [GitHub 새 저장소](https://github.com/new) → Owner **dimon3898-sys** → 이름 **world-engine-connect** → **Public** → **Add README** 켜기 → **Create repository**.

이 계정 작업 후 Codex가 새 저장소 접근·HTTPS 배포를 이어간다. 현재는 PC·Docker·터미널·토큰 채팅 전송·유료 GPU 실행을 요구하지 않는다. 기존 연동이 새 저장소에 접근할 수 없으면 그때 공식 저장소 접근 권한만 추가한다.

배포 후 최초 한 번 필요한 Dropbox callback 등록과 GitHub Secret 쓰기 승인 버튼·최소 범위는 [README](README.md)에 기록했다. 이후 연결 화면이 Refresh Token 수령·암호화 Secret 등록·무료 검증 시작을 처리한다. 기존 App Folder 앱을 새로 만들거나 이미 완료한 권한을 반복 설정하지 않는다.

## 다음 실행 지점

독립 HTTPS 호스팅 권한 확인 → 실제 주소 HTTP 및 파일 SHA 검증 → Dropbox callback 등록 → 휴대폰 로그인·Allow → GitHub의 제한된 정식 권한 승인 → 자동 Secret 저장 → 기존 CPU 백업·다운로드·복구 proof.

`MOBILE_CONNECTION_CPU_VERIFIED`

`USER_ACCOUNT_AUTHORIZATION_REQUIRED`

실제 Dropbox proof 전 유료 GPU 실행은 차단을 유지한다. FINAL 승격은 하지 않는다.
