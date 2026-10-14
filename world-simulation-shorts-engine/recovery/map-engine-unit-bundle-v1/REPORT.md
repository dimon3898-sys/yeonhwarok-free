# MAP ENGINE / NATIONAL UNIT 5S CANDIDATE

기술 검사는 PASS이며 영상 품질은 **IMPROVED / NEEDS_REWORK**다. 사용자 영상 승인은 아직 없으며 최종 상태는 USER_VIDEO_REVIEW_REQUIRED다.

사용자의 명시적 선택에 따라 공개 영상은 기존 현대 가상 시나리오를 유지한다. ROK, US 현대 50성, DPRK, PRC, 현대 러시아 삼색기를 사용하는 표식 8개다. 실제 한국전쟁 재현으로 주장하지 않는다. 미국 48성·소련 국기 및 역사적 날짜/참전 역할 게이트는 별도 비공개 검사다. 소련 지상군 점령으로 표시하지 않는다.

기존 엔진에 실제 height/normal/lighting API와 비침습적인 재질 확장 경로가 있어 두 번째 엔진을 만들지 않았다. 해당 지역에 사용 가능한 한국 DEM은 없다. 기존 Natural Earth I의 허가된 원본 RGB를 사용하며 수에즈 높이 자료, RGB 추정 고도, 허위 depth, 레퍼런스 영상 배경은 사용하지 않았다. 따뜻한 지형 표현은 원본의 밝은 면에 적용하는 절제된 재질 색조로, DEM 기반 물리 조명으로 주장하지 않는다.

| 품질 항목 | 판정 | 실제 비교 결과 |
| --- | --- | --- |
| 지형 | 미달 | 과한 금빛 점을 줄였으나 거칠고 뭉친 능선 질감이 남음 |
| 바다 | 보완 필요 | 규칙적인 분석 줄무늬 제거, 수면·해안 세밀도 부족 |
| 금빛 조명 | 미달 | 절제된 따뜻한 면 표현, 목표의 입체적 지형 조명에 미달 |
| 움직이는 전선 | 보완 필요 | 실제 영토 경계만 연속 강조, 기존 64-knot 단순화 유지 |
| 카메라 | 양호 | 기존 카메라 트랙과 동일, 큰 점프·화면 모서리 잘림 없음 |
| 국가 표식 | 양호 | 국기 식별 개선, 작은 역할 glyph와 UI tablet 느낌은 남음 |

실제 출력 150프레임을 전부 디코딩해 각 RGB SHA/PTS를 기록했다. Root와 독립 검수자가 chronological contact 전체 및 5개 삼자 비교를 직접 확인했다. 실시간 30fps 재생 검수나 레퍼런스 동등 품질은 주장하지 않는다. 비교 순서는 레퍼런스 / 보호된 기존 65409 / 새 Candidate다. 구간은 기존과 같은 실제 레퍼런스 5.181813–10.181813초다. Source 전체 958프레임의 기존 검수는 원본 SHA 일치로 재사용하고, 이번에는 관련 151프레임과 이전 Candidate 150프레임을 새로 디코딩해 저장된 RGB와 일치시켰다.

원본 MP4는 1080×1920, 30fps, 150프레임, 5초, H.264, 무음이다. SHA-256은 `4f1b676baef6a4ba6fefbfd58a5d6b2e235fb57ada7d11cfd2baf827ec79f12e`다. 전체 오프라인 캡처/인코딩 wall time은 253.288초, 완료된 draw 평균 wall time은 884.423ms다. 실제 backend는 SwiftShader이며 하드웨어 GPU timer나 실시간 30fps 성능으로 해석하지 않는다.

전체 150프레임의 GL 오류, 검은/빈 프레임, 모서리 실패, Safe Area 위반, 표식 간 critical collision은 0이다. 같은 Camera/Control/Projection을 유지하며 새 국기 표식은 모든 프레임에서 한 개의 일정한 화면 offset만 사용한다. 원래 source anchors는 별도로 그대로 저장했다. 실제 군대의 측량 위치로 주장하지 않는다. 최소 전선 여유는 보수적인 표식 외접 영역 기준 12.384px다. 영상 안에 written words, arrows, routes는 없다.

원격 개발 브랜치는 `development/map-engine-unit-bundle-20261014`다. 보호된 parent는 `882bd8e939010962b40a81c268937e7f7e88bb62`이며 V5/Event/Flow/Area FINAL 및 모든 이전 Source/Candidate/데이터 파일 변경은 0건이다. 구현 A는 `6240c9f26947534b2972a8ed6eca05fafe993082`, 렌더 직전 Source B는 `61bdae3d16472d6926bf9cf3d20c78513d826579`, 원본 MP4 저장은 `d13f097c1bd592b315b6a8c28e7b3a0be9795a70`다. 각각 원격 일치를 확인한 후 다음 긴 단계를 진행했다.

Public Review에는 원본 MP4, 삼자 비교 PNG 5개, 실제 Scene JSON, SHA256SUMS만 포함한다. 비공개 flag sheet/Source/Diagnostic/내부 계획은 추가하지 않는다. 실제 immutable HTTPS GET 및 원본/Git/다운로드 byte와 SHA 확인 결과는 `evidence/HTTP_DOWNLOAD_VERIFY.json`에 저장한다. 원격 저장 확인은 `evidence/REMOTE_VERIFICATION.json`, 저장된 필수 파일 확인은 `evidence/PERSISTENCE_VERIFICATION.json`에 기록한다. 필요한 temp-only 파일은 0이며 캡처/다운로드 cache는 재현에 필요하지 않다.

독립 검수는 `evidence/FULL_MAP_MATERIAL_REVIEW.json`, `evidence/FULL_NATIONAL_UNIT_REVIEW.json`, 전체 Root 판정은 `evidence/WHOLE_VISUAL_REVIEW.json`이다. 두 정지 프레임 시도도 모두 보존했다. 추가 상세 데이터가 없는 위험한 물리 지형 분기는 시작하지 않았다. Permanent Gate, 14초 확장, FINAL 승격 및 다음 기능 개발은 수행하지 않았다.
