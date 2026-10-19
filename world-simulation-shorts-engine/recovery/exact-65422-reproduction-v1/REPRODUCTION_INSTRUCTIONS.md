# 65422 원본 조건 재현

이 경로는 기존에 성공한 5초 가상 시나리오를 그대로 실행한다. 한국전쟁 80초 Scene이나 Studio의 역사 전선 변환을 사용하지 않는다. 기존 FINAL·Candidate·렌더러·셰이더·캐시를 변경하지 않는다.

원본 소스는 `2c097df2d02432a3f9ae4dae5d714dbc9eacd434`, 원본 실행 증거는 `45af879d7417abba58e9ebd59d8e6630a785ac28`에 고정되어 있다. 정확한 설정·원본 파일 SHA·시간축은 `ORIGINAL_EXECUTION_PROFILE.json`에 기록된다. 원본 제작 이미지 digest는 증거가 없어 미확인으로 유지한다.

독립 캡슐은 원본 보고서에 바인딩된 73개 파일과 같은 소스 커밋의 실행 의존성 7개를 복원한다. 기존 파일과 바이트가 다르면 덮어쓰지 않는다. 원본 private Scene은 공개 ZIP에 넣지 않으며, 기존 Git 원본에서 검증된 바이트를 독립 캡슐 안에 복원한다. 원본 보고서 전체와 중간 프레임 캐시는 공개하지 않는다.

필수 실행 버전은 Node `24.19.0`, Playwright `1.62.1`, Chromium `154.0.8037.57`이다. 원본과 같은 SwiftShader WebGL2 실행이며 실제 NVIDIA 검증이나 유료 GPU 실행을 뜻하지 않는다. FFmpeg 인코더 버전 차이는 별도 비교 결과에 남긴다.

다음 명령은 개발자·자동 실행 관리자용 재현 기록이다. 휴대폰 사용자가 터미널에서 실행할 필요는 없다. `/workspace/yeonhwarok-free-studio-startup`에서 실행하며, 기존 산출물이 없는 별도의 캡슐·캐시 경로를 사용한다.

```bash
python3 world-simulation-shorts-engine/recovery/exact-65422-reproduction-v1/tools/restore_capsule.py --capsule=/workspace/exact-65422-capsule-20261020
node world-simulation-shorts-engine/recovery/exact-65422-reproduction-v1/tools/capture_original.mjs --capsule=/workspace/exact-65422-capsule-20261020 --original-report=/workspace/exact-65422-original-report-20261020.json --cache=/workspace/exact-65422-fresh-capture-20261020
```

새 환경에서는 `restore_capsule.py`가 Git 원문에서 원본 보고서를 읽기 전용으로 확보한다. 캡슐의 `reference_runtime.mjs`가 원래 `VISUAL_REFERENCE_STUDY` 모드·동일 Scene·동일 scalar 영토·국기·회전·로컬 프레임 `0..149`를 사용한다. 완성 영상에 원본 MP4를 복사해 넣지 않는다.

출력은 `public-review/WORLD_ENGINE_65422_EXACT_REPRODUCTION_5S.mp4`이며 1080×1920·30fps·150프레임·5초·H.264·무음이다. 원본도 무음이므로 효과음을 새로 추가하지 않는다. 기존 정상 파일과 같은 이름의 출력이 있으면 자동 덮어쓰기를 거부한다. 완료된 신규 캡처 행과 PNG는 소스·프레임·해시가 일치할 때만 같은 재현 작업에서 재사용한다.

`reports/comparison/ALL_150_FRAME_COMPARISON.json`과 CSV는 원본·신규 영상 전체를 실제 디코딩해 비교한 결과다. 원시 RGBA/PNG 동등성, 인코딩 후 픽셀, 카메라·회전·영토·전선·표식 상태와 타이밍을 구분한다. 길이·해상도만 같다는 이유로 재현 성공을 선언하지 않는다. 실제 판정은 비교 보고서와 `RESULT.md`를 따른다.

휴대폰에서는 검증된 다운로드 URL의 MP4를 열고, 필요하면 비교 PNG와 공개 인계 ZIP을 확인한다. GitHub 커밋에 고정된 URL의 HTTP 200·다운로드 SHA가 원본과 일치한 경우에만 전달 완료로 기록한다. 유료 GPU 실행, 80초 렌더링, FINAL 승격은 수행하지 않는다.
