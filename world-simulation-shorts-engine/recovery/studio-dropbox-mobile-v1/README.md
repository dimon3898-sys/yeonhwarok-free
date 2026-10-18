# Android 전용 Dropbox 연결 후보

사용자에게 PC·Docker·터미널 명령을 요구하지 않는다. 기존 offline 자동 갱신·암호화 백업·복구는 변경하지 않고, 최초 인증 화면만 추가한다. 실제 계정 연결과 CPU 모의 검증은 별개이다.

## 현재 반드시 필요한 사용자 행동

**독립 무료 HTTPS 사이트를 만들 계정 권한**이 필요하다. 현재 Codex GitHub 연동은 `POST /user/repos`를 `403 Resource not accessible by integration`으로 거부했다. 없는 권한을 우회하지 않았다. 기존 Pages는 별도 ‘연화록’ 서비스이므로 대체·삭제·설정 변경하지 않는다.

Android 브라우저에서:

1. [GitHub 새 저장소](https://github.com/new)를 연다.
2. Owner `dimon3898-sys`, Repository name **`world-engine-connect`**, **Public**, **Add README** 켜기를 선택한다.
3. **Create repository**를 누른다.

생성 후 Codex가 해당 저장소 접근을 다시 확인하고 연결 화면 배포를 이어간다. 현재 단계에서 토큰을 채팅에 보내거나 유료 GPU를 실행할 필요가 없다. GitHub 연동이 새 저장소에 접근하지 못하면 그때 공식 연결 권한만 추가한다. 미확인 링크를 연결 완료 주소로 제공하지 않는다.

## HTTPS 주소가 실제로 발행된 뒤의 휴대폰 순서

아래는 배포 후 사용할 화면의 계약이며, 현재 실행 완료라는 뜻이 아니다.

1. 실제 연결 페이지의 **처음 연결할 때만 확인 → 주소 복사**를 누른다. Dropbox App Console → 기존 App Folder 앱 → **Settings → OAuth 2 → Redirect URIs**에 붙여넣고 **Add**를 누른다. 주소를 임의로 만들지 않는다.
2. **Permissions**에 `files.content.read`, `files.content.write`, `files.metadata.read`가 있는지 확인하고 필요한 경우 **Submit**을 누른다. 이미 설정된 항목은 반복 변경하지 않는다.
3. 모바일 연결 화면에 같은 앱의 **App key**를 넣고 **Dropbox 연결 → 로그인 → Allow**를 누른다. PKCE offline 교환으로 Refresh Token을 직접 받으며, 사용자는 토큰을 복사하지 않는다.
4. 현재 Codex 연동은 Repository Secret 저장 권한을 갖고 있지 않다. 최초 한 번 GitHub의 정식 권한 연결이 필요하다. 연결 화면의 **GitHub 권한 화면 열기**를 누르고, 아래 최소 범위로 발급한 단기 권한을 그 화면의 비공개 입력칸에만 넣는다.

GitHub 휴대폰 화면: 프로필 → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**. 짧은 만료일, **Only select repositories → yeonhwarok-free**만 선택한다. Repository permissions에서 **Secrets: Read and write**, **Actions: Read and write**만 추가한다. Contents 쓰기·관리자 권한은 필요하지 않다. 생성한 값은 채팅·로그·Git 파일·URL에 넣지 않는다.

5. **권한 확인**을 누른다. 기존 App secret이 있으면 다시 입력하지 않는다. 최초 설정에 값이 없을 때만 같은 Dropbox 앱 Settings → App secret → **Show**의 값을 비공개 입력칸에 넣는다. 이는 기존 실행 이미지와의 호환 설정이며 Dropbox PKCE 요청에는 전송하지 않는다.
6. **연결 저장 · 무료 백업 검증**을 누른다. Refresh Token과 필요한 설정을 GitHub repository public key로 브라우저에서 봉인 암호화하고 Secret API에 저장한다. 검사 workflow가 자동 실행된다. 실제 proof를 읽기 전에는 백업 성공을 표시하지 않는다.

## 자동 처리와 보존

- S256 PKCE, state·유효 시간·동일 HTTPS callback 검사, 한 번만 사용하는 인증 코드.
- 짧은 PKCE verifier/state만 sessionStorage에 보관하고 callback 즉시 소비·삭제한다. Refresh Token·Access Token·App secret·GitHub 권한·암호화 키는 브라우저 저장소나 URL에 넣지 않는다.
- 기존 백업 키·App secret은 보존한다. 키가 없는 경우 실제 App Folder 백업 경로가 비었음을 확인해야만 첫 키를 생성한다. 기존 백업이 있으면 새 키로 대체하지 않는다.
- 기존 인증이 이미 있으면 앱·계정 일치 여부를 확인할 수 없는 교체를 차단한다. 새 연결은 Secret 메타데이터의 익명 식별 표식을 사용하며 원문 계정 ID를 공개하지 않는다.
- GitHub Secret은 기존 `WORLD_ENGINE_STUDIO_BACKUP_KEY`, `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY`, `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET`, `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN`을 사용한다. 사용자가 Refresh Token을 수동 등록할 필요는 없다.
- 기존 `/WORLD_ENGINE_STUDIO_BACKUPS_V1` App Folder 경로와 AES-GCM/HKDF 암호화, 완료 장면·마지막 체크포인트 복구를 그대로 사용한다.
- 실제 검증은 이미 만들어진 immutable 이미지 `sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0`를 CPU에서 실행한다. 새 이미지 빌드·GPU 배포·렌더링은 없다.

## 보안·운영 한계

이 페이지가 안전한 HTTPS 주소에 배포되기 전에는 `config.js`가 비활성화 상태로 유지된다. 임의 Host·Origin을 신뢰하거나 기존 웹사이트를 덮어쓰지 않는다. 계정 소유자의 Dropbox 동의와 GitHub Secret 쓰기 권한을 Codex가 대신 생성할 수는 없다.

페이지를 닫으면 메모리에만 있던 인증 자료는 버린다. 이미 GitHub Actions로 시작된 무료 검증은 계속된다. 연결 저장 전 탭을 닫으면 Dropbox 승인부터 다시 시작해야 한다. 이전 Studio 작업·claim·캐시·완성 영상은 이 UI가 변경하지 않는다.

외부 플랫폼이 표준 OAuth callback 접근을 내부 로그에 남길 수는 있으나, 콜백 코드는 짧게 유효한 일회용이며 PKCE verifier 없이 교환할 수 없다. 페이지는 callback query를 첫 스크립트에서 제거하고 referrer 전송을 막는다. 자체 로그·분석·외부 CDN 스크립트는 없다.

기존 키·앱 인증이 옛 경로에서 설정되어 새 식별 표식이 없는 경우 자동 교체하지 않는다. 기존 자격증명을 무료 검증으로 확인하고 같은 앱·계정에 대한 안전한 이관을 별도로 수행해야 한다. Secret 값은 GitHub API에서 읽어낼 수 없다.

## 무료 검증과 다음 재개 지점

Core 계약, 실제 모바일 Chromium UI, 공식 libsodium 브라우저 암호화와 네이티브 복호화, proof-only workflow의 집중 검사를 수행한다. 합성 provider 응답은 실제 Dropbox 연결로 표시하지 않는다. 최신 수치·원격 커밋·CI 상태는 `RESULT.md`에 기록한다.

현재 재개 지점: **독립 HTTPS 호스팅 계정 권한 → 실제 URL 검증 → Android에서 최초 동의 → 무료 실제 Dropbox 백업·복구 proof**. 실제 proof 전 유료 GPU는 실행하지 않는다. 기존 FINAL·Candidate·렌더러·영상·자료는 모두 보존한다.
