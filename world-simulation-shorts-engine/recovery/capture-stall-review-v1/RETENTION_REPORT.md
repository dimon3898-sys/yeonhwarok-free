# WORLD ENGINE — 캡처 기록 보존 인수 결과 (2026-11-05)

기존 캡처 기록기를 실제 worker의 `--export-root` 전달 경로에 연결했다. 마지막 작업 단계와 프레임은 private 경로에 원자적으로 기록하고, 기존 공유 저장소 어댑터를 사용하는 별도 helper가 진행률 변화와 무관하게 1초 주기로 안전한 스냅샷을 복사한다. 예외 발생이나 finally 실행이 없어도 이전에 복사된 기록을 회수할 수 있다.

소스와 무료 CPU 검증은 완료했다. 현재 운영 이미지에는 미적용이며, 실제 gCube 마운트의 외부 회수·GPU 캡처 정체 해결·레퍼런스 품질은 아직 검증하지 않았다.

## 신규 성과

- gCube 공식 지원 답변을 SUPPORT_RESPONSE.json에 보존했다. 삭제 컨테이너 private 파일과 stdout/stderr 회수 경로는 종료했으며, 정체 원인은 미확정으로 유지했다.
- 최신 품질 브랜치 b52e9367과 이전 Work의 11월 5일 증거를 대조했다. 남아 있던 미저장 연결 코드와 미실행 검증을 별도 복사본에서 이어받았다.
- PAGE_EVALUATION, DRAW, READBACK, PROOF_VALIDATION, PNG, ENCODER_WRITE, ENCODER_DRAIN, PROGRESS의 단계/프레임을 구분한다. 기존 브라우저 실행 옵션, FFmpeg 설정, 감독 제한 시간과 렌더링 결과 계약은 유지한다.
- FFmpeg drain 구독은 write 직후 설정해 기록용 await 때문에 이미 발생한 drain 이벤트를 놓치지 않도록 했다.
- 기록은 16 KiB 이하의 고정 스키마와 내부 SHA256을 가진 단일 파일이다. 공유 저장이 지연되면 helper만 종료하고 자동 재시도를 하지 않는다. GPU lease와 기존 정리 완료 조건은 그대로다.
- private 파일의 소유권/0700·0600 검사를 유지한다. 공유 경로는 기존 storage.py의 public-export 규칙을 재사용하여 FUSE의 합성 권한과 미지원 fsync를 private 보안 조건과 구분한다. 공유 fsync 미지원은 원격 영속성 증명이 아니다.

## 실제 변경 파일

| 파일 | 변경 |
|---|---|
| codex-to-gcube-handoff-v1/capture_vulkan.generated.mjs | 기존 단계 기록기 연결, 페이지·인코더·진행률 구분 |
| codex-to-gcube-handoff-v1/backend/capture_operation_diagnostics.mjs | 단계 보존, 허용된 작업 ID, 실패 프레임 유지 |
| codex-to-gcube-handoff-v1/controller/safe_capture_export.py | 정리 전에도 허용된 스냅샷만 공유 경로로 원자적 내보내기 |
| codex-to-gcube-handoff-v1/controller/capture_diagnostics_safe.py | 1초 주기의 제한된 저장 helper 관리 |
| codex-to-gcube-handoff-v1/controller/nvidia_worker.py | 진행률 변화와 독립된 helper 호출 |
| RUNTIME_SOURCE_MANIFEST.json, backend/GENERATED_SOURCE_MANIFEST.json | 변경된 소스 해시만 갱신; 기존 356행 유지 |
| studio-cold-start-v2/bootstrap.py, STARTUP_MANIFEST.json | 새 소스 manifest에 대한 기존 시작 체인의 해시만 갱신 |
| capture-stall-review-v1/tests, .github/workflows/world-engine-active-retention-cpu.yml | 새로 연결된 범위의 무료 CPU 검증 |

gcube-storage-fix-v1/storage.py는 기존 파일을 그대로 재사용했으며 수정하지 않았다. 전체 경로와 바이트/SHA256은 evidence/RETENTION_SOURCE_SEAL.json에 있다.

## 검증 결과

- 최종 유효 검사 20개: 최초 실행의 변경 없는 캡처 연결 8개 유지 + 공유 저장소 보완 후 저장 계약 6개 + 강제 종료·회수 6개.
- 실제 UID1000에서 Node 기록 → Python 저장 helper → SIGKILL → private 폴더 삭제 → 남은 파일 읽기와 SHA256 대조를 완료했다. 모의 정체/오류이며 GPU나 브라우저를 실행하지 않았다.
- 공유 폴더 0755/파일 0644, fsync 미지원, 실제 I/O 오류, 심볼릭 링크, 과대 기록, 저장 helper 정체를 검사했다. 오류 시 이전 정상 스냅샷이 보존된다.
- 첫 CPU 실행: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/41969700208
- 공유 저장소 변경 범위 실행: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/41970182375
- Dropbox /WORLD_ENGINE에 844바이트 진단 샘플을 실제 저장하고 별도 fetch로 JSON 내용과 내부 snapshot SHA256을 확인했다. 텍스트 추출은 끝 개행을 정규화하므로 원본 다운로드 바이트 SHA256을 검증했다고 주장하지 않는다. gCube 마운트를 통한 업로드 검증과는 별개다.
- 이미지 빌드 0, 이미지 게시 0, gCube 설정 변경 0, GPU 기동/렌더링 0, 과거 PASS 재실행 0.

## 남은 차단 원인과 다음 행동

운영 이미지에 미반영되어 있고, 현재 gCube 마운트를 통한 실제 저장·외부 회수는 확인하지 않았다. 기존 1/300 정체의 근본 원인도 미확정이다. 1초 표본 간격보다 짧은 마지막 단계나 저장 helper 자체가 실패한 이후의 기록은 보장하지 않는다. 추가 CDP/fsync 비용은 실제 GPU에서 미측정이다.

NEXT_GATE.json에 고정한 기존 품질 이미지와 9개 변경 파일을 기준으로 신규 이미지 단계를 준비한다. 별도 승인된 GPU 세션에서는 마운트→외부 회수부터 확인한 뒤 승인된 품질 작업을 한 번 실행하고, 실제 기록으로 정체 위치를 판별한다. 기본 10초 영상·라벨·지도·품질 Scene을 다시 만들지 않는다.
