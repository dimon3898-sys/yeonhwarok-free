# 이번 80초 실행의 백업 없는 Studio 설정

상태: **NO_BACKUP_80S_PREFLIGHT_READY_COST_APPROVAL_REQUIRED**.

사용자는 이번 실행에서 새로 생성되는 private Scene·장면 캐시·체크포인트가 유실될 위험을 수용했다. 그 범위에서 기존에 지원하던 정상 Studio 실행 경로를 재사용한다. 유료 GPU 배포·렌더링·기존 워크로드 중지·Secret 변경은 수행하지 않았다. 새 MP4, 다운로드 URL, SHA는 아직 생성되지 않았다. 영상 품질 PASS나 FINAL 승격이 아니다.

## 선택한 기존 실행 경로

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:studio-proxy-v1-4589328-39085567166-1
```

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da
```

이는 Dropbox API durability가 추가되기 전의 보존된 Studio 이미지다. 새로운 durability 이미지의 필수 백업 검사를 비활성화하는 방식이 아니다. 최신 이미지에는 지원되는 `BACKUP_MODE=off` 설정이 없으므로 그런 변수를 만들거나 필수 검사를 우회하지 않는다. 기존 Dropbox 이미지·기능·Secret·암호화 키·백업 데이터는 그대로 보존한다.

기존 `studio-https-proxy-fix-v1/IMAGE.json`, 원격 build/pull 증거를 재사용했다. 이번 공개 레지스트리 GET에서 태그와 고정 digest 모두 HTTP200이고 같은 manifest/config SHA를 가리킨다. source commit은 `83bf1e0c7fc5955d9ff1d06441264f4c0d5a702b`, config digest는 `sha256:2cf8b7fbf188da61d475299b580064bc308481a2a0d2b9dcce49a8796fe825f4`다. 신규 이미지 빌드·push·중복 대용량 pull은 하지 않았다.

기존의 관리자 인증·Origin·CSRF·이미지/소스 SHA·GPU admission·비용 승인·중복 claim·private POSIX 권한 검사와 공유 저장소 쓰기/재읽기 검사를 유지한다. ASTRA·Camera·Area·Flow·Event·Planner·전선·표식·인코딩·SFX는 기존 코드 그대로다.

## 저장본 및 CPU 확인

- 작업 시작 remote HEAD: `development/gcube-secret-handoff-review-20261018`의 `053f122e8062328133eec2c49001e39c57ad0c8e`.
- 보존된 Dropbox GPU 후보: `development/dropbox-gpu-production-20261018`의 `646a79a2ae98ebb4b785f3371946ddb1ff0d591f`.
- 기존 감사의 필수 Git 객체 **422/422 일치**, 누락0·변경0. 원본 자료 재다운로드·재파싱·중복 백업 없음. `PROTECTION.json` 참조.
- 기존 실제 Dropbox 업로드/다운로드/복구 proof `08398705cd4ffb90a7f68a26ee6f65a121c5efa62ad4f854c1aa50ea371b55a7`는 보존하며 이번 실행의 백업 보증으로 재해석하지 않는다.
- 기존 80초 plan SHA: `2632f9106962bb126bf333422bce2be5094d4af7b25c5701acdf4455a2829dc6`. 1080×1920·30fps·2,400프레임·12개 연속 장면을 확인했다. 기존 역사 자료의 근사/미검증 제한도 그대로 유지한다.
- 집중 CPU **10/10 PASS**: 기존 두 승인 검증기의 14,400초 허용, 부족한 비용/만료/과도한 재시도/누락된 승인 거부, 기존 승인의 비확장, 12장면 체크포인트 순서, 저장 또는 재읽기 실패 시 다음 장면 차단. `FOCUSED_CHECKS.json` 참조.
- 체크포인트 순서 검사는 원본 coordinator의 명시적 `TEST_ONLY` seam을 사용했다. 실제 MP4 내보내기, 외부 Dropbox 동기화, NVIDIA 렌더링 검증이 아니다. 기존 실제 미디어 합성/내보내기 및 이미지 독립 pull 증거를 재사용했다.

## 240분과 비용 승인

기존 Studio/controller/coordinator가 이미 `maxWallSeconds:14400`을 지원한다. 신규 승인 작업에만 적용되며 실패한 과거 작업의 승인·claim을 연장하거나 초기화하지 않는다. 준비·렌더링·SFX·합성·내보내기·검증이 같은 전체 기한 안에 포함된다. 승인 만료시각이 더 이르면 먼저 종료한다. 기존 private 정책과 다른 값을 덮어쓰는 것도 허용되지 않는다.

