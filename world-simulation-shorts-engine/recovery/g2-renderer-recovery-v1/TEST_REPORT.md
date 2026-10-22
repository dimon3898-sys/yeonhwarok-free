# TEST_REPORT — PHASE 2 FAIL

기존 52개와 신규 49개 CPU/계약 검사는 모두 통과했다. 실제 지역 렌더 검사에서 Nepal 초기화가 실패했으므로 PHASE 2 전체는 FAIL이다. 코드 PASS를 영상 품질 PASS로 취급하지 않는다.

| 검사 | 실행 수 | 결과 |
|---|---:|---|
| 기존 집중 검사 |52|PASS, skip 0|
| 새 지형/계약/좌표/감사 검사 |49|PASS, skip 0|
| 실제 main 원본 렌더 probe |4회, 3시점|PASS|
| Namibia 실제 원본 렌더 probe |4회, 3시점|PASS|
| Nepal 실제 원본 렌더 probe |0프레임|FAIL — 보호 Layout 검사|
| 새 Studio 180프레임 |0|BLOCKED — PHASE 2 미통과|

## 실제 실행 명령 및 로그

원문 stdout/stderr·종료 코드·시간은 reports/CPU_TEST_RESULTS.json에 저장했다. 기존 캐시 변경 방지를 위해 PYTHONDONTWRITEBYTECODE=1과 python -B를 사용했다.

```text
python -B -m unittest discover -s world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/tests -p test_*.py -v
```
결과: PASS, 35개, skip 0, exit 0, 15.816초.

```text
node world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/tests/test_native_preparation.mjs
```
결과: PASS, 8개, skip 0, exit 0, 0.490초.

```text
node world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/tests/test_camera_numerics.mjs
```
결과: PASS, 6개, skip 0, exit 0, 0.041초.

```text
node world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/tests/test_source_geometry_contract.mjs
```
결과: PASS, 3개, skip 0, exit 0, 0.038초.

```text
python -B -m unittest discover -s world-simulation-shorts-engine/recovery/g2-renderer-recovery-v1/tests -p test_*.py -v
```
결과: PASS, 37개, skip 0, exit 0, 1.292초.

```text
node world-simulation-shorts-engine/recovery/g2-renderer-recovery-v1/tests/test_capture_recovery.mjs
```
결과: PASS, 8개, skip 0, exit 0, 0.062초.

```text
node world-simulation-shorts-engine/recovery/g2-renderer-recovery-v1/tests/test_prepare_recovery_plan.mjs
```
결과: PASS, 4개, skip 0, exit 0, 0.433초.

## 실제 소프트웨어 렌더링 명령

기술 probe는 동일 capture_recovery.mjs의 동일 native runtime을 사용했다. 별도 이미지 합성 렌더러가 아니다. 명령의 --expected-sha256는 실제 private 입력 파일 SHA이며, 비밀값은 아니다. 입력에는 토큰·owner code·세션을 넣지 않았다.

```text
node tools/probe_recovery.mjs --plan=<SHA-bound private MAIN_PROBE_PACKAGE.json> --expected-sha256=c8c962eab4e6025034af90c5bf92e9bb854da7696be7011ef335990d1fad8459 --output-root=<new namespace>/captures/phase1-main-source-support --frames=0,90,179,90
node tools/probe_recovery.mjs --plan=<NAMIBIA_DESERT_COAST_PROBE_PACKAGE.json> --expected-sha256=3ae1c6f88ad020cb9b73cb108762a8d40e3d2e48b9abbd0f3c490a4b094c3e5d --output-root=<new namespace>/captures/phase2-namibia_desert_coast --frames=0,1,2,1
node tools/probe_recovery.mjs --plan=<NEPAL_HIMALAYA_PROBE_PACKAGE.json> --expected-sha256=2561b75494786d1c48ca19ef96eec721abb277694b81b202147f5b393af9dd08 --output-root=<new namespace>/captures/phase2-nepal_himalaya --frames=0,1,2,1
```

두 지역 입력의 좌표·source receipt·Native Plan·hash는 fixtures/GENERIC_PROBE_INPUTS.zip에 보존했다. 원본 필드와 원본 카메라 계산을 재사용했다. 실제 새 MP4, NVIDIA, 회전 지원, 모바일 실기기 재생 검증은 실행하지 않았다.
