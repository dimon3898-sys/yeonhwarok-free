# 65422 원본 조건 재현

원본 가상 시나리오를 보존된 원본 런타임으로 새로 렌더링했습니다. 원시 픽셀·PNG·10개 상태가150프레임 모두 같지만, H.264 압축 후에는 픽셀 차이가 있어 최종 판정은 `REPRODUCTION_NEEDS_REWORK`입니다.

- 실행 프로필: `ORIGINAL_EXECUTION_PROFILE.json`
- 전체 원인 조사: `reports/ROOT_CAUSE_LEDGER.md` 및JSON/CSV
- 원본 환경: `reports/ORIGINAL_ENVIRONMENT.md`
- 실제 전 프레임 비교: `reports/comparison/ALL_150_FRAME_COMPARISON.json` 및CSV
- 영상·체크포인트·비교PNG: `public-review/`
- 모바일 인계ZIP: `handoff/`

원본 내부Scene는 새 독립 캡슐에 동일 Git bytes로 복원했습니다. 공개ZIP에는 내부Scene 본문·전체 원시 진단 대신 원본 경로·SHA·복원 도구와 안전한 검증 결과만 포함합니다. 기존 소스·FINAL·영상·이미지·캐시는 변경하지 않았고, 유료GPU·80초 렌더·FINAL 승격은 실행하지 않았습니다.
