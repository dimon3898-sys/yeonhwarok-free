# 주제 선정: 몽골제국 초기 영역의 두 원자료 상태

**설계 후보로 선정:** 1206–1209년 상태 → 1210–1215년 상태. 제목은 ‘몽골제국’으로 유지한다. 20초에 한 번의 인접 상태 변화만 보여준다. **GPU 실행 주제로는 아직 승인·확정하지 않는다.** 필수조건8인 새연속profile의 정식GPU입력 연결이 차단되어 어떤 후보도8/8을 충족했다고 선언할 수 없다.

## 선정 근거

| 조건 | 판정·실제 근거 |
|---|---|
| 기존 검증 역사데이터 | 충족: `../mongol-empire-6s-20261113/source/SOURCE_AUDIT.json`, 동일 Cliopatria v0.2.1 추출본 |
| 시기정보 | 충족: FromYear/ToYear 1206–1209,1210–1215. 특정일자나 정복연도로 재해석하지 않음 |
| 도형출처 | 충족: 고정커밋5f433377139a6eeaeacbdc894b70f8805b72c8b5, 원본ZIP SHA e10a4e429fca708788ff9e7572a95fce801fae55852d217cffabc1c59cd4eed4 |
| 연속변화 | 충족: 기존 continuous runtime의106개 중간도형 및 양끝 source 상태를 바이트동일 재사용 가능. 기존 기술PASS 재실행 안 함 |
| 지리범위 적합성 | 조건부충족: 약90.4191–126.1711°E,40.6144–56.8686°N를 자연지형 배경에서 표현. 북방원근·source밀도 때문에 원본같은 초근접확대 불가 |
| 20초 사건구조 | 충족: 초기범위→광역맥락→한번의인접상태변화→읽기→제한된추가접근→결과유지. 많은사건으로20초를 채우지 않음 |
| 새공통기능 없이 설계 | 기존formal runtime의 camera/scene/territory/labels 구성으로 가능. exact-reference 자동prompt 옵션과 실제GPU연결은 후속기능 격차 |
| 실제GPU입력경로 | **BLOCKED**: 기존6/10초GPU·historical admission·generated runtime과 새600프레임연속profile 불일치. FEATURE_GAP_REPORT P0 |

## 실제 자료에서 보여줄 것

- 1206–1209 상태: 출처면적 약2,464,171km², bounds [92.675827,40.614410,126.171127,55.703117].
- 1210–1215 상태: 출처면적 약2,821,825km², bounds [90.419098,40.614410,126.171127,56.868607].
- 영역은 대체로 커지지만 완전한 포함관계가 아니다. 기존SOURCE_AUDIT의 작은 removed영역도 그대로 보존한다. 누적fill로 합쳐 실제source를 바꾸지 않는다.
- 관찰 가능한 변화위치와 source기간만 표시한다. 북쪽·서쪽 등 화면방향은 실제 도형에서 확인하며 특정전투·장수·진군순서를 붙이지 않는다.
- 106개 중간도형은 시각적보간이며 역사적으로 관측된106개시점이 아니다. 기존 고지 ‘중간 움직임: 시각적 보간 / 일부 시기’를 유지한다.
- 화면라벨: ‘몽골제국’, ‘1206-1209’, ‘1210-1215’. 면적수치는 source기록에만 남기고 영상에는 추가하지 않는다. source center를 수도·도시·사건핀으로 사용하지 않는다.

## 데이터 경로·출처

- 원본추출: `world-simulation-shorts-engine/production/mongol-empire-6s-20261113/source/CLIOPATRIA_MONGOL_1206_1259.geojson`.
- 기존정식Scene/geometry: `../continuous-territory-20261114/FORMAL_SCENE.json`.
- 재사용중간도형: `../continuous-territory-20261114/RUNTIME_REQUEST.json` → segments[0].presentation.territoryChanges.items[0].continuous.
- 이미검증된camera구도: `../integrated-visual-20261114/final-a1/CHANGE_SCOPE.json`의cameraAudit. 이번600경로는 별도로검사한다.
- 학술설명: Bennett et al.(2025), Scientific Data12:247, https://doi.org/10.1038/s41597-025-04516-9 ; 공개본문 https://pmc.ncbi.nlm.nih.gov/articles/PMC11822181/ . 제공자 데이터 https://github.com/Seshat-Global-History-Databank/cliopatria/tree/v0.2.1 . CC BY4.0.
- 새웹확인(2026-11-14): 논문은 정치체영역·시기를GeoJSON으로제공하며 역사경계의근사·불확실성을설명한다. 논문표의다른버전면적을현v0.2.1값으로대체하지않는다. 이확인은기존원본추출검사를다시실행한것이아니다.

## 제외·축소한 후보

| 후보 | 결정·이유 |
|---|---|
| 몽골1206–1226,4상태/3변화 | 기존20S_TIMING은타이밍만PASS. 동서범위가약67.5도로넓어져 세로화면의지형디테일이줄고 자동3cycle을반복한다. 이번목표인참조리듬을위해6개후속상태를제외 |
| 몽골1206–1259전기간 | 8개상태를20초에압축하면읽기시간과확대품질을잃음. 제외 |
| 한국전쟁기존20초 | v11은GENERAL_ONLY의10초×2준비증거이며, v10은과거직접runtime우회를취소한기록. 새연속profile/historical admission을해결하는대체증거가아님. 사건의의미를GENERAL로바꾸지않음 |
| 일본V3 | 기존지리연출기술PASS는보존. 이번조건에필요한동일수준의인접역사영토변화·시기·source polygon증거가선정자료에없어교체하지않음 |

결론: 현재자료로 가장정밀하게설계할수있는후보는몽골두상태다. 필수GPU조건을충족하지못하므로 최종상태는BLOCKED를유지하며, 자료가없다는이유로임의의새역사주제를만들지않는다.
