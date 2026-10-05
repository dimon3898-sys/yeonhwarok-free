# Mixed label + explicit scene edit: 읽기 전용 guard 제안

현재 동결 source를 수정/테스트하지 않고 정리한 후속 제안이다. Root의 full172가 끝난 뒤 별도로 승인·구현·검증해야 한다.

Dedicated place/status label request가 있을 때 **명시적인** lighting/camera 변경 명령도 함께 있으면 부분 적용하지 말고 `UNSUPPORTED_COMBINED_LABEL_EDIT`을 반환한다. 메시지는 “라벨 대비와 조명·카메라 변경은 각각 요청해 주세요. 조명 변경은 지명·상태 색상도 함께 맞춥니다.”처럼 동작 가능한 순서를 설명한다. 제안 Diff나 새 revision/approval을 쓰기 전에 차단한다. Label+label 조합 및 label이 없는 기존 camera+routes/ships 조합은 그대로다.

명령 검출은 현재의 generic `낮|밤|밝게|faster` 단어만 재사용하지 않는다. 설명에도 이런 단어가 나오므로 false positive가 생긴다. 작은 별도 검출기로 **대상/방향+지시 표현**을 묶는다.

- Lighting: `낮/주간/밤/야간 + 으로/로 + 바꿔/바꾸/변경/전환/해줘` 또는 `조명 + 밝게/어둡게 + 해줘/바꿔/조정` 등의 bounded 명령. 영어는 `switch/change/set ... to day/night` 등. 맨 `밤`, `밝은 지표`, `낮은 대비`는 명령이 아니다.
- Camera: `카메라 + 빠르게/느리게/천천히 + 해줘/하고/바꿔/조정` 또는 명시적인 `줌아웃해줘/줌아웃하고` 등. `빠른 카메라 이동 구간에서`, `줌아웃 중`은 설명이다. 영어는 `make/set camera faster`, `speed up the camera`, `zoom out ... and` 같은 명령 패턴.
- `Scene5 낮으로, ...`처럼 기존 짧은 조명 명령 뒤 comma/분리 접속이 오는 명확한 지시도 별도 검토한다. `밤으로 바뀌면서`처럼 상태 변화 설명과 구분해야 한다. 과도한 wildcard로 라벨 자체의 “대비를 높여”까지 scene 지시로 잡지 않는다.

초기 집중 회귀 사례:

| 판정 | 자연어 요청 | 근거 |
|---|---|---|
| 차단 | Scene5 낮으로 바꾸고 상태 라벨 대비를 높여 | 명시적 lighting+label |
| 차단 | Scene5 밤으로 전환하고 지명 라벨 대비를 높여 | 명시적 lighting+label |
| 차단 | Scene5 카메라를 더 빠르게 하고 상태 라벨 대비를 높여 | 명시적 camera+label |
| 차단 | Scene5 카메라를 천천히 움직여 주고 지명 라벨 대비를 높여 | 명시적 camera+label |
| 차단 | Scene5 줌아웃해 주고 상태 라벨 대비를 높여 | 명시적 camera+label |
| 차단 | Scene5 switch to night and improve status label contrast | 영어 lighting+label |
| 차단 | Scene5 make the camera faster and improve place label contrast | 영어 camera+label |
| 허용 | Scene4와Scene5 지명과 운하 상태 라벨의 대비를 높여 | 실제 combined label-only 후보 |
| 허용 | Scene4 지명 라벨이 밝은 지표에서 안 보여. 대비와 크기를 높여 | 설명+label |
| 허용 | Scene5 밤 배경에서 상태 라벨이 안 보여. 대비를 높여 | 밤 context+label |
| 허용 | Scene5 낮은 대비 때문에 상태 라벨이 안 보여. 대비를 높여 | 낮은=low contrast, day 명령 아님 |
| 허용 | Scene5 빠른 카메라 이동 구간에서 상태 라벨이 안 보여. 대비를 높여 | camera context+label |
| 허용 | Scene5 줌아웃 중 상태 라벨이 안 보여. 대비를 높여 | camera context+label |
| 허용 | Scene5 improve status label contrast on the bright ground/night backdrop | 영어 context+label |
| 기존 동작 유지 | 32~38초 카메라를 조금 더 빠르게 하고 배 두 척 추가 | label이 없는 기존 실제 supported composite |
| 기존 동작 유지 | Scene2 항로 두 개 추가 | label이 없는 기존 route geometry 검수 |

상태 검증은 차단 시 base bytes/hash/Scene IR·approval가 동일하고 revision 파일도 생성되지 않음을 확인한다. 허용 시 기존 appearance 필드 범위와 gate를 그대로 검증한다. 이는 제한된 문법의 fail-closed 보강이며 임의 모든 자연어 조합을 해석한다는 주장은 아니다. 새로운 camera/lighting/quality 기능이나 renderer 변경은 제안하지 않는다.
