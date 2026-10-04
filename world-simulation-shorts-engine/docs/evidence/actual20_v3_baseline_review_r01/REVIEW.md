# Actual v001 20초 — MASTER V3 기준 시각 검토

작성일: 2026-10-04 UTC. 범위: 기존 이미지와 완료된 v001의 실제 출력·QC 기록을 읽고 비교한 정지 프레임 평가. 전체 실시간 재생·직접 청취·실물 스마트폰 검수·수정 v002 승인은 하지 않았다.

## 판단

자동화가 MASTER V3의 구면·원본 shader·8K 도시광/구름·깊이 기반 대기·입체 항공기 자산을 유지한 것은 확인된다. 평면 슬라이드로 바뀌거나 기본 도형 항공기로 퇴행한 결과는 아니다. 다만 source 재사용과 렌더 완료가 같은 영상미·시청 지속·최종 합격을 증명하지 않는다.

검토한 이미지에서는 새로 깨진 기체, texture 누락, 잘린 중요 문자, 과한 neon glow 같은 즉각적인 graphics 결함을 발견하지 못했다. **HERO의 기체 재질·지표 분리감은 기존 V3보다 약하게 읽히는 구간이 있으며, 전체 재생에서 시각적 최고점이 충분히 남는지 확인해야 한다.** E006 누락은 실제 QC 실패로 유지한다. 이 검토를 근거로 전체 목표를 통과 처리하지 않는다.

## 실제 산출물과 preflight의 구분

- `projects/project_b89a30908047/versions/v001/final/final.mp4`는 20.0초/1080×1920/30fps/H.264의 실제 완성 파일이다. 다섯 scene의 manifest가 complete이며 각 4초/120프레임, 내부 2160×3840 HIGH다.
- 기존 `qc/qc_report.json`이 실제 인코딩 RGB 600프레임 디코딩과 600개 대응 audit를 기록한다. black/exact duplicate/clipping/GL error/missing asset/broken route는 0, near-frozen 최대 0초다. 이 검토에서 전체 영상을 다시 디코딩하거나 600장을 사람이 판독하지 않았다.
- 직접 본 `qc/contact_sheet.png`는 실제 출력의 **10시점**(0/1/2/3/6/10/13.1/14/18/19초), 각 270px 폭이다. 600프레임을 보여 주는 contact sheet가 아니다.
- 이전 `qc/preflight_*`와 mobile review 이미지는 별도 preflight이며 실제 후반 MP4의 증거로 바꾸어 설명하지 않는다. actual v001 15초 한 장만 새로 추출해 이 폴더의 `actual_v001_15_00.png`로 보존했다.
- `qc_report.passed=false`: E006 country_reveal의 실제 draw 누락 때문에 `MEANINGFUL_EVENT_NOT_RENDERED`, 파생 `STAGNATION`(4.3초), `BROKEN_CAUSALITY`가 발생했다. 계획상 사건 합격과 actual rendered event 합격은 다르다. 움직이는 6초 프레임을 보고 E006이 발생했다고 대신 인정하지 않는다.
- 실제 전체 재생은 수정 v002에서 별도로 확인할 예정이다. v001 검사 결과는 수정본의 합격 결과가 아니다.

## 같은 시간대의 인간 시각 비교

기준은 `cinematic-world-map/outputs/comparison_v3_{0.50,2.00,6.00,10.00,15.00,19.00}.png`다. MASTER V3는 서울→도쿄→싱가포르, 새 자동화는 뉴욕→런던→두바이로 지역·카메라·연출 시간이 다르다. 같은 시각은 동등 pose 또는 픽셀 비교 조건이 아니다.

| V3 시각 | 새 v001 근거 | 관찰 |
|---|---|---|
| 0.5초 | actual contact 0/1초; preflight hook 0.733초 별도 | 큰 야간 구면·실제 도시권·얇은 대기 림이 유지된다. 새 hook의 한국어 여정 문구가 사건 맥락을 준다. 실제 0.5초 프레임은 이 검토에서 보지 않았다. |
| 2초 | actual contact 2초 | 도시와 진행 방향을 공개하는 구조를 유지한다. 상단 문구가 fade 중인 시점이므로 한 프레임의 낮은 opacity를 누락으로 보지 않는다. |
| 6초 | actual contact 6초; 기존 Scene2 실제 5초 추출 프레임 보완 | 항로는 밝은 core로 읽힌다. 기체는 작은 실루엣이다. 기존 V3의 6초 추적 기체도 작으므로 크기만으로 새 model 퇴행을 주장하지 않는다. E006은 실제 검사가 확인한 누락이다. |
| 10초 | actual contact 10초 | 밝은 Europe/day와 국가 영역 강조로 공간·상황이 바뀐다. 지리 읽기는 쉬워지나 기존 야간 V3보다 밝고 지도 설명 장면의 인상이 강하다. renderer source가 평면화된 것은 아니다. |
| 15초 | actual_v001_15_00.png; actual contact 14초 | 15초의 기체는 기존 V3 HERO보다 작고 상면 중심이다. 밝은 육지 위에서 동체·엔진 명암이 약하다. 새 기체의 큰 강조 시점은 약14초이므로 같은 시각의 크기 차이를 동일 shot 조건의 품질 수치로 쓰지 않는다. |
| 19초 | actual contact 19초; final r02 preflight 19.9667초 별도 | 실제 출력에서 세 도시명과 두 주 항로가 읽힌다. final r01의 사라지는 도시명·제목 문제는 r02에서 교정됐다. 19초 contact에 아직 나오지 않은 마지막 제목의 유지 여부는 최종 재생에서 확인한다. |

