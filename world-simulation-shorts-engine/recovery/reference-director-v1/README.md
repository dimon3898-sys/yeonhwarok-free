# Reference 64306 director V1 — partial, not a rendered reproduction

이 작업은 `82854af429d09aebb4b31c2f168e2f0ddc9560c9`에서 시작한 별도 확장입니다. 기존 G1/G2/FINAL, 307개 보호 파일 및 기존 렌더러·셰이더·캐시를 변경하지 않았습니다.

**현재 판정: `CAPABILITY_EXTENSION_REQUIRED` + `DATA_DETAIL_BLOCKED`. 실제 레퍼런스 재현 영상이나 영상 품질 PASS는 없습니다.**

## 실제로 확인한 것

- 이름이 다른 사용자 첨부 MP4가 원본 64306과 동일합니다. 파일 SHA 및 순차 디코딩 635/635 프레임의 BGR 픽셀 SHA, PTS가 제공된 로그와 일치합니다.
- 첨부 목표 JSON은 실행 가능한 기존 Scene이 아니라 미바인딩 연출 명세입니다. 기존 503개 검사를 실제로 다시 실행했습니다. 명령·개별 검사 목록·실패했던 환경 시도·재개 로그를 보존했습니다.
- 기존 렌더러는 bounds 카메라 갱신만 공개합니다. 지형 샘플링의 역투영까지 함께 회전시키는 공개 계약이 없습니다. 완료 화면을 복사해 회전하는 기존 경로는 이번 MASTER가 금지하므로 사용하지 않았습니다.
- 기존 50m 국가 형상과 지역 단위 두 위치는 부분 연결했습니다. 초근접 대상의 상세 형상·실제 경계·충분한 지도 원본은 부족합니다. 영상에 보이는 `85 m`는 관찰된 문자열이며 실측 인증이 아닙니다.

## 새로 구현한 범위

- `director_camera.mjs`: 동일 투영의 수학 모델, 앵커/두 점/폴리곤 화면 맞춤, C1 전역 경로, 회전 viewport 네 모서리 역투영 및 소스 검사. **기존 native camera에 연결되지 않은 수학 계약입니다.**
- `director_events.mjs`: 1회 팝인, grapheme 글자 공개, 원본 지리 선의 길이에 따른 reveal, 고정 지리 중점 metric, 역할별 가시성 규칙 및 새 핀 SVG. **실제 지도 픽셀 소비자는 아직 연결되지 않았습니다.**
- `studio_preflight.py`: 기존 관리자 인증·Origin·CSRF를 재사용하는 localhost 전용 읽기 검사. 새 요청을 설명할 수 있지만 `ready=false`, `renderAllowed=false`이며 제출·claim·worker 생성을 차단합니다. 기존 UI·배포·운영 이미지는 바꾸지 않았습니다.
- `COMPILED_DIRECTOR_TRACK.json`: 전역 546프레임의 **authoring 이벤트 상태**. 실제 카메라·투영·픽셀 측정은 `null`입니다. 실행 가능한 Scene 또는 완성된 camera track으로 사용하지 마십시오.
- `INPUT_TO_PIXEL_TRACE.csv`: 입력/sidecar 대응을 기록합니다. 실제 픽셀 칸은 비어 있고 `NOT_EXECUTED_BLOCKED`로 표시합니다.

## 영상 제작을 멈춘 이유

MASTER 9.4·11에 따라 보호 렌더러 변경과 상세 데이터 부재를 통과시키지 않았습니다. A 180/B 180/C 186프레임 창의 전역 시간 계약은 검증했으나, 필수 static draw/Studio MP4/전후 픽셀 비교는 미실행입니다. 가짜 프레임·대체 영상·placeholder 비교 이미지는 만들지 않았습니다.

정확한 다음 연결 범위는 [CAPABILITY_GAP_AND_PATCH_MAP.md](CAPABILITY_GAP_AND_PATCH_MAP.md), 필요한 자료의 형식·해시는 [SOURCE_DETAIL_AND_LICENSE_REPORT.md](SOURCE_DETAIL_AND_LICENSE_REPORT.md)와 [REFERENCE_DIRECTOR_INPUT.json](REFERENCE_DIRECTOR_INPUT.json)에 있습니다.

원본 영상 및 디코딩된 원본 이미지들은 공개 ZIP에 포함하지 않았습니다. 원본 재배포 권한을 가정하지 않았습니다. CPU·브라우저 컴포넌트 검사와 실제 WORLD ENGINE 지도 영상은 구분합니다.

유료 GPU/API·배포·80초 제작·FINAL 승격은 실행하지 않았습니다. G3는 계속 BLOCKED입니다.
