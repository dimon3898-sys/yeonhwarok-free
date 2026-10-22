# Studio 통합 결과 — 사용자 검수 대기

최신 Studio 소스의 인증된 HTTP 제작 경로에서 원본 65422 입력으로 **새로운 5초·150프레임 소프트웨어 영상**을 생성했다. 작업 `studio-cabdd833dbd67903da41f58a7993d9c3`는 브라우저와 HTTP 서버 연결 종료 후에도 완료됐으며 211.179초가 걸렸다. 실제 NVIDIA 또는 gCube 배포 검증은 아니다.

| 검사 | 실제 결과 |
|---|---|
| 입력 → 실행 | 기존 관리자 인증·Origin·CSRF를 재사용한 preflight → submission → consent/start claim → 원본 runtime 선택 → 독립 worker → draw/readPixels |
| 중복·재접속 | 중복 시작과 controller 재시작 모두 같은 작업 ID 유지 |
| 원본 소스 캡처 비교 | raw RGBA 및 PNG 해시 150/150 일치. 카메라·회전·scalar 영토·전선·지형·presentation·국가 표식·보호 상태도 150/150 일치 |
| 실제 MP4 | 1080×1920, 30fps, H.264, 150프레임, 5초, 원본처럼 무음 |
| 인코딩된 원본 MP4와 비교 | 픽셀 동일하지 않음. 최초 차이는 f0, RGB MAE 1.00307/255, PSNR 43.97386dB, RGB uniform-7 SSIM 0.980716 |
| 최종 판정 | 소스 경로의 G1 렌더 후보 확보. 엄격 비교의 `REPRODUCTION_NEEDS_REWORK`를 유지하며 사용자 품질 승인을 대신하지 않음 |

새 MP4의 SHA-256은 `3b68fead7b9b79e8671f91afa24a7f04bd687f69e1d836f5f50c4f103bf78041`이다. 원본 MP4는 `f3de1bdf9244171a47c6e5eccca6aae1370f58d8bf4721a7658b6bca2eed2ef6`이다. 새 영상은 이전 복원본을 복사하거나 재인코딩한 증거가 아니라 이번 작업의 새 캡처 receipt와 프레임별 해시로 추적된다. 디코딩된 MP4의 차이를 원본 소스 캡처 일치와 혼동하지 않는다.

기존 151개 기능 표와 53개 원래 미연결 항목은 그대로 보존했다. 참조는 `recovery/astra-event-director-v2/reports/FEATURE_STATUS_151.csv`와 `FEATURE_STATUS_SUMMARY.json`이며, CSV SHA는 `ac9ab4ff5c800d36c41359d5ce55908d78513dfe20ba30e1a89112fbb36cac37`이다. 이번 가상 시나리오의 G1 캡처 증거를 한국전쟁 80초의 역사 영토·표식·음향 검증으로 승격하지 않았다. 기능별 기존 분류와 남은 항목은 `../reports/REUSE_AND_REMAINING.json`에 연결했다.

인천·서울 공식 지도 원문은 재사용·검토했지만 실제 양측 통제면의 시작·종료, 독립 지리등록, 전환 대응관계와 LOCAL 카메라 admission은 부족하다. 범용 CPU control provider를 구현하고 32개 집중 검사를 통과했으며, 하나의 상태에서 owner·unknown·contested·공유 전선을 평가한다. 합성 fixture의 성공은 역사 자료 승인이 아니다. **G2_BLOCKED이며 G3 역사 영상은 렌더하지 않았다.** 부분선을 해안으로 닫거나 부산 도식·현대 국경·가상 65422 영토로 대체하지 않았다.

제목 점프는 프레임마다 달라지는 기존 보호 장애물을 기준으로 위치를 다시 선택하는 경로에서 확인했다. 기존 Layout·Occlusion을 보존한 범용 고정 예약 planner를 추가했다. 실제 보관된 f640–642의 CPU guard 재생 검사는 통과했지만, 전체 chapter-04의 200프레임 중 실제 context가 101개뿐이다. 전체 장면 admission과 실제 동일 입력 재렌더는 차단돼 있으며 **화면에서 고쳤다고 보고하지 않는다.**

12개 역사 사건 프로필과 원래 80초 Scene은 변경하지 않았다. 전쟁 발발 → 남하 → 낙동강 → 인천 → 서울 → 북진 → 중국군 개입 → 남하 → 재반격 → 교착 → 협상 → 정전의 사건 ID와 0–2400 전역 프레임을 보존했다. 전체 양측 통제 상태·전환·역사 표식의 빈 자료를 채워 넣지 않았다.

원래 보호 파일 307개(318 manifest 항목)는 변경 0건이다. 기존 영상·캐시·claim은 삭제하거나 덮어쓰지 않았다. 새로운 이미지·배포·유료 GPU·전체 80초 MP4·FINAL 승격은 수행하지 않았다. EVIDENCE.zip은 32MiB 도구 제한으로 읽지 못했고, 64306 원본도 이번 환경에서 접근되지 않았다. 기존 분석 인용과 실제 새 검증을 분리했다.

다음 단계는 제공된 G1 MP4와 비교 PNG의 사용자 검수다. 역사 G2의 근거 자료와 전체 장면 layout context가 확보되기 전에는 인천 연속 영상이나 80초 제작을 시작하지 않는다. **USER_REVIEW_REQUIRED**.
