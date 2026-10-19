# 5초 Candidate 제작 경로 대조·수정

이 계층은 기존 renderer, shader, camera, Scene, 자료, Candidate를 변경하지 않습니다.
최신 기준 저장점은 `1c34f688908e87520d60b578484eea3d9940ed6e`입니다.

## 확인된 차이

- 과거 65422: `2c097df` 소스 checkout에서 직접 실행한 현대 가상 시나리오입니다.
  scalar 상보 영토·연속 전선·presentation roll·국기 8개를 사용했습니다.
- 현재 실제로 확보한 파일: SHA `3899d87c...de83f66`, `e236131` 소스 checkout의
  역사 자료 Area/ASTRA/V5 경로입니다. scalar/national 입력은 null입니다.
- `66461.mp4`와 `66430.mp4`의 원본·동일성 SHA는 확보하지 못했습니다.
  알려진 파일과 동일하다고 단정하지 않습니다.
- image 안에 코드가 있는 사실, import, CPU compiler 성공, 실제 draw, 픽셀 변화,
  NVIDIA 실행과 사용자 품질 승인은 각각 별도 증거입니다.

## 최소 수정

1. source admission은 원래 검증기가 먼저 수행합니다. 새로운 native capability
   guard는 현 producer가 제공하지 않는 scalar 합성 슬롯을 GPU 시작 전에 차단합니다.
   이 조건부 지연 실패를 null 입력 영상의 원인으로 주장하지 않습니다.
2. 카메라 수치 delta를 화면 픽셀 단위로 분류합니다. 원래 bounds 48종은 약 0.60px
   이동일 뿐이며 가독성 있는 카메라 동작·확대·회전의 증거로 사용하지 않습니다.
3. 별도 무료 observation 경로는 원래 factory·draw를 호출하고 세 global 프레임에서
   각 단계 전후 readPixels를 관측합니다. 셰이더·원본 픽셀·시점을 바꾸지 않습니다.
   원본 80초 Scene에서 연속 150프레임만 캡처하며 전체 영상은 제작하지 않습니다.

Studio 인증·Origin·CSRF·정책·GPU admission·lease·claim·인코딩·Dropbox 경로는
기존 소유자를 재사용합니다. 기존 작업을 초기화하거나 유료 GPU를 실행하지 않습니다.

## 재현

```text
python -B recovery/render-path-reconciliation-v1/package_manifest.py
python -B -m unittest discover -s recovery/render-path-reconciliation-v1/tests -p 'test_*.py' -v
node --test --test-isolation=none recovery/render-path-reconciliation-v1/tests/test_trace_binding.mjs
```

실제 무료 캡처는 검증된 `PREPARED.json`의 source 옵션과 새 비어 있는 private 출력
경로, 실제 source checkout commit을 `free_trace_capture.mjs`에 전달합니다.
이 내부 분석 경로는 인증된 Studio production API에 노출하지 않습니다.

보고서·151개 판정표·실제 새 캡처 증거·이미지 증거는 각각 `reports`, `proof`,
`runs`에 보존합니다. 기술 성공을 레퍼런스 품질 성공으로 승격하지 않습니다.
