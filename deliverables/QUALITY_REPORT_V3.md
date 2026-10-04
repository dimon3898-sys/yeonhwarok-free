# CINEMATIC WORLD MAP — MASTER V3 품질 보고서

작성일: 2026-10-04 UTC. **20초 유음·묵음 MP4 생성 완료, 규격·600프레임 디코딩·모바일 브라우저 재생 검사 통과.**

V2 대비 공간·재질·입체 항공기의 개선을 실제 비교 프레임에서 확인했다. 사진 수준 타깃과 동급, 직접 청감 합격, 실물 스마트폰 검수 또는 시청 지속률 향상까지 인증하는 보고서는 아니다. GitHub 전달 상태는 마지막 절에서 별도로 기록한다.

## 1. 산출물과 렌더 설정

| 항목 | 실제 결과 |
|---|---|
| 영상 | `outputs/master_cinematic_20s_v3.mp4`, `outputs/master_cinematic_20s_v3_muted.mp4` |
| 규격 | 1080×1920, 9:16, 30fps, 20.0초, H.264/yuv420p MP4, SDR |
| 색 정보 | BT.709 primaries/transfer/matrix, limited range(tv), 명시적 H.264 VUI |
| 음향 | 유음본 AAC 48kHz stereo; 묵음본에는 audio stream 없음 |
| 내부 렌더 | 2160×3840 선형 HDR WebGL, MSAA 2, nominal scene sample 1, 7탭 운동 번짐 근사 |
| 인코딩 | JPEG 99 → full BT.601/limited BT.709 변환 → Lanczos 축소 → H.264 CRF 15 slow |
| 이미지 | `preview_v3_01.png`~`preview_v3_04.png`, `preview_v3_hero.png` |
| 실제 비교 | `outputs/VISUAL_COMPARISON_V2_V3.png`; 0.5/2/6/10/15/19초의 V2·V3 동일 시점 |

앞 10초는 검수된 r15의 두 5초 구간, 뒤 10초는 r23으로 순차 렌더했다. 완성 manifest와 입력 동등성 proof를 검사한 뒤 picture bitstream을 재압축 없이 연결했다. 각 source SHA는 segment manifest에 기록하며 r15 source snapshot은 `docs/review-sources/v3-r15/`에 보존한다. V2의 기존 구면·geodesy·camera·scene 구조를 유지한 별도 V3 shader/material/model 개선이다.

## 2. V2 문제와 가장 큰 개선 5가지

V2는 이미 구면 기반 GIS와 카메라·항로·도착 연출을 갖췄다. 다만 큰 정보 블록, 상대적으로 단순한 지표/대기 재질과 확대 시 드러나는 기존 기체의 평평한 날개·원통형 엔진이 영화적 공간감을 제한했다.

| 핵심 개선 | 변경 | 실제 프레임 관찰 |
|---|---|---|
| 1. 지도 공간과 노출 | 별도 8K day/night, terminator, 깊이를 사용하는 Sun/Moon 대기 | 얇은 blue rim·warm 도시권·지구 곡률의 구분이 강화됨 |
| 2. 입체 항공기 | 새 original 곡면 fuselage/airfoil/nacelle/fan, quarter-front 시점 | 동체·날개·엔진 입구와 하부 명암이 기존 기체보다 구분됨 |
| 3. 재질과 공통 조명 | HERO coating, Earth/cloud cube 반사, Sun/Moon 자체 그림자 | 기체가 지구·구름과 같은 빛을 받는 공간의 주체로 읽힘 |
| 4. 구름의 높이와 깊이 | 기본 altitude shell, HERO coverage 기반 density raymarch | 15초 전후 구름·기체·지표가 서로 다른 거리로 느껴짐 |
| 5. 화면 규모와 정보 리듬 | 얇은 도시명, chase→orbit→HERO→arrival→overview | 반복 HUD를 줄이고 이동·확장·곡률·결말의 규모 변화에 시선을 집중 |

