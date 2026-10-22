# ROOT_CAUSE_REPORT — Nepal 초기화 실패

기준 `3913ad8e90885c769cdccc91f396072d83e356f2`. 기존 실패 기록을 보존하고 코드·Native Plan·실제 font/asset 요청과 비교했다. PHASE A 판정은 **원인 확인 PASS**이며, 실제 수정 화면·영상 PASS와는 구분한다.

## 확정 원인

기존 입력은 스키마상 유효하지만 `location: true`인 측정 Layout을 선택한다. `ZONE` 라벨에는 marker 40px, gap 18px, 고정 36px 실제 글꼴이 적용된다. Layout 알고리즘은 이 gap에서 LEFT·RIGHT·ABOVE·BELOW 네 후보만 검사한다. Nepal의 좁은 실제 Primary 경계는 네 후보의 보호 상자와 모두 충돌한다. 안전 검사가 정확히 실패한 것이다.

Nepal 입력은 anchor `[84,28]`, final extent `[75,13,95,45]`다. 기존 frozen Layout 투영

```text
x = (longitude - west) / (east - west) * 1080
y = (north - latitude) / (north - south) * 1920
```

의 결과는 `[486,1020]`이며 실제 오류 기록과 일치한다. pinned font의 실제 ink는 95×27px이다. 후보 ink box는 다음과 같다.

| 후보 | x,y,w,h | 실제 결과 |
|---|---|---|
| LEFT | 353,1006.5,95,27 | Primary 8px clearance 충돌 |
| RIGHT | 524,1006.5,95,27 | 동일 |
| ABOVE | 438.5,955,95,27 | 동일 |
| BELOW | 438.5,1058,95,27 | 동일 |

safe area 위반과 glyph font 미확보는 없었다. 폰트 및 실제 NE1 PNG 자산은 HTTP 200·원본 SHA 일치를 기록했다. 이 초기화 실패의 원인을 타일 손상·UV·투영법·GPU 오류로 단정할 근거는 없다.

## 실제 호출 경로

1. `universal-source-pipeline-v2/tools/prepare_native.mjs:24`~`:27`의 `prepareNative`가 `ZONE`·`DEMO`와 기존 measured profile을 선택하고 Scale compiler의 활성 정보 설정을 유지한다.
2. `native_runtime.mjs:68`~`:70`의 `createUniversalSourceRuntime`이 `createMapInfographicRenderer({plan:nativePlan, layoutPlan:nativePlan})`를 호출한다.
3. `web/map_infographic_v1/renderer.mjs:467`~`:477`이 실제 pinned font를 로드하고 final extent 기준 `layoutScreen`으로 `buildMeasuredGraphicLayout`을 호출한다.
4. `graphic_layout.mjs:122`~`:130`은 glyph 보호 상자와 실제 Primary ring을 기존 최소 8px clearance로 검사한다. `:137`~`:168`은 네 위치를 비교하며 모두 실패하면 `NO_SAFE_BOUNDARY_CLEAR_LOCATION_PLACEMENT`를 기록한다.
5. factory가 `MEASURED_LAYOUT_INVALID`를 throw한다. 상위 runtime은 부분 자원을 dispose하고 원래 오류를 다시 throw한다. 실제 Nepal probe는 `ACTUAL_NATIVE_FACTORY_INIT`, 캡처 0프레임으로 끝났다.

기존 native runtime의 `graphics:false`, `location:0`과 moving-graphic pass의 `location:0`은 **factory 초기화 이후** 적용된다. 따라서 화면에서 사용하지 않는 native 위치 라벨이라도 초기 Layout 입장 검사는 먼저 일어난다. 이를 숨기거나 삭제하는 방식으로 해결하지 않는다. 기존 DEMO에 위치 라벨이 실제 표시됐다고 주장하지도 않는다.

## Namibia와의 차이

Namibia는 anchor `[17,-23]`, final extent `[5,-38,25,-6]`, 화면 anchor `[648,1020]`이다. 같은 95×27px 글꼴·gap 18·marker 40·theme·safe area·공통 엔진을 사용한다. RIGHT `[686,1006.5,95,27]`, ABOVE, BELOW 후보가 안전하며 RIGHT가 선택됐다. Nepal의 실패는 국가명 분기가 아니라 실제 Primary 형태와 anchor 주변의 안전 공간 차이에서 발생했다.

## 최소 복구 범위

별도 `layout_extension.mjs`는 명시적으로 선택된 `locationPlacement` 정책에 한해 기존 `buildMeasuredGraphicLayout`을 그대로 반복 호출한다. 먼저 기존 gap을 검사하고, 실패 코드가 이번 위치 후보 고갈일 때만 bounded gap 후보를 제안한다. 실제 글꼴 크기·지리 anchor·소스 geometry·경계 clearance·safe area는 유지한다. 다른 오류는 그대로 실패하며 예외를 삼키지 않는다. 정책이 없는 기존 Scene은 원래 결과를 그대로 반환한다.

기록된 실제 글꼴 metrics를 사용한 CPU 검사에서 Nepal은 gap 18/34/50을 거부하고 gap 66의 BELOW `[438.5,1106,95,27]`를 기존 검사가 허용했다. Namibia는 기존 gap 18과 모든 item·기존 validation 필드를 유지했다. 이 CPU 증거를 실제 브라우저 draw 성공이나 영상 품질 PASS로 표시하지 않는다. 실제 draw·Studio 제작·전체 프레임 결과는 후속 게이트 보고서에서 별도로 판정한다.

원문·SHA·수치·코드 위치: `reports/PHASE_A_AUDIT.json`, 원본 실패 기록은 이전 복구 namespace에 변경 없이 남아 있다.
