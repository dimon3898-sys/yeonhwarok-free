# Production Default Integration v1 — QC Report

작성: 2026-10-05T22:20:48.192761+00:00 (UTC)

**12초 통합 샘플의 기술·시각·브라우저 재생·다운로드 검증 PASS.** 승인된 PREMIUM FLAT v004와 MASTER V3 Earth를 유지하면서 Production Default를 통합했다. 검증 범위는 이 짧은 동아시아 샘플과 명시한 증거에 한정한다. 실제 사람의 청취, 실물 휴대폰 테스트, 시청 유지율의 실측은 포함하지 않는다.

## 결과물과 적용 설정

- [사운드 포함 12초 MP4](production_default_integration_12s.mp4)
- [무음 MP4](production_default_integration_12s_muted.mp4)
- [SFX OFF 비교 MP4](production_default_integration_12s_sfx_off.mp4): TTS와 BGM은 유지한다.
- [Scene Plan](scene_plan_readable.md), [Scene JSON](scene_plan.json), [출처·라이선스](source_report.md), [Contact Sheet](contact_sheet.png)

최종본은 **1080×1920, 9:16, 30 fps, H.264 High/yuv420p, BT.709, 12.000초/360프레임**이다. 내부 렌더 해상도는 2160×3840이다. 오디오 포함본은 AAC LC 48 kHz 스테레오이며 무음본에는 오디오 스트림이 없다. 원본 최종 MP4 SHA-256은 `e0281d4d1a3ec7bb17d5c433ec881be674e6372b549b6823ea8e7316572c5b3b`이다.

구성은 S001–S004 각각 2.5초의 PREMIUM FLAT MAP, S005 2초의 Earth/HERO다. FLAT 10초(83.3%), Earth 2초(16.7%)로 짧은 기능 검증에 맞춘 구성이며 실전 비율 가이드를 기계적으로 강제하지 않았다. TTS/BGM/SFX는 ON, 자막은 OFF다. 이번 출력은 자막 ON 영상의 별도 렌더 테스트가 아니다.

## 검사 결과

| 검사 | 실제 확인 결과 | 근거 |
|---|---|---|
| FAST PACE | NORMAL 15초 기준을 Scene timing으로 12초로 구성. 카메라 travel/zoom, focus, route/entity 진행과 전환 시간을 개별 조정. 전체 영상 배속 없음, 나레이션 rate 1.0 유지 | [Scene JSON](scene_plan.json), [통합 게이트](INTEGRATION_QC.json) |
| 최소 지도 텍스트 | 짧은 도시·국가·거리·상태 라벨을 지도 위치와 연결. 중앙 대형 설명 문구 없음 | [독립 프레임 검수](INDEPENDENT_FINAL_MOBILE_FRAMES.json) |
| 국가·지형 | 지형을 유지하는 반투명 강조, 한국/일본/대만의 색상 구분과 선명한 해안선 확인 | [모바일 프레임 1](mobile_frames_1.jpg), [프레임 2](mobile_frames_2.jpg) |
| Entity/Route | 실제 3D 항공기 방향과 세 이동체 분리 확인. 주 항로 core 6.75px/head 6.9px 대 보조 3.25px/3.4px(1080px 기준), 주 항로 opacity 1.0 대 보조 0.3 | [독립 AV/실제 draw audit](INDEPENDENT_FINAL_AV.json) |
| AUTO FOCUS/NEXT EVENT CAMERA | 기존 v004 기능을 유지. 현재 대상 강조와 다음 지역 선행 카메라 연결 확인 | [Scene JSON](scene_plan.json), [독립 프레임 검수](INDEPENDENT_FINAL_MOBILE_FRAMES.json) |
| FLAT→Earth/HERO | 등록된 지리 위치를 유지하며 곡률 확장. 전체 지도를 가리는 veil 없음. 마지막 Earth에서도 아시아 해안선과 도시가 읽힘 | [모바일 프레임 3](mobile_frames_3.jpg) |
| 최종 새 정보 | SHANGHAI는 검증된 Natural Earth 도시 좌표로 표시. Taipei→Shanghai 가상 연결이 새로 그려지며 이전 항로의 재등장으로 사건을 부풀리지 않음 | [Scene JSON](scene_plan.json), [독립 AV](INDEPENDENT_FINAL_AV.json) |
| Retention/Event Diversity | 실제 post-draw 사건 12개, 평균 1.0061초, 최대 간격 2.2667초. 첫 3초 4개, 사건 종류 11개, 동일 종류 최대 연속 1개. 카메라 pan/zoom은 사건으로 세지 않음 | [자동 QC](AUTOMATIC_QC.json) |
| 기술 QC | 최종 H.264 RGB 360프레임 전부 decode. 검정/정확 중복 0, 최대 coarse 정체 0.467초. 실제 native 360프레임의 clipping/asset/WebGL/route 오류 0, 보이는 항공기 bounding-box 겹침 0 | [자동 QC](AUTOMATIC_QC.json), [독립 AV](INDEPENDENT_FINAL_AV.json) |
| 카메라 수치 게이트 | 최대 각도 변화 2.485022도/프레임으로 기존 2.5도 제한 통과. 렌더러 또는 게이트 기준을 낮추지 않음 | [자동 QC](AUTOMATIC_QC.json) |
| 재사용/버전 관리 | v002 실패와 완료 4개 Scene 보존. v003은 S005 JSON만 수정하고 완료 4개 Scene 재사용. SFX OFF v004는 전체 5개 Scene 캐시 재사용, 새 그래픽 렌더 0 | [캐시 비교](CACHE_COMPARISON.json) |

