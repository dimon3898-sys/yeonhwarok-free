# Dropbox offline token support — 사용자 설정 대기

기록: 2026-10-18 Asia/Seoul.

## 저장·이미지

- Branch: `development/dropbox-offline-token-v1-20261018`
- Design checkpoint: `23996e675dbf36422664095496ca4317390f79c9`
- Implementation/image source: `86b3a159eec2b3fefc6ee9248e102a61ad34288a`
- CI evidence persisted through: `7a37e34`
- [무료 CI #39100005538](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39100005538): build PASS, independent pull PASS.
- New tag: `studio-dropbox-offline-v1-165a348-39100005538-1`
- New immutable image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:6d2e87fc8fb7f10edc2ebb7f77b5d666e329904b9c37f7f060b289f943bdd9d0`
- New image payload manifest SHA-256: `ef64427925e5c0eb92a3a8f79b0139dd23f14428b4bec79ed1adf8a81a56fa75`

## 구현·검증

| 항목 | 실제 결과 |
| --- | --- |
| OAuth 2 offline Refresh Token | 독립 실행 경로 연결 완료 |
| 만료 전 갱신·단일 401 갱신 재시도 | CPU 모의 검증 PASS |
| 갱신 실패 시 다음 장면 시작 차단 | 기존 production coordinator의 실제 분기 + 모의 하드웨어 I/O로 PASS |
| 분리된 웹·작업·장면 coordinator·시작 복구 | 같은 인증 공급자 재연결, CPU PASS |
| App Folder·metadata scope | 구현 및 CPU 요청 계약 PASS; 실제 계정 검증 미실행 |
| 새 CPU 집중 테스트 | 49/49 PASS, FAIL 0, SKIP 0 |
| Host packaging 검사 | 12/12 PASS |
| 기존 FFmpeg 체크포인트·완료 캐시 복구 | 집중 회귀 2/2 PASS, 합성 CPU 미디어 |
| 별도 image entry CLI | 컨테이너에서 manifest 검증 및 `cli --help` PASS |
| 기존 FINAL·Candidate·렌더러·카메라·전선 | 변경 0; 부모 재귀 hash 검사 빌드 전후 및 독립 pull 동일 |
| 기존 의존성 | system Python inventory 및 기존 isolated venv의 169 파일 동일 |
| Secret Scan | 기본 gitleaks v8.24.3: findings 0 |
| Required temp-only implementation files | 0 |
| GPU·유료 실행·FINAL 승격 | 실행하지 않음 |

기존 백업·암호화·Scene JSON·완료 장면 저장·복구를 새로 구현하지 않았다. 새 계층은 기존 정확한 DropboxStore 클래스와 Vault, 백업 barrier, fresh-root restore, 승인 및 claim 검사를 재사용한다. 기존 Access Token Secret은 삭제하지 않으며 새 offline 프로필에서는 사용하지 않는다.

## 실제 Dropbox 검증 상태

`runs/39100005538-1/pull.json`의 실제 결과:

```json
{
  "status": "BLOCKED",
  "reasonCode": "OFFLINE_EXTERNAL_SECRETS_NOT_BOUND",
  "credentialsAvailable": false,
  "offlineTokenRefreshVerified": false,
  "metadataReadVerified": false,
  "externalStorageRecoveryVerified": false,
  "gpuExecuted": false
}
```

무료 CI의 기술적 성공은 실제 계정 백업·복구 성공을 뜻하지 않는다. 인증 입력 네 개 중 하나 이상이 Actions에 연결되지 않아 실제 Dropbox 요청은 시작하지 않았다. Secret 값이나 누락된 특정 Secret의 값을 조회·추측하지 않았다. 이 상태에서 유료 GPU 실행은 차단을 유지한다.

## 사용자가 할 설정

1. Dropbox App Console → 해당 App Folder 앱 → **Permissions** → `files.content.read`, `files.content.write`, `files.metadata.read` → **Submit**.
2. [설정 안내](README.md)의 무료 CPU consent helper로 **offline** 동의를 수행한다. **Generated access token → Generate**로 만든 단기 토큰을 Refresh Token으로 사용하지 않는다.
3. GitHub → 저장소 **Settings → Secrets and variables → Actions**에서 기존 `WORLD_ENGINE_STUDIO_BACKUP_KEY`는 그대로 유지하고 다음 실제 앱 자격증명을 Secret으로 등록한다:
   - `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY`
   - `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET`
   - `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN`
4. **Actions → WORLD ENGINE Studio Dropbox offline token candidate → Run workflow**, 위 브랜치를 선택한다. 실제 refresh·metadata·암호화 업로드·다운로드·fresh restore의 `externalDurability.status=PASS`를 먼저 확보한다.

백업 경로는 API 기준 `/WORLD_ENGINE_STUDIO_BACKUPS_V1`로 유지한다. Dropbox 화면에서는 `Apps/<앱 폴더>/WORLD_ENGINE_STUDIO_BACKUPS_V1`이다. 키·Refresh Token을 `/world-storage`·Git·채팅에 넣지 않는다. 올바른 Secret 연결 후 기존 체크포인트에서 복구하되 새 운영 승인 없이 GPU를 재시작하지 않는다.

## 판정

`DROPBOX_OFFLINE_TOKEN_CPU_VERIFIED`

`USER_CONFIGURATION_REQUIRED`

다음 허용 단계는 사용자 Secret 설정 후 무료 실제 Dropbox 백업·복구 검증이다. 실제 gCube 컨테이너 재시작·NVIDIA 렌더링·영상 품질은 검증하지 않았다. 이번 작업은 여기에서 중단한다.
