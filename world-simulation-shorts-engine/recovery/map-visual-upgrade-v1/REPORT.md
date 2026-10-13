실제 5초 사용자 검수용 Candidate를 생성했다. 1080×1920, 30fps, 150프레임, H.264, 무음이다.

Technical PASS와 영상 품질을 구분한다. 종합 영상 품질은 QUALITY_NEEDS_REWORK이며 USER_VIDEO_REVIEW_REQUIRED에서 멈춘다.

- 기존 FINAL과 저장된 65406의 모든 파일, GIS, 64-knot 영토 진행, 카메라, 8개 유닛 anchor/rotation을 보존했다.
- 실제 NE1 음영·녹색·제한된 금빛 밝은 지형 표현, 파란 바다 계조와 작은 수면 표현, 일관된 Purple, 실제 공유 전선의 얇은 빛, 독창적인 전신 infantry를 새 격리 계층에 구현했다.
- Source 구간 151프레임 및 이전 Candidate 150프레임을 새로 디코딩하고 기존 RGB와 일치 확인했다. 최종 MP4 150프레임 전체와 정렬 비교 5장을 실제 시간순으로 검수했다. 네이티브 30fps 재생 검수는 주장하지 않는다.
- 지도 질감·금빛 조명과 바다의 자연스러움은 목표보다 부족하다. 한국용 상세 DEM은 없으며 RGB에서 가짜 높이나 새로운 지리를 생성하지 않았다.
- 영토 색상과 진행은 읽히지만 기존 전선 형태는 레퍼런스보다 거칠다. 첫 약 1.1초 일부 infantry가 전선을 가린다. Source-art 투영 근사에서 opaque core overlap 72 unit-frames, 단일 유닛 최대 약 39.45px centerline 가림이 추정됐다. 이는 실제 GPU 픽셀 정밀 측정이 아니며 기존 Marker/Label 보호 충돌 0과 별개다.
- 아이콘은 원본 badge/국기/insignia를 복제하지 않았다. 모바일에서 존재감과 faction 구분이 약하며, 기존 해안 부근 anchor가 전신 infantry 표현에서 떠 있는 것처럼 보일 수 있다.
- 카메라가 Source B와 이전 Candidate에서 변경되지 않았고, 출력 PTS 150개가 30fps로 연속한다. SwiftShader offline capture 평균 약 907ms/frame이므로 실시간 렌더 성능 PASS를 주장하지 않는다.

원본 MP4 SHA-256:
`0630ab5c5e5e362d1a74ef65fd6041482d30f0ae1b12daa7f3f99490983c0772`

개발 브랜치: `development/map-visual-upgrade-20261014`.
구현 저장: `9e46d72ff533c45e1710c68f88b78f6a47ee859c`.
렌더 Source 저장: `d801c24b351641e3dc15b51a99a838a291da59b0`.

Public Review에는 새 원본 MP4, 비교 PNG 5개, 실제 실행 Scene JSON, SHA256SUMS만 둔다. 각 URL의 실제 HTTP GET·원본/Git/다운로드 SHA 결과는 private `evidence/HTTP_DOWNLOAD_VERIFY.json`, 원격 저장 결과는 `evidence/REMOTE_VERIFICATION.json`에 기록한다. Source/Fixture/Asset/Dependency/Import/Hash Manifest와 재현 안내를 영구 저장한다. Required temp-only files = 0.

14초 확장, Planner FINAL, 기존 FINAL 변경, 다음 개발 단계, 사용자 승인 전 승격은 실행하지 않았다. 사용자 검수를 기다린다.
