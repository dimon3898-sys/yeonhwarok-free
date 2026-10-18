# 80초 작업 복구 준비 결과

**CPU_RECOVERY_PREPARED_ACTUAL_CACHE_ACCESS_REQUIRED**

전체 재렌더링을 하지 않는 복구 도구와180분 미래 정책 도구를 구현하고 무료 CI를 통과했다. 사용자의 실제80초 MP4 복구·캐시 보존·Dropbox 외부 다운로드는 아직 미확인이다. 실제 제작을 완료했다고 보고하지 않는다.

## 실제 조회와 남은 차단

- 대상: #5373 / `studio-bcd340f797498d7c9fea8181921f91b9`.
- 사용자 보고: FAILED, `STUDIO_APPROVED_DEADLINE_EXCEEDED`, 3600초, 12/12장면·2400/2400프레임.
- [읽기 전용 무료 Actions39090934940](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39090934940)에서 기존 Repository Secret 인증 성공. **2026-10-18 11:41:15 KST** Pod Running 확인.
- 공식 기존 SSH 등록 GET 결과가 없었다. SSH 등록·워크로드 변경·GPU 실행은 하지 않았다. 따라서 private STATE/JOB/cache/앵커와 Dropbox 마운트 파일을 직접 검사하지 못했다.
- Pod 로그 API404. CLI 로그는25초 제한까지 스트리밍됐지만 작업 기록의 실제 실패 단계·컨테이너 종료코드를 확보하지 못했다. CLI 스트림 제한 종료를 GPU/컨테이너 종료로 해석하지 않았다.

**캐시 보존 여부는 미검증이며, 유실됐다고 판단한 것도 아니다.** 코드에는 장면별 private cache와 Dropbox scene-recovery 체크포인트를 만드는 경로가 존재한다. 실제12개 파일과 retained private anchor가 남았는지는 접근 후 확인해야 한다.

## 원인 구분

원본 `studio_runtime._worker`와 하위 coordinator는 렌더링·장면 검증·무음 합성·SFX·최종 저장을 승인된 wall deadline에 포함한다. 완료 카운트가2400이어도 합성/검증/export 완료를 뜻하지 않는다. 실제 실패가 COMPOSE인지 SFX인지 다른 단계인지는 private STATE/JOB와 timing 증거가 필요하다. 기존 Resume는 원래 승인·비용·retry·deadline을 유지하므로 만료된 작업을10800초로 자동 갱신하지 않는다.

이번 무료 CI 드라이버에는 별도의 `/opt` 경로 오류를 확인해 수정했다. 얕은 설치 경로에서 존재하지 않는 `parents[2]`를 읽던 `IndexError`다. 이는 무료 검증 도구의 오류이며, 기존 #5373의3600초 실패 원인이라고 주장하지 않는다. 실패39091294752·39091582869도 숨기지 않고, 두 번째 실패 증거를 보존했다. 수정 후39091801710 전체 성공이다.

## 구현과 검증

`recover.py`는 기존 무음 완성본을 검증 후 우선 재사용한다. 없으면 전체 장면의 plan/frame 범위·cache key·native provenance·SHA를 검증한다. private cache가 없거나 손상되면 별도로 검증된 retained Dropbox 체크포인트만 사용할 수 있다. 공유 MP4/SHA만으로 새 역사·NVIDIA 출처를 만들지 않는다.

원본 compose/SFX/mux/export를 CPU로 재사용하고 원본 job·claim·approval·영상·cache를 보존한다. 새로운 CPU 승인 파일은 부모 job·plan·원래 승인 SHA·실제 만료에 고정하며 최대10800초, GPU 허용false, 추가 GPU 비용0, 재시도0이다. 실제 유료 호스트 과금까지 중지하는 승인은 아니다. 누락·손상·실행중 PID·미해결 claim은 차단하며 원래 GPU start/resume/render 호출로 넘어가지 않는다. 기존 Studio START.lock을 공유해 모바일 신규 작업 시작과의 경합도 차단한다. 별도 관리자가 직접 실행하는 외부 수동 launcher의 동시 실행을 자동 관리한다고 주장하지 않는다.

