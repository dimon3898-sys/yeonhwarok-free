# G2_GATE_DECISION

**G2 TECHNICAL_PASS / QUALITY_REVIEW_REQUIRED**

**G3 BLOCKED. 사용자 영상 승인 없음. FINAL 승격 없음.**

| 단계 | 결과 | 실제 근거 |
|---|---|---|
| PHASE A | PASS | 원래 Nepal의 폰트·앵커·네 후보·8px 경계 충돌과 Namibia 차이 추적 |
| PHASE B | PASS | 기존 Layout의 안전 검사를 그대로 사용하는 opt-in bounded gap 입력 확장, 미설정 시 기존 동작 유지 |
| PHASE C | PASS | 기존 101 + 추가 42 검사, skip 0. 5지역 실제 draw 20회·결정성·카메라/마스크·Layout 검사 통과 |
| PHASE D | PASS | 실제 인증 Studio → source normalizer → claim → detached worker → native renderer → FFmpeg. 6초·1080×1920·30fps·180프레임 H.264 무음 |
| PHASE E 기술 | PASS | 전체 180프레임 decode/PTS, 원본 카메라·영역·전선·마커 상태 180/180 동일, 검은 화면·누락 없음, 매 프레임 Layout 유효 |
| 보호 | PASS | 원래 307 SHA 일치. 기존 namespace 223개 및 캐시 235개 보존. 이전 복구 결과 포함 |
| 영상 품질 최종 | USER_REVIEW_REQUIRED | 실제 Studio MP4·전후 비교 PNG 증거 확보. 사용자 직접 영상 승인 전 PASS 처리하지 않음 |

## 경계 탐지 경고의 처리

고정 기준 vertical P99 `12.133750066757203`을 바꾸지 않았다. f133의 `12.166666984558105` 한 건을 경고로 보존했다. 실제 f132/133/134, 같은 위치의 기존 MP4와 원본 NE1 RGB를 독립 비교했다. 기존의 직선 재질 전환은 사라졌고, 해당 지점은 새 소스 내부의 연속된 산지·하천 명암이다. 새 소스 경계는 180개 실제 카메라 viewport 밖에 있다. 이 판단을 `INDEPENDENT_VISUAL_REVIEW.json`과 실제 crop PNG로 남겼으며 자동 경고를 삭제하거나 임계값을 낮추지 않았다.

0.25도 계단 형태는 원본 합성 영역 데이터다. smoothing이나 새 역사 좌표를 만들지 않았다. native 위치 라벨은 원래 기술 DEMO에서 숨긴 상태를 유지하며 입장·동적 배치 검사를 통과했다. 표시되지 않는 라벨의 픽셀 품질을 승인한 것으로 보고하지 않는다. 이전 재질 복구의 f0/f90/f179 raw PNG와 새 Studio의 같은 raw PNG는 3/3 bytes·SHA가 동일하다. 이는 세 시점의 보존 증거이며 이전에 없던 전체 180프레임 비교라고 과장하지 않는다.

## 실행·저장·다음 행동

- 실제 Studio job: `studio-ed20f92b16cf939f72cc078c24f217c7`, worker 측정 `209.255초`.
- MP4 SHA-256: `2aa3c8de7ad867863b7ec7d8f2ad60f6e93255c742cb631732c9d7a57fd41cc9`.
- 무료 CPU SwiftShader, source checkout 실행. NVIDIA·운영 OCI 이미지 실행·유료 GPU·유료 API·gCube 배포/변경 없음. 기존 gCube 과금 상태는 조회하지 않았다.
- 원격 체크포인트: 보호 `507c732`, 구현 `120da8d`, 범용 실제 draw `6bf9b2b`, 실제 MP4 `ae8631a`. 최종 보고·다운로드 검증도 새 브랜치에 저장한다.
- 사용자에게 필요한 일은 MP4와 전후 비교 이미지 검토다. gCube 환경변수·Secret 변경은 필요하지 않다.
- G3·80초·FINAL 등 다음 제작은 이번 작업에서 진행하지 않는다.
