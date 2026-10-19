# 80초 스토리 감독 · 실제 16프레임 검수

**FRAME_RENDER_PASS / STORY_NEEDS_REWORK / USER_REVIEW_REQUIRED**

원본 80초·2,400프레임의 전역 시각 0, 5, …, 75초를 실제 WORLD ENGINE WebGL2 렌더러로 각각 출력했다. 추가 인접 9장을 포함해 실제 draw/readPixels는 25회다. 전체 80초 영상이나 5초 영상을 만들거나 캡처하지 않았다. 출력은 모두 1080×1920 PNG이며 AI 이미지를 사용하지 않았다.

실행은 로컬 소스 `21eac98a31e19dab9d2b1c6cb8e6ccf3f5af4b1a`와 Chromium **SwiftShader SOFTWARE_PREVIEW**다. NVIDIA·gCube·GPU 컨테이너 실행 증거가 아니다. 저장소 최신 이미지 메타데이터, Scene에 포함된 이미지 식별자, 실제 실행한 소스를 `reports/RENDER_PROVENANCE.json`에서 구분했다.

## 12장면과 실제 자료

원본 12장면 순서와 200프레임씩의 경계를 보존했다: 발발 → 북한군 남하 → 낙동강 방어 → 인천상륙 → 서울 수복 → 국군·유엔군 북진 → 중국군 참전 → 전선 남하 → 재반격 → 38선 부근 교착 → 1951~1953년 전선 변화 → 정전. 자세한 시각·출처·자료 시점은 `STORYBOARD_12_SCENES.md`, 22개 자료 구간은 `STORY_80S_SOURCE_LEDGER.csv`에 있다. 지시서의 8개 감독 시간 구간과 원본 경계가 충돌하는 부분은 원본을 우선했다.

첫 60프레임은 사건 geometry 없음, 1,490프레임은 근사 도식 held-core, 마지막 850프레임은 자료 범위 내 부분 사료 전선이다. 8개 사료 날짜를 실제 출력에서 확인했다. 초기 사건의 공식 본문 검증 및 원본 지도 투영법·전체 위치 정확도는 미확인이다. 사건 날짜 확인을 정밀 전선 검증으로 취급하지 않았다.

## 화면의 큰 결함 3개

1. **사건과 지도 변화의 간격:** 20~45초의 인천·서울 수복·북진·중국군 참전 문구에도 부산 방어 도식이 유지된다. 10초/30초는 각각 5초/25초와 지도·카메라 상태가 같고 문구만 달라진다. 기존 데이터·geometry clock을 그대로 보존한 결과이며 스토리 완성으로 판정하지 않는다.
2. **전체 점령색·표식 부족:** 검증된 양측 전체 영토와 역사적 부대 위치가 없다. 청록 도식과 부분 전선만 사용했으며 반대편 영역, 국기·군대 이동을 지어내지 않았다. 강한 금빛 현대 국가 경계가 역사 전선과 혼동될 수 있다.
3. **국지 확대·연속 이동 한계:** 기존 Regional admission floor를 보존했다. 실제 최대 줌 약 1.269×, 고정 지명의 실제 투영 이동 최대 약 312.69px이나 더 가까운 확대와 회전은 차단된다. 사료 전선은 관측 시점의 hold/endpoint 전환이며 연속적인 역사 전선 이동을 증명하지 않는다.

65422의 기존 native 지도·지형 재질·V5·reference camera adapter는 재사용했다. 가상 시나리오의 scalar 영토·국기 좌표를 한국전쟁에 옮기지 않았다. 원본 full scalar compositor, 국가별 군대 표식, Flow 이동은 입력/소비자 부족 때문에 이 경로에서 완전 활성화되지 않았다. `RENDER_PATH_REUSE.md`와 151개 기능 적용표에 이를 명시했다.

## 수정과 검증

새 director namespace의 독립 실행·카메라 입력 연결·실제 PNG 캡처·출처 추적·검수 도구만 추가했다. 실제 시작 실패 2건을 보존했다. 중복 native headline 충돌은 기존 title reveal 선택으로 제거했고, 기존 native 확대 제한에 맞게 후보 프로필을 조정했다. 카메라·renderer·validator core를 수정하거나 admission을 우회하지 않았다.

집중 검사 25개 PASS. 기존 evaluator와 실제 25개 draw의 지리 geometry·alpha·상태 SHA가 모두 일치했다. 전환 첫 프레임 1500은 이전 NORTH_ADVANCE 상태이며 SEOUL_WITHDRAWAL은 목표 메타데이터임을 별도로 확인했다. 카메라 전역 2,400프레임의 native layout 계산에서 위반·source cropping은 0건이다. 이는 2,400장의 실제 렌더링이나 시각 품질 승인과 다르다.

검수 10항목은 **8 PASS / 0 FAIL / 2 UNKNOWN**이다. 역사 정밀도와 국가색·모바일 시각 품질은 미확인/사용자 검수 대기이므로 전체 완성 PASS가 아니다. 151개 기능 × 16프레임을 추적했고, 31개 기능의 소프트웨어 소비자를 관측했으며 24개 기능은 입력/소비자 부족을 명시했다. 모든 기능이 화면에 나타나거나 프롬프트로 호출된다는 주장은 하지 않는다.

기준 `3cd19dafe450666748ee16d4aed45c38b4fc65ed` 대비 새 namespace 밖 기존 파일 변경 0건. FINAL·Candidate·Scene·Asset·운영 이미지·기존 작업 기록 보존. Secret scan 공개 대상 0건. 필수 temp-only 파일 0개이며 기존 Git 자료에서 재생성하는 명령은 `EXACT_REPLAY_INPUTS.md`에 있다.

## 검수 자료

- `public-review/CONTACT_SHEET_4X4.png`: 실제 PNG 16장만 배열한 비교 이미지, 왼쪽 위부터 시간순.
- `public-review/FRAME_00_T000.png` … `FRAME_15_T075.png`: 변경하지 않은 실제 원본 출력.
- `public-review/ADJACENT_TRANSITIONS_3X3.png`: 인접 시점 3묶음, 개별 원본은 `adjacent/`.
- `FRAME_REVIEW_16.csv`, `CAMERA_AND_FRONT_TRACE.csv`, `FRAME_APPLICABILITY_151.csv`: 프레임별 기대/실제·카메라·기능 소비 증거.
- `handoff/`: 원본 PNG·검수 문서·소스 해시·실행 도구의 공개 허용 ZIP. 전체 private Scene, 원본 지도·PDF·Secret·raw diagnostic cache는 제외.
- 원격 게시 후 `reports/DOWNLOAD_VERIFICATION.json`에 commit 고정 익명 HTTPS 200·원본/다운로드 SHA 일치를 저장한다. 다운로드 주소 목록은 `DOWNLOADS.md`에 추가한다.

사용자는 실제 프레임을 검토하면 된다. 시각 승인 전에는 영상 제작·유료 GPU·FINAL 승격을 진행하지 않는다.
