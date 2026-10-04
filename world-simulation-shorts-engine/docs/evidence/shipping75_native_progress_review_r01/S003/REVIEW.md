# B75 S003 실제 인코딩 장면 독립 검수

- 입력: `project_594442ec2df9 / v001`, 전체 시작 15.0초, 장면 7.5초. `scene_results.json` complete 및 movie/audit 등록을 확인한 이후만 MP4를 열었다.
- 실제 MP4는 H.264 / 1080×1920 / 30fps / 225프레임 / 7.5초(metadata ffprobe). Movie SHA는 등록값 `a99e7bd1b2519fdd9e178dd13e412a0a28808a55a46fbb8f0acf1f0218fa0c03`이며 독립적인 전 프레임 decode QA 또는 전체 재생을 수행한 것은 아니다.
- 직접 본 실제 encoded 프레임: local .7 / 3.0 / 5.1 / 7.2초(전체 15.7 / 18.0 / 20.1 / 22.2초), 1080×1920 원본 및 375×667 파생 이미지 각각 확인. 모든 캡처는 이 새 exclusive evidence 폴더에 생성했고 원본을 덮어쓰지 않았다.

## 실제 사건·중복 검사

| 사건 | 계획 local | 첫 실제 local / global | 지연 | 표시 프레임 | 실제 primitive |
|---|---:|---:|---:|---:|---|
| E010 / 12,694 km REMAINING | .2500 | .3000 / 15.3000 | .0500s | 38 / 1.2667s | information |
| E011 / 15,531 / 21,991 km | 2.4000 | 2.4667 / 17.4667 | .0667s | 38 / 1.2667s | information |
| E012 / NEW CONNECTIONS | 4.5500 | 4.6000 / 19.6000 | .0500s | 38 / 1.2667s | information |
| E013 / 15,531 km | 6.7000 | 6.7667 / 21.7667 | .0667s | 21 / .7000s | information |

- 실제 native audit 225개를 전부 읽고 S003 소유 ID만 분리하여 owner/kind/visible/지원 primitive/actual_time과 해당 native t 일치/정보 text를 검사했다. 네 사건 모두 누락·.2833초 onset 지연 허용치 초과·.1초 미만 표시 없음. 다른 미완성 Scene에 대해서 full-plan retention gate를 실행하거나 통과를 주장하지 않았다.
- 고정된 `analyze_duplicate_place_labels`를 **원래 full plan + S003 실제 audit만** 입력하여 실행했다. 전체 시작시간 15초가 보존된다. 결과 findings=[], unresolved_targets=[], exemptions=[]; `duplicate_place_labels.json`에 checker source SHA와 범위를 기록했다. 이 검사에서 S002와 같은 persistent/event-owned 지명 중복은 없다. OCR 또는 모든 정보문구 의미의 올바름까지 증명하는 검사로 해석하지 않는다.
- 정보 caption 최대 1개/프레임, 여러 정보 caption 동시표시 0프레임. 실제 네 이미지에서도 동일 도시명 두 줄이나 읽을 수 없는 텍스트 겹침은 보이지 않는다.
- `NEW CONNECTIONS`는 information caption으로 실제 표시되었다. 이 Scene의 현재 native/샘플 이미지가 새 항로 분기나 network primitive의 생성까지 증명하는 것은 아니다. 비교 숫자도 caption이며 두 항로를 동시에 펼친 지도 비교 장면으로 보고하지 않는다.

## 지도·카메라·선박·모바일

- 이베리아/Gibraltar → 서부 지중해 → 이탈리아/Sicily 쪽으로 실제 그림이 진행된다. 해안과 섬 형태는 구분되고 흰 항로는 해상으로 이어진다. 수에즈 실제 운하 통과 또는 운하 정밀도 검수는 이후 장면의 과제다.
- 네 샘플에서 선박은 화면 중앙 부근, 핵심 caption은 상단 왼쪽 안전영역 안에 있다. 선체가 깨지거나 경로가 끊어지거나 가장자리에서 잘리는 모습은 보이지 않는다. 중앙 밝은 route head와 짧은 trail로 이동체 위치를 찾을 수 있다.
- 뒤로 당기며 지구 곡률·얇은 푸른 대기 림이 5.1/7.2초에 드러난다. 225개 native camera quaternion 간 최대 변화 .093126°/프레임이며 수치상 갑작스러운 점프를 발견하지 못했다. 네 정지 이미지와 이 수치만으로 실제 재생의 모든 카메라 리듬을 승인하지 않는다.
- 선박 native visible/screenVisible 225/225. screenRadius 26.9011–43.1021 내부2160픽셀은 화면 영역 근사이며 실제 선박 길이/물리 크기가 아니다. 1080에서 선체/상부 형태가 구분되지만 375px에서는 작은 이동체로 보인다. 이후 HERO에서 입체감과 충분한 크기를 확인해야 한다.
- 밝은 육지·산맥 위 가는 흰 정보문구는 375px에서도 판독 가능하지만 대비의 여유가 약하다. 특히 `middle_E011_3_00_375.png`의 숫자 비교는 어두운 바다 위 문구보다 즉시 읽기 어렵다. 새로운 명백한 clipping/자산 결함과 구분되는 디자인 한계로 남긴다.
- native countryOutlines 0: 이 Scene에서 국가 경계 공개/강조를 검증했다고 하지 않는다. 확대 지표는 부드럽고 사진 수준 항구/도시 close-up·실제 DEM·고해상도 건물은 구현된 그림이 아니다.

## 수치와 한계

- native225: textClipped/entityClipped/missingTextures/routeDiscontinuities/webglError/routeInsideEarth/font not ready 모두 0. 상세 `native_event_coverage.json` 참조.
- 샘플에서 **새 명백한 S003 재렌더 결함은 발견하지 못했다**. 재사용 판단을 위한 provenance/cache/최종 QC는 root가 별도로 확인한다.
- 전체75초 완료/승인, 모든 인코딩 프레임의 직접 육안 검수, 전체 재생, 실물 스마트폰, 직접 사운드 청취, 시청지속 효과 및 inline target 동급을 주장하지 않는다.
- source/plan/project/worker/server/cache/Git와 기존 결과는 변경하지 않았다. 추가 렌더·WebGL·전체 영상 생성 없이 새 evidence 캡처/JSON/문서만 기록했다. S003 검수 후 동결하고 다음 root 알림을 기다린다.
