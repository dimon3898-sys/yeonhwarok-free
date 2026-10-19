# 통합 후보 공개 저장·다운로드 검증

成果物固定コミット: `1fdf3570a10898bd98428fcba9fc1b39eda8160b`。ブランチ: `development/universal-integration-v1-20261019`。

## 휴대폰 검토 자료

- [전체 ZIP](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1fdf3570a10898bd98428fcba9fc1b39eda8160b/world-simulation-shorts-engine/recovery/universal-integration-v1/WORLD_ENGINE_UNIFIED_INTEGRATION_V1_20261019.zip)
- [읽기 안내](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1fdf3570a10898bd98428fcba9fc1b39eda8160b/world-simulation-shorts-engine/recovery/universal-integration-v1/README.md)
- [151개 기능 판정 CSV](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1fdf3570a10898bd98428fcba9fc1b39eda8160b/world-simulation-shorts-engine/recovery/universal-integration-v1/reports/FEATURE_DECISIONS_151.csv)
- [53개 미연결 검토 CSV](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1fdf3570a10898bd98428fcba9fc1b39eda8160b/world-simulation-shorts-engine/recovery/universal-integration-v1/reports/UNWIRED_REVIEW_53.csv)
- [V2 프롬프트 명세](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1fdf3570a10898bd98428fcba9fc1b39eda8160b/world-simulation-shorts-engine/recovery/universal-integration-v1/PROMPT_V2_COOKBOOK.md)
- [검증된 입력 JSON](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1fdf3570a10898bd98428fcba9fc1b39eda8160b/world-simulation-shorts-engine/recovery/universal-integration-v1/fixtures/V2_80S_PROMPT.json)
- [80초 전체 coverage CSV](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1fdf3570a10898bd98428fcba9fc1b39eda8160b/world-simulation-shorts-engine/recovery/universal-integration-v1/reports/TIMELINE_80S_COVERAGE.csv)
- [ZIP SHA-256](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1fdf3570a10898bd98428fcba9fc1b39eda8160b/world-simulation-shorts-engine/recovery/universal-integration-v1/DOWNLOAD_SHA256SUMS.txt)

공개 자료 33개를 실제 HTTP 200으로 내려받았으며, 모든 다운로드의 SHA-256이 원본과 일치했다. ZIP 내부 파일별 SHA도 검증했다.

ZIP SHA-256: `76cabf54d436883438da6b1a10b33aa58a947149265d0d707190fae7dac771a4`

## 저장 및 판정

구현 체크포인트는 `756c20cb63e6a4b8e6a7bfe2cc8930cecec1d22b`이며 원격 저장을 확인했다. 이 publication receipt는 ZIP 생성 뒤 별도 커밋으로 저장하므로 ZIP 안에는 포함하지 않는다. 필수 temp-only 파일은 0이다.

151개 판정: SUPPORTING 87 / BLOCKED 22 / UNVERIFIED 27 / NOT_APPLICABLE 15 / APPLIED 0. 집중 CPU 검사 132개 PASS이다. 이 결과는 실제 영상 적용이나 영상 품질 PASS가 아니다. 기존 FINAL/Candidate와 원본 렌더러·카메라·전선·데이터·운영 이미지 변경은 0이다.

새 이미지 빌드·실제 NVIDIA 실행·5초/80초 렌더링·유료 배포·FINAL 승격은 수행하지 않았다. 현재 gCube 운영 이미지는 새 V2 계약을 포함하지 않는다. 현재 화면에 V2 JSON을 넣거나 제작 시작을 누르지 않는다.

역사 데이터, 고급 전선/Detail/카메라 연결 등 남은 차단은 별도 보고서에 보존했다. 차단 해결과 신규 이미지 검증 후 현재 요금·비용 상한을 확인하여 5초 GPU 실행을 별도 승인해야 한다. 실제 5초 레퍼런스 비교 및 사용자 품질 승인 전에는 80초 제작을 허용하지 않는다.

**UNIVERSAL_INTEGRATION_PARTIAL_BLOCKED / USER_APPROVAL_REQUIRED**

지금 사용자에게 필요한 작업은 자료 검토뿐이다. 새로운 Secret 설정이나 GPU 실행 승인을 현재 요청하지 않는다.
