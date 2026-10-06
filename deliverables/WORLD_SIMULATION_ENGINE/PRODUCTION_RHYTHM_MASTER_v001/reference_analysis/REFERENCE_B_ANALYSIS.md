# Reference B — 실제 화면·리듬 분석

작성: 2026-10-06T00:18:14.411986+00:00 (UTC). 원본: `lv_0_20261006090338.mp4`, SHA-256 `3eeb3c3b28836f086746bb78b52850700a1e4b1f01e7fd7aa3b6379b277e2dc3`.

## 분석 범위와 정밀도

822×1920/H.264/30fps/424프레임, video14.133333초, stereoAAC48kHz/audio12.075333초다. 실제 원본을 decode하고0.5초 contact,0.1초 fine frame, 일부 인접 프레임을 직접 확인했다. 사람이 전체 영상을 실시간으로 청취·재생한 검수는 아니다.

**원본 내용은 frames0–363, 0–12.133333초 미만이다.** frame363(12.100초)는 지도이며 frame364(12.133333초)에서 검정 화면으로 cut 후 CapCut export card가 나타난다. 마지막60프레임/2초를 사건 빈도·정지시간·결말로 계산하지 않는다. [실제 경계](contact_exact_onsets_04.jpg).

영상에는 휴대폰 statusbar와 Shorts UI가 녹화되어 있다. 이것을 원본 지도 디자인의 HUD나 엔진 그래픽으로 분석하지 않았다. 파일의 가상 상황을 현실 사실·예측으로 인증하지 않는다.

## 의미 있는 사건

첫 프레임에 이동체/발광 선두가 이미 움직인다. clip 앞의 launch가 보이지 않으므로 새 출발 시각을0초로 만들어 세지 않는다. 아래7개는 관찰 가능한 새 의미 사건이다. 대부분0.1초 sampling/편집적 판정이며 국가 tint의 첫 가독 시점은 약±0.1–0.2초 불확실성이 있다. 두 impact의 인접 프레임은 별도로 확인했다.

| ID | 관찰 시각 | 사건 | 화면 근거 |
|---|---:|---|---|
| B01 | 0.733초 | country_reveal | Primary highlighted geographic target enters the view while existing moving heads continue. |
| B02 | 1.967초 | impact | Converging movement becomes one distinct impact center. Continuous later ring growth is not counted again. |
| B03 | 4.800초 | region_highlight | Secondary coastal region becomes visibly warmer/redder; terrain and region context remain. |
| B04 | 6.000초 | entity_spawn | A fleet/group enters as a new actor, not another country tint. |
| B05 | 7.400초 | counter_response | Previously neutral group center changes to an active luminous state before departure. |
| B06 | 8.100초 | route_start | New outgoing movement separates from the group and crosses toward land. |
| B07 | 10.900초 | impact | Outgoing movement resolves into a second discrete geographic impact. Later ring expansion remains the same event. |

새 onset 간 평균 **1.694초**, 최대 **2.833초**, 최소 **0.700초**다. 첫 화면의 이미 진행 중인 상태는 별도로 기록한다. 평균은 실제 onset의6개 간격으로 계산했으며 길이÷사건 수로 대체하지 않았다.

카메라 pan/zoom, 자막 교체, 같은 충격 효과의 매 프레임 성장·입자를 각각 새 사건으로 세지 않았다. 완전 자동 의미 detector의 측정값이나 복원된 원본 제작 타임라인이 아니다. 상세 uncertainty/evidence frame은 [REFERENCE_B_EVENTS.json](REFERENCE_B_EVENTS.json)에 기록했다.

## 카메라·다음 사건 예고·미세한 완급

0초부터 넓은 지역을 빠르게 이동한다. 약1.8–2.4초에 속도가 줄고 impact가 시선을 받는다. 약2.4–4.4초에는 나라 윤곽을 유지하며 효과의 Peak와 감소를 읽게 한다. 약4.5초부터 다음 해안 지역으로 접근하여4.8초의 tint,6.0초의 새 actor를 미리 예고한다. 약6.6–8.1초에는 actor가 읽힐 시간을 남긴 뒤 activation→departure로 상황을 진행한다. 마지막에는 local impact를 잠깐 읽게 한다.

짧은 settle이 보이는 구간은 대략2.0–2.3,4.1–4.4,6.8–7.2,11.3–11.7초다. 완전 정지나 정확히 측정한 camera velocity0이라는 뜻은 아니다. 같은 속도로 계속 이동하는 구성이 아니라 **빠른 travel→감속→핵심 인지→다음 대상 예고→재가속**의 리듬이다.

