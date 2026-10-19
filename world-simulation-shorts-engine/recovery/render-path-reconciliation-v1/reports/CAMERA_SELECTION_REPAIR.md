# 카메라 선택·보고 판정 최소 수정

## 확인한 결함

기존 `universal-overnight-v3/camera_activity.py:177–180`은 bounds의 부동소수점 값이 한 번이라도 달라지면 `OBSERVED_MOVING`으로 표시한다. 기존 `preview_contract.py:184–195`는 이 pair 수를 구간 선택 최우선 점수로 사용했다. 실제 알려진 5초 출력의 48개 bounds variant / 47개 변경 pair는 모바일에서 읽히는 이동의 증거가 아니었다.

원본 카메라·선택기·Scene·후보 결과는 수정하지 않았다. 독립 신규 모듈 `camera_pixel_activity.py`에서 **이미 관측된 좌표만** 재평가하고 기존 보고의 의미를 교정했다. 카메라 포즈·전선·시간축을 생성하지 않는다.

## 실제 자료 재평가

동일 1080×1920 기준, 첫 관측 화면의 고정된 3×3 지리 격자점 9개를 이후 모든 관측 bounds에 투영한다. 같은 GIS 지점의 화면 위치 변화이므로 중점만 비교할 때 놓치는 확대도 측정한다. 명시적으로 실제 관측된 `rotationDegrees`가 모든 행에 있을 때만 화면 중심 회전을 포함한다.

| 실제 자료 | 프레임 | 첫 화면 대비 최대 격자 변위 | 판정 |
|---|---:|---:|---|
| 이전 고급 5초 Candidate | 150 | bounds만 596.078px / 관측된 roll 포함 638.962px | `OBSERVED_PIXEL_SCALE_MOVEMENT` |
| 알려진 overnight 5초, 원본 [1400,1550) | 150 | 0.602065px | `NUMERIC_SUBPIXEL_ONLY` |

이전 고급 영상은 source `2c097df…`, 원본 증거 `45af879…`의 실제 150개 관측을 사용했다. 그 Scene은 가상 연출 연구이며 한국전쟁 사실 자료가 아니다. 알려진 새 영상은 source `e236131…`, SHA `3899d87c…`의 실제 관측이다. 사용자 파일명 `66461.mp4`와 동일하다고 확정하지 않는다.

새 영상의 bounds 폭 비율은 1.0~1.0000000000000033으로, 수치 오차 수준이다. 별도 actual diagnostic의 `actualV5Turn`은 150프레임 모두 false다. bounds만으로 roll이 0이었다고 추론하지는 않는다.

보존된 200개 실제 관측 [1400,1600)에서 연속 150프레임 창은 51개다. **51개 모두 1px 기준 미만**으로, 선택 결과는 `NO_OBSERVED_VISIBLE_CAMERA_WINDOW`다. 알 수 없는 다른 80초 구간에 좋은 카메라가 있다고 추정하거나 새로운 구간을 만들어 선택하지 않았다.

## 정확한 신규 API

```python
from camera_pixel_activity import assess_camera_activity, select_visible_camera_window

measurement = assess_camera_activity(
    actual_rows, width=1080, height=1920, min_visible_pixels=1.0)
selection = select_visible_camera_window(
    actual_rows, frame_count=150, width=1080, height=1920,
    min_visible_pixels=1.0)
```

각 행에는 `frame` 또는 `globalFrame`과 `bounds` 또는 `cameraBounds`가 필요하다. 좌표 순서는 `[west,south,east,north]`다. frame과 bounds는 실제 렌더링 진단에서 받아야 하며 사용자 설명 문구로 대신할 수 없다.

- `assess_camera_activity`: 완전히 관측된 연속 프레임만 허용한다. 누락·중복·역순·잘못된 좌표·부분 회전 관측을 명시적으로 거부한다.
- `select_visible_camera_window`: 관측이 빠진 구간은 연결하지 않는다. 불연속일 수 있는 큰 프레임간 점프도 연속 이동 후보에서 제외한다. 구간이 없으면 명확한 차단 결과를 반환한다.
- 누적 jitter 경로 길이가 길어도 첫 고정 격자의 최대 변위가 1px 미만이면 pixel-scale 이동으로 승격하지 않는다.
- 남반구·서반구·날짜 변경선 횡단을 지원한다. 유효 위도 ±90도 범위와 비퇴화 bbox를 검사한다. 측정은 직사각형 equirectangular 출력에 한정하며 다른 투영법·극지 지형 정확도를 검증했다고 주장하지 않는다.
- 1px는 객관적인 화면 좌표 변화 판정 기준이다. 인간의 인지·모바일 시각 품질·레퍼런스 동급 판단이 아니다. 모든 결과에서 `visualQualityPass=false`이고 `mobilePerceivedMotionVerified=false`다.

## 실행 경로 적용 원칙

이 신규 모듈은 재조정 경로의 분석·사전검사에서 사용할 수 있다. 기존 selector·V5·80초 Source를 덮어쓰지 않는다. “눈에 보이는 카메라가 필요한 preview”에서 모든 실제 관측이 subpixel이면 명시적으로 후보 부재를 반환한다. 자동으로 더 좋은 범위가 생겼다고 표시하거나 새 카메라 포즈를 만든 후 기존 상태라고 주장하면 안 된다.

실제 추가 카메라 활동이 필요하면 기존 고급 Candidate의 별도 source-bound 프로필을 정확한 데이터/Scene 계약으로 선택하거나, 보존된 전체 타임라인에서 이미 존재하는 카메라를 실제로 관측해야 한다. 가상 5초 카메라를 역사 Scene에 무조건 복사하는 것은 본 수정 범위가 아니다.

## 집중 검증

```text
python -B world-simulation-shorts-engine/recovery/render-path-reconciliation-v1/tests/test_camera_pixel_activity.py
20 tests PASS / 0 FAIL
```

실제 이전/새 150프레임 회귀 2개와 static·subpixel·확대·명시 roll·jitter·남/서반구·날짜 변경선·극지 bbox·누락/중복/불규칙 clock·큰 점프·차단 결과 검사를 포함한다. 모의 NVIDIA 성공이나 카메라 품질 PASS를 만들지 않았다. 실제 관측과 입력 SHA는 `CAMERA_PIXEL_ACTIVITY.json`에 저장되어 있어 `/tmp` 자료 없이 재검증할 수 있다.
