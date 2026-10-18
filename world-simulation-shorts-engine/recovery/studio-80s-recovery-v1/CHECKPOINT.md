# 80초 deadline 복구 구현 체크포인트

대상은 #5373의 `studio-bcd340f797498d7c9fea8181921f91b9`다. 사용자 보고는 FAILED / STUDIO_APPROVED_DEADLINE_EXCEEDED / 12장면·2400프레임 완료다. 실제 MP4·캐시 파일 검증과 이 상태 보고를 구분한다.

2026-10-18 11:41:15 KST 공식 인증 읽기 전용 조회(무료 Actions39090934940)에서 workload deploy / Pod Running을 확인했다. 기존 SSH 등록 GET 결과가 없으므로 private 작업 파일 검사를 실행하지 않았다. Pod 로그 API404, CLI 로그는25초 스트림 제한으로 종료됐으며 실제 job phase/timings/cache bytes는 확보하지 못했다. SSH 등록·재배포·렌더링·파일 변경은0건이다. 캐시가 없어졌다고 결론 내리지 않는다.

원본 코드는 장면별 private cache와 Dropbox scene-recovery 체크포인트를 만들며, 후자는 private trust anchor가 있어야 검증된다. 장면 완료 카운트만으로 원본 bytes 보존이나 최종 MP4 완료를 주장하지 않는다. 전체 렌더→합성→SFX→내보내기가 기존 승인 deadline 안에 있으므로 원인 단계는 실제 private STATE/JOB 기록이 필요하다.

새 `recover.py`는 명시적 별도 CPU-only grant로만 실행한다. 검증된 기존 silent export를 우선 재사용하고, 없으면 검증된 전체 장면만 CPU 합성한다. cache가 없거나 손상되면 별도로 검증된 retained Dropbox checkpoint만 대체할 수 있다. 원본 job/approval/claim은 수정하지 않는다. 누락·해시 오류·실행중 PID·미해결 claim은 차단하고 GPU render/start/resume fallback은 없다. 기존 compose·SFX·mux·Dropbox 어댑터를 재사용한다.

`policy.py`는 다음 신규 작업에만10800초를 적용하는 versioned 정책 staging/명시적 activation 도구다. 기존 요금·비용·재시도 상한을 늘리지 않고 원본 validator를 재사용한다. 기존3600초 job 승인·retry ledger는 유지한다. 실제 기존 비용 상한이3시간을 감당하지 못하거나 실제 승인 만료가 충분하지 않으면 차단한다. 현재 gCube 정책은 접근 불가로 변경하지 않았다.

로컬 집중검사49개 PASS: 복구15, 미래 정책24, 읽기 전용10. 실제 FFmpeg로80초·2400프레임·12장면 합성 및 SFX·export를 실행했지만 **64×96 합성 fixture**이며 사용자의1080×1920 영상 복구나 NVIDIA 검증이 아니다. 최종 무료 CI와 보호/Secret/SHA 증거는 후속 보고에서 확정한다. 기존 FINAL·렌더러·카메라·전선·이미지는 변경하지 않는다.