이번 재제작에는 기존 지원 API인 `WORLD_ENGINE_STUDIO_STATE_ROOT=/var/lib/world-engine-private/engine/studio-no-backup-80s-v1`로 별도 private 상태를 선택한다. 기존 image의 상위 디렉터리와 원본 0700/0600·UID1000 생성/검증 함수를 사용한다. 예전 상태·정책·작업·claim을 건드리지 않는다. 새 leaf가 이미 사용되어 다른 정책이 존재하면 차단하며 덮어쓰지 않는다. 동일 관리자 환경변수를 재사용하고 실제 HTTPS는 새 상태에 인증 후 등록해야 한다. 이는 데이터의 영구 보존 경로가 아니다.

무료 표준 GitHub Actions [39122321947](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39122321947)에서 기존 승인된 Secret으로 공식 요금 catalogue를 GET **1회** 했다. 2026-10-18T11:12:54.982829+00:00, HTTP200:

| RTX4080SUPER16GB | 시간당 catalogue | 4시간 산술 범위 | API availability |
| --- | --- | --- | --- |
| tier2 | 252–360 KRW | 1,008–1,440 KRW | false |
| tier3 | 154–220 KRW | 616–880 KRW | false |

이는 실제 선택 노드의 고정 견적이나 사용자 비용 승인이 아니다. 세금·반올림·저장소·네트워크·배포/대기 시간을 확정하지 않는다. 실제 노드의 요금, 최대 승인 금액, 승인 만료시각은 **미확정**이다. 현재 가용성도 해당 조회에서 false이므로 실행 전에 다시 실제 화면을 확인해야 한다. 해당 JSON/원격 commit/SHA는 `PRICING_REFERENCE.json`에 연결했다.

애플리케이션의 240분 타임아웃은 gCube 워크로드 정지나 과금 종료 기능이 아니다. 사용자가 결과 보존을 확인하고 gCube에서 수동 중지해야 하며, 워크로드 종료 시각까지의 비용은 별도다. 미승인 유료 실행·재시도는 하지 않는다.

## 이미 지원되는 장면별 내보내기

원본 `universal-auto-video-v2/orchestrator.py`는 완료 장면마다 `delivery.export_scene_checkpoint`를 호출하고 공유 마운트의 SHA 재읽기 성공 후에만 `SCENE_COMPLETE` 처리 및 다음 장면을 진행한다.

```text
/world-storage/world-engine-export-<실행ID>/scene-recovery-<고유ID>/segment.mp4
/world-storage/world-engine-export-<실행ID>/scene-recovery-<고유ID>/SHA256SUMS
```

최종 Studio 출력은 같은 실행 폴더 아래 `studio-<고유ID>/WORLD_ENGINE_STUDIO_VIDEO.mp4`다. 별도 환경변수·백업 모듈 개발 없이 기존 경로를 사용한다. 마운트 접근 실패/재읽기 실패는 다음 장면을 차단한다.

이 마운트 복사본은 private Scene JSON·캐시·신뢰 앵커를 영구 보존하지 않는다. private 상태를 잃으면 공유 MP4+SHA만으로 GPU provenance를 신뢰하거나 자동 복구할 수 없다. 마운트 저장/재읽기 성공은 Dropbox 외부 동기화·휴대폰 다운로드 성공과 다르다.

실제 승인된 새 실행 이후에는 기존 파이프라인으로 80초 MP4 전체 디코딩·2,400프레임·규격·SFX·SHA를 확인하고, 실제 다운로드 URL에서 HTTP200과 원본 SHA 일치를 검증해야 한다. 아직 실행하지 않은 결과를 PASS로 기록하지 않는다.

## 다음 실행 지점

`GCUBE_SETTINGS.md`의 기존 이미지와 지원 설정을 사용한다. 실제 선택 노드의 요금·승인 비용·만료시각을 확정하기 전에는 배포/제작하지 않는다. 기존 owner code와 모든 Secret을 그대로 유지하고, 새 Studio 작업만 명시적으로 시작한다. 과거 정책·작업·claim·완성 파일 삭제는 필요하지 않다.

작업 브랜치: `development/studio-no-backup-80s-20261018`. 변경 범위는 이 새 evidence/test namespace뿐이다. 커밋 자체의 SHA는 Git 이력으로 확인한다. Required temp-only files0. 실제 GPU/영상 검수 및 사용자 비용 승인을 기다린다.
