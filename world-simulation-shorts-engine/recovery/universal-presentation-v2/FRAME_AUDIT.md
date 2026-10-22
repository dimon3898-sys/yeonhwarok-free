# Actual frame audit

- 실제 Studio 작업 3개, 각각 180프레임. 원본 MP4와 공개 복사본 SHA 일치.
- 전체 540프레임 디코딩, 정확한 30fps PTS, 6초·1080×1920·H.264 검사 PASS.
- 모든 실제 프레임의 전역/지역 프레임 번호, Scene trace, 좌표 투영,
  소스 범위·gutter, GL 오류, 원본 영역/경로 geometry, 표식 이벤트 구간 검사 PASS.
- 6개 Scene의 실제 바탕 픽셀 변화 수는 90/72, 90/72, 90/90이다.
  이동·확대와 경로 추적이 실제 바탕 픽셀에 반영됐다. 끝의 의도된 hold는
  제거하거나 누락·인코딩 중복으로 단정하지 않았다.
- 가상 영토의 두 번째 Scene은 실제 제공된 큰 영역에서 시작하고 작은 영역으로
  축소한다. CUT 전후 같은 원본 상태는 유지하며, 카메라의 명시적 CUT까지
  부드러운 연속 이동이었다고 주장하지 않는다.
- 각 영상의 180개 실제 decoded thumbnail과 8개 native 크기 PNG를 생성했다.
  전체 자동 검사와 사람이 실제 본 영상·프레임의 범위는 구분한다.
  수동 검수의 구체적인 page·프레임 목록은 `VISUAL_OBSERVATIONS.md`를 따른다.
- 비교 PNG의 설명 문구는 검수 이미지에만 있다. MP4에 검수용 문구를 합성하지 않았다.

상세 판정·측정값·CSV·원본 입력→Scene→실제 픽셀 대응은
`reports/FINAL_MOVIES_AUDIT.json` 및 다음 경로에 있다.

1. `reports/MOVIE_AUDIT_1_TRACE_SCOPED/`
2. `reports/MOVIE_AUDIT_2/`
3. `reports/MOVIE_AUDIT_3/`

첫 감사 harness 실패도 `reports/MOVIE_AUDIT_1/`에 보존했다.
`AUDITOR_SCOPE_CORRECTION.md`에 원인을 설명했다. 실제 영상을 다시 렌더링하지 않았다.

**기술 검사 PASS / 시각 품질 USER_REVIEW_REQUIRED / NVIDIA NOT_EXECUTED.**
자동 검사나 작은 thumbnail으로 모든 시각적 결함이 없다고 보증하지 않는다.
