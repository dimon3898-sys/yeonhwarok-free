# CHANGE_MANIFEST

기준은 `0069e9af1c0888843289d312d86bad29ac26007e`, 작업 브랜치는 `development/g2-renderer-recovery-20261022`다. 모든 추가·변경은 새 `recovery/g2-renderer-recovery-v1/` 안에서만 수행했다. 기존 파일을 삭제하거나 덮어쓰지 않았다.

## 새 파일과 이유

| 파일·그룹 | 이유 |
|---|---|
| `terrain_style.py`, `fixtures/MAP_STYLE.json` | 같은 NE1 지도 스타일 선택, CRS·native 해상도·실제 지원 범위·SHA·카메라 여유 검증 |
| `assets/terrain/*.png`, `source-provenance/*`, style receipts | 기존 출처의 Public Domain NE1 원본에서 보간 없이 추출한 실제 RGB window와 좌표·권리 증거 |
| `tools/build_terrain_assets.py`, `tools/prepare_recovery_plan.mjs` | 원본 RGB 보존 crop과 기존 Scale compiler를 사용한 자산 메타데이터 갱신 |
| `tools/build_recovery_fixture.py`, `fixtures/SOURCE_BUNDLE.zip` | 기존 Scene·field·geometry를 보존하며 Native Plan의 지도 소스만 명시적으로 재연결 |
| `studio_controller.py`, `studio_service.py`, `software_worker.py`, `source_contract.py`, `tools/run_studio_recovery.py` | 기존 인증·CSRF·claim·worker를 호출하는 별도 복구 프로필. 새 입력/자산/실행 파일의 SHA 검증과 단계 게이트 추가 |
| `capture_recovery.mjs`, `capture_source.mjs`, `tools/probe_recovery.mjs` | 기존 capture의 고정 경로와 새 자산 경로를 분리하는 실행 조정 계층. 원래 native runtime과 렌더러를 그대로 제공 |
| `tools/build_generic_probes.py`, generic fixtures | Namibia 사막·해안과 Nepal 산악의 범용 합성 입력. 사실·점령 데이터로 표시하지 않음 |
| `tests/*`, `tools/audit_baseline.py`, `tools/audit_recovery_video.py` | 경계·좌표·입력·소스·결정성·기존 계약과 실제 프레임을 검사. 새 영상 감사 도구는 준비만 했으며 새 MP4에 실행하지 않음 |
| `tools/check_protection.py` | 작업 전 확보한 307개 SHA 및 기존 namespace·cache 보존 검사 |
| `reports/*`, 문서, `public-review/*.png` | 원인·실행 로그·실패·실제 부분 프레임과 단계 중단 근거 보존 |

파일별 bytes·SHA는 `reports/CHANGE_FILES.csv`에 기록한다. 최종 다운로드 파일은 `SHA256SUMS`로 검증한다. 목록·해시 파일 자체의 재귀 해시는 만들지 않는다.

## 보호 범위

- 원래 GPU/native renderer·shader·Camera V5·Area V3·Flow V2·Event V1·GIS·Layout·Marker·Planner 파일 변경 0건.
- 기존 G1·기존 G2 namespace 143개 파일의 원본 bytes 유지.
- 작업 전 확보한 보호 파일 307개 원본 SHA 유지. 기준 manifest SHA: `cc09c9dca0262b800387df1d27e6ac91d0fd18d2c5c582862cc600baf843ce3e`.
- 기존 cache/작업 223개 파일의 size·mtime·inode·mode 유지. 인증 파일 내용은 보고서에 복사하지 않음.
- 새 native runtime 구현이나 렌더러 복제 없음. 기존 runtime 파일을 byte 동일하게 사용한다. 새 코드는 실행 조정·입력 계약·실제 지도 소스 처리에 한정된다.
- 기존 영상·claim·완료 기록·Secret 삭제, 기존 gCube 변경, 유료 실행, FINAL 승격 없음.

보존 검사는 `reports/PROTECTION_FINAL.json`에 있다. Secret Scan은 명시된 강한 토큰/키 패턴 검사이며 계정 전체나 미공개 파일의 포괄적 보안 감사라고 주장하지 않는다.

## 저장 및 중단 지점

PHASE 0은 `35347aa15de5649283f0e76d626e4c835521fe28`, 소스·연결 구현은 `da58b4f70fe6826152c33e2a4d90556f1ab6c340`에 commit/push 후 원격 일치를 확인했다. 이 보고·실패 증거도 별도 commit/push한다.

PHASE 2에서 Nepal Layout 초기화가 실패했다. 그 이후 코드를 고치거나 검사 기준을 바꾸거나 다시 렌더링하지 않았다. PHASE 3의 `G2_RECOVERY_DEMO_6S.mp4`는 생성하지 않았다. `G2 NEEDS_REWORK`, `G3 BLOCKED`에서 중단한다.

필수 재개 입력·실제 부분 PNG·보고서는 Git에 보존한다. 임시 private 컴파일 입력은 저장된 fixture에서 다시 만들 수 있다. 700MB 원본 TIFF는 재배포하지 않으며 고정 출처 URL·SHA·추출된 실제 PNG와 좌표 receipt를 보존한다. 삭제되면 새 데이터 조사 없이 고정 원본을 다시 취득할 수 있다. 기존 미완료 Studio job이나 GPU 환경은 이번 작업에 의존하지 않는다.
