# 검증된 모바일 다운로드

다음 고정 커밋의 파일을 실제로 다운로드했다. 모든 파일 HTTPS·HTTP 200·SHA-256 일치.

산출물 커밋: `ebef78299bf1742113c1768c641a12785b9a707d`. 최종 다운로드 검증 기록은 이 파일과 같은 최종 저장본의 `reports/DOWNLOAD_VERIFICATION.json`이다.

| 파일 | 실제 다운로드 바이트 | SHA-256 |
|---|---:|---|
| [유럽 항공 연결 · 6초](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/ebef78299bf1742113c1768c641a12785b9a707d/world-simulation-shorts-engine/recovery/universal-presentation-v2/public-review/UP2_AVIATION_EUROPE.mp4) | 2,106,637 | `cec3447d1f2b932bc2c55de5156300194f30eb7ed806f6732fbfdde2fe53a8b8` |
| [남미 무역 연결 · 6초](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/ebef78299bf1742113c1768c641a12785b9a707d/world-simulation-shorts-engine/recovery/universal-presentation-v2/public-review/UP2_TRADE_SOUTH_AMERICA.mp4) | 3,123,729 | `28befce9d5ff11d05e5f9f4e989e1d16b278b1489386710b8a06cc74bd7bf1dc` |
| [아프리카 가상 영토 · 6초](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/ebef78299bf1742113c1768c641a12785b9a707d/world-simulation-shorts-engine/recovery/universal-presentation-v2/public-review/UP2_FICTIONAL_AFRICA.mp4) | 2,542,642 | `c831b90282022ce58b7112b06498018a4227830cbceca11866e9d7c99440caf6` |
| [24개 실제 프레임 비교 PNG](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/ebef78299bf1742113c1768c641a12785b9a707d/world-simulation-shorts-engine/recovery/universal-presentation-v2/public-review/STUDIO_THREE_TOPIC_CONTACT_SHEET.png) | 3,117,768 | `2212d2df7e9a2edc05ea265920f11006fb29a7fdcea6d8869db6eeabb31806a7` |
| [전체 검수 ZIP · 약 68 MB](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/ebef78299bf1742113c1768c641a12785b9a707d/world-simulation-shorts-engine/recovery/universal-presentation-v2/review-package/WORLD_ENGINE_PRESENTATION_V2_REVIEW.zip) | 68,161,963 | `d131c85e2aab88f66bed018d1a38c07aa5c889b78e4e37008b3cbbf8ed95f9c5` |
| [MP4·비교 PNG SHA256SUMS](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/ebef78299bf1742113c1768c641a12785b9a707d/world-simulation-shorts-engine/recovery/universal-presentation-v2/public-review/SHA256SUMS) | 378 | `8a0eb991b56fdf869645cd00a77a20ff27613c12399d8014d0fb68fd1b2cfb1a` |
| [ZIP 포함 전체 주요 산출물 SHA256SUMS](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/ebef78299bf1742113c1768c641a12785b9a707d/world-simulation-shorts-engine/recovery/universal-presentation-v2/SHA256SUMS) | 555 | `2487c5eeea6fcd19deccdb146296f99d19b36aa623d1e2ef089bd3df4d257469` |

세 영상은 실제 Studio API·분리 worker·CPU SwiftShader 출력이다. 현재 배포된 운영 이미지나 기존 textarea는 변경하지 않았다.

ZIP은 HTTPS readback 이전에 생성한 기술 검수 snapshot이다. 이후 다운로드 검증·모바일 브라우저 재생 검증의 최신 기록은 최종 GitHub 저장본의 `reports/`에 별도로 추가한다. ZIP과 MP4는 검증 후 수정하지 않았다.

Android 모사 Chromium에서 세 파일을 끝까지 재생하고 탐색·재생을 확인했다. 각 180프레임 디코딩, 드롭·손상 0이며 실물 휴대폰 검사는 아니다. 근거: `reports/MOBILE_BROWSER_PLAYBACK.json`.

**USER_REVIEW_REQUIRED.** 유료 GPU·80초 제작·FINAL 승격은 실행하지 않았다.
