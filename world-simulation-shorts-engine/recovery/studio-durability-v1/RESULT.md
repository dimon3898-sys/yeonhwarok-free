# Studio data-loss prevention — implementation result

Status: **CPU_IMPLEMENTED_EXTERNAL_RECOVERY_PENDING**.

Branch: `development/studio-durability-v1-20261018`.
Runtime source: `6d7d4ce061acefbfa0442828f2ed858e3e8dccf2`.

## 구현 및 검증

- 실제 Scene JSON·SFX 설정을 작업 시작 전에 체크포인트 저장합니다.
- 완료된 장면 MP4와 검증된 재사용 캐시를 자동으로 암호화 백업합니다.
- 전송 후 원격 readback·해시·암호 인증·복구 receipt 게시가 끝나야 다음 장면으로 진행합니다.
- 저장 실패 시 첫 worker 생성 또는 다음 장면을 차단합니다.
- 새 private root 복구 및 명시적 컨테이너 시작 시 복구를 제공합니다. 복구 자체로 GPU 작업을 시작하지 않습니다.
- 실제 CPU MP4 2개를 백업하고 원본 fixture private state를 제거한 뒤 복구했습니다. 기존 coordinator가 복구된 2개를 재사용하고 누락된 1개만 처리했습니다. 이 검사는 명시적인 TEST_ONLY이며 NVIDIA 검증이 아닙니다.
- 무료 CI의 실제 후보 컨테이너 UID/GID 1000에서 **77 tests / 0 fail / 0 error / 0 skip**.
- Secret Scan 0건. 기존 private-root·관리자 인증·Origin·CSRF·GPU admission·비용/시간 승인·claim 보호를 유지합니다.
- 기존 FINAL·렌더러·카메라·전선 변경 0건. 기존 이미지·데이터·claim 삭제 0건. Required temp-only 0.

## 저장 위치

- 운영 상태·캐시는 기존 private root 아래 `production`에 유지합니다. 기본값은 `/var/lib/world-engine-private/engine/production-studio-mvp-v1/production`입니다.
- 기존 영상 결과 내보내기는 `/world-storage`를 그대로 사용합니다.
- 복구용 백업은 Dropbox API의 `/WORLD_ENGINE_STUDIO_BACKUPS_V1`에 불투명한 암호화 object ID로 보존합니다. `receipts/`에는 암호 인증된 발견용 목록을 둡니다.
- `/world-storage`를 Studio private root로 바꾸지 않았습니다.
- Scene·오디오·이미지·소스 해시를 확인하고 새 승인 후에만 미완료 장면을 처리합니다. 이전 승인·정책·세션·활성 claim·PID는 복구하지 않습니다.

## 실제 외부 저장 검증 — 아직 BLOCKED

독립 CI의 실제 결과: `DURABILITY_EXTERNAL_SECRETS_NOT_BOUND`.
백업용 Repository Secret 두 개가 해당 검사에 연결되지 않아 실제 Dropbox 업로드·다운로드·새 private root 복구는 실행하지 못했습니다.
CPU/모의 검사와 실제 외부 저장 성공을 구분했습니다. 실제 외부 복구 증명 없이는 이 실행 경로가 제작을 허용하지 않습니다.

사용자에게 필요한 조치:

1. 승인된 Secret 저장소에 별도 보관한 복구 키를 Repository Secret `WORLD_ENGINE_STUDIO_BACKUP_KEY`로 연결합니다. 형식은 32바이트 난수의 canonical URL-safe base64입니다. 키를 채팅·소스·이미지에 넣지 않습니다.
2. 승인된 Dropbox API credential을 `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_TOKEN`으로 연결합니다. 기존 gCube token과 다른 credential입니다.
3. CI run `39097611749`의 **verify-pull job만** 무료 재실행합니다. 이미지 재빌드 없이 실제 외부 복구 검사와 proof ID 발급을 수행할 수 있습니다.
4. 성공 후 gCube에 아래 설정과 Secret을 적용합니다. 이 작업에서는 gCube 배포·렌더링을 실행하지 않았습니다.

## gCube 설정

- 후보 이미지: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:54e7f67627a14755117a3f232c03785f9ceac4ab490a33e8f5834fb9fe114b9b`
- 고유 tag: `studio-durability-v1-f983adc-39097611749-1`
- `WORLD_ENGINE_STUDIO_BACKUP_MODE=dropbox-api`
- `WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_PREFIX=/WORLD_ENGINE_STUDIO_BACKUPS_V1`
- `WORLD_ENGINE_STUDIO_BACKUP_PROOF_ID`: 실제 무료 검사에서 발급된 값만 사용합니다.
- 위 두 백업 Secret을 같은 이름으로 연결합니다. 기존 소유자·HTTPS·실제 이미지 digest·운영 요금/비용/시간 정책은 유지합니다.
- `WORLD_ENGINE_STUDIO_STATE_ROOT`는 기존 private 기본값을 유지합니다. `/world-storage`로 변경하지 않습니다.
- 명시적 복구에만 `WORLD_ENGINE_STUDIO_RESTORE_CHECKPOINT_ID`, `WORLD_ENGINE_STUDIO_RESTORE_PLAN_SHA256` 및 새 private local STATE_ROOT를 사용합니다. 같은 immutable image가 필요합니다. [README](README.md)에 전체 절차가 있습니다.

기존 Dropbox 계정을 사용할 수 있으므로 추가 PVC 자체가 필수는 아닙니다. 다만 승인된 API 접근·충분한 저장 용량·컨테이너 밖 복구 키 보관이 필요합니다.

## 남은 경계

- 실제 Dropbox 외부 영구 저장·복구 증명: BLOCKED, Secret 연결 필요.
- 실제 gCube 컨테이너 재시작 및 복구: 미실행.
- 긴 cold restore: CPU 제한 600초. 새 이미지 Docker health start period는 20분입니다. gCube의 독립 startup probe가 이를 허용하는지는 미확인이므로 긴 복구 전에 확인해야 합니다.
- 카탈로그 목록은 기본 128개, 최대 256개로 제한됩니다. 제한 초과 시 fail-closed이며, 이미 확인한 checkpoint ID의 직접 복구는 별도 가능합니다.
- Dropbox token 만료·quota·네트워크 실패는 저장 실패로 처리하고 다음 장면을 중단합니다.
- 기존 미백업 80초 작업의 유실 파일을 되살렸다는 의미는 아닙니다. 새 작업부터 적용할 후보입니다.
- 유료 GPU 실행·실제 NVIDIA·80초 영상 품질·FINAL 승격은 수행하거나 PASS로 선언하지 않았습니다.

## 이미지 및 오류 복구 근거

[무료 CI와 독립 pull](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39097611749).
전체 digest·source/asset 보호·테스트·외부 차단 결과는 `IMAGE.json`, `PROTECTION.json`, `runs/39097611749-1/`에 보존했습니다.

첫 후보 빌드는 기존 native Python에 pip가 없어 중단됐습니다. 고정 digest의 공식 Python builder에서만 wheel을 준비해 독립 venv로 복사하도록 수정했습니다. 기존 Python/GDAL 의존성은 변경하지 않았고, 새 이미지와 독립 pull 양쪽에서 기존 의존성·보호 파일 해시 동일성을 검증했습니다. 이전 실패 이미지·태그는 덮어쓰지 않았습니다.

검수 대기. 실제 외부 복구 검증 전에는 유료 GPU를 실행하지 않습니다.
