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

기록된 실제 글꼴 metrics를 사용한 CPU 검사에서 Nepal은 gap 18/34/50을 거부하고 gap 66의 BELOW `[438.5,1106,95,27]`를 기존 검사가 허용했다. Namibia는 기존 gap 18과 모든 item·기존 validation 필드를 유지했다. 이후 아래 실제 브라우저 검사로 초기화 복구를 별도 확인했다. CPU·지역 probe 결과를 최종 영상 품질 PASS로 표시하지 않는다.

## 실제 수정 후 PHASE C 결과

동일한 기존 native runtime·renderer·카메라·지도 소스 처리에 새 opt-in Layout adapter를 연결해 Namibia, Nepal, 한반도, 유럽 Germany, 남미 Chile를 각각 4회 그렸다. **5개 지역 총 20회 실제 SwiftShader draw PASS**다. 모든 지역에서 초기화, 실제 glyph callback과 현재 factory projection을 사용한 Layout 검사, source partition, asset HTTP/SHA, 같은 프레임 재검사 해시가 통과했다. 이벤트 투영 오차는 기록된 모든 draw에서 0px, GL 오류 0이다.

| 지역 | 초기화 선택 gap | 이동·줌/재검사 gap 순서 | 실제 draw |
|---|---:|---|---:|
| Namibia | 18 | 18,18,18,18 | 4 PASS |
| Nepal | 66 | 50,66,50,66 | 4 PASS |
| 한반도 | 50 | 34,50,34,50 | 4 PASS |
| 유럽 Germany | 18 | 18,18,18,18 | 4 PASS |
| 남미 Chile | 34 | 18,34,18,34 | 4 PASS |

Nepal 실제 factory 초기화는 기존 네 후보의 실패를 기록한 후 gap 66에서 통과했다. 현재 카메라 projection의 diagnostic Layout도 이동/줌에 따라 50 또는 66의 안전 후보를 선택했다. 원래 Namibia 입력과 결과의 gap 18을 유지했다. 원래 Namibia·Nepal의 source geometry·anchor·camera 입력 bytes는 보존됐다.

**이 결과는 실제 지도 draw와 glyph 보호 상자 검증이다. 기존 기술 DEMO가 숨기는 `ZONE` 위치 라벨이 실제 영상에 표시됐다는 뜻이 아니다.** native location reveal은 원래대로 0이고, 동적 Layout 검사는 diagnostic-only다. 숨겨진 라벨의 모바일 픽셀 가독성이나 새로운 이동 라벨의 출력 품질을 검증했다고 주장하지 않는다.

기존 **101개 전수 검사와 추가 42개 검사 PASS**, skip 0을 기록했다. 새 보고 harness가 JSON summary를 잘못 읽어 처음 기록한 실패는 별도로 보존했고, 원래 테스트 프로그램과 기준은 변경하지 않았다. 추가 Chile Scene의 최초 recognition extent가 원본 지도에 포함된 Easter Island와 남단을 누락해 사전 준비에서 거부된 것도 보존했다. 새 합성 입력 extent만 실제 Primary 전체를 포함하도록 고쳤다. 기존 Namibia·Nepal Scene, 원본 geometry, 보호 카메라, 안전 기준을 변경하지 않았다.

증거는 `reports/ACTUAL_REGIONS.json`, 지역별 `ACTUAL_REGION_*.json`, `CPU_REGRESSION_RESULTS.json`, `INDEPENDENT_PHASE_C_REVIEW.json`에 있다. 이후 실제 인증된 Studio 작업 `studio-ed20f92b16cf939f72cc078c24f217c7`이 180/180프레임을 약 209초에 완료했다. 완성된 6초 MP4 전체를 디코딩했고 원본과의 카메라·영역·전선·마커·시간 상태가 180/180 일치했다. 기존 직사각형 재질 전환은 비교 화면에서 사라졌다. 고정 수치 기준에서 표시된 f133 한 건은 독립 원본 비교에서 지형 명암으로 분류했으며 임계값을 변경하지 않았다. 실제 증거는 `FRAME_AUDIT.md`와 `reports/INDEPENDENT_VISUAL_REVIEW.json`에 있다. 기술 조건은 통과했지만 사용자 영상 품질 승인은 대기한다. NVIDIA·유료 GPU·G3·80초 제작은 실행하지 않았다.

원문·SHA·수치·코드 위치: `reports/PHASE_A_AUDIT.json`, 원본 실패 기록은 이전 복구 namespace에 변경 없이 남아 있다.