주 작업자는 최종 모바일 contact 7장(0~19.5초, 0.5초 간격 40시점)과 동일 시점 비교 6쌍을 직접 확인했다. 눈에 보이는 깨진 기체, 라벨/기체 clipping, 항로 단절은 발견하지 않았다. 15초 HERO의 공간감이 가장 강하고 16~18초 Singapore 접근으로 연결되며, 19~20초 전체 항로와 도시명을 읽을 수 있다. 모든 600프레임을 사람이 한 장씩 판독했다는 의미는 아니다. V2의 큰 정보 블록은 한 프레임의 설명력에서 장점이 있어 모든 정보 가독성이 V3에서 개선됐다고 주장하지 않는다.

## 3. 객관 검사와 품질 게이트의 범위

| 검사 | 결과 | 근거/범위 |
|---|---|---|
| 전체 디코딩 | 600/600, 20.0초 | `master_cinematic_20s_v3_validation_v3.json` |
| black/empty-earth/exact duplicate | 각 0 | 실제 인코딩 RGB 검사 |
| 사실상 정지 | Earth ROI coarse-motion 임계값 0.1에서 최대 0초 | 블록 평균 차이 검사; 시청자의 정체감 자체를 측정하지 않음 |
| 첫 0.5초 움직임 | coarse-motion 최소 2.697875 | 디코딩된 Earth ROI의 변화 확인 |
| 문자·기체 | clipping, 기체 safe-scene 이탈, label/plane 근접, label overlap 각 0 | 최종 영상과 대응 scene audit; 관찰 검수 보완 |
| 글꼴 | 서울 330.926/도쿄 337.713/싱가포르 576.843px, 각각 한 폭 | 내부 2160px canvas glyph metric; `fonts.load/check` 후 render ready |
| 카메라·항로 | 최대 각도 변화 1.462456470°/30fps frame, progress 단조 증가 | 순간이동 수치 위반 없음; 연출의 자연스러움은 정성 평가 |
| 기하 preflight | 1,201 pose numerical violation 0; 항로별 720표본 고도 11~15km | r23과 같은 engine, 공항 끝점 오차 약 2.6×10⁻¹²km |
| 기체 지구 교차 | 799 가시 pose, 30,272,512 삼각형 검사, 교차 0 | 변경 없는 모델/자세; 최소 여유 2.036287km, 연속 시간·구름 교차 증명 아님 |
| Chrome mobile 재생 | ended 20초, 600 frames/callbacks, drop 0/corrupt 0/error 없음 | 375×667 viewport; 실물 스마트폰 시험 아님 |
| 원본 크기 Chrome 재생 | ended 20초, total 600, drop 2/corrupt 0/error 없음 | 브라우저 presentation에서 2 drop; 파일에는 600프레임 정상 디코딩 |
| 유음/묵음 picture 동일성 | 전체 600 RGB 동일, 앞 300 RGB는 검수된 r15와 동일 | `v3_final_picture_identity.json`의 실제 디코딩 비교 |
| r15→r23 앞 10초 입력 proof | complete/exactInputsEqual/staticInputsEqual true, 120Hz 1,201 pose, mismatch 0 | `v3_r15_r23_first10_input_equivalence_bounded.json`; GPU draw/RGB proof 아님 |

전체 RGB 연결 SHA-256: `5249c7f13f6d5a4d1c6f3bcb7d50e6dc694a851ca46da32c08d1efa1bc1fcd35`.

authoring timeline에는 20개 사건 시작점이 있고 평균 간격 1.010526초, 최대 1.9초다. 첫 3초에는 0/0.3/0.6/0.9/1.2/1.5/2.2초의 7개 시작점이 있다. 움직이는 시작, 도시/대기 접근, 항로 생성과 기체 출발을 순차 공개한다. 이 숫자는 설계된 사건 간격이며 모든 사건의 지각 강도나 실제 retention 실험 결과가 아니다. 규모 확장(8~10초), HERO(14~16초), 최종 pullback(18~20초)은 직접 프레임 검수에서 확인했다.

