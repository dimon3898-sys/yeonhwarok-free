# 300/300 이후 JSON_SIZE_INVALID — 2026-11-08

## 이번에 확보한 증거

- 사용자 화면: 작업 `studio-06ff7116b2bb6c464a64c1a576f3faf0`, FAILED,2/2장면,300/300프레임,242.122724885121초,`JSON_SIZE_INVALID`.
- 영구 저장소의 해당 작업 CAPTURE_CHECKPOINT와 CAPTURE_DIAGNOSTIC를 회수했다. 진단 파일의 SHA256 및 체크포인트 내부 snapshot 해시가 일치한다. 새 실제 작업에서 외부 Dropbox 회수까지 확인된 증거다.
- 작업의 sourceInputSHA256 `ffc9cf86546776b36f3909d278114a7a064f0f15832412964a474f48691a257f`는 기존 PART_01의 canonical JSON SHA256과 일치한다. 입력 파일은 바꾸지 않는다.
- 마지막 기록은 frameIndex299, renderedFrames300, nativeProofCompleted=true, 마지막 PROGRESS END다. capture process exitCode0, supervisor cleanupVerified=true다.
- gCube에서 RTX5090/driver580.126.09/CUDA13.0.0이 표시됐다. 이후 종료·노드 미할당을 확인했다. Work는 시작·중지를 수행하지 않았다.
- 해당 작업 진단의 저장 시각11:52와 gCube 최신 배포 시각11:56은 다르다. 작업ID가 일치하는 증거로만 원인을 판단하며, 실패를 이후 배포에 임의로 귀속하지 않는다.

## 확정한 코드 경계와 남은 불확실성

기존 `universal-auto-video-v2/cache.py`의 JSON 읽기 상한은32MiB다. 정식 worker는 캡처 프로세스가0으로 종료된 뒤 `_validate_capture()`에서 CAPTURE_RECEIPT와 FRAME_EVIDENCE를 이 작은 문서용 reader로 읽는다. 실패 시 최종 export에 도달하지 못한다.

기존에 보존된 실제 진단 프레임192의 상세 geometry를 재사용해47,057,408바이트의 **합성 시험용 JSON**을 만들었다. 기존 reader는 동일한 JSON_SIZE_INVALID로 거부했고, 수정 reader는 모든 내용을 동일하게 읽었다. 이는 저장 형식의 크기 경계 재현이며 새 영상·프레임 생성이나 실제 실패 파일 복구가 아니다.

실패한 원본 private CAPTURE_RECEIPT/FRAME_EVIDENCE는 종료 후 접근할 수 없다. 따라서 실제 실패 파일명·정확한 바이트 수는 확인 불가다. 반복되는 전체 geometry가 들어 있는 FRAME_EVIDENCE의 초과가 코드와 무료 재현에 가장 잘 부합한다. 외부 진단의 `missingEvidence.capture=true`는64KiB 제한의 안전한 요약 reader가 읽지 못했을 때도 발생하므로 원본 파일이 없었다는 증거가 아니다. `nvidiaVerified=false`도 회수되지 않은 receipt를 요약한 기본값이므로 GPU 실패의 독립 증거로 쓰지 않는다.

## 최소 수정

정식 `nvidia_worker.py`에 **FRAME_EVIDENCE 전용 읽기 경로만** 추가했다. 상한은 예상 프레임당2MiB, 전체 최대512MiB다. 무제한 JSON 로딩이 아니며 공용 cache의32MiB 제한은 유지한다. 해당 파일의 receipt SHA256, 소유권·권한·단일 hardlink, symlink 금지, 읽기 중 inode/크기/시간 변경, 중복 키·비정상 숫자 검사를 적용한다.

기존 프레임 증거를 삭제·축약하지 않는다. 기존 프레임 번호/개수/glError 검사와 실제 MP4 ffprobe·전체 디코딩 검사, 원래 export 경로를 유지한다. 입력, Scene 컴파일러, 렌더러, 인코더, GPU 설정, 인증, 합성기는 변경하지 않았다.

집중 검사10개 PASS: 처음9개 성공,1개는 실제 guard가 예상보다 먼저 거부해 시험의 오류코드 기대값만 수정한 뒤 그 항목만 성공했다. 후보 코드는 수정하지 않았으며 통과한9개는 재실행하지 않았다. 기존 프로젝트 PASS 재실행0회다.

패키징은 기존 이미지에 worker와 필수 source/startup manifest 세 파일만 추가한다. 별도 새 태그를 쓰고 기존 이미지를 보존한다. 실제5090 재실행 성공, MP4 최종 전달,20초 품질은 이 무료 검증으로 승인하지 않는다.

## 다음 실행의 범위

새 이미지 게시·설정 저장 후에만 사용자가 실패한 PART_01을 새 작업으로 제출한다. 기존 입력 JSON을 그대로 사용하며, 과거 FAILED 작업의 상태 새로고침은 재실행이 아니다. Work는 배포·렌더링·중지를 대신하지 않는다. PART_01의 실제 MP4·QUALITY_SUMMARY·SHA256SUMS 다운로드가 완료된 뒤 PART_02로 진행한다.

Studio 자동 두 작업 합성 UI 미연결, HISTORICAL 차단, 실제20초 시각 품질 미검증은 그대로다. 기존 CLI 합성 경로를 사용한다. 삭제된 컨테이너의 private 원문이나 stdout/stderr 회수는 반복하지 않는다.
