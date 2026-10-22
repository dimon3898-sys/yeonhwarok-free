# G2 Universal Renderer Recovery — NEEDS_REWORK

PHASE 0/1의 원인 확인과 부분 소스 복구를 완료했다. PHASE 2는 기존 52개·신규 49개 코드 검사 PASS, Namibia 실제 draw PASS, Nepal 초기 Layout FAIL이다. 사용자 지시에 따라 PHASE 3를 시작하지 않았다.

**새 6초 MP4 없음. 새 Studio 180프레임 job 없음. G3 BLOCKED.**

- `ROOT_CAUSE_REPORT.md`: 재질 불연속과 데이터 격자 원인.
- `CHANGE_MANIFEST.md`: 새 연결 계층과 기존 파일 보존.
- `TEST_REPORT.md`: 실행 명령, 52+49 검사, 실제 실패.
- `FRAME_AUDIT.md`: 기존 180프레임 및 부분 복구 프레임의 실제 검수 범위.
- `G2_GATE_DECISION.md`, `reports/GATES.json`: 중단 결정.
- `public-review/BEFORE_AFTER_CONTACT_SHEET.png`: 동일 시점의 원본 WORLD ENGINE PNG 비교. 새 영상에서 추출한 프레임이 아님.
- `review-package/G2_RECOVERY_EVIDENCE.zip`: 모바일 검토용 코드·보고서·fixture·비교 PNG. 큰 지도 자산은 Git의 `assets/terrain/`에 별도 보존한다.
- `SHA256SUMS`: 전달 파일 SHA.

재개 지점은 Nepal의 정보 활성 프로필과 기존 Layout 입장 계약 대조다. 기존 안전 검사를 제거하거나 실패 지역을 교체하지 않는다. PHASE 2 전체 통과 전 Studio 영상 제작을 실행하지 않는다. gCube 환경변수나 Secret 변경은 필요하지 않다.

원격 체크포인트와 실제 HTTP 200/다운로드 SHA 결과는 `reports/DOWNLOAD_VERIFICATION.json`과 `reports/SESSION_CHECKPOINT.json`에 보존한다. 유료 GPU·역사 영상·80초 제작·FINAL 변경은 수행하지 않았다.