## 4. 사운드와 레퍼런스 평가

original synth의 낮은 tension, opening/final impact, low whoosh, route sweep, stereo pass-by와 arrival hit를 cue sheet에 배치했다. 0/0.6/1.2/1.5/7.1/8.3/10.2/14/16.5/17.25/18.1/19.2초가 주요 cue다. 실제 최종 AAC 측정은 **−18.31 LUFS, −2.49dBTP, LRA 7.9LU**이며 `v3_final_audio_validation.json`에 기록한다. 최초 6초 원 score와의 교차상관은 0.99999355, 측정 지연 0초(0.25ms 해상도)다. 20초 browser 재생에서 audio decode를 확인했으나 직접 청취는 하지 못했다. 음색·밸런스·각 hit의 청감 합격을 주장하지 않는다. loudnorm pass1의 출력 예측과 실제 AAC 측정값을 구분한다.

첨부 영상의 기존 분석(`docs/REFERENCE_ANALYSIS.md`)은 지도 content 사건 간격 평균 약 0.97초/최대 2.5초(±0.25초 관찰 오차), 목적지→결과→새 범위 공개를 장점으로 기록한다. V3는 이동·목적지·네트워크·곡률·최종 전체 경로로 상황을 이어가며 과한 충격 효과나 디자인을 복제하지 않는다. 레퍼런스의 관찰 간격과 V3의 authored 간격은 측정 방식이 달라 수치만으로 우열을 판정하지 않는다. GIS/재질/기체의 정돈된 일관성은 개선으로 평가하되 매우 희미한 배경 네트워크는 작은 화면에서 레퍼런스처럼 강한 상황 변화로 읽히기 어렵다.

사용자의 VISUAL TARGET은 대화에서 주 작업자가 정성 분석한 inline 이미지다. 로컬 원본이 없어 동일 픽셀 비교를 하지 않았고 실제 비교 이미지는 V2·V3 두 열이다. 목표의 얇은 대기·warm 도시권·입체 기체 방향은 반영했지만 사진 같은 근접 항공기/지표/도시 랜드마크와 동급이라고 판단하지 않는다. 타깃의 구도·문구·랜드마크 장면을 복제하지 않았다.

## 5. 구현·출처·라이선스

- 최종 renderer는 Three.js 0.170.0(MIT), original WebGL/GLSL·PBR·camera·scene와 FFmpeg이며 Blender 최종 렌더가 아니다. GPU 없는 현재 환경은 Chromium SwiftShader를 사용했다. Blender 단일 프레임 시험은 이 환경의 prototype 비교이며 엔진의 일반적 우열 근거가 아니다.
- Earth day/night/cloud 세 원본은 실제 8192×4096 Solar System Scope, **CC BY 4.0**. 고정 mirror commit·원본·파일별 라이선스 근거·치수·SHA는 `assets/v3/earth/SOURCES_V3.json`에 기록한다. 전체 GitHub repo LICENSE로 외부 texture 사용권을 추정하지 않았다.
- Natural Earth 벡터/해안·국가 데이터는 public domain으로 보존한다. 사용한 미세 topology bump는 three-globe MIT이며 실제 DEM displacement/도시 건물 모델이 아니다. 실제 공항 좌표와 구면 great-circle을 사용하되 모든 국경의 새 영상별 정밀 측량 검사를 했다고 주장하지 않는다.
- `src/aircraft_v3.js`: original 31 mesh, 21,046 vertices, 37,888 triangles. 외부 모델·로고·사진 없음. 항공기 화면 크기는 **visual proxy**이며 실측 길이나 실제 비행 시간을 재현하지 않는다.
- Open Sans Light는 Apache 2.0. 음악/SFX waveform은 original CC0; 외부 음악·레퍼런스 음원을 복사하지 않았다.
- `assets/v3/CREDITS_V3.txt`와 두 MP4의 attribution metadata를 보존한다. `v3_final_metadata_validation.json`에서 Solar System Scope/원본/CC BY 4.0 링크를 확인했다. YouTube 게시 설명에도 이 저자·출처·라이선스 링크가 필요하다.

