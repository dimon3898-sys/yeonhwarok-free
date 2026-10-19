# 조건부 native 합성 슬롯 오류: CPU 재현과 최소 차단

현재 5초 결과의 고급 표현이 비어 있는 원인과 별개로, **미래의 source-valid scalar 선택이 사전검사를 통과하고 native draw에서 실패할 수 있는 연결 계약 불일치**를 확인했다. 현재 검증된 추가 scalar·국가별 unit source는 0개이고, 실제 Preview의 두 선택값은 `null`이다. 이 결함이 현재 null 선택 영상의 픽셀 품질 저하를 일으켰다고 주장하지 않는다.

## 고정된 실제 코드 근거

검증 기준 source commit은 `e23613195c356ad53874030f983a30a0e30d639f`이다. 기존 파일은 수정하지 않았다.

| 역할 | 실제 파일 | SHA-256 |
|---|---|---|
| 기존 27개 파일 manifest | `universal-overnight-v3/OVERNIGHT_FILES.json` | `ceca8be224e0b7e8ca73a429c7a36217d371fe09308d3829e9ff5b0d67a35fa7` |
| 기존 parent 55개 파일 manifest | `universal-integration-completion-v2/COMPLETION_FILES.json` | `99caa40a2c7566982f5c5502ce4d5ce95e35367dc5809c8e7013ca4e83c7b3e9` |
| native 정보 발행자 | `universal-integration-completion-v2/production_camera_bridge.mjs:25` | `41f79321ce2beb7c04a694bffabba9bce75f7096cad3f4c37c52d51ee2be08ab` |
| private frame context | `universal-integration-completion-v2/frame_context.mjs:9` | `2930b8777eff4a23afb97319986ee18eea42f2039ccf5b20a6c9a23c0559b86b` |
| 선택 기능 합성자 | `universal-overnight-v3/browser_adapter.mjs:30` | `df89ddc6f6d568d27c3fecf695a93821a5117631432458ae8f59075158fa9590` |
| 선택 기능 소비자 | `universal-overnight-v3/visual_extensions.mjs:138` | `770adb1f498c91ec772b1321b29cdcaee2d1d53cc243aa3917d0cda146e72666` |

기존 `runtime_bridge.py:33–43`의 `_visual_admission`은 검증된 source payload를 기존 JS compiler에 전달하고 `CPU_ADMITTED`를 확인한다. 이 단계에는 native producer capability 검사가 없다.

기존 producer는 `{frame, native: result, boundarySegments}`만 발행한다. 새 선택 합성자는 parent draw를 마친 뒤 다음 값을 읽는다.

- `internalBoundarySegments`: producer가 발행하지 않음. 선택 scalar의 모든 활성 프레임에서 필수.
- `actualTerrainSnapshot`: producer가 발행하지 않음. 지형 destination-light를 켠 frontier에서 동일 프레임의 실제 pre-territory texture가 필수.
- `nativeRoleCoverage`: producer가 발행하지 않음. outer gold domain 효과에서 실제 같은 프레임 coverage가 필수.
- scalar 전용 parent replacement slot: 현재 없음. 기존 geographic Area fill/front가 있는 프레임은 선택 scalar가 중복해서 덮어쓸 수 없으며 소비자가 명시적으로 거부한다.

이는 import 누락이 아니다. 기존 parent map/GIS/ASTRA/Area는 실제 호출된다. 없는 데이터를 빈 배열·가짜 texture·추정 role coverage로 채우면 안 된다.

## 재현 범위

`tests/test_native_capabilities.py::test_actual_original_cpu_compile_then_missing_native_context_failure`은 기존 실제 `compileTerritoryControlPlan`, `compileVisualExtensions`, `evaluateVisualExtensionsFrame`을 호출한다.

1. 기존 테스트 계약과 같은 범용 서·남반구 합성 scalar source를 만든다.
2. `allowSynthetic:true`는 이 CPU 테스트에만 사용한다. 역사 검증·production catalog 통과로 재분류하지 않는다.
3. 기존 compiler는 scalar binding을 생성한다.
4. 실제 producer가 제공하는 key에 맞춘 context로 평가하면 `OVERNIGHT_SCALAR_PARENT_COMPOSITION_SLOT_REQUIRED`가 발생한다.
5. CPU 테스트 context에 `internalBoundarySegments:[]`만 추가하면 순수 CPU 평가가 진행된다. 이것은 실제 native slot·해안·texture·GPU 픽셀 검증이 아니다.

이 재현은 현재 실제 production source가 scalar admission을 통과했다는 뜻이 아니다. 현재 catalog에는 해당 자료가 없어 원래의 source admission에서 이미 차단된다. 다만 source가 안전하게 추가되어도 current native producer의 구조적 불일치가 남는다는 점을 입증한다.

## 별도 namespace의 최소 수정

`render-path-reconciliation-v1/native_capabilities.py`만 추가했다.

- 기존 manifest 27개 및 parent 55개 파일 전체 무결성과 위 producer/compositor/consumer의 정확한 hash를 검증한다.
- source가 달라지면 자동으로 capability를 추정하지 않고 실패한다.
- Scene·프롬프트·환경변수에 capability map을 넣어 허용 상태를 주장할 수 없다.
- scalar 선택은 GPU 실행 전에 `RECONCILE_NATIVE_SCALAR_COMPOSITION_UNAVAILABLE`로 명확히 차단한다.
- null 선택은 기존 경로의 나머지 모든 사전검사로 진행한다.
- 국가별 unit 선택은 기존 source admission과 현재 프레임의 safe-area·충돌·layout 검사에 계속 위임한다. 자료가 없다는 사실을 숨기거나, unit native owner가 없다고 잘못 단정하지 않는다.
- 이 guard는 인증·역사·Scene·image·예산·GPU admission의 대체물이 아니며 항상 `renderAllowed:false`, `gpuVerified:false`를 기록한다.

기존 gate를 호출한 뒤 `guard_native_selection(request, source_admission=context['selectedVisualAdmission'])`을 실행하는 새 Studio 확장 경로에 연결한다. 기존 FINAL·engine·camera·Area·후보·영상·claim은 그대로 둔다.

## 검증 명령 및 한계

```text
python -B -m unittest discover -s world-simulation-shorts-engine/recovery/render-path-reconciliation-v1/tests -p test_native_capabilities.py -v
```

집중 검사 9개: 실제 보존 파일 27+55, null 유지, scalar 사전 차단, national 기존 owner 유지, source receipt 정합, capability 주입 거부, manifest/component 변경 실패, 실제 기존 CPU compiler의 late-failure 재현.

이 수정은 늦은 실패와 잘못된 활성화 기대를 예방한다. 고급 scalar·양측 점령색·국가별 역사 unit·reference 품질을 구현 완료 또는 적용 완료로 승격하지 않는다. 정상 null 선택 영상의 픽셀을 개선했다고 주장하지 않는다. 실제 NVIDIA GPU 검증은 수행하지 않았다.
