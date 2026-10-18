# WORLD ENGINE Dropbox offline token candidate V1

상태: 사용자 Secret 설정 대기. 무료 CPU 검증과 실제 Dropbox 검증은 구분한다. 이 프로필은 유료 GPU 배포·렌더링을 시작하지 않는다.

## 변경 범위와 보호

보호 부모는 `165a3489eede6e6f66c20f2d6ca1d70fd8c79560`의 `studio-durability-v1`이다. 부모 이미지:

`ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:54e7f67627a14755117a3f232c03785f9ceac4ab490a33e8f5834fb9fe114b9b`

기존 DropboxStore, AES-GCM/HKDF 암호화, 체크포인트·장면 캐시·복구·claim·승인 검사를 그대로 호출한다. 기존 FINAL·Candidate·렌더러 파일은 변경하지 않는다. 새 이미지의 독립 진입점만 Refresh Token 공급자를 연결한다. 기존 Access Token Secret을 삭제하거나 덮어쓰지 않는다.

- Access Token은 응답의 `expires_in`과 단조 시계를 사용해 만료 전 갱신한다. 여유 시간은 최대 60초이며 짧은 TTL에서는 10%이다.
- 파일 API의 명시적 HTTP 401에만 한 번 갱신하고 한 번 재전송한다. 업로드 연결 중단·403·429·5xx를 무조건 재시도하지 않는다.
- 갱신 실패는 기존 백업 오류로 전달한다. 입력 체크포인트 실패 시 작업을 시작하지 않으며, 장면 백업 실패 시 다음 장면을 시작하지 않는다.
- 재시작은 기존의 마지막 검증된 원격 체크포인트·완료 장면 복구를 사용한다. 이전 실행 권한·PID·claim을 복구하여 자동 실행하지 않는다. 재개에는 새로 유효한 운영 승인이 필요하다.
- Access Token은 메모리에서 사용한다. 부모 생성자 계약을 위해 새 0600 임시 파일에 잠깐 전달한 뒤 삭제한다. 장기 Secret·키는 백업·로그·이미지에 넣지 않는다.

## 1. Dropbox 앱 설정

