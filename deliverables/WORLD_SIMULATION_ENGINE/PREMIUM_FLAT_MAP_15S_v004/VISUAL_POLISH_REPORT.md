# PREMIUM FLAT MAP — FINAL VISUAL POLISH v004

검수 완료한 15초 샘플이다. **1080×1920 · 9:16 · 30fps · H.264 · yuv420p · limited-range BT.709**. 내부 렌더는 2160×3840이며 Lanczos로 다운샘플했다. TTS·자막 OFF, BGM·13개 효과음 ON을 기존 v003과 동일하게 유지했다. 샘플 스타일의 최종 사용자 승인은 대기한다. 75초 렌더와 기존 MASTER 재렌더, 생성기 기본 프리셋 교체는 하지 않았다.

## 다운로드와 비교

- [사운드 포함 v004 MP4](flat_map_premium_test_15s_v004.mp4)
- [무음 v004 MP4](flat_map_premium_test_15s_v004_muted.mp4)
- [Flat 시작 비교](before_after_flat.png)
- [국가·도시 강조 비교](before_after_country_focus.png)
- [출발·이동·네트워크·접근 기체 비교](before_after_entity_route.png)
- [전환 직전·중간·직후 비교](before_after_transition.png)
- [마지막 Earth 비교](before_after_earth.png)

비교는 기존 v003과 최종 인코딩된 수정본의 같은 실제 프레임이다. 0.5/1.8/2.0/4.5/7.8/10.8/11.9/11.9667/12.1/12.4/14.9초, 총 11개 시각을 사용했다. native1080과375px 모바일 축소를 함께 표시했고 비교 프레임을 재색보정·미화·업스케일하지 않았다. 비공개 첨부 레퍼런스 영상·이미지·음원은 공개 산출물에 넣지 않았다.

## 가장 큰 개선

1. 지형의 과한 밝기를 낮추고 미세한 local contrast·detail sharpening을 보정했다. 깊은 바다와 자연스러운 육지 색을 유지하며 해안선을 검은 테두리로 만들지 않았다.
2. 선택 국가에 지형을 유지하는 반투명 warm tint, 얇은 경계 강조, 국소 대비를 적용했다. 주변 밝기·채도를 조금 낮췄으며 주변 지리는 계속 보인다.
3. 주요 도시를 Noto Cinema400, 최종1080 기준 최소54px와 약한 dark edge/shadow로 표시한다. 고정된 공항 외곽 slot으로 기체·지형과의 충돌과 라벨 흔들림을 줄였다. 라벨은 지리 anchor와 연결된다.
4. 주요 3D 항공기 표시의 크기 하한88/82px, 얇은 발광 route core 약5.5px, 더 읽기 쉬운 head와 fading trail을 사용했다. 실제 footprint는 회전·원근에 따라 달라진다. 동일 공항 출발/수렴 기체를 부드럽게 분리했다.
5. 전체 화면 대기 veil을 제거하고 같은 검증된 지리 좌표의 평면→구면 기하 전환, 등록된 카메라, 재질 정착을 연결했다. Earth의 surface exposure/fill을 높이고 도시광·구름·대기층은 유지했다.

AUTO FOCUS, NEXT EVENT CAMERA, Entity/Route/MAP VFX의 이벤트 시각·경로·GIS·카메라 설계는 그대로다. 새 Story Engine·Plugin·UI는 추가하지 않았다. 새 렌더 마감은 `visual_polish.version=v004`에만 적용되는 별도 adapter이며 기존 렌더러의 바이트와 캐시 digest는 보존했다.

## 부분 재렌더와 버전 출처

기존v003을 덮어쓰지 않고 독립적으로 변경된5장면을 내부v004 초안으로 렌더했다. S001–S004는 지형/국가/라벨/Entity/Route 변경, S004는 기하 전환, S005는 지형 밝기와 incoming 연결 변경 때문에 각각 캐시가 달랐다. 이는 75초나 기존 MASTER를 다시 만든 작업이 아니다.

