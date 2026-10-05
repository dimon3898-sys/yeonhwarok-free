# PREMIUM FLAT MAP 품질 보고서

2026-10-05 UTC. 최종 검증 대상은 **`project_c047b389d1f8/v003`의 15초 샘플**입니다. 최초 v001, S002 부분 수정 v002도 보존합니다. 기존 MASTER V1/V2/V3·75초 결과·Git 이력·완료 Scene·자산·캐시는 보존했습니다. 기본 Planner를 Flat으로 교체하지 않았으며 사용자 샘플 승인 전 75초 전체 렌더는 시작하지 않습니다.

**최종 판단:** 독립 Premium Flat/2.5D 렌더러를 추가했고 실제15초 v003의450프레임 기술 QC·사건 신선도/Retention/Diversity·모바일 브라우저 전체 재생·다운로드가 통과했습니다. v001/v002에서 발견한 E011의 이른 활성화는 S004만 수정해 해결했습니다. 해안선·지형·이동체·진행 경로의 가독성 개선은 실제 출력 프레임에서 확인했습니다. 샘플은 사용자의 스타일 승인 대상이며, 자동 QC가 실제 시청 지속률을 보장하지는 않습니다.

## 요청한 14개 항목

| 항목 | 실제 검증 상태 |
|---|---|
| 1. FLAT MAP 구현 | 독립 `FLAT_MAP_PREMIUM` 백엔드로 S001~S004 360프레임 렌더 완료 |
| 2. 기존 기능 보존 | 기존 V3 소스·Earth runner/page 유지, 기본 Planner/Earth·오디오·부분 수정·checkpoint 유지; 기존 Earth cache key 동일 |
| 3. Premium / 2.5D 품질 | 최종1080 프레임과375px 실제 표시에서 해안·산맥·강·3D 항공기·진행 경로 확인; V3 Earth는 마지막3초에 유지 |
| 4. 대륙·해안선 선명도 | 수동 비교에서 기존75초의 보존된26.25초 모바일 캡처보다 육지/바다와 지형이 명확; 서로 다른 장면의 관찰이며 전체 영상 통제 비교 아님 |
| 5. AUTO FOCUS | 국가 tint와 지역 focus를 시간에 따라 한국→일본→타이베이→차단 출발지로 전환; 지형을 불투명 원색으로 덮지 않음 |
| 6. NEXT EVENT CAMERA | S003의 타이베이 사건 전 0.65초 lead를 실제 공유 카메라 rig에 반영; 카메라 예고는 사건 수에서 제외 |
| 7. 진행형 Route | 실제 이동체 진행률에 맞춰 core/head/trail 생성; v003 E010의 새 우회 route head가9.8초에 실제 표시됨을 확인 |
| 8. 다중 Entity | S004에서 도쿄의 정지 이동체와 두 지원 항공기를 분리된 verified route에 배치; actions 계약·방향·속도 easing 검사 |
| 9. MAP VFX | 샘플의 차단 barrier·우회·국가/지역 강조 확인; 8종 전체는 별도 실제 4K 정지 프레임 fixture와 20개 JS 계약 검사로 검증 |
| 10. Flat→Earth | 마지막 3초에 실제 보존 V3 렌더러 사용, shared atmospheric handoff; projection vertex morph는 미구현 |
| 11. Retention / Diversity | v003 실제12사건/11종/평균1.2182초/최대2.9667초/첫3초4사건/같은 종류 연속최대1, 카메라 제외; 새 연결10.733333초 실제 확인 |
| 12. 15초 제작시간 | 최초47분44.333초, S002부분 수정4분50.544초, S004최종 수정5분56.785초; 알려진3작업 누계58분31.662초 |
| 13. V3와 실측 속도 | 이번 구간 기준 Flat99.460초/영상1초, Earth546.875초/영상1초; 약5.50배 차이, 동일 내용 통제 실험 아님 |
| 14. 남은 문제 | 같은 공항의 출발/정지 항공기 순간 겹침·반대 전환 실제 MP4·야간 지형/라벨 대비·전환의 정보 가림·동아시아 밖 terrain·CPU 비용·실물폰/직접 청취 |