[Map ROI pixel-change proxy](MAP_ROI_CHANGE_PROXY.json)는 UI/footer 대부분을 제외한140×220 grayscale의 프레임 차이를 계산했다.0.5–1.5초 평균9.856,2.0–2.5초2.224,4.5–5.5초9.540,6.5–7.5초2.920이다. 카메라와 VFX/텍스트가 함께 영향을 주므로 이것을 camera speed나 실제 배속 배수로 변환하지 않는다.

## 텍스트 on/off

본문을 복제하지 않고 약12개의 짧은 역할 단위만 기록했다. lower-center의 나레이션 fragment이며 **지도 위치와 직접 연결된 국가/거리 라벨의 예시는 아니다.** 글자/색/배치/UI를 그대로 이식하지 않는다. fade와 잠깐의 작은 공백을 사용하고, 짧은 clause를 사건 전에 보여 기대를 만든다.0.2초 수준의 매우 짧은 qualifier도 있으나 모바일 가독성을 위해 엔진에서 그대로 따라야 하는 목표가 아니다.

| ID | 대략 표시 구간 | 역할 |
|---|---|---|
| T01 | 0.0–0.8초 | Initial question/context clause;already present at frame0 |
| T02 | 0.9–2.2초 | Hypothetical condition clause |
| T03 | 2.2–2.7초 | Short question fragment |
| T04 | 2.7–3.4초 | Question completion |
| T05 | 3.8–4.6초 | Next geographic subject preview |
| T06 | 4.8–5.8초 | Geographic proximity fragment |
| T07 | 5.8–6.0초 | Very short qualifier |
| T08 | 6.1–7.4초 | New-actor/action clause |
| T09 | 7.6–8.7초 | Counter-response setup |
| T10 | 8.8–10.0초 | Outgoing-action clause |
| T11 | 10.1–10.5초 | Very short target qualifier |
| T12 | 10.6–12.1초 | Outcome/action clause;excerpt cuts off |

표의 끝점은 최초 비영점 opacity가 아닌 실제 still에서 구분되는 caption 구간에 대한 약±0.1–0.2초 판정이다. [Caption contact](contact_captions_02s.jpg).

## Peak 전후와 재사용 가능한 후보 원리

첫 Peak는1.2–1.93초의 선두 수렴,1.967초의 contact,2.7–3.3초의 최대 visual reward,3.4–4.4초의 decay와 다음 지역 힌트로 이어진다. 두 번째는7.4초 actor activation→8.1초 departure→10.9초 contact→11.3–11.8초 local reward다. 발광 ring 성장 전체를 여러 차례의 새 impact로 부풀리지 않는다. 파일의 exportcard는 결말이 아니다.

후속 레퍼런스 A와 비교해 공통인지 확인할 후보는 다음과 같다.

- 시작할 때 상황이 이미 진행 중이고, 큰 질문은 짧게 공개한다.
- 현재 효과를 읽는 동안 다음 대상의 힌트를 먼저 주고 카메라가 따라 준비한다.
- actor 등장→활성화→이동→반응처럼 **종류가 다른 사건**이 인과관계를 갖는다.
- travel에는 가속, 핵심에는 감속/짧은 settle을 사용한다. 전체 영상 배속과 다르다.
- Peak는 접근과 후속 결과가 함께 있어야 하며 큰 VFX 하나만 반복하는 구성이 아니다.

이는 B에서 나온 후보일 뿐, A와의 공통 검증을 끝냈다는 선언이 아니다. 원본 국가 순서·대본·불투명 tint·무기/폭발 디자인·자막 font·게임 같은 glow를 복제하지 않는다. 현재 승인된 PREMIUM FLAT v004/V3 재질을 유지하며 리듬만 번역할 대상이다.

오디오 측정은 별도 [B_AUDIO_MEASUREMENTS.json](../rhythm_reference_audio_v001/B_AUDIO_MEASUREMENTS.json)에 있다. 직접 청취하지 않았으며 mixed waveform의 dip/onset을 검증된 개별 SFX 개수로 표시하지 않는다.

이번 작업은 읽기·분석·분석용 frame/contact 추출만 했다. 엔진 수정·샘플/75초/MASTER 렌더는0회다. 참조 이미지·원본은 private evidence이며 Git/공개 deliverables로 복제하지 않는다. 출처 자산을 상업 사용 라이브러리로 재사용하지 않았다.
