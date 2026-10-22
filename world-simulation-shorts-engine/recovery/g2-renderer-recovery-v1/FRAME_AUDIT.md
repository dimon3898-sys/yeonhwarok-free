# FRAME_AUDIT — 새 180프레임 제작 차단

## 실제 검사 범위

| 대상 | 실제 검사 | 결과 |
|---|---|---|
| 기존 MP4 | 전체 180프레임 decode·PTS·RGB·검은 화면·경계 수치 | 완료, 재질 경계 f0~179 지속 |
| PHASE 1 복구 main | 실제 원본 렌더러 4 draw: f0/f90/f179/f90 | GL 0, 동일 f90 raw SHA 일치 |
| Namibia | 실제 원본 렌더러 4 draw: local 0/1/2/1, V5 source 0/54/0 | PASS |
| Nepal | 초기화 단계 | FAIL, draw 0 |
| 새 Studio MP4 | 실행 안 함 | PHASE 2 실패로 BLOCKED |
| 새 MP4 전체 180프레임 감사 | 실행 안 함 | 새 MP4가 없으므로 PASS 주장 없음 |

기존 영상은 1080×1920, 30fps, 180프레임, H.264, 6초, 무음이다. 원본 180 decoded PNG와 전체 행별 검사는 새 scratch에 저장했으며 기존 영상·캐시는 변경하지 않았다. 공개 보고서는 `BASELINE_VIDEO_AUDIT.json`, `BASELINE_FRAME_AUDIT.csv`다.

## 육안 검수

실제 렌더 PNG의 f0/f90/f179 전후 contact sheet와 Namibia 중간 시점을 확인했다. main 부분 복구 프레임에서 지역/global raster의 직선·직사각형 경계가 사라졌다. 모든 장면은 WORLD ENGINE이 직접 그린 PNG이며 contact sheet는 해당 PNG를 축소 배열했을 뿐이다. 이미지 생성 AI·새 이미지 덧씌우기·지형 생성·블러는 사용하지 않았다.

`public-review/BEFORE_AFTER_CONTACT_SHEET.png`의 BEFORE와 SOURCE RECOVERY는 동일 Scene·카메라·actor·geometry·시간의 **원본 raw-render PNG**다. 새 MP4에서 꺼낸 화면이라고 표시하지 않는다. 같은 장면의 source 자산만 바뀌었다.

영역의 계단은 합성 fixture의 0.25도 격자 형태로 유지됐다. AA나 smoothing으로 실제 소스 영역을 바꾸지 않았다. 정밀한 점령선 또는 역사 사실을 의미하지 않는다.

현재 main·지역 probe는 flat extent 이동/줌을 사용한다. 회전은 선택되지 않았으므로 실제 G2 회전 정합을 검증했다고 주장하지 않는다. G1의 기존 회전·고급 효과는 재렌더 없이 원본 해시로 보호했다.

## 미완료 항목

새 전체 180프레임의 재질 경계 재발·코덱·프레임 누락·검은 화면·전체 이동/줌·해안 검수는 수행할 수 없었다. `tools/audit_recovery_video.py`는 준비됐지만 PHASE 3가 차단되어 새 영상에 실행하지 않았다. 모바일 실기기 재생·NVIDIA·GPU 성능도 미검증이다.

판정: 부분 복구의 실제 화면 증거는 있으나 **전체 영상 품질 PASS가 아니다. G2 NEEDS_REWORK.**
