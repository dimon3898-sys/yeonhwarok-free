# 게시 커밋의 새 의존성 설치 검증

GitHub main에서 확인한 커밋 **365cdc488dd33765e39f5767b08203a952c17ee6**의 전체 Git archive를 새 체크아웃에 풀고, 수정하지 않은 `bash tools/setup_cloud.sh`를 처음 실행해 **설치 및 157개 회귀 PASS**를 확인했습니다. 같은 Linux 머신의 새 의존성 설치 검증이며 새로운 OS/클라우드나 실제 휴대폰 검증은 아닙니다.

| 실제 실행 | 결과 |
|---|---|
| 설치 명령 | `bash tools/setup_cloud.sh`, installer 수정 없음, exit code 0 |
| 설치·검사 명령 wall | **682.586762초** |
| 포함된 unittest | **157개 PASS, 646.071초** |
| 새 체크아웃의 tracked 파일 | 545개, 실행 전후 내용 SHA·전체 mode 변경 0 |
| 원래 workspace tracked 파일 | 545개, 실행 전후 내용 SHA·전체 mode 변경 0 |
| 의존성 초기 상태 | venv/Three.js node_modules/eSpeak 실행 파일 없음; runtime 디렉터리에는 tracked 출처 metadata만 존재 |
| Python 의존성 | 새 `.venv`에서 로드, `pip check` PASS, 시스템 site-packages 상속 없음 |
| JavaScript 의존성 | 새 체크아웃의 Three.js 0.170.0·Playwright 1.62.1에서 로드 |

`wall`은 setup 명령 한 번의 실제 실행 시간이며 646.071초 unittest를 포함합니다. 두 값을 더해 총시간으로 계산하지 않습니다. 기록된 시작은 2026-10-04 22:31:12 UTC, setup 종료는 22:42:35 UTC입니다. 이 실행 중 기존 B75 v002 생산 렌더는 별도로 진행됐습니다.

두 사전 wrapper는 **설치를 실행하기 전에** 중단됐습니다. 첫 wrapper는 원래 worktree의 0600 권한과 Git archive의 0644 정규화를 소스 변경으로 오판했습니다. 교정은 내용 SHA·Git 실행 비트를 비교하고 각각의 자체 baseline에서는 전체 mode를 보존하는 방식입니다. 두 번째 wrapper는 tracked `tools/runtime/SOURCES.json`만 있는 디렉터리를 설치된 runtime으로 오판했습니다. 실제 eSpeak 실행 파일의 부재를 확인하도록 교정했으며, 두 경우 모두 installer 실행 0·소스 변경 0입니다. 따라서 r03은 같은 의존성 없는 체크아웃에서 실행한 **최초 실제 설치**이고 설치 실패를 반복해 성공시킨 결과가 아닙니다.

원본 `REPORT.json`/`PROBE_VERIFICATION.json`의 `system_site_packages=true`는 `include-system-site-packages = false`가 있는지를 검사한 boolean에 반대 이름을 붙인 **메타데이터 표현 오류**입니다. 두 원본 파일은 그대로 보존했습니다. [PYVENV_METADATA_CORRECTION.json](PYVENV_METADATA_CORRECTION.json)은 정확한 cfg 바이트/SHA, 새 Python의 site/sys.path 및 module origin을 읽기 전용으로 다시 확인해 **system_site_packages_enabled=false·외부 site-packages 0·모든 대상 dependency가 새 venv**임을 기록합니다. 이 정정으로 installer/테스트를 재실행하거나 생산 worker를 변경하지 않았습니다.

Python/node/Chromium/FFmpeg 등의 시스템 실행 파일은 제공된 같은 Linux 환경을 사용했습니다. 기존 proxy·CA 신뢰를 유지하고 새 venv/node_modules에 의존성을 설치했습니다. 새 클라우드 세션의 인증·OS 설치, GPU 렌더, 75초 최종 MP4/QC/벤치마크, 공개 앱이나 물리 휴대폰을 검증한 증거가 아닙니다. GitHub 공개 다운로드 검증도 선택된 코드 파일의 HTTP 200·내용 SHA에 관한 것이며 공개 앱 배포를 뜻하지 않습니다.

검증 근거:

- [REPORT.json](REPORT.json), [SETUP_EXECUTION.json](SETUP_EXECUTION.json), [PROBE_VERIFICATION.json](PROBE_VERIFICATION.json)
- [FRESH_INITIAL_STATE_R03.json](FRESH_INITIAL_STATE_R03.json), [PYVENV_METADATA_CORRECTION.json](PYVENV_METADATA_CORRECTION.json)
- [TRACKED_SHA_BEFORE_R03.json](TRACKED_SHA_BEFORE_R03.json), [TRACKED_SHA_AFTER_R03.json](TRACKED_SHA_AFTER_R03.json)
- [첫 사전 guard 교정](PREINSTALL_GUARD_CORRECTION.json), [runtime metadata guard 교정](PREINSTALL_METADATA_GUARD_CORRECTION.json)
- [GITHUB_SOURCE_VERIFICATION.json](GITHUB_SOURCE_VERIFICATION.json), [민감 URL 정보를 제거한 실제 setup 로그](setup.sanitized_r03.log)

원본 private 로그·실행 중 프로젝트 상태·`/tmp` checkout·설치된 의존성/runtime 파일은 게시 자료에 포함하지 않습니다. 원본 Git 이력과 MASTER V1/V2/V3 파일은 변경하지 않았습니다.