## 실제 파일과 규격

- [최종15초 영상](flat_map_premium_test_15s.mp4): 21,370,496 bytes, SHA256 `ebb7d6ed7f16b811548cd1f34a5a672108930601870bb85d84451fcd3265df85`.
- [최종 무음 영상](flat_map_premium_test_15s_muted.mp4): 20,849,370 bytes, SHA256 `d3e604072a6f40abafc1821376d3c81705371584da82cbc240af36b911aa6a73`.
- [첫 화면](flat_preview_01.png), [경로 추적](flat_preview_02.png), [네트워크](flat_preview_03.png), [최종 Earth](flat_preview_final_earth.png).
- [Scene Plan](scene_plan.json), [읽기용 계획](scene_plan_readable.md), [QC](qc_report.json), [Contact Sheet](contact_sheet.png), [출처](source_report.md).

1080×1920/9:16/30fps/H.264 MP4, 15.000초/450프레임, 내부2160×3840, yuv420p/BT.709입니다. 링크는 저장소 배포 파일의 상대 위치이며 외부 공개 HTTP 검증을 대신하지 않습니다. 원본 v001/v002 영상은 작업공간 `projects-flat-validation/project_c047b389d1f8/versions/v001|v002/final/`에 별도로 보존하며 공개 링크로 표시하지 않습니다.

## 지리와 그래픽

국가·해안선·도시는 검증된 Natural Earth 데이터로 배치합니다. 국가 경계는 50m vector이며 서울·도쿄·타이베이 좌표는 저장된 GIS catalog/source ID와 일치해야 합니다. AI가 새 좌표나 지리를 그리지 않습니다. 국가 tint는 terrain을 유지하고 얇은 경계·국소 노출·focus로 핵심 대상을 분리합니다.

Natural Earth I의 원본21600×10800 raster를 **1/60도/픽셀의 원래 해상도로 지리 등록하여 잘라낸** 동아시아 지형을 사용했습니다. 확장 ROI는 104~152°E, 약−8~65°N, 2880×4380 PNG입니다. 원래 좁은 ROI PNG도 삭제하지 않고 함께 등록합니다. Natural Earth 경로명 `10m`은 지도 축척 자료군의 이름이며 10m 고도 DEM을 의미하지 않습니다. 현재 relief는 실제 cartographic shaded relief와 2K topology bump이고 survey DEM 기반 수치 지형 시뮬레이션이 아닙니다.

Flat은 비용이 큰 지구 대기·구름 전체 계산 없이 투영된 mesh와 고급 raster 재질을 사용합니다. 실제 3D 항공기, 약한 그림자, 경로 core/head, 미세한 tilt로 깊이를 유지합니다. 표시용 고도와 이동체 크기는 지도 표현에 맞춘 것으로 항공 운항의 물리 계산 결과가 아닙니다. 외부 지역은 기존 글로벌 자료를 사용하며 현재 동아시아 ROI와 동일한 지형 정밀도를 자동 보장하지 않습니다.

## 사건 진행과 추가 수정

의도한 진행은 한국 강조→서울 출발→도쿄 예고→거리 정보→일본 공개→도착→타이베이 목적지 변수→연결 차단→직접 연결→지원 연결 확대→전체 Earth 공개입니다. 사실은 GIS 위치·구면 거리이며 목적지 변경과 연결 보류는 ASSUMPTION, 이동·네트워크는 해당 가정의 SIMULATION으로 분리합니다.

계획상의 평균 사건 간격은1.2136초입니다. **최종 v003 실제 프레임** 기준은 평균1.2182초/최대2.9667초이며, 첫3초에4사건, 11종의 사건, 연속 같은 종류 최대1회, 이야기와 실제 네트워크 변화를 결합한 Peak1개입니다. 카메라 pan/zoom은 사건으로 세지 않습니다. 경로/네트워크/차단 같은 물리적 사건은 caption만으로 증명하지 않습니다.