실제 초안 인코딩 검수에서 S004 마지막 타이베이 접근의 두 항공기가 겹치는 것을 발견했다. 초안·완료장면·캐시·체크포인트를 보존하고 **S004의 `visual_polish.entity_separation=v1`만 수정한 내부v005**를 만들었다. 실제 재실행은 **새 S004 하나 + 네 Scene 캐시**였고, S001/S002/S003/S005의 영화와 audit SHA가 초안과 완전히 같다. 공개 요청 이름은 `PREMIUM_FLAT_MAP_15S_v004`로 유지한다. [부분 재렌더 증거](PARTIAL_RERENDER_PROOF.json), [실제 Scene Plan](scene_plan.json), [독립 검수](INDEPENDENT_REVIEW.md)를 제공한다.

기체 분리는 실제 충돌회피/항로 변경 계산이 아니다. 정확한 항로와 ground anchor를 유지하면서 실제 3D model Box3를 현재 투영으로 검사하고 표시 proxy만 옆으로 옮긴다. 짧은 leader가 원래 위치와 표시를 연결한다. 정지기 사전 예약은 기체를 조기 등장시키지 않는다. moving pair는375px 기준 약12px 간격을 확보했으며 실제90프레임 렌더 중 보이는 기체 경계 겹침 검사도0이었다. 원래 경로/진행률/등장 시각은 불변이다.

최종 사운드 MP4 SHA-256: `9e9df36ac7ef172c1fc46573f6f45b9628b5a395b8e8043e5ada103680ee3bfb`
무음 MP4 SHA-256: `275ce496fbaa956f44e66d56bbde0e19052dcc276275c0dcda8532bc650d16b9`
두 파일의 coded H.264 video track SHA가 동일하다. 원본v003·초안v004·내부v005의 오디오 WAV SHA도 동일하다.

## 품질 게이트

| 항목 | 실제 검수 결과 |
|---|---|
| 육지/바다·중국/한반도/일본/대만 | native·375px 비교에서 구분된다. 밝은 지형의 개선은 소폭이며 전체 지도 대비가 크게 증가했다고 주장하지 않는다. |
| 자연스러운 해안선·지형 | 실제 Natural Earth 표면과50m 벡터 유지. 불투명 원색/인위적 검은 해안선 없음. |
| 국가 강조·AUTO FOCUS | 선택 색·경계가 읽히고 산맥/relief가 남으며 주변 지리도 유지된다. |
| 도시 라벨·Entity·경로 방향 | 주요 도시명과3D 기체가 더 쉽게 읽히고 route head/방향/궤적을 구분할 수 있다. |
| 다중 기체 겹침 | 수정 native90프레임의 실제 posed3D 경계 겹침0, 라벨/model 겹침0. 인코딩10.8/11.9667초 픽셀에서도 분리 확인. |
| Flat→Earth 정보 |11.9/12.1/12.4초에도 지역·라벨·항로가 계속 보인다. opaque geographic veil0. 기존>=50%veil 약0.6333초 구간 제거. |
| 마지막 Earth |14.9초 중국·한국·일본/동아시아 해안선이 더 밝게 읽히며 도시 불빛·곡률·대기층 유지. |
| 기술 QC |450 decoded frame 검사, black/duplicate/near-frozen/missing asset/WebGL/broken route/clipping 오류0, 경고0. [QC report](qc_report.md). |
| 실제 전체 재생 |375×812 Chromium에서15.0363초 실제시간으로 끝까지 재생,450decoded, dropped0, corrupted0, element/browser error0. |
| 실제 다운로드 |앱 attachment 다운로드13개 완료, SHA 일치. HTTP Range206 검증. 공개 GitHub 확인은 별도 `PUBLIC_DOWNLOAD_VERIFICATION.json`에 기록한다. |
| 기존 기능·파일 |원래 renderer/cache identities 보존, 작은 opt-in schema/dispatch/QC 추가만 수행. 기존부분수정/캐시/checkpoint/audio/subtitle/I2V/defaultPlanner 유지. 이번 샘플에서TTS/자막ON을 새로 시험했다고 주장하지 않는다. |
| 레퍼런스의 즉각적 전달력 |국가·도시·기체·방향·변수·결과를 연결하고 정보가 없는 전환을 없앴다. 자체 frame 검수 판정이며0.5초 이해속도나 시청 유지율을 사람에게 실험한 결과는 아니다. |

실물 스마트폰 하드웨어 검사나 직접 청취로 기록하지 않는다. 실제 브라우저 재생/음원 디코딩·파형/레벨 검수와 사람의 청취는 구별한다.

