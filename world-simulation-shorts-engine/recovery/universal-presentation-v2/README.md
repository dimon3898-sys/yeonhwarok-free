# WORLD ENGINE 범용 입력·연출 V2

**무료 source-checkout 기술 PASS / USER_REVIEW_REQUIRED.**

기준 `b0d0138`의 G1·G2·기존 생성기·FINAL은 보존했다. 자연어와 제공 자료를
연결하고, 실제 지도 소스 범위 안에서 카메라·경로·영토·표식·CUT를 실행했다.
기존 298개 + 새 핵심 205개 검사가 PASS이며, 실제 Studio에서 다음 3종을
각각 1080×1920·30fps·6초·180프레임으로 제작했다.

- [유럽 항공 연결 MP4](public-review/UP2_AVIATION_EUROPE.mp4)
- [남미 무역 연결 MP4](public-review/UP2_TRADE_SOUTH_AMERICA.mp4)
- [아프리카 가상 영토 MP4](public-review/UP2_FICTIONAL_AFRICA.mp4)
- [실제 프레임 비교](public-review/STUDIO_THREE_TOPIC_CONTACT_SHEET.png)
- [최종 보고서](FINAL_REPORT.md), [입력 예제](SUPPORTED_INPUT_EXAMPLES.md)
- [전체 검수 ZIP](review-package/WORLD_ENGINE_PRESENTATION_V2_REVIEW.zip), [SHA256SUMS](SHA256SUMS)

540프레임 전체 디코딩·입력/Scene/픽셀 대응 검증을 마쳤다. 307개 보호 파일과
기준 6,439개 SHA가 일치하고 기존 캐시도 보존됐다. 직접 본 프레임의 범위와
시각적 한계는 [시각 검수](VISUAL_OBSERVATIONS.md)에 구분했다.

자연어는 제한된 한국어·영어 문법과 첨부 자료 기반이다. 자료·좌표·역사적
사실을 임의 생성하지 않는다. 기존 배포 Studio의 textarea와 운영 이미지는
이번 작업에서 변경하지 않았다. 실제 실행 범위는 인증된 Studio API와 분리
worker를 사용하는 새 무료 source-checkout 프로필이다.

SwiftShader 검증이며 NVIDIA·최종 영상 품질 PASS가 아니다. 유료 GPU·API·배포,
80초 제작·역사 G3·FINAL 승격은 실행하지 않았다.

다운로드의 실제 HTTPS·HTTP 200·SHA 검증은 ZIP 생성 후 최종 원격 기록
[DOWNLOAD_VERIFICATION.json](reports/DOWNLOAD_VERIFICATION.json)에서 확인할 수 있다.
