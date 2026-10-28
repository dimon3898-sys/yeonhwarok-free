# WORLD ENGINE 일괄 복구 작업 결과 — 2026-10-28

판정: **DIAGNOSTIC_IMAGE_CPU_VERIFIED_PUBLISHED_NOT_DEPLOYED**

## 완료
- 진단 소스의 실제 job 경로·저장소 테스트 경로·고정 오류 허용목록·I/O 제한 문제 수정.
- 복구 브랜치에 소스·테스트·기록 저장. 원격 11파일 크기·SHA256 일치.
- 고정 운영 이미지의 Python·UID/GID1000에서 진단 14개 검사 PASS.
- 원본 runtime와 매니페스트를 보존하고 별도 디렉터리에 352파일의 파생 runtime 구성.
- 신규 이미지의 기본 ENTRYPOINT, 합성 Owner 인증·HTTPS origin 등록, 기존 6초 plan 생성, TERM 종료, Owner 누락 차단 PASS.
- 설치된 진단 모듈의 파일 해시·실제 저장 경로 검증 PASS.
- GHCR 신규 태그 게시 후 익명 Registry에서 manifest 및 config digest 재확인 PASS.
- source CI와 image CI를 각 1회 실행, 자동 재시도 0. GPU 배포·렌더링·gCube 설정 변경 0회.

## 변경 범위
기존 production worker의 실패 분기에만 8줄을 추가했고 진단 모듈 2개를 추가했다. 별도 이미지에 복사된 bootstrap의 runtime 해시 고정값만 갱신했다. 기존 렌더러·Scene·UI·인증·supervisor 로직과 main·원본 이미지·원본 매니페스트는 유지했다.

## 남은 조건
원래 GCUBE_CAPTURE_RUNTIME_FAILED의 실제 내부 원인은 아직 미확정이다. 실제 GPU 캡처, gCube 운영 설정 적용, 새 진단 파일의 Dropbox 마운트 원격 동기화·다운로드는 미실행이다. 6초 MP4는 아직 없다. CPU의 합성 인증·origin 검사와 실제 HTTPS 운영 검증을 구분해야 한다.

## 다음 실행 전
- BATCH_CHECKPOINT.json에 기록한 새 이미지 태그와 manifestDigest를 사용한다.
- WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST와 WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST는 새 manifestDigest와 일치시킨다. configDigest로 대체하지 않는다.
- 기존 RTX4080S 1개·공유 메모리3GB·Dropbox /world-storage·Owner 안전 입력을 유지한다.
- 이미지 기본 ENTRYPOINT를 사용하며 만료된 정책은 실제 승인된 실행 시각에 맞춰 갱신한다.
- 유료 GPU 실행은 별도 승인 후 최대 1회·자동 재시도0. 2,000원·30분은 플랫폼 강제 차단 보장이 아니다.
- 실패 진단 보존을 위해 과금 한도를 넘겨 대기하지 않는다. 짧은 수신 확인 후 Stop 및 Finished를 확인한다.

이 기록은 GPU 실행 승인서가 아니다. 새 이미지에 필요한 변경부 검증은 완료했지만 6초 렌더링 성공으로 해석해서는 안 된다.

검증 근거와 모든 고정 해시는 BATCH_CHECKPOINT.json을 참조한다. 이전 source-import 시점 보고서는 당시 상태의 불변 기록이며, 본 체크포인트가 현재 진행 상태다.