1. [Dropbox App Console](https://www.dropbox.com/developers/apps)에 로그인하고 이미 만든 **Scoped App / App Folder** 앱을 연다. Full Dropbox 앱으로 바꾸지 않는다.
2. **Permissions** 탭에서 `files.content.read`, `files.content.write`, `files.metadata.read` 세 항목을 체크하고 **Submit**을 누른다.
3. **Settings** 탭의 **App key**, **App secret → Show**를 본인만 확인한다. 값을 채팅·GitHub 파일·로그에 붙여넣지 않는다.
4. 다음 오프라인 동의를 새로 수행한다. Permissions 변경만으로 이전 토큰의 권한이 추가되지는 않는다. **Generated access token → Generate**는 이 기능의 Refresh Token 발급 절차가 아니다.

## 2. Refresh Token 최초 발급: 무료 CPU에서 한 번

공식 Dropbox OAuth 2 NoRedirect 인증 코드 흐름을 사용한다. helper는 다음 공식 URL에 `response_type=code`, `token_access_type=offline`, 위의 세 scope를 지정한다. 임의 Redirect URI나 가짜 주소를 등록하지 않는다.

`https://www.dropbox.com/oauth2/authorize`

PC 등의 무료 Docker 환경에서 이 후보 이미지의 immutable digest를 사용한다. 정확한 새 참조는 `RESULT.md` 및 `runs/`에 기록한다. GPU 옵션은 넣지 않는다. 아래 경로는 **새로 만드는 Secret 전용 디렉터리**이며 `/world-storage`, Git 체크아웃, 공개 동기화 폴더로 바꾸지 않는다.

```bash
install -d -m 700 "$HOME/world-engine-dropbox-secret"
docker run --rm -it --user 1000:1000 --read-only --cap-drop ALL \
  --security-opt no-new-privileges --tmpfs /tmp:rw,mode=1777 \
  --mount "type=bind,src=$HOME/world-engine-dropbox-secret,dst=/run/offline-secret" \
  --entrypoint /opt/world-engine-studio-durability-venv/bin/python \
  <RESULT.md에 기록된 새 이미지@sha256:...> -B \
  /opt/world-engine-studio-dropbox-offline/consent.py \
  --refresh-secret-file /run/offline-secret/dropbox-refresh-token
```

이 명령의 마운트는 실행 사용자 UID/GID 1000 소유의 0700이어야 한다. 호스트가 이 조건과 다르면 기존 폴더 권한을 강제 변경하지 말고 별도 무료 CPU 환경의 본인 전용 1000:1000 디렉터리를 사용한다. 기존 파일이 있으면 helper는 덮어쓰지 않는다.

숨김 입력 순서는 **App key → App secret → Dropbox authorization code**이다. helper가 표시한 공식 URL을 브라우저에서 열고 본인 계정으로 로그인하여 **Allow**를 누른다. Dropbox가 보여주는 코드를 helper의 숨김 입력에 넣는다. 결과 Refresh Token은 지정한 비공개 파일에만 저장된다. 그 파일을 안전한 로컬 편집기로 열어 다음 GitHub Secret의 입력칸에만 붙여넣는다. 채팅이나 `echo`/명령 인자로 전달하지 않는다.

이 발급 과정은 사용자의 실계정 동의가 필요하며 Codex가 대신 승인하거나 토큰을 만들어내지 않는다. 발급 파일은 승인된 Secret 관리자에 안전하게 보관한다. 기존 암호화 키를 잃으면 기존 백업을 복구할 수 없다.

## 3. GitHub Repository Secrets

저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 아래 이름으로 등록한다. 기존 항목은 **Update**를 사용하되, 기존 백업 키를 새 키로 바꾸지 않는다.

| 정확한 Secret 이름 | 넣을 실제 값 |
| --- | --- |
| `WORLD_ENGINE_STUDIO_BACKUP_KEY` | 기존 백업에 사용한 동일한 32바이트 키의 Base64 값. 기존 값 유지 |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY` | 동일 Dropbox 앱의 App key |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET` | 동일 앱의 App secret |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN` | 위 helper가 발급받은 Refresh Token |

기존 `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN`은 보존한다. 새 offline 프로필은 이를 사용하지 않는다. Refresh Token을 이 예전 Access Token 필드에 넣지 않는다. Secret이 Actions에 등록되어도 gCube에 자동 전달되지는 않는다.

## 4. 실제 Dropbox 백업·복구 무료 검증

GitHub **Actions → WORLD ENGINE Studio Dropbox offline token candidate → Run workflow → Branch: `development/dropbox-offline-token-v1-20261018` → Run workflow**를 누른다.

이 워크플로는 공개 저장소의 표준 무료 CPU runner만 허용한다. 기존 이미지 보존, 고유 태그, 독립 digest pull 후, 위 네 Secret이 모두 있을 때만 실제 Dropbox 검증을 수행한다. 네 값 중 하나라도 없으면 `OFFLINE_EXTERNAL_SECRETS_NOT_BOUND / BLOCKED`이며 성공으로 취급하지 않는다.

실제 검사에는 Refresh Token 교환, App Folder metadata 권한 요청, 기존 암호화 백업 업로드·다운로드, 합성 CPU MP4 체크포인트의 새 private 디렉터리 복구가 포함된다. GPU나 기존 제작 작업은 실행하지 않는다. 검사 결과는 새 `runs/` 아래 안전한 JSON으로 저장된다. Refresh Token·키·파일 이름 목록·원문 HTTP 응답은 기록하지 않는다.

실제 결과의 `externalDurability.status=PASS`, `offlineTokenRefreshVerified=true`, `metadataReadVerified=true`, `externalStorageRecoveryVerified=true`를 확인한다. `actualContainerRestartRecoveryVerified` 및 NVIDIA 렌더링은 별도 검증이며 CPU proof로 PASS를 선언하지 않는다. 기존 production preflight의 유효 proof 요구를 그대로 유지한다.

## 5. 이후 gCube 설정: 실제 Dropbox proof 후에만

이번 작업은 유료 GPU를 배포하지 않는다. 이후 사용자가 승인한 배포에 한해 기존 owner·Origin·운영 정책·private state 설정을 유지하고 새 후보 이미지를 선택한다.

일반 환경 설정:

| 이름 | 값 |
| --- | --- |
| `WORLD_ENGINE_STUDIO_BACKUP_MODE` | `dropbox-api` |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_AUTH_MODE` | `offline` |
| `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_PREFIX` | `/WORLD_ENGINE_STUDIO_BACKUPS_V1` |
| `WORLD_ENGINE_STUDIO_BACKUP_PROOF_ID` | 무료 실제 검증에서 발행한 유효 `proofId` |

위 네 Secret은 gCube의 승인된 Secret 입력 경로에 **같은 이름**으로 연결한다. Secret 파일 마운트 방식도 지원하며 각각 이름 뒤에 `_FILE`을 붙인 변수에 비공개 파일의 경로를 지정한다. 이 경우 파일은 UID/GID 1000, 0600, 부모 디렉터리는 0700이고 링크가 없어야 한다. Secret 값을 일반 명령·이미지 빌드 인자·Git 파일로 넣지 않는다.

API 경로 `/WORLD_ENGINE_STUDIO_BACKUPS_V1`는 App Folder 내부 상대 경로이다. Dropbox 화면에서는 **Apps → 앱 폴더 → WORLD_ENGINE_STUDIO_BACKUPS_V1**에 해당한다. `/Apps/...`를 prefix에 추가하지 않는다. `/world-storage`는 기존 공개 결과물용이며 Secret·Studio private state·암호화 키의 저장소로 쓰지 않는다.

갱신 거부·권한 부족·네트워크 오류는 안전한 오류 코드로 표시되고 다음 장면이 차단된다. 올바른 Secret을 연결한 뒤 기존 체크포인트 복구 절차와 새 운영 승인으로 재개한다. 기존 claim·캐시·완성 영상을 삭제해서 우회하지 않는다.

## 검증 범위

CPU 모의 OAuth 검사와 기존 FFmpeg 체크포인트 복구 회귀는 실제 Dropbox 계정, gCube 재시작, NVIDIA GPU 검증이 아니다. 최종 CI 수치·이미지 digest·실제 외부 proof 상태는 `RESULT.md`에 기록한다. 실제 Dropbox 백업·복구 proof 전에는 유료 GPU를 실행하지 않는다.

공식 근거: [Dropbox Python SDK OAuth](https://github.com/dropbox/dropbox-sdk-python/blob/main/dropbox/oauth.py), [공식 offline scopes 예제](https://github.com/dropbox/dropbox-sdk-python/blob/main/example/oauth/commandline-oauth-scopes.py), [공식 Files API scope 정의](https://github.com/dropbox/dropbox-api-spec/blob/main/files.stone). 기존 App Folder 호환성 조사 결과를 재사용했다.
