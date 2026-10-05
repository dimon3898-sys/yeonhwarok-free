# 운하 상태 라벨 가독성 수정 — R04

실제225프레임 S005의 local1.8/2.9초375px 검수에서 `ASSUMPTION · CANAL CLOSED`가 밝은 사막 위46px 흰색·opacity.8로 식별하기 어려운 결함을 root와 독립 검수자가 확인했다. City-only 후보는 S004에 효과가 있으나 이 상태 문구는 기존 범위에서 제외되어 추가 수정이 필요했다. 기존168 PASS/이전focus/원본 영상 증거는 보존했다.

## 변경과 보존

`SOURCE_BEFORE_R04/`에 planner/revisions/테스트 exact bytes를 보존하고 SHA/길이를 `SOURCE_BEFORE_R04.json`에 기록했다. `R04_SOURCE_DIFF.patch`에 이번 좁은 코드/검사 변경을 기록했다.

- 기존 helper에 `include_status=False`를 추가했다. 기본 지명-only 호출은 계속 status를 보존한다.
- 미래 DAY_DOCUMENTARY/GEOGRAPHY_READABILITY 및 generic 실제 조명 변경은 `include_status=True`로 verified role=status의 **color/opacity만** 맞춘다. text/timing/coordinates/role와 명시적·암묵적 글자 크기를 그대로 둔다. 밤/HERO 미래 baseline은 이전대로다.
- 명시적 `운하 상태 라벨` / `상태 라벨` / `status label` 대비·가독성 요청을 지원한다. Status-only는 status 객체만 선택해 city를 건드리지 않는다. 지명+상태를 함께 요청할 때만 둘을 변경한다.
- 없는 라벨, 잘못된 좌표, status가 아닌 caption은 status-only 수정에 `UNSUPPORTED_LABEL_EDIT`을 반환한다. Status 글자 확대만의 요청은 지원하지 않는다. 자막·이동체·효과 라벨은 이번 수정 대상이 아니다.
- schema/JS/renderer/asset/server/production IR/승인/worker/Git은 변경하지 않았다. 이후 실제 native/pixel/영상 확인은 root가 담당한다.

## 실제 combined 제안

`Scene4와Scene5 지명과 운하 상태 라벨의 대비를 높여.`

원본 production v002를 임시 read-only plan store로 읽어 `NATURAL_COMBINED_LABEL_PROPOSAL.json`, `NATURAL_COMBINED_LABEL_DIFF.json`, standalone `combined_candidate_plan.json`, `COMBINED_LABEL_FIELD_PROOF.json`을 저장했다. 이 파일은 **미승인 static 후보**이며 production v003나 영상 생성물이 아니다. 원본 byte copy는 `shipping75_v002_before_exact.json`이다.

정확히8개 appearance 경로만 변경:

- S004/S005 labels.0 각각 color 없음→#102430, size 없음(default46)→52, opacity.9→1.0.
- S005 labels.1(status) color 없음→#102430, opacity.8→1.0. size 필드는 기존처럼 없다(default46).

다른8 Scene canonical SHA 동일, 모든 선택 Scene labels 외 필드 동일, status text·시간·좌표·크기 동일, 원본 production bytes SHA `12d997d125443af691267b88ef6743d4295438c108705f6af8bea154abaffab5` 그대로이다. 전체 schema/Retention/frozen pure Three 기하 certificate PASS, 실제2.7615초. 카메라·조명·경로·엔티티·대본·사건·SFX·FACT/ASSUMPTION/SIMULATION·entry/exit를 바꾸지 않았다.

설치된 OpenSans-Light 실제 advance+2.7px spacing으로 상태 문구의46px 폭은1080기준703.8361px/2160기준1407.6723px이다. 안전폭756px 안에 들어간다.52px로 올리면787.1887px로 안전폭을 넘으므로 font46을 유지한다. 이는 font-metric 증거이며 새 canvas/실제pixel 가독성 PASS는 아니다. 후보 native 검수는 S004 local6.2, S005 local1.8/2.9처럼 지명과 상태가 실제 보이는 시각에서 필요하다.

## 집중 검사 및 동결

`focused_unittest_r04.log` / `FOCUSED_TEST_REPORT_R04.json`: 단일 실행15개 PASS53.702초, 외부54.2827초, source_changes=[]. 기존11개와 combined 실제8필드 범위/status-only/부재·미검증·비-status 차단/밤 전환 font46+safe-width 검사를 포함한다. Future day status와 generic lighting switch의 상태 palette 동기화도 확인했다. 원래 city-only 요청은 계속 status를 보존하며 중복 Gate를 약화하지 않았다.

```bash
cd /workspace/yeonhwarok-free/world-simulation-shorts-engine
PYTHONPYCACHEPREFIX=/tmp/wss_status_label_r04_pycache .venv/bin/python -m unittest discover -s tests -p test_place_label_readability.py -v
```

소스/테스트는 이 검사 후 동결했다. root의 별도 full172는 이후 실행 중이고 완료 결과를 이 증거가 주장하지 않는다. 추가GL/render/승인/production 작업은 하지 않았다.

읽기 전용 독립 코드 검토는 R04 지정 문구에서 범위 오류를 찾지 않았다. 기존 제한인 label+실제 camera/lighting 명령의 한 문장 묶음은 dedicated label branch의 continue 때문에 후자가 누락될 수 있다. root가 이 별도 회귀의 fail-closed guard를 검토 중이며, active full172 동안 여기서는 구현하지 않았다. `MIXED_LABEL_GUARD_READONLY_PROPOSAL.md`는 설명 문구를 오인하지 않는 후속 제안일 뿐 현재 실행 기능이 아니다.

## 동결 SHA-256

| 파일 | SHA-256 |
|---|---|
| `engine/planner.py` | `1d4489985a3f402cb6f0404e25de44b4dba512495c26ee42188acdd7642b4ce5` |
| `engine/revisions.py` | `86a81c2bd12f62851b548eaab4e579caec857bb6392bd470a5ffef692b314785` |
| `data/scene_plan.schema.json` | `7f1d8550c2696359ba4642e6d54ceaf9cb1456cdd7c7f3d89407fab489e3006e` |
| `web/earth_adapter.js` | `c0f6c890e67ab5be7aea56739f384db01f1df962330564947dc3a1e378c172f9` |
| `tests/test_place_label_readability.py` | `ce78053f83dd3001aef4e36627c0193067c29b0f74201c666378fc32ab76c13d` |
| `tests/fixtures/shipping75_v002_label_readability_original.json` | `12d997d125443af691267b88ef6743d4295438c108705f6af8bea154abaffab5` |