FACT는 실제 도시 위치/거리의 출처, ASSUMPTION은 목적지 변경·정지 가정, SIMULATION은 새 항로 연결에 사용했다. 항공편 운항이나 결과를 실제 예측으로 표시하지 않았다.

## 사운드와 동기화

라이브러리는 **21 Category × 각 3 Variant(63개)**다. 이 샘플에서 실제 사용한 것은 **13개 cue, 12개 서로 다른 WAV, 11개 Category**다. 전체 라이브러리 63개를 모두 이 영상에서 재생했다고 주장하지 않는다. 연속 같은 파일 반복 0회, 최근 4초 안 같은 파일 재사용 0회다. 원본 절차적 합성 SFX/BGM의 저작자·출처·CC0-1.0 메타데이터와 실제 WAV SHA-256을 확인했다. 정통 항공기/선박 현장 녹음이 아닌 절제된 시네마틱 cue다.

SFX 강도는 LOW 0.048, MEDIUM 0.09, HIGH 0.145, PEAK 0.235의 실제 gain으로 구분한다. BGM 에너지와 FAST의 pulse도 이벤트 타이밍을 따른다. TTS 우선 믹스의 실제 envelope 최저 gain은 BGM 0.16, SFX 0.25이고 attack 0.18초/release 0.45초다. 기존 입력 PCM을 성분별로 독립 재구성했을 때 float32 반올림 수준의 오차로 일치했으며 그 PCM/큐 파일이 최종 v003과 동일한 바이트임을 확인했다. 음성 구간 10ms RMS bin의 음성 대 duck된 SFX+BGM 비율 중앙값은 24.05dB지만 이것을 발음/청취 명료도의 보증으로 해석하지 않는다.

**효과음 배치는 30fps 프레임 그리드에 맞으며 48kHz에서 프레임당 1,600샘플이다.** 6자리 Scene JSON 시간 반올림과 프레임 시간의 최대 차이는 약 0.333μs다. 실제 AAC와 준비된 PCM의 상관 정렬 오프셋은 **0샘플**, 유사도는 **0.999983283**다. 실제 화면의 fade는 0 opacity에서 시작하므로 첫 양수 노출은 보통 다음 1프레임이고 더 강한 의미 판정 alpha 기준은 2프레임 늦을 수 있다. 모든 효과음과 완전히 밝아진 픽셀이 0프레임 차이라는 주장은 하지 않는다. 마지막 SHANGHAI의 새 경로·라벨은 **11.233333초**, 대응 SFX 시작은 **11.200000초**다.

실제 최종 AAC를 다시 decode해 측정한 통합 loudness는 **−18.0 LUFS**, true peak **−2.5 dBTP**, sample peak **-2.5024dBFS**다. 비정상/클리핑 샘플은 0이다. AAC decoder의 마지막 블록에는 512개의 padding sample이 있으나 MP4 video/audio presentation과 container 길이는 정확히 12.000초다.

