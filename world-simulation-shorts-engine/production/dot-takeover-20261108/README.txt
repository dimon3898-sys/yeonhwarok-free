WORLD ENGINE Dot generation3 인수 보존본 — 배포 불가

기준 HEAD: 667f453d80fcc2540f50a49af333fba90e292f77
새 브랜치: recovery/dot-generation3-intake-20261108
실제 상태: CHECKPOINT.json

archive/CODE_REVIEW_STAGE_generation3.zip.b64는 Dot 코드 검토 ZIP의 손실 없는 Base64 보존본이다. 디코딩한 ZIP의 SHA256은 7f87328586477424212c2546142c8bd26a2655ed61a59d4c3f5e81d9695bab2f, 크기는1,048,365 bytes이다.
복원 명령: base64 --decode archive/CODE_REVIEW_STAGE_generation3.zip.b64 > CODE_REVIEW_STAGE_generation3.zip

96개 저장소 파일(기준 대비 동일66/신규24/변경6), 별도 browser overlay16개, 출처 문서12개를 보존한다. 이는 실행 경로에 적용된 코드가 아니다. 원래 renderer/runtime과 기존 PASS·v16 이미지를 유지한다.
ZIP 153개 항목 중 명세에 기록된151개 파일의 크기/SHA256 일치 및 원격 Base64 회수 대조를 확인했다. 기존 시험은 다시 실행하지 않았다. 검사 성공 주장과 실제 기능 검토를 구분한다.

Dot 원본 /workspace/shared가 이 Work 환경에 없어 인벤토리 경로387개 중 접근0개이다. 런타임354경로(216고유객체,732,449,036 bytes), 추가 source-admission6개(23,880,454 bytes), registry(20,711,336 bytes), 최신 두 제출파일 및 추가 소스/증거가 누락되었다. 약856MB rehearsal 전체 수량과는 서로 범위가 다르다.

DOT_TRANSFER_REQUEST.json은 전달용 명세이며 Studio 렌더링 입력이 아니다. DOT_TRANSFER_INSTRUCTIONS.txt에 따라 원본 바이트를 회수한 뒤에만 목적지 재결속·독립 코드 검토·CPU 화면 검사·필요한 수정과 이미지 빌드 순서로 진행한다. 아직 새 배포 이미지와 실행용 입력은 확정되지 않았다.

최신 GitHub Actions의 성공 영상진단은42451652447/42451035648, 보존 이미지 빌드는42446481907이다. Dot 최신 개발분을 검증한 Actions 결과가 아니며 이번 인수로 Actions를 실행하지 않는다.
GPU 실행·Studio 렌더링·배포 시작/중지는 사용자 담당으로 유지한다.
