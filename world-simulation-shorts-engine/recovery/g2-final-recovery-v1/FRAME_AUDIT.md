# Actual encoded Studio frame audit

Technical status: PASS. Visual status: QUALITY_REVIEW_REQUIRED; no automatic quality approval.

Decoded all180frames at1080×1920/30fps/6seconds. Exit0; sequential PTS verified. Recovery MP4 SHA256 `2aa3c8de7ad867863b7ec7d8f2ad60f6e93255c742cb631732c9d7a57fd41cc9`.

Before/after exact scene-state frames: 180/180. Camera, owner/unknown/contested/shared-front, marker, glyph and frame clock compared; terrain style metadata intentionally excluded.

Source coverage all180viewports: True; decoded native overlap exact: True; actualHTTP/receipt: PASS.

Old support-edge thresholds remain vertical12.133750066757203 and horizontal0.75. Flagged recovered frames: vertical1, horizontal0.

These are known-location diagnostics, not a generic image-quality test. Inspect flagged natural features before classifying a defect. No threshold was relaxed or refit.

Comparison PNG shows actual encoded frames [0, 30, 60, 90, 120, 150, 151, 179]. The script performs no manual semantic review; independent reviewer must record their actual viewed frames separately.

All180decoded PNGs remain in the new private scratch directory. Existing baseline source/video/cache files are not modified. HistoricalG3 remains BLOCKED.

Detailed results and exact commands: `reports/RECOVERY_FRAME_AUDIT.json`; per-frame data: `reports/RECOVERY_FRAME_AUDIT.csv`.


## Final recovery layout evidence

Overall technical status after current-camera layout checks: PASS. Visual status: QUALITY_REVIEW_REQUIRED; user approval remains required.

Current-camera layout checks: PASS, 180/180 frames. The original location label stays selected and is measured with the actual font and projection. The unchanged source runtime does not draw its native LOCATION_LABEL; it draws the marker and the SYNTHETIC caption. These checks prove layout admission and collision safety, not visible location-label pixel quality. No label deletion or collision-check bypass is inferred.

Detailed per-frame evidence: `reports/FINAL_LAYOUT_FRAME_AUDIT.json`. All 180 original comparison measurements and support-edge thresholds were reused unchanged.


## 실제 수동·독립 검토

전체 180프레임을 번호가 있는 108×192 축소 개요에서 확인했고, 동일 시점의 전후 8개 pair 및 f133 전체 화면·f132/133/134의 확대 crop을 확인했다. 180개 전체를 원본 해상도로 육안 검사하거나 휴대폰 실기기에서 재생했다는 뜻은 아니다. 상세 범위는 `reports/ROOT_MANUAL_FRAME_REVIEW.json`과 `INDEPENDENT_VISUAL_REVIEW.json`에 있다.

고정 임계값을 소폭 넘은 vertical f133 한 건은 새 원본 NE1 내부의 연속된 산지/하천 명암이다. 기존 직선 재질 경계와 다르며, 같은 지점의 원본 RGB와 앞뒤 실제 프레임으로 독립 확인했다. 자동 경고는 보고서에 보존했고 임계값·픽셀·감사 코드를 바꾸지 않았다. horizontal 경고는 0건이다. 영역의 격자 계단은 원본 합성 데이터대로 남겼다.

최종 판정: **G2 TECHNICAL_PASS / QUALITY_REVIEW_REQUIRED**. 사용자 실제 영상 승인 전 품질 PASS·FINAL 승격 없음. G3 BLOCKED.