[독립 최종 AV](INDEPENDENT_FINAL_AV.json), [입력 성분/ducking 검사](INDEPENDENT_AUDIO_INPUT.json), [사용 SFX 메타데이터](sfx_sources.json), [실제 cue 타임라인](sfx_cues.json)을 함께 보존한다. 직접 청취하지 않았으며 eSpeak의 기계적인 한국어 음색을 프리미엄 나레이션 품질로 인증하지 않는다.

## 모바일 재생·다운로드와 보존

375×812 viewport의 실제 Chromium에서 전체 12초를 실시간으로 끝까지 재생했다. main/SFX OFF 모두 360프레임 decode, dropped/corrupted frame 0, browser 오류/재생 정체 0이다. browser 검사 중 렌더 요청은 0회다. 지도 영상의 실제 encoded keyframe 15개를 375px 너비로 직접 검수했다. 실물 휴대폰 화면·스피커 검증이나 사람이 전체 음성을 들으며 본 검증은 아니다.

main과 SFX OFF 각각 13개 산출물(최종/무음/보고서/Scene 파일 등)을 **브라우저 attachment 다운로드**하여 저장된 바이트와 HTTP SHA-256 일치를 확인했다. 250ms 간격 다운로드로 Chromium 연속 자동 다운로드 제한에 영향을 받지 않도록 검사했고 보안 설정을 해제하지 않았다. media Range 요청은 206을 반환한다. [Main 증거](MOBILE_FULL_PLAYBACK_AND_DOWNLOAD.json), [SFX OFF 증거](SFX_OFF_MOBILE_FULL_PLAYBACK_AND_DOWNLOAD.json).

보존 범위의 **867개 고유 파일, 2,198,487,765바이트**를 독립 streaming SHA-256 검사했다. public v004/기존 Scene·cache 188개, 기존 프로젝트 570개, MASTER·75초 기준 124개, 최종 frozen source 17개, 승인 계획과 source 백업이 모두 일치한다. 기준 Git 커밋이 현재 이력의 ancestor임을 확인했다. 이 숫자는 검사 범위이며 모든 신규 파일이나 모든 캐시를 무제한으로 해시했다는 뜻이 아니다. 기존 MASTER/75초를 다시 decode하거나 렌더하지 않았다. [보존 검사](INDEPENDENT_PRESERVATION.json).

## 남은 한계와 회귀 검증 상태

- 고품질 native FLAT terrain은 등록된 동아시아 영역에 우선 적용된다. 다른 지역은 보존된 V3 Earth 경로를 사용하며 동일 native FLAT coverage를 검증했다고 주장하지 않는다.
- eSpeak 한국어 나레이션은 기능 검증용이며 기계적인 음색이 남는다. 직접 청취/실물 휴대폰 검사는 미실시다.
- 지형을 유지하는 FLAT→야간 Earth 전환에서 재질·조명 변화는 눈에 보인다. 지도 전체가 가려지는 전환은 아니다.
- CPU 내부 4K Earth 렌더 비용이 크다. [실측 벤치마크](BENCHMARK.md)에 캐시 시간과 새 렌더 시간을 구분했다.
- retention 수치는 의미 있는 primitive/event의 연출 검사이며 실제 시청자 유지율·조회수 예측이 아니다.

최종 실제 승격 상태의 **전체 회귀 검사 255개가 모두 PASS**했다. unittest 실제 실행 시간은 **293.622초**이며 명령 래퍼 측정은 **295.080214초**다. [REGRESSION_REPORT.json](REGRESSION_REPORT.json)에 실제 count·시간·종료코드와 전후 SHA-256을 보존했다. 승격 기본값은 검사 전후 active=true이며, 핵심 17개 소스·불변 인증서·최종 MP4·승격 기록이 모두 동일하다. 이 검사에서 프로젝트·MASTER·75초 렌더를 실행하지 않았다.

실제 모바일 기획 UI에서 FAST 기본 선택, NORMAL/CINEMATIC 선택, SFX ON/OFF를 확인했다. 세 계획 모두 승격된 PRODUCTION_DEFAULT를 사용하며 렌더는 시작하지 않았다. [모바일 옵션 검사](MOBILE_PACE_OPTIONS.json). 공개 checkout의 visual dependency도 확인했다: [53개 의존성 검사](PUBLICATION_DEPENDENCIES.json).

이번 작업은 짧은 Production Default 검증으로 끝낸다. **75초 전체 재렌더, 새 실전 소재 생성, MASTER 재작성은 수행하지 않았다.**