그러나 v001 S004의 도쿄→타이베이 지원 route/entity의 start_time은 local1.05초(전체10.05초)이고, native 프레임에서 실제 연결은10.0667초부터 나타납니다. E011은 local1.7초(전체10.7초)에 새 연결로 기록됐습니다. 새 연결의 실제 최초 활성화10.0667초부터 마지막 공개13.7초까지는3.6333초이므로, receipt만으로 새 사건 밀도 통과를 선언할 수 없습니다.

이를 렌더 전 차단하도록 Flat의 meaningful `network_expand`/`network_expansion`은 실제 target route의 progress_start=0, start_time과 event time의 오차≤1프레임을 요구하는 검증을 추가했습니다. 일반 final_reveal이나 기존 Earth 계획은 그대로 유지합니다. 실제 v001 계획을 이 새 검사에 넣으면 `FLAT_NETWORK_EVENT_TIMING_MISMATCH`로 거부합니다.

**v003에서는 route/entity를local1.7초로 맞춘 S004만 실제 재렌더했습니다.** 실제 새 연결의 첫 native 표시는 전체10.733333초이며, 마지막 공개13.7초까지2.9667초입니다. 다른4 Scene의 영상/audit SHA는 v002와 같아 원본 Earth를 다시 렌더하지 않았습니다. 새450프레임의 기술·사건 검사와 전체 재생이 통과했고 원본 v001/v002도 보존했습니다.

E005의 `648 km TO TOKYO`는 해당 시각 실제 새 거리 정보이며, E006은 tint가 먼저 시작하더라도 실제 `JAPAN` 라벨 공개를 별도로 확인합니다. 이러한 정보 공개와 물리적 새 연결을 같은 증거로 취급하지 않습니다.

## 전환 검수 범위

S004 종료와 S005 시작의 generic camera/state는 맞추고, Flat pullback/tilt와 실제 V3 구체를 shared atmospheric veil로 연결했습니다. 사건 eligibility를 제외하는 opacity>.4 구간은 약0.767초입니다. 실제 native opacity≥.5는19프레임/0.6333초, ≥.9는7프레임/0.2333초로 정보가 가려집니다. 그 구간은 사건이 보인 프레임으로 세지 않으며 중요한 사건을 배치하지 않았습니다. Scene 시간은 겹쳐 잘라내지 않아 전체15초를 유지합니다.

이는 지리 구도와 대기 통과를 이용한 실제 백엔드 전환입니다. 평면 mesh를 구체로 바꾸는 vertex projection morph를 구현했다고 주장하지 않습니다. `EARTH_TO_FLAT` 반대 방향 인터페이스는 있으나 이번 단방향15초 샘플로 실제 반대 전환 영상까지 통과한 것은 아닙니다. 서로 다른 투영 공간의 camera 좌표를 같은 단위로 비교하는 자동 수치 검사 대신 최종 경계 프레임의 수동 검수가 필요합니다.

## 기술 QC·모바일·사운드

최종 v003의 encoded RGB450프레임과 native audit450프레임을 검사했습니다. black frame·exact duplicate·near freeze·clipping·WebGL error·missing asset·broken route는 발견되지 않았습니다. Flat 최대 프레임 이동은 화면 span의0.032385, Earth 최대 위치 변화는 지구 반지름의0.022098입니다. 첫0.5초의 실제 화면 변화도 확인했습니다. 이 수치 검사는 조회수·시청 지속 효과의 보장이 아닙니다.

375×812 모바일 viewport의 실제 브라우저에서 최종 v003 전체15초가 `ended`로 종료했습니다.450 decoded/444 presentation callbacks, dropped3/corrupted0/stall0, JS오류0/가로 넘침0입니다. HTTP Range206과13개 다운로드 attachment를 실제 수신해 서버 원본과 SHA를 비교했습니다. 검수 중 새 render POST는0건입니다. 근거: [최종 UI_END_TO_END_REPORT.json](../../../world-simulation-shorts-engine/validation/flat_premium15_final_v003_playback_download_r01/UI_END_TO_END_REPORT.json). 실물 스마트폰, 공개 호스팅, 물리 스피커의 직접 청취까지 검증했다고 주장하지 않습니다.