## 요소별 평가와 확인할 약점

| 요소 | 유지된 부분 | 한계/다음 검수 |
|---|---|---|
| genuine 3D | 지구 silhouette/곡률, 낮은 시점의 horizon, 입체 기체의 날개·fin·엔진, 높이가 다른 구름 | 지표는 texture/bump이며 DEM mesh·건물 깊이가 아니다. 스틸만으로 연속 parallax·모든 occlusion을 인증하지 않는다. |
| shader·빛 | 야간 amber 도시권, blue 대기, 낮/밤 상태 변화, 원본 Rayleigh renderer | daylight의 밝은 green/blue는 기존 야간 톤보다 설명 지도처럼 읽힐 수 있다. shot 변화의 리듬을 전체 재생으로 평가한다. |
| aircraft | 원본 V3 곡면 모델 유지, 기체 clipping/깨짐 발견 없음 | HERO 상면·밝은 ground·작은 후반 scale 때문에 cockpit/intake/곡면 명암이 약하게 보인다. 효과 추가보다 카메라/공통 광원/노출을 검토할 가치가 있다. |
| routes | progressive core, 지리적 연결과 마지막 전체 항로 | background network는 저해상도 contact에서 대부분 희미하다. 주 항로는 명료하나 network 진행감을 실제 모바일 재생에서 확인해야 한다. |
| cloud·surface | 실제 coverage, HERO volume 활성, scene 높이 분리 | 확대된 8K 육지는 부드러운 색면으로 보이고 cloud density는 저표본 근사다. 도시 근접·실제 weather 장면이 아니다. |
| mobile safe area | 중심 기체, 여유 있는 hook 위치, final 도시명은 프레임 안에 있음 | 270px contact에서 얇은 font·작은 기체의 세부는 제한된다. Shorts 실제 UI·폰 하드웨어·플랫폼 재인코딩은 시험하지 않았다. |

Scene1→2 camera handoff는 audit상 약 .0021°로 이어지지만 가시 aircraft quaternion은 4.4616° 바뀐다(장면 내부 최대 약 .32°). 앞서 추출한 경계 스틸 두 장에서는 명백한 시각적 튐으로 판단하기 어려웠다. 최종 4초 재생 확인 후보이며 수치만으로 GPU 재렌더를 결정하지 않는다.

## 재렌더 판단과 최종 한계

이 정지 프레임 검토만으로 E006 외 새 graphics artifact 때문에 전체 20초 GPU 재렌더를 요구할 근거는 발견하지 못했다. **원본 V3와 완전히 같은 영화적 품질이라고 합격 처리할 근거도 부족하다.** E006이 실제 보이는 정보·국가 관계로 교정됐는지, v002의 전체 재생에서 HERO 강조와 day/night 연결·final label 유지가 충분한지 확인해야 한다. corrected QC를 threshold 완화나 계획상 사건 수로 대체해서는 안 된다.

사진 같은 도시 근접·landmark·실사 항공기 clip은 구현되지 않았다. 외부 target 원본을 이 검토에서 직접 보지 않았고 pixel 비교하지 않았다. visual proxy aircraft scale, 8K 확대 한계, cloud/atmosphere/reflection 근사와 직접 청취 미실시를 유지한다. 실제 retention 실험이나 게시 품질 승인 문서가 아니다.

v001 manifest에서 MASTER V3 renderer SHA `b378269674833f9a79cbbbb2d9c24b004d5ca398063ca897ec1a5359eed0d6d3`와 aircraft SHA `fe23bb1b297f0fb16bbe492fcfc5245ab9461c9991195bbd6fe7a616ab12404b`를 확인했다. Scene audit는 8192×4096 입력, `MASTER_V3_RGB_RAYLEIGH_12x4`, HERO volume 활성과 `cartographic_visual_proxy`를 기록한다. 이는 provenance 자료이며 새 camera/uniform/state나 RGB가 원본 마스터와 같다는 proof는 아니다.

이 작업은 본 evidence 폴더의 문서·JSON·actual15 PNG만 새로 만들었다. 기존 문서·source·영상·preflight를 수정하지 않았고 GL·새 영상 렌더·전체 재생을 실행하지 않았다.
