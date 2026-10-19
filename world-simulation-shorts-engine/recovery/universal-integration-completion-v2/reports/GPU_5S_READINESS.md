# 유료 5초 검수 전 준비 상태

**현재 `NOT_READY_FOR_PAID_RENDER`. 이번 작업에는 유료 실행·GPU 배포·5초/80초 렌더 승인이 없다.**

| 항목 | 상태 | 다음에 필요한 실제 조치 |
|---|---|---|
| 후보 소스·manifest·고유 이미지 | CPU 및 독립 digest pull 검증 완료 | IMAGE_CANDIDATE.json과 동일 immutable digest 사용 |
| 기존 FINAL·Camera·Scene·Asset | 기존 파일 변경 0 | 계속 보존 |
| 80초 입력 | 정규화·소스 admission 완료 | full profile 모듈 gate는 별도이며 현재 BLOCKED |
| 고급 scalar·Detail·roll·역사적 부대/이동 | 미연결 또는 자료 부족 | 판정표의 정확한 누락 계약/자료를 먼저 해결; 가짜 보완 금지 |
| 150프레임 preview 범위 | 미구현 | 원본 전역 frame·상태·source signature를 보존하는 별도 제한 실행 어댑터와 CPU 시험 필요 |
| 비교 구간 | 미확정 | 실제 사건 진행과 시각적 변화를 검토해 동일 의미의 연속 구간 선정. 첫 장면은 최초 접근을 보존하므로 새 chapter tracking 검증에는 부족 |
| 65379 기준 파일 | 실제 보존·기존 전체 decode receipt 재사용 | 향후 실제 preview와 content 영역 기준 픽셀·시간 분석; 플랫폼 UI 제외 |
| 66430 이전 실제 출력 | 미확보 | 원본·SHA 확보 전 직접 비교는 BLOCKED |
| NVIDIA·WebGL2·VRAM·프레임 성능 | 새 후보 미검증 | 별도 승인 이후 실제 하드웨어 결과로만 판정 |
| 실제 GPU 요금·최대 비용 | 이번 작업에서 조회/승인하지 않음 | 당시 실제 단가·통화·비용 상한·시간·재시도 0 또는 승인 상한·만료 시각 명시 |
| Dropbox 외부 다운로드 | 새 결과 없음 | 기존 저장 어댑터를 사용하고 실제 외부 HTTP·다운로드 SHA를 별도 확인 |
| 5초 영상 사용자 품질 승인 | 없음 | 실제 비교 영상 제출 후 명시적 승인 필요 |
| 80초 제작 | 차단 | 위 준비·실제 5초 승인·기존 GPU admission/비용/중복 작업 gate 전부 통과 후만 가능 |

현재 80초 고정 prompt에 길이 5초를 넣어 preview를 만든다고 안내하지 않는다. 지원하지 않는 입력은 거부한다. 프레임 시작점을 바꾸면서 카메라·영토 상태를 처음부터 초기화하거나, 새로운 임의의 사건을 만들어 구간을 맞추면 안 된다.

향후 후보 실행 시 기존 인증·HTTPS Origin·관리자·운영 정책·이미지 digest 설정을 유지해야 한다. 새 `WORLD_ENGINE_COMPLETION_IMAGE_PROOF_JSON`은 독립 pull receipt의 **비밀정보가 아닌 JSON**을 기존 private tree에 고정하는 operator 전용 입력이다. prompt나 사용자 자기 선언으로 image gate를 통과시킬 수 없다. 기존 Secret과 작업 claim을 삭제하거나 초기화하지 않는다.

예상 시간·개선율·GPU 비용 수치는 이번 CPU 작업으로 확정하지 않는다. 컨테이너 시간 제한과 플랫폼 과금 중지는 별개이며, 이번 변경은 자동 배포·정지 기능을 추가하지 않는다.
