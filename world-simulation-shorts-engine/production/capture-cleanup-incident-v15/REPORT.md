# 158/300 UNRESOLVED_CAPTURE_CLEANUP — 증거 감사

2026-11-08 KST. 기존 v14 CHECKPOINT와 HEAD a57c9418824ca84604a90ffbbd4933f2ca652311을 먼저 확인했다. 이전 PASS를 재실행하지 않았다. 현재 원인은 **BLOCKED / 미확정**이며 이미지와 배포 설정을 변경하지 않는다.

## 새로 확인된 사실

- v14로 gCube 배포와 Studio 기동이 이루어졌고 실제 작업이158프레임까지 진행했다. 따라서 v13의 기동 전 고정 해시 불일치와 이번 오류는 같은 단계가 아니다. 전체 GPU/MP4 PASS는 아니다.
- 작업ID studio-b5687598139382feecef4973b903f86a.2장면 중1장면,300프레임 중158,경과134.34975125221536초가 사용자 화면에 보인다.
- 외부 Dropbox에서 해당 CAPTURE_CHECKPOINT를 회수하고 canonical snapshot SHA256을 확인했다.12:56:00.850에 frameIndex158의 DRAW START,renderedFrames158,sequence2765다. firstFailure/cleanupFailure/storageError는 null이다. nativeProofCompleted=true도 전체 MP4 기술검증을 대신하지 않는다.
- 해당 작업의 외부 진단 폴더는 없었다. 이번 배포 시각 이후 새 export 폴더5개를 확인했으며 storage-preflight JSON만 있고 MP4는 없었다. 삭제된 컨테이너의 private 원문을 회수할 수 있다고 주장하지 않는다.
- 조사 시작 때 워크로드는 실행 중이었고, 웹 터미널은 셸 프롬프트 뒤 곧 연결 종료가 표시됐다. 명령은 실행하지 않았다. 이후 사용자가 중지한 종료·노드 미할당 상태를 확인했다. Work는 시작/중지하지 않았다.
- 보존 모니터링을12:50~13:00,1분 간격으로 조회했다. 표시 최대값은 GPU3%,GPU메모리0.4GB,CPU4%,메모리2.9GB다. 샘플 사이의 순간 증가나 개별프로세스 OOM·드라이버 오류는 이것만으로 배제할 수 없다.

## 코드상 정확한 의미

배포 manifest와 로컬 소스 SHA를 대조해 nvidia_backend.py,lease_supervisor.py,capture_diagnostics_safe.py,safe_capture_export.py,process_guard.py가 같은 바이트임을 확인했다. 이는 소스 식별이며 과거 기능 PASS 재실행이 아니다.

nvidia_backend.py의 studio_status는 RUNNING/QUEUED 상태에서 state.pid의 /proc/stat을 읽어 startTicks 일치와 zombie가 아님을 확인한다. PID/시작정보 누락,읽기 실패,PID 소멸,시작시각 불일치,zombie 중 어느 경우든 같은 HANDOFF_UNRESOLVED_WORKER_OR_DESCENDANTS를 반환한다. 따라서 화면만으로 실제 worker 사망, GPU 오류, 잔존 자식 프로세스를 확정할 수 없다. 이 응답은 ACTIVE claim을 유지하며 새로운 작업을 허가하지 않는다.

또한 worker가 초기에 state를 읽고 launcher가 뒤에 PID/시작정보를 게시하는 순서가 있다. launch.json 존재 후 state를 다시 읽지 않는 부분은 식별정보가 오래될 수 있는 검토 대상이나, 이번 state.json이 없어 그 상황이 실제 발생했다고 주장하지 않는다. 근거 없이 이 가능성만으로 수정 이미지를 게시하지 않는다.

## 확인된 진단 보존 한계

현재 ActiveCheckpointMirror는 worker 안에서 실행되고 캡처 operation checkpoint만 외부에 기록한다. preserve_before_cleanup은 이름 그대로 로컬 private pending 진단만 기록한다. 전체 CAPTURE_DIAGNOSTIC 외부 내보내기는 cleanupVerified=true 뒤에만 허용된다. 정리가 미확인된 이번 분기에서는 종료 원인 원문/프로세스 식별정보가 외부 체크포인트에 포함되지 않는다. 외부 진행기록 보존은 확인됐지만 모든 오류 원인까지 영구 보존된 것은 아니다.

이 보존 한계는 확인됐으나 원래 안전장치나 lease를 해제해서 우회하지 않는다. 새로운 레코더,한국전쟁 전용 생성기,영상 편집,자동 재시도를 도입하지 않는다.

## 남은 차단과 다음 최소 작업

직접 원인을 좁히려면 이번 시각의 worker 상태/종료정보 또는 플랫폼이 이미 보존한 OOM·SIGKILL·GPU Xid·Pod 이벤트가 필요하다. 원문이 삭제된 경우 복구를 반복하지 않는다. SUPPORT_REQUEST.txt는 기존 플랫폼 메타데이터만 묻는 문의 초안이며 전송하지 않았다.

플랫폼 증거가 없다고 확인되면, 후속 최소 코드 범위는 기존 상태 확인 분기의 생존확인 실패 사유와 읽을 수 있는 기존 supervisor/browser 진단 요약을 기존 영구 체크포인트 경로에 연결하는 것이다. 실제 worker 종료 원인을 모르는 상태에서 임의 GPU 설정/시간 제한/렌더러 변경이나 유료 재실행을 권하지 않는다. 현재는 이 증거 게이트에서 BLOCKED다.

유지된 PASS: 기존10초 기본MP4,한국전쟁 데이터/Scene 사전검사,v13 JSON 경계10개 검사,v14 시작 경계 검사. 신규 GPU0,렌더0,이미지빌드0,기존PASS재실행0. PART_02 및20초 합성은 PART_01 실제MP4 성공 뒤에만 진행한다.