TTS와 자막은 이번 시각 샘플에서 OFF이며, BGM과13개 효과음은 ON입니다. 오디오는48kHz stereo,−18.0 LUFS/true peak−2.5dBFS입니다. route block→warning hit, reroute→transition sweep, 새 변수→tension rise, 네트워크→wide riser, 마지막→deep hit를 authored event 시각에 연결했습니다. BGM/효과음은 CC0 procedural이며 레퍼런스 음원을 샘플링하지 않았습니다. native 공개 시점에는 일부 fade allowance가 있으므로 시각 onset과 음향의 정확한 체감 일치는 직접 청취의 별도 평가가 필요합니다.

기존 TTS·외부 narration·ducking·자막 ON/OFF 기능은 유지합니다. Flat 자막 ON의 안전영역 모듈은 실제 label/entity/focus bbox를 사용하여 별도 ASS를 생성하고 원래 파일을 보존합니다. 이번15초에는 자막이 없으므로 이를 실제15초 자막 영상 검증으로 기록하지 않습니다. narration 정렬 보고서에는 TTS OFF 상태의 국가ID가 장소 catalog에서 미해결이라는 경고가2건 남아 있으며, 직접 발화 정렬을 측정한 결과가 아닙니다.

## 회귀·캐시·부분 수정

Flat 도입 후 기존 전체 회귀 **214개 통과**를 확인했습니다(도구 wall399.442초, unittest runner397.849초). 이후 cache URL 범위 수정은 **15개 집중 검사 통과**, 사건 신선도 검증 추가는 **17개 집중 검사 통과(4.193초)**입니다. 이후 변경까지 포함한 전체 suite를 다시 실행했다고 표기하지 않습니다. renderer JS의 공유 카메라/route/actions 계약20개도 통과했습니다. 8종 VFX는 실제 4K fixture 정지 프레임 증거이며 모든 종류가 이번15초에서 사용됐다는 뜻은 아닙니다.

근거: [전체 회귀 로그](../../../world-simulation-shorts-engine/docs/evidence/flat_upgrade_core_regression_20261005T090141849004Z/unittest.log), [cache URL 집중 검사](../../../world-simulation-shorts-engine/docs/evidence/flat_cache_url_schema_r01_20261005T091327749439Z/TEST_RESULT.json), [사건 신선도 검증](../../../world-simulation-shorts-engine/docs/evidence/flat_network_freshness_guard_20261005T102216443701Z/RESULT.json), [8종 VFX Sheet](../../../world-simulation-shorts-engine/docs/evidence/flat_renderer_map_vfx_native_r01/MAP_VFX_CONTACT_SHEET.png).

일반 Earth hash는 `2225c343…4271646`으로 유지합니다. Flat은 독립 source/projection/settings/assets hash로 캐시하고 전환 Earth는 별도 어댑터 키를 사용합니다. terrain 디스크 cache-hit 검증은0.805707초이며 브라우저 geometry/texture cache는 프로세스 단위입니다.

**v002 S002 부분 수정 실제 완료:** 자연어→Diff→승인→S002 camera_speed×1.2의 새 버전에서4 cached/1 rendered를 확인했습니다. 비대상4 Scene 영상·audit SHA는 원본과 같고 current_render_seconds=0입니다. S002만 새 영상으로 생성됐으며 code/asset SHA는 같고 Scene JSON만 다릅니다. 신규 Scene269.777719초/작업 전체290.543848초입니다. 전체15초450프레임 기술 QC와 모바일 브라우저 재생·13개 attachment SHA도 확인했습니다. 단, 재생 callback349.9ms 지연1건은 남아 있어v002의 stall0은 주장하지 않습니다. 이는 부분 수정 기능의 검증이며 아직 미수정 E011의 최종 시청 지속 통과를 의미하지 않습니다. [부분 재렌더 증거](../../../world-simulation-shorts-engine/validation/flat_premium15_partial_revision_r02/actual_4cache_1new_source_video_audit_proof.json).

