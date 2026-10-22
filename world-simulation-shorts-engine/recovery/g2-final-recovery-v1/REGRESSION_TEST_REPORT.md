# REGRESSION_TEST_REPORT

기준 `3913ad8e90885c769cdccc91f396072d83e356f2`, 새 브랜치 `development/g2-final-recovery-20261022`. 기존 파일·기존 검사 기준을 바꾸지 않았다. 기술 검증과 사용자 영상 품질 승인은 별개다.

## 실행한 CPU 검사

| 검사 | 개수 | 결과 |
|---|---:|---|
| 기존 source Python |35|PASS|
| 기존 Native preparation / Camera numerics / Source geometry |8+6+3|PASS|
| 이전 G2 복구 Python / Capture / Native Plan |37+8+4|PASS|
| 이번 Studio·입력 계약 / 5지역 데이터 |12+8|PASS|
| 이번 Capture 조정 계층 / Layout 확장 |11+11|PASS|
| 합계 |기존 101 + 추가 42|PASS, skip 0|

실제 명령·stdout/stderr·종료 코드·시간은 `reports/CPU_REGRESSION_RESULTS.json`에 있다. 실행 진입점:

```text
PYTHONDONTWRITEBYTECODE=1 python -B world-simulation-shorts-engine/recovery/g2-final-recovery-v1/tools/run_cpu_regressions.py
```

첫 집계 실행은 실제 기존 101개 및 추가 검사의 종료 코드가 모두 0이었지만, 마지막 Layout 검사의 JSON 요약을 TAP 형식으로만 읽어 `tests:null`로 중단됐다. 해당 실패 로그를 `CPU_REGRESSION_HARNESS_FAILURE.json`에 그대로 보존했다. 테스트·판정 기준은 변경하지 않고 집계기에서 명시적인 JSON 요약을 읽도록 고쳤다. 이미 통과한 기존 101개는 원문 실행 로그 SHA와 함께 재사용하고 추가 검사만 다시 실행했다. 실제 재개 명령:

```text
PYTHONDONTWRITEBYTECODE=1 python -B world-simulation-shorts-engine/recovery/g2-final-recovery-v1/tools/run_cpu_regressions.py --reuse-preserved-report <new-namespace>/reports/CPU_REGRESSION_HARNESS_FAILURE.json
```

## 실제 5지역 draw/readPixels

동일한 native renderer·Layout 확장·Camera V5·Area V3를 사용한다. 원본 투영·지리 앵커·폰트·8px 경계 보호를 유지한다. 지역 선택은 데이터 fixture에만 있으며 알고리즘에 국가 예외를 넣지 않았다.

| 지역·지형 | 실제 draw | 현재 카메라별 선택 gap | 결과 |
|---|---:|---|---|
| Namibia 사막·해안 |4|18/18/18/18|PASS|
| Nepal 산악 |4|50/66/50/66|PASS|
| 한반도 육지·해안 |4|34/50/34/50|PASS|
| Germany·중부 유럽 |4|18/18/18/18|PASS|
| Chile·남미 산악/해안 |4|18/34/18/34|PASS|

각 입력은 local frame 0/1/2/1, 실제 V5 source frame 0/54/0의 이동·줌을 검사했다. 네 번째 draw는 동일 local frame 1의 결정성 확인이다. 모든 지역의 GL 오류 0, 실제 glyph/카메라 기반 Layout 유효, 충돌·화면 이탈 0, 지리 앵커 투영 오차 1e-6px 미만, 동일 프레임 raw SHA 일치, NE1 자산 HTTP 200·SHA 일치와 source-native viewport coverage를 확인했다. 15개 source field의 영역 밖·누락·중복 면적은 모두 0이다.

```text
PYTHONDONTWRITEBYTECODE=1 python -B world-simulation-shorts-engine/recovery/g2-final-recovery-v1/tools/build_probe_packages.py --output-root /workspace/g2-final-probe-packages-20261022
PYTHONDONTWRITEBYTECODE=1 python -B world-simulation-shorts-engine/recovery/g2-final-recovery-v1/tools/run_actual_regions.py
```

개별 실제 Node 명령과 입력 SHA는 `reports/ACTUAL_REGIONS.json`, 상세 증거는 `reports/ACTUAL_REGION_*.json`에 있다. 5개 중간 시점의 실제 PNG를 contact sheet로 배열해 육안 확인했다. 새 지도는 고정된 Public Domain NE1 원본의 native RGB crop이며 데이터 보간·블러·경계 은폐를 하지 않았다.

Chile의 첫 **입력 준비**에서 새 시작 bbox가 원본 Easter Island를 포함하지 않아 V5 입장이 거부됐다. 실패는 `GENERIC_REGIONS_INITIAL_PREPARATION_FAILURE.json`에 남겼다. 원본 지오메트리에 맞게 이 새 Scene의 시작 범위만 넓힌 뒤 새 디렉터리에서 입력을 준비했다. 원래 Chile 자료를 빼거나 임계값·렌더러를 바꾸지 않았다. 실제 5지역 draw 검사는 수정된 입력으로 한 번씩 실행했고 모두 통과했다.

## 범위 제한

기존 source runtime은 native `LOCATION_LABEL`의 **입장 Layout**을 검사하지만 실제 화면에는 native marker와 `SYNTHETIC DEMO` caption만 그린다. 이번 수정은 활성 location 역할·실제 폰트 측정·기존 충돌 검사를 유지한다. 측정한 `ZONE` 위치가 실제 화면에 그려졌다고 주장하지 않는다. 해당 진단은 `nativeLocationRendered:false`로 명시했다.

SwiftShader는 무료 CPU 소프트웨어 렌더링이다. NVIDIA·유료 GPU·성능·모바일 실기기 재생·사용자 최종 품질 승인은 이 결과에 포함되지 않는다. G3 역사 제작·80초·FINAL 승격은 실행하지 않는다.
