# 65379 Reference Reproduction — User Review Candidate

31.813189초 압축 목표 레퍼런스 전체 958프레임을 실제 디코딩하고,
처음부터 마지막까지 시간순 Contact Sheet로 검수했다. 기존 14초 한국전쟁
Candidate는 비교 자료로만 보존했으며 재현 목표로 대체하지 않았다.
선정 구간은 정확히 5.181813–10.181813초이다.

5.0초·150프레임·1080×1920·30fps·H.264·무음 원본 MP4와 같은 상대 시각의
비교 PNG 5개를 생성했다. 출력 전체 150프레임도 실제 디코딩 후 시간순으로
검수했다. 실시간 30fps 재생 검수나 레퍼런스 동등 품질은 주장하지 않는다.

MP4: `WORLD_ENGINE_REFERENCE_65379_REPRODUCTION_5S.mp4`

SHA-256: `a9dd5e0280d302528c7bf68b7768593fe0f1820649a657e29f593ecab69ed7ba`

| 비교 항목 | 실제 결과 |
|---|---|
| 연속 영토색 | Purple 북진·Orange 같은 위치의 수축. 전체 영역 일괄 교체·화살표·Route 대체 없음 |
| 카메라 | 선택 구간의 측정 상대 zoom 1.1515×를 재현. C1 pan/zoom이며 약 6° roll은 미지원 |
| 시작 RGB 중앙값 | Reference Purple 89/38/154, 출력 88/37/153. Reference Orange 157/50/16, 출력 154/47/14 |
| 형태·위치 | 실제 국가 GIS 유지. 전진 경계는 근사이며 더 각지고 동부 위치에 차이가 있음 |
| 지형·바다 | 기존 Native 스타일을 보존하여 원본 녹색 위성 지형·청록 바다와 큰 차이가 있음 |
| 경계 Material | Orange 내부 띠는 제거됨. Purple 농도 차이와 밝은 내부 지지 영역 띠가 남음 |
| 선택 요소 | Reference 병력 배지·자막·휴대폰 UI 생략, 기존 Native Label 유지 |

화면 결함과 보호 검사는 통과했다. 보호 픽셀 범위는 실제 불투명 Glyph/Marker와
외곽·비공유 Native Boundary이다. 반투명 가장자리의 배경 의존 변화와 공유 내부
separator의 의도된 Material 교체는 별도 수치로 기록하며 전체 국가 Boundary나
모든 Marker 사각형의 RGBA 동일성을 주장하지 않는다.

기존 FINAL과 전체 원본 tracked 파일 2,866개는 보호된다. 새 개발 브랜치는
`development/reference-reproduction-20261014`, 실제 렌더 Source는
`312b335d5cc1e2a2e14470a3d0c70c52ba0f2015`이다. 실패 프레임 24의 검증 UV만
수정했으며 이미 검수한 정적 PNG 3개의 바이트는 동일하다. 기존 실패 기록과
프레임 캐시는 보존되어 있다. 완료된 분석·기능·데이터를 다시 만들지 않았다.

Public Review는 원본 MP4·비교 PNG 5개·정확히 실행된 Scene JSON·SHA256SUMS만
포함한다. 실제 원격 commit·HTTP 200·다운로드 SHA 일치는 별도 영구 기록
`evidence/HTTP_DOWNLOAD_VERIFY.json`과 `evidence/PERSISTENCE_VERIFICATION.json`에
저장한다. Source·Manifest·Diagnostics·전체 Reference 영상은 Public Review에 없다.

판정: 기술·기능 검수 PASS, Reference fidelity NEEDS_REWORK.

종료 상태: `USER_VIDEO_REVIEW_REQUIRED`. FINAL 승격과 다음 개발 단계는 실행하지 않는다.
