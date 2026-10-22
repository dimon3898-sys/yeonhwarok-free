# LAYOUT_FIX_REPORT

## 적용 계약

기존 core·renderer·Layout 파일은 변경하지 않는다. 새 namespace의 `layout_extension.mjs`가 기존 함수와 버전 상수를 전달하며, 별도 실행 프로필만 이 adapter를 선택한다. 기존 Scene에는 선택 필드가 없어 원래 결과가 그대로 유지된다.

```json
{
  "layout": {
    "locationPlacement": {
      "schema": "WORLD_ENGINE_LOCATION_PLACEMENT_POLICY_V1",
      "mode": "BOUNDED_GAP_SEARCH",
      "maxGap": 216,
      "step": 16
    }
  }
}
```

네 필드 외 입력은 거부한다. `maxGap`은 기존 gap 이상이며 canonical 화면 짧은 변의 20% 이하다. `step`은 4~32의 정수다. 위치 정보가 비활성화된 입력에 이 정책을 사용하면 명시적으로 거부한다. 국가명·좌표·언어·사건별 분기는 없다.

## 동작

1. 기존 함수·기존 gap으로 먼저 평가한다. 기존 결과가 valid이면 원래 items 및 모든 원래 validation 필드를 유지한다.
2. 실패가 `LOCATION_LABEL / NO_SAFE_BOUNDARY_CLEAR_LOCATION_PLACEMENT`인 경우에만 gap을 bounded 순서로 증가시킨다. 각 후보는 **동일한 기존 Layout 함수**가 실제 projected geometry·glyph metrics·safe area·충돌 검사로 판정한다.
3. 전체 Layout이 valid인 첫 결과만 채택한다. bounded search를 모두 소진하면 invalid를 반환하고 기존 factory의 명시적 실패 처리를 유지한다.
4. input Plan은 수정하지 않는다. 폰트·표식 크기·지리 anchor·geometry·투영법·경계 clearance·안전 여백을 바꾸지 않는다. 라벨을 삭제하거나 숨기는 기능이 아니다.
5. `validation.locationRecovery`에 기존/선택 gap, 각 후보의 판정·실패·충돌, 기존 검사 사용 여부를 기록한다. 이 추가 증거는 opt-in 입력에만 붙는다.

## 호환성·범용성 검증

`tests/test_layout_extension.mjs`는 다음 11개 CPU 검사를 수행했다. 실제 draw 성공은 별도 증거가 필요하다.

- opt-in이 없으면 기존 Nepal 실패 결과와 완전 일치.
- 실제 기록 font metrics·원본 Primary로 Nepal의 안전 gap 선택.
- Namibia 기존 valid items 및 원래 validation 필드 완전 일치.
- 반복 결과 결정성·원본 입력 불변.
- 알 수 없는 필드·범위·step·비활성 위치 정책 거부.
- bounded search 소진 시 명시적 실패.
- 불가능한 safe area 보호.
- 크기 초과 등 다른 glyph 오류를 유지하고 재시도로 숨기지 않음.
- 실제 font 예외가 원래대로 전달됨.
- dynamic diagnostic의 실제 callback 요구와 렌더 주장 분리.
- 지리 geometry ID·국가명 변경이 결과를 선택하지 않음.

CPU fixture는 이전 실제 source geometry와 pinned-font export에서 필요한 입력만 추출했다. 실제 PNG를 그린 것으로 표시하지 않는다. `fixtures/LAYOUT_FAILURE_CASES.json`에 원본 파일 SHA와 분류가 있다.

## 이동·줌 검사 연결

`auditRuntimeLayout({plan,screen})`은 실제 factory가 이 adapter를 호출할 때 사용한 **동일한 실제 glyph 측정 callback**과 현재 factory projection을 재사용한다. 출력은 validation·보호 상자·선택 근거이며 새 렌더 pass가 아니다. native runtime에서 숨긴 라벨을 실제 그린 것으로 주장하지 않는다. callback 또는 실제 projection이 없으면 실패한다.

Browser는 원래 Layout을 `/modules/graphic_layout_legacy.mjs`로 byte 동일하게 제공하고, 새 실행 프로필의 `/modules/graphic_layout.mjs`만 adapter에 연결한다. Node CPU 검사는 원래 파일을 직접 import한다. 기존 G1·FINAL 실행은 이 별도 프로필을 선택하지 않는다.

## 실제 범용 검사 결과

기존 101개 전수 회귀와 추가 42개 검사에서 모두 PASS, skip 0을 확인했다. 별도로 5개 지역의 실제 SwiftShader draw 20회가 통과했다. 모든 지역은 같은 renderer·source runtime·adapter를 사용했다.

| 지역 | factory 초기화 | 현재 카메라 Layout diagnostic | 실제 지도 draw |
|---|---|---|---|
| Namibia | 기존 gap 18 유지 | 18/18/18/18 valid | 4 PASS |
| Nepal | gap 66 선택, 위치 역할 유지 | 50/66/50/66 valid | 4 PASS |
| 한반도 | gap 50 선택 | 34/50/34/50 valid | 4 PASS |
| 유럽 Germany | 기존 gap 18 유지 | 18/18/18/18 valid | 4 PASS |
| 남미 Chile | gap 34 선택 | 18/34/18/34 valid | 4 PASS |

기존 Namibia·Nepal 원본 source/Scene 입력은 변경하지 않았다. 실제 같은 프레임 재검사는 raw SHA가 같고, owner partition과 shared-front source binding이 유지됐다. 모든 기록 draw에서 이벤트 좌표 투영 오차 0px, GL 오류 0, black fraction 0을 확인했다. 실제 지도 자산 요청의 HTTP 200·SHA와 source-native coverage 검사도 통과했다. 독립 read-only 검토는 PHASE C의 실제 기록 범위에서 차단 오류가 없다고 판정했다.

`auditRuntimeLayout`은 초기화와 같은 실제 glyph callback 및 각 draw의 현재 projection을 사용했다. 이는 보이지 않는 native 위치 라벨의 보호 상자 정합 검사다. 기존 runtime의 `location:0`은 유지되므로 **새로운 위치 라벨이 화면에 그려졌거나 모바일에서 읽힌다는 주장은 하지 않는다**. Label 삭제·활성 역할 비활성화로 초기화 검사를 우회한 것이 아니다.

관련 증거: `reports/CPU_REGRESSION_RESULTS.json`, `ACTUAL_REGIONS.json`, `ACTUAL_REGION_*.json`, `INDEPENDENT_PHASE_C_REVIEW.json`. 준비 과정의 최초 Chile recognition 입력 오류와 summary parser 오류도 별도 실패 기록으로 보존했다. 전자는 새 예제 viewport만 수정했고 후자는 보고 harness만 수정했다. 기존 테스트·보호 core·geometry·입장 기준은 완화하지 않았다.

## 완료 범위

구현·기존 101개 및 추가 42개 CPU 회귀·5개 지역 실제 draw를 완료했다. 이후 실제 인증 Studio가 6초·180프레임 MP4를 생성했다. 전체 디코딩·PTS·상태·Layout 검증을 통과했으며 기술 근거와 수동 검수 범위는 `FRAME_AUDIT.md`, 실제 실행은 `reports/STUDIO_FINAL_EXECUTION.json`에 있다. 판정은 `G2 TECHNICAL_PASS / QUALITY_REVIEW_REQUIRED`다. NVIDIA 검증은 실행하지 않았으며 사용자 실제 영상 승인 전 영상 품질 PASS·FINAL 승격을 선언하지 않는다.