**최종 v003 S004 부분 수정 완료:** 4 cached/1 rendered와 비대상4 Scene 영상/audit SHA 일치를 다시 확인했습니다. 신규 S004333.022753초/전체356.784606초입니다. 이로써 자연어 부분 수정과 실제 품질 수정 모두 전체 영상을 다시 렌더하지 않고 조립·QC·다운로드까지 검증했습니다. [최종 부분 재렌더 증거](../../../world-simulation-shorts-engine/validation/flat_premium15_final_v003_playback_download_r01/actual_v003_4cache_1new_source_video_audit_proof.json).

## 레퍼런스 비교와 남은 품질 판단

레퍼런스의 디자인·음원·문구를 복제하지 않고 국가/이동체/차단/대응/규모 확대의 진행 원리를 가져왔습니다. 첨부된 개인 레퍼런스 이미지는 공개 산출물에 포함하지 않습니다. 검수자는 기존 레퍼런스 분석/private sheet와 실제 encoded 샘플의375px 캡처10개 및1080 종료/전환 프레임을 직접 비교했습니다. 해안선·산맥·강·두 진행 연결·3대 항공기를 구분했고, 보존된 기존75초26.25초 캡처의 구름/밝은 지표/흰 자막 중첩보다 이번 Flat의 정보 대비가 개선됐습니다. 서로 다른 장면의 수동 관찰이며 전체 영상의 통제 비교나 시청 지속률 측정은 아닙니다.

최종 v003 수동 검수에서는375px18개와1080 출력4개를 직접 보았습니다. E011 직전51개 native 프레임에서 지원 route progress=0/entity hidden, 최초route/entity/network10.733333초를 확인했습니다.11.0/11.2초에는 실제3대 항공기와2개 신규 진행 경로가 분리되어 보이며 해안선·지형·tint 이후 terrain·선행 카메라·지구 규모 공개가 검수 범위를 통과했습니다. [최종 v003 실제 encoded 수동 검수](../../../world-simulation-shorts-engine/docs/evidence/flat15_readonly_review_harness_20261005T092022513665Z/actual_encoded_review_20261005T103713255502Z/V003_MANUAL_ENCODED_REVIEW.md).

10.8초에는 도쿄 공항의 정지기와 막 출발한 지원기가 순간적으로 겹치고,11.0/11.2초에 분리됩니다. 최종 Earth의 공간 깊이·구름·대기 rim은 유지되지만 세부 지형은 앞 Flat보다 어둡고 항공기는 작습니다. 마지막 SEOUL 글자가 도시광 위에 일부 겹치며375px에서는 완료된 과거 경로가 약합니다. 해당 Earth는 v001~v003에서 영상/audit가 같은 보존 캐시입니다. 의미 시각 정렬은 v003에서 해결했지만 “레퍼런스보다 모든 항목에서 우수하다” 또는 사용자 승인 완료를 주장하지 않습니다. [v001 수동 검수와 수정 원인](../../../world-simulation-shorts-engine/docs/evidence/flat15_readonly_review_harness_20261005T092022513665Z/actual_encoded_review_20261005T101136878445Z/V001_MANUAL_ENCODED_REVIEW.md).

남은 핵심 항목은 같은 공항의 출발/정지 항공기 순간 겹침, 전환의 잠깐 가려지는 정보, 다른 지역의 고해상도 terrain 확대, 반대 방향 실제 전환 영상, 야간 최종 라벨 대비, 직접 음향 평가와 CPU 제작 비용입니다. 기존 MASTER와 완료 자료124개의 SHA-256 재검사에서는 변경·누락0개였습니다. 샘플 승인 이후에도 설명 중심 장면을 Flat으로 선택하고 중요한 Peak만 V3로 선택할 준비가 된 구조이며, 기본 Planner의 변경은 아직 활성화하지 않았습니다.

사용 방법은 [PREMIUM FLAT MAP 안내](../../../world-simulation-shorts-engine/docs/FLAT_MAP_PREMIUM_GUIDE.md), 시간 범위·비교 한계는 [벤치마크](../../../world-simulation-shorts-engine/FLAT_MAP_BENCHMARK.md)에서 확인할 수 있습니다.