`policy.py`는180분을 **다음 신규 작업에만** 적용하도록 비활성 revision과 명시적 활성화를 제공한다. 기존 정책 원문과 과거 승인·retry ledger는 보존한다. 실제 요금·통화·최대 비용·재시도 상한은 늘리지 않는다. 기존 비용 상한이3시간 요금을 감당하지 못하거나 실제 승인 만료가 부족하면 차단한다. 현재 원격 정책 파일은 읽지 못했으므로10800초 원격 적용은 미완료다.

[무료 CI39091801710](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39091801710) 결과:

| 검사 | 결과 |
| --- | --- |
| 읽기 전용 수집기 | 10 PASS |
| CPU 복구 | 16 PASS |
| 미래180분 정책·비용·보존 | 24 PASS |
| SKIP/FAIL | 0/0, 최종 실행 기준 |
| 실제 FFmpeg 합성·SFX·전체 디코딩 | 80초·2400프레임·12장면, **64×96 TEST_ONLY fixture** |
| 기존 이미지 source hash 전후 | 동일: HTTPS21, Studio51, 엔진 inventory373 및 기존 proxy12 |
| Secret Scan | 고정 SHA Gitleaks8.24.3, 발견0 |
| GPU·새 이미지 build/push·유료 배포 | 0 |

실제 fixture 측정은 총5.211401초: 복사0.093886, 합성3.239015, 무음 export0.038245, SFX/최종 합성/export/검증1.790016초다. 검증된 기존 silent 재사용은1.696146초였다. **이 수치는 작은 합성 fixture의 CPU 검사이며 사용자의1080×1920 제작시간·GPU 성능·60분 목표 달성 근거가 아니다.** 사용자의 실제 단계별 병목은 미확보다. 도구는 실제 복구가 실행되면 단계 시간을 별도 새 기록에 저장한다.

## 필요한 최소 GPU 작업과 다음 행동

검증된 무음 MP4 또는 모든 장면·private 기록이 남았다면 **신규 GPU 렌더링0프레임**으로 CPU 합성·SFX·저장이 가능하다. 실제 데이터가 불완전하면 복구를 차단하고, 현재 도구가 임의로 GPU 재렌더링하지 않는다. 누락이 확인되기 전에 필요한 재렌더 장면 수를 추정하지 않는다.

다음 선행조건은 **현재 #5373의 공식 SSH 접속 경로 확보**다. 기존 토큰은 재사용 가능하다. 재배포·private 초기화 전에 캐시와 private 앵커를 보존해야 한다. 허용된 실행자의 공식 SSH 등록과 읽기 전용 파일 조회가 가능해지면 실물 해시 검증을 할 수 있다. SSH 등록은 현재까지 수행한 GET-only 조회와 구분되는 연결 설정 작업이다.

현재 모바일 Resume 버튼을 반복 눌러 원래 승인 제한을 우회하지 않는다. SSH 비밀번호·토큰·관리자 코드를 채팅으로 보내지 않는다. 실제 등록·읽기·보존·합성 절차와 기본 경로는 [RECOVERY_RUNBOOK.md](RECOVERY_RUNBOOK.md)에 기록했다. 새 GPU 이미지를 배포하는 것은 이 복구의 선행조건이 아니다.

## 저장

- 브랜치: `development/studio-80s-recovery-20261018`.
- 구현 체크포인트: `b54602e`, 검증 완료 소스: `d9cff9429ce78286881eb1a2533b1c0977047557`.
- CI 성공 증거 커밋: `6d5276d`.
- 원본 FINAL·렌더러·카메라·전선·이미지·기존 작업 파일 변경0건. 새 namespace와 새 workflow만 추가.
- 필수 temp-only 파일0. 원격 읽기 증거, 실패/성공 CI 증거, 소스·테스트·복구 절차·SHA는 이 branch에 영구 저장한다.