대기는 고도 밀도·시선 길이·지구 차폐를 고려한 RGB Rayleigh single scattering(12 view/각 4 Sun·Moon 표본)이다. 전체 다중 산란/Mie·실제 달 광량 재현은 아니다. Sun의 HERO 최대 5° 회전과 Moon/Hemisphere fill은 공통 방향을 유지한 연출이며 천문 시간 시뮬레이션이 아니다.

HERO 구름은 실제 8K coverage를 gate로 하는 4.5~11km noise density volume(14 view×4 Sun 표본, Sun 경로 최대 40km)이고 나머지는 4.5/7.5km 두 texture shell이다. scene depth로 기체/지표 가림을 처리한다. actual weather/측정 cloud altitude·사진 같은 도시·새 지형을 생성한 것이 아니다. 반사는 128²/면 Earth/cloud cube 근사이며 volume의 완전한 반사나 ray-traced shadow가 아니다. motion integration과 cloud는 완전한 시간 적분이 아니다.

## 6. 남은 약점과 60초 확장 전 해결할 것

1. 배경 항공 네트워크가 매우 희미해 폰 크기에서 새 상황 전달이 약하다. 주 항로와 경쟁하지 않는 contrast/등장 시간 재검수가 필요하다.
2. 확대된 8K 지표·도시광의 제한과 저표본 구름 때문에 중경이 부드럽거나 덩어리로 보인다. regional 고해상도 GIS·cloud alias/LOD 검토가 필요하다.
3. HERO는 입체감이 개선됐지만 기체 중간톤·재질과 근접 표면의 사진 수준 현실감에는 차이가 남는다. 모델을 유지하며 광원/반사/노출을 실제 프레임으로 검수해야 한다.
4. 직접 청취와 실물 스마트폰·YouTube 재인코딩 시험이 필요하다. 파형/AAC decode/desktop viewport만으로 게시 청감·실물 가독성을 확정하지 않는다.
5. 60초 확장 전 새 지역별 texture LOD·공항/도시 좌표·camera safe area, clip 삽입·복귀, 30/60fps motion/triangle 샘플 검사를 재검증해야 한다. 현재 세 도시의 결과가 전 세계 모든 지역 합격을 의미하지 않는다.

객관적인 규격·결함 탐지·picture 동일성·모바일 browser 재생 게이트는 위 범위에서 통과했다. 공간/재질/기체는 V2 대비 명확한 정성 개선으로 평가한다. 실제 retention, 직접 청감, 사진 타깃 동급을 포함한 모든 주관적 게이트를 YES로 표시하지 않는다. UI·60초 생성기·TTS·업로드 자동화는 이번에 구현하지 않았다.

## 7. 원본 보존과 전달 상태

`outputs/v3_preservation_final.json`: 기존 197개 파일 SHA 변경/누락 0, V3 staging 전 기존 tracked repo diff 0. 보존 archive는 354,814,032B, SHA-256 `cc3e9d306388489787344bdea3c99741ed1987c387d39fbb716e11969735ad1e`다. 기존 V1/V2 영상·코드·자산·문서를 삭제하거나 덮어쓰지 않았다.

로컬 최종 산출물과 검증 근거는 `outputs/`에 있다. 전달 파일은 저장소 루트의 `deliverables/`에 추가한다. [GitHub 다운로드 폴더](https://github.com/dimon3898-sys/yeonhwarok-free/tree/main/deliverables)에서 V3 MP4·무음본·5개 프리뷰·비교 이미지·이 보고서·검증 JSON·SHA manifest·ZIP을 제공한다. ZIP에는 동일한 V3 파일과 크레딧을 함께 넣는다. 실제 commit 확인과 원격 다운로드 해시 대조는 게시 후 최종 응답에서 보고한다. 재현 명령은 [README_V3.md](../cinematic-world-map/README_V3.md)를 참조한다.