## 지형 측정과 Retention

4.5초 같은1080 좌표에서 중국 내부[40,320,200,600], 바다[700,1400,980,1780]를 비교했다. 선택 patch의 weighted8bit encoded-sRGB Y 중앙값은 육지170.0988→163.9006, 바다35.2642→29.4086이다. 육지-바다 차이는134.8346→134.4920으로 유지됐고 육지 variation/std는12.8221→13.0647(약+1.89%)로 소폭 늘었다. 전체 지도 segmentation/선형 광도/새DEM 디테일 인증이 아니다.

기존 Retention/Event Diversity Gate를 유지했다. 의미 있는12사건,11종류, 평균1.2182초·최대2.9667초, 첫3초4사건, 동일종류 연속최대1, Peak1이다. 단순 camera pan/zoom은 세지 않는다. 자동 E006은5.2667초 `country_highlight`로 귀속하지만 이전 tint 자체를 신규 사건으로 다시 계산하지 않았다. 독립 검수에서는 **새 JAPAN 라벨이 실제 등장한5.3초**를 새로운 정보 공개로 인정했고, 보정 뒤에도 위 count/평균/최대간격은 같다. 세밀한 자동 primitive 귀속은 추후 개선할 부분이다.

원본 레퍼런스의 사건 간격은 기존 전체 분석에서 약0.97초/최대2.50초로 측정됐다(초기contact sheet 기준 약±0.25초). 우리의12사건은 무작정 원본 밀도를 복제하지 않고 가독성·원인→반응→우회→네트워크→결과를 유지한다. 시청자의 실제 유지율을 측정하지 않았다.

## 실제 시간·비용

CPU_LOCAL,CPU4quota/SwiftShader, HIGH/내부2160×3840/출력1080×1920/30fps에서 기록한 수치다. 추정시간을 실측으로 보고하지 않는다.

| 측정 구간 | 실제 기록 |
|---|---:|
| 순수한 코드 작성 활동 시간 | 별도 활동 계측 없음. 파일 시각을 키 입력 시간으로 환산하지 않았다. |
| 초기 분석·코드·테스트·native스틸 검수의 wall window |4004.547초(66분44.547초),11:06:56.269→12:13:40.816UTC |
| 처음 변경5장면 렌더 |4367.815초 |
| 초안5장면+audio/assembly/QC 전체 pipeline |4390.572초(73분10.572초) |
| 문제 S004만 실제 부분 재렌더 |444.127초(7분24.127초) |
|4cache+1new+audio/assembly/QC 전체 재실행 |464.384초(7분44.384초) |
| 두 production pipeline의 합계 |4854.956초(80분54.956초) |
| 두 자동 전체QC 합계 |28.855초 |
| 수정 S004 native4K 스틸4개+90layout 추가 검사 |44.369초 |
| 모바일전체재생·앱다운로드 검사 harness |21.176초(그 중전체실시간재생15.0363초) |
|11개 시각 전후 이미지 추출·조합 |22.995초 |
| 작업시작→영상/QC/검수/패키징 완료의 전체 wall |10133.271초(168.888분),종료2026-10-05T13:55:49.540227+00:00 |

코드 수정·추가 검토가 첫 렌더와 겹친 구간이 있어 위 시간을 전부 합산해 작업 총시간으로 만들지 않는다. Git 게시·공개다운로드 확인 종료는 별도 공개검증 JSON에 기록한다. 기존v003 재실행356.785초는 **1새 S004+4cache**였으며, 이번5변경 장면의 총시간과 같은 범위로 비교할 수 없다.

최종 Scene provenance의 native Flat12초는1578.069초/영상1초당131.506초다. 첫Flat구현의12초1193.521초/99.460초보다 이번 마감 비용은 약32.22% 높다. 이번polish가 예전Flat보다 빨라졌다고 주장하지 않는다. Earth3초는2755.037초/영상1초당918.346초다. 이 샘플의 다른 shot끼리 관찰한 Earth/Flat 비용비는 약6.98배이며 동일구도의 통제 벤치마크나75초 시간 예측이 아니다. Flat1tap/Earth7motion taps, terrain·cloud·shader·카메라 구도 차이가 있다. 경량Flat cache/부분재렌더의 장점은 유지했지만 CPU 비용 최적화는 남는다.

