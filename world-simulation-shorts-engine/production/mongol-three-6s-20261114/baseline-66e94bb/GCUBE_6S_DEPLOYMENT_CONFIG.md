# gCube #5373 — 차단된 배포 준비 기록

상태: **BLOCKED_NOT_APPLIED**. 새 설정 저장, 이미지 변경, 배포 시작, Studio 렌더링 모두 0회다. 최신 사용자 진술은 중지 상태다. 이번 작업에서는 gCube UI 상태를 새로 관측하지 않았으며, 이를 새 readback PASS로 표현하지 않는다.

## 과거 실제 성공 기준

- 이미지: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:g2-diagnostics-v1-27f9fa5c133a-40767632198`
- Digest: `sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da`
- GPU: RTX 4080 SUPER ×1, NVIDIA 580.159.03.
- CPU/RAM/스토리지 용량 및 현재 가능한 GPU 노드: 이 성공 기록에서 정확한 값 미확인. 임의 값으로 채우지 않는다.
- 과거 Studio 접근 주소: `https://ae20158c.service.gcube.ai:24999/`. 현재 접근 가능성은 검증하지 않았다.
- Chromium 선택 인수·sandbox·환경 관측값: `SIX_SECOND_GPU_SUCCESS_BASELINE.md` 참고. 기록되지 않은 EGL 환경을 임의 구성하지 않는다.
- 정식 입력 전달: Studio의 기존 structured input → Controller 검증 → Worker. 몽골 HISTORICAL 180은 이 단계에서 거부되므로 업로드 파일은 아직 없다.
- 출력: 각 formal job의 private `capture/VIDEO.mp4`, export `public/WORLD_ENGINE_STUDIO_VIDEO.mp4`. 세 job의 실제 독립 output ID 및 충돌 검사는 입력 생성 후에만 확정할 수 있다.

## 별도 후속 설정 증거 — 위 성공 환경과 혼합 금지

`release-guard/recovery-20261113/gcube-readback/GCUBE_SETTINGS_RECEIPT.json`은 required-fixes `8f7a…e329` 이미지가 중지 상태로 저장·재열기 된 기록이다. RTX 5090 ×1, 12vCPU, RAM 63GB, shm 3GB, 내부 포트 8080, `/world-storage`가 기록돼 있다. 이는 G2 RTX4080 성공 당시 사양이 아니다.

당시 정책은 1,300원/시간, 상한 2,000원, 최대 1,800초, 자동 재시도 0회였다. 현재 요금/3편 소요시간의 검증값이나 신규 실행 승인이 아니므로 이번 비용 견적에 전용하지 않는다. 현재 예상 비용은 확인 불가다.

## 다음 실행 게이트

1. 변경 없는 성공 이미지와 HISTORICAL 입력 간 호환성 차단 해결.
2. 정식 계약이 있는 세 JSON과 분할 상태 연속성 무료 검사 완료.
3. 그 결과에 맞는 이미지·manifest·digest 및 중지 상태 설정 readback 확보.
4. 그 뒤 사용자 별도 유료 GPU 시작 승인. 현재는 승인 요청 단계가 아니다.

향후 승인된 실제 실행에서는 각 편을 순서대로 실행·검증·다운로드하고 gCube 배포를 중지한다. 실패 시 자동 재시도 없이 배포 중지와 기존 로그 보존이 우선이다. 이번 문서는 실행 가능한 최종 설정이나 READY 선언이 아니다.
