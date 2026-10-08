# v018: 동일 카메라 화질 검증 자료

기준은 실제 RTX4080S 64458 완성본이다. `before/` 네 PNG와 `actual-contact.jpg`는 첨부 MP4에서 디코딩한 실제 프레임이다. 24초 전체 720프레임의 수치는 `all-frame-metrics.json`에 보존했다. 원본 MP4를 중복 저장하지 않고 SHA256으로 식별한다.

## 확인된 원인

Suez/Singapore 확대 시 주된 세부 제한은 고정 8192×4096 day/night 소스의 확대 footprint와 지역 detail LOD 부재다. 고정 2048×1024 높이 자료는 별도의 물리 relief 한계다. HIGH는 이미 2160×3840에서 렌더해 1080×1920으로 축소하므로 저해상도 내부 렌더의 upscale 문제가 아니다. mipmap/trilinear filtering과 색 공간의 오류를 입증하는 자료는 없다.

Suez 밝은 지형은 대비가 눌리고 해양 반사가 넓게 보인다. Singapore 도시광의 사각 패턴은 실제 8K night 소스에도 있다. cloud/atmosphere가 전체 흐림의 주원인이라는 증거는 없으므로 그대로 유지한다.

## 필요한 재료만 추가

21600×10800 Natural Earth TIFF를 세계 전체 텍스처로 교체하지 않는다. 합격한 두 EVENT VIEW를 덮는 원본 RGB 영역을 resize/sharpen 없이 1440×1680씩 추출했다. 실제 1:50m Natural Earth 해안 polygon 마스크로 육지 detail만 블렌딩한다. 원본의 해양과 WIDE 질감을 유지한다.

이 TIFF는 1 arcminute shaded-relief/land-cover cartography다. 새로운 DEM이나 고해상도 위성 사진이 아니다. RGB의 지형 명암을 물리적 높이·normal로 잘못 사용하지 않는다. 기존 2K 높이/normal 경로를 유지하며 그 데이터 해상도 한계도 남는다.

카메라 거리만 관찰하여 지역 detail을 연속적으로 섞는다. 가까운 화면에서 원본 표면의 daylight exposure/specular와 city power/gain을 제한한다. 야간 readability fill, 원래 8K day/night/cloud, MASTER V3, 구름·대기·AA·글꼴·텍스트·SFX는 유지한다. 실측 NVIDIA capability 범위 안에서 anisotropy를 제한하고 source가 강제로 축소되는 상황은 실패로 표시한다.

고해상도 night 자료는 확보하지 못했다. NASA 자료 요청은 환경 네트워크 proxy에서 차단됐다. 도시광의 과도한 밝기 증폭을 줄이지만 night texel footprint 자체나 사각 도시광 세부를 완전히 해결했다고 주장하지 않는다. 흐림/샤프닝으로 가짜 도시 세부를 만들지 않는다.

## BEFORE / AFTER 상태

| 항목 | BEFORE 실제 GPU | v018 현재 검증 |
|---|---|---|
| WIDE F000 / 0초 | 실제 PNG 보존 | 동일 카메라, 기존 재료와 동일 weight=0 계약 PASS |
| Suez F240 / 8초 | 실제 PNG 보존 | 지역 RGB/native density·daylight material 계약 PASS; AFTER NVIDIA NOT_RUN |
| CONTINENT_WIDE F435 / 14.5초 | 실제 PNG 보존 | 동일 카메라, 기존 재료와 동일 weight=0 계약 PASS |
| Singapore F630 / 21초 | 실제 PNG 보존 | 지역 RGB·city 증폭 제한 계약 PASS; AFTER NVIDIA NOT_RUN |

`before-after-comparison-manifest.json`에는 상대 경로·PNG SHA·동일 frame 카메라 위치/회전/FOV/state·AFTER NOT_RUN을 기록했다. `frozen-camera-trajectory-720.json`은 과거 계획과 코드에서 계산한 회귀 fixture이며 실제 GPU pose capture가 아니다. 720개 카메라 값과 카메라/사건 필드를 제외한 다른 계획 변경 여부를 모두 검사했다. 검증된 trajectory는 UNCHANGED다.

로컬 static shader 계약과 CPU GLSL syntax 검사는 NVIDIA shader compile 또는 pixel draw를 대신하지 않는다. 실제 동일 카메라 AFTER 프레임, 해안 detail, 도시광, 새로운 material의 눈으로 보는 품질은 다음 실제 RTX4080S 검증까지 NOT_RUN이다.

## 성능과 공개 검증의 범위

네 regional RGBA texture와 mip pyramid의 추가 저장량 계산은 약 49.2MiB다. 이는 브라우저 decoder/driver overhead를 제외한 분석값이며 실제 GPU peak memory가 아니다. 실제 frame time/전체 render time도 NOT_RUN이다. 원본 데이터 각축 sampling density는 2.64배이며, 이 수치만으로 최종 영상 화질 개선을 PASS라고 판정하지 않는다.

`local-preflight-report.json`은 이미지 게시 전 로컬 검사 결과다. 최종 Docker/public pull/boot/login/persistence 검증은 별도 release evidence로 확인해야 한다. 파일 이름의 local과 NVIDIA NOT_RUN을 공개 완료 또는 실제 GPU 검증으로 바꿔 읽지 않는다.