## 보존·출처·구현

기존 MASTER V1/V2/V3·75초 산출물/자산570파일과 별도75/MASTER baseline124파일, 기존샘플 baseline143파일을 실제SHA-256으로 대조했다(서로 겹치는 baseline이며837개의 고유 파일이라는 의미가 아님). 샘플142개 원래 경로는 byte동일이며 가변current project pointer의 이전v003369bytes는 정확한 archive에 보존했다. 원래 Git source archive77,240,320bytes의 SHA도 일치한다. Git 이력을 삭제·재작성하지 않았다. [보존증거](PRESERVATION_PROOF.json).

GIS/Natural Earth1의 native21600×10800 source에서 만들어진 기존2880×4380 지역 crop(104–152E/−8–65N) 및50m country/coastline vector를 재사용했다. 실제Geo catalog의 Seoul126.997785/37.568295,Tokyo139.749462/35.686963,Taipei121.568333/25.035833을 유지했다. 이 지형은 cartographic shaded relief와 기존bump 표현이며 측량DEM/현재위성기상/물리적수심이 아니다. 별도2.5D깊이 처리도 실측고도로 주장하지 않는다.

Natural Earth는PublicDomain. 기존 Earth/day/night/cloud 입력의 Solar System Scope/NASA 출처와CC-BY4 요구를 유지한다. OpenSans·Noto·Three.js·절차적3D/효과음의 출처/라이선스는 [source_report.md](source_report.md)를 따른다. 저작권불명 신규자산이나 생성형지도를 사용하지 않았다.

구현은 새 `flat_polish_renderer.js`, `geographic_polish_transition.js`, `earth_polish_adapter.js`,선택적 `flat_entity_separation_polish.js`와 별도 native pages/runners다. 기존 renderer/SceneJSON은 삭제하지 않았다. `tools/build_flat_visual_polish.py`는 존재하는 원본을 새 version으로만 만들고 guard를 통과하지 않으면 중단한다. 이번 샘플이 완료된 상태에서 명령을 반복하면 보호 guard가 거부하는 것이 정상이다. 일반 생성기·자연어 수정·부분 렌더·사운드 파이프라인은 기존 실행 방법을 그대로 사용한다.

구조 검증: 기존 Flat42/JS20, core+revision34, 새 opt-in4/JS21의 관련 검사가 통과했다. 각 검사의 겹치는 항목을 총 독립 test 수로 합치지 않았고, 소스/계약 test를 화질·시청 유지율 인증으로 사용하지 않았다. 최종 실영상90/450프레임 검사와 모바일 playback을 별도로 수행했다.

## 남아 있는 문제와 승인 범위

- 지역NaturalEarth atlas→8K위성표면의 북쪽 재질 혼합 경계가 보인다. 지리는 사라지지 않지만 재질의 완전한 일치는 아니다.
- 12초 Earth overview로 넘어갈 때 기체 표시가 작아진다. 마지막 Earth 경로도 Flat보다 얇고 SEOUL 주변 도시광과 경쟁한다. 글로벌 결과/도시 연결은 읽히지만 근접 설명은 Flat이 더 명확하다.
- 지형 개선은 미세한 마감이며 전체 지도 대비의 큰 상승이나 진짜 DEM 추가가 아니다. 해상도는 기존 검증된 소스 범위를 따른다.
- CPU polish 비용은 기존 Flat보다 늘었다. 캐시/단일 Scene 교체와 Earth 대비 경량성은 유지되지만 고품질 CPU 렌더가 즉시 생성되는 수준이라고 보고하지 않는다.
- 자동 E006 primitive 귀속은 manual로 신규 JAPAN 정보 등장을 확인했다. 이후 gate 개선 시 항상 새 정보만 세는 정밀 바인딩이 필요하다.
- 모바일은 실제375×812 브라우저 검사다. 물리적 단말/직접 청취/조회수/시청 지속 성공을 검증한 것은 아니다.

요청된 시각 마감 샘플은 자체·독립 검수를 통과하여 사용자에게 제공 가능하다. 사용자의 샘플 승인 전까지75초 전체 렌더나 생성기 default 교체는 수행하지 않는다.
