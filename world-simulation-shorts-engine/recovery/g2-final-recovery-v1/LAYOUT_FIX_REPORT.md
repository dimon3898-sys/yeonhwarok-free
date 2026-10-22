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

## 완료 범위

본 파일은 구현과 CPU 단위 검사 범위를 설명한다. 5개 지역 실제 draw, 기존 101개 전체 회귀, 실제 Studio 6초 MP4, 전체 180프레임 품질은 각각 해당 실행 보고서가 있어야 완료로 판정한다. 사용자 실제 영상 승인 전 영상 품질 PASS·FINAL 승격을 선언하지 않는다.
