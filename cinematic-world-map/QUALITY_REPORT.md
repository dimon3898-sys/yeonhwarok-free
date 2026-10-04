# QUALITY REPORT — THE INVISIBLE CORRIDOR

작성 기준: 2026-10-04, Korea Standard Time. 이 문서는 현재 제작물의 기술 검증과 화면 관찰을 기록한다. 미실행 항목이나 청취하지 못한 사운드를 통과로 표시하지 않는다.

## 레퍼런스 분석

구현 전 작성한 [상세 분석](docs/REFERENCE_ANALYSIS.md), 전체 길이를 포함하는 `docs/contact_0.jpg`–`contact_2.jpg` 참조.

레퍼런스는 822×1920 / 약 30fps / 14.9667초, 실제 지도 콘텐츠는 약 12.8초이며 마지막은 CapCut 카드다. 첫 장면부터 카메라와 발광 이동체가 움직이고, 도착 효과 → 원점 지역 → 이름 → 범위가 순차적으로 공개된다. 주요 콘텐츠 사건 간격은 약 0.97초, 최장 약 2.5초; 엔딩 전환까지 포함하면 평균 1.07초다. 표본 프레임에 기반하므로 사건 경계는 ±0.25초 정도의 근사값이다. 군사 내용, 대본, 사진, 음악과 디자인은 재사용하지 않았다.

새 시퀀스는 민간 항공 물류를 가정한다. 지리 좌표는 창이 103.9915°E / 1.3644°N, 인천 126.4407°E / 37.4602°N, 나리타 140.3929°E / 35.7719°N. 반지름 6371.0088km 구면의 대권거리 4,624.77km + 1,258.11km = 5,882.88km. 영상의 시간은 축약한 연출 시간이고 실제 운항속도를 나타내지 않는다.

## 구현한 효과

- 실제 구면 곡률과 투시 카메라. 지리 좌표, 높이, tilt, yaw, roll을 Hermite 보간해 팬·줌·가감속을 연속적으로 연결했다. 경유지에서는 이동 방향을 부드럽게 전환한다.
- 지표·미세 지형 입력, 어두운 해양 grade, GIS 국경과 해안선의 독립 벡터 geometry, 희미한 city lights, 대기 림. 생성형 지도 이미지 없음.
- Singapore / South Korea / Japan의 실 폴리곤을 점진적으로 강조. 국경은 과도한 네온 대신 얇은 cyan/ivory 선으로 강조한다.
- 지구 곡면을 따르는 elevated geodesic route. 진행 구간만 그려지며 head, 약한 다중 glow, 감쇠 tail, 작은 particle trail을 사용한다.
- 오리지널 입체 항공기: fuselage, swept wings, tail, nacelles, windows, cockpit, 좌우 navigation lights. 표면 법선·경로 접선에 맞춘 자세, 약한 banking, 나타남·퇴장 페이드.
- 출발·도착 ripple, 지역 라벨의 순차 공개, 태평양 방향 저각 지구 샷, 마지막 네트워크 pull-out. PNG 슬라이드나 지리 순간이동 없음.
- 원본 합성 stereo score: harmonic tension, low whoosh, route pulse, stereo pass-by, soft hit, final deep impact. 타임코드는 `assets/audio/cue_sheet.json`에 기록했다.
- `SceneManager.insert_cinematic_clip()` 등록 구조를 마련했다. 이번 마스터에는 외부 I2V 클립이 없다. 외부 모델 호출, 자동 TTS, 전세계 자동 장면화는 구현하지 않았다.

## 렌더링 설정

| 항목 | 설정 |
|---|---|
| 내부 화면 | 2160×3840 WebGL + 2D typography composite |
| Anti-aliasing | WebGL MSAA + 2배 선형 해상도 supersampling / Lanczos downsample |
| Motion blur | 장면 시간 2개 샘플, 각 30fps 프레임의 약 1/60초 셔터 폭; 텍스트는 blur 후 합성 |
| 프레임 전송 | 2160×3840 JPEG quality 0.99 image2pipe; preview PNG는 실제 최종 MP4 decode에서 추출 |
| 최종 | 1080×1920, 9:16, 30fps, H.264, 4:2:0 full-range, BT.709, CRF16 slow, MP4 faststart |
| 음향 | 원본 48kHz float32 stereo, 24-bit PCM master → AAC 320kbps |
| 음악·효과 loudness | PCM 실측 약 −19.9 LUFS integrated, −2.0 dBFS true peak, 약 4.4 LU LRA |
| 재사용 | 동일 설정·시간 결정성의 검수 구간을 비트스트림 무재압축 연결; 마지막 완성본을 전체 재검수 |

## 제작 중 수정 기록

1. 초기 shader에서 topology 차분이 과하게 적용돼 지형이 검은 얼룩처럼 보였다. 지형 명암을 미세 수준으로 줄이고 지표/ocean tone과 명시적 출력 gamma를 수정했다. 초기 테스트 프레임을 최종 자산으로 사용하지 않는다.
2. 첫 5초 MP4를 전체 디코딩하고 관찰했다. 150프레임, 1080×1920, 30fps, 5.0초, AAC stereo가 확인됐다. 첫 버전에서 출발 항공기가 하단 자막과 너무 가까운 구도를 발견해 카메라 키를 수정했다.
3. 전체 pull-out에서 Seoul / Tokyo 라벨을 좌우로 나누고 offset을 달리해 겹침을 줄였다. 카메라 변경 후 4.5, 6, 9, 16.2, 19.96초의 4K 프레임을 다시 관찰했다.
4. 검수 도구 이름이 Python 표준 `inspect` 모듈과 충돌해 수치 보고서 생성이 실패했다. `tools/validate.py`로 이름을 바꾸고 검수를 재실행해 해결했다. 렌더된 영상 자체의 실패는 아니었다.
5. 375px급 모바일 축소에서 가독성을 다시 검토해 주 자막을 43px, 도시 이름을 30px(1080 출력 기준)로 키웠다. 수정 전 중간 렌더는 별도 보존하고 최종으로 사용하지 않는다.
6. 글자를 키운 후 인코딩된 4.5초 프레임에서 싱가포르 라벨이 항공기 꼬리와 겹쳤다. 싱가포르 라벨을 고정된 왼쪽 아래 위치로 옮기고 3.0, 4.5, 19.96초 프레임에서 충돌 해소를 관찰했다.
7. 다른 소프트웨어 OpenGL 설정도 검사했지만 동일한 SwiftShader 장치로 처리됐다. 검증된 renderer를 유지했으며 해상도나 시간 샘플 수를 낮추지 않았다.

## 품질 게이트 / 최종 결과

수정된 5초: 150프레임 전체 decode, 5.0초, 1080×1920, 30fps, H.264 / AAC stereo. 10초: 300프레임 전체 decode, 지도 ROI의 인접 프레임 차이 최솟값 0.911/255, median 2.402/255, 완전/근사 정지 연속 구간 0초. 5초와 10초 contact sheets와 원본 크기 프레임을 관찰해 출발·접근·도착의 연결, 지리 위치, 레이블 간격을 확인했다. 

최종: **20.000초 / 1080×1920 / 30fps / H.264 / 600프레임**. 전체 프레임 decode 성공. 지도 ROI 차이 최솟값 0.309/255, median 2.159/255, near-duplicate map run **0초**. UI 진행선/하단 자막을 제외한 지도 영역에서도 연속 변화가 확인됐다. 연결점 5.0초의 map difference 3.720/255, 10.0초 2.150/255; 전체 contact sheets와 연결점 전후의 구도를 관찰했으며 지리 순간이동은 없다.

Chromium 실제 **20초 전체 재생 완료**: totalVideoFrames 600, droppedVideoFrames 0, corruptedVideoFrames 0, videoError 없음. 음향 709,205 bytes decode. Screenshot 중 frame callback 간격은 최대 0.133초였으며 player는 dropped frame 0을 보고했다. `outputs/playback_validation.json` 참조. 이 자동 재생 결과와 assistant의 직접 청취를 구분한다.

무음 파일에는 audio stream이 없고, 두 MP4의 video packet SHA-256은 모두 `3c17d714628455417f1418b7de466e418fcdfc66b37b807dc58611ac905a4b60`으로 동일하다. 최종 AAC stream의 별도 EBU R128 측정: **−19.9 LUFS integrated / −2.0 dBFS true peak / 4.3 LU LRA**. Clipping 없음.

`insert_cinematic_clip()`은 준비된 frame callback의 local time 0.5초 호출과 실제 canvas pixel [32,90,132,255] 합성으로 기능을 검사했다. 종료 시각은 exclusive다. 이는 삽입 연결 지점 검증이며 외부 I2V 생성·디코더를 구현했다는 의미는 아니다. 테스트 색상은 마스터 영상에 들어가지 않는다.

| 게이트 | 결과 / 근거 |
|---|---|
| 국가·국경·해안 | 충족: Natural Earth GIS, vector projection, 데이터 checksum 일치, geographic anchors 관찰. |
| 지형·지도 표현 | 충족: 실제 지표/지형 기반 texture와 구면, 초기 명암 결함 수정. 지형 displacement DEM은 사용하지 않음. |
| 카메라 | 충족: 연속 flight / zoom / pan / 추적 / parallax / 최종 감속. 전체 frame 검사와 실제 재생에서 warp 없음. |
| 모션 | 충족: 600프레임에 지도 영역 정지 구간 0초. 경로·항공기·단계적 국가/도시 reveal, 2-sample motion blur. |
| 디자인·가독성 | 프레임 관찰 기준 충족: 자료 카드 전환 대신 3D 공간 이동, 일관된 cyan/ivory/metal palette, 43px main text, 30px city names, airport label collision 수정. |
| 시청 유지 | 충족: 첫 1초부터 이동, 1.5–4초 지역·이동체 reveal, 약 1.55초 authored event 간격, 최대 약 2.3초. |
| 음향 기술·동기화 | 충족: 정상 AAC stereo decode, clipping 없음, 명시적 cue time과 map events 대응, 음악과 효과를 함께 생성. |
| 음향 청감 | **미검수**: assistant에게 청취 입력이 제공되지 않아 직접 청감 및 레퍼런스 sound 비교를 통과로 표시하지 않음. |

최종 주요 프레임은 실제 MP4에서 0.75 / 14.2 / 19.7초에 추출했다. 별도 렌더의 더 좋은 프레임으로 바꾸지 않았다. 필수 산출물 2 MP4 + 3 PNG, 설치/실행 문서와 품질 보고서를 보존했다.

## 레퍼런스 대비 비교

| 항목 | 새 마스터의 접근 / 판단 한계 |
|---|---|
| 지도 | 레퍼런스의 평면 satellite-like map 대신 실제 지형 기반 구면과 vector borders. 녹화 앱 UI가 없는 1080×1920 깨끗한 출력. 지표는 4K 전세계 텍스처여서 극단적 확대에는 제한이 있다. |
| 카메라 | 연속 구면 카메라 이동. 레퍼런스의 East Asia jump cut을 사용하지 않고 flyover와 low-angle / pull-out로 연결한다. |
| 모션 | 항공기가 경로를 직접 생성한다. 설명 장면에서도 카메라가 이동하며, 큰 동작과 여백을 같이 배치한다. |
| 아이콘 | 사진 cutout과 무명 glowing entity 대신 동일 디자인의 오리지널 입체 민간 항공기. |
| 경로 | 실제 airport coordinates와 geodesic distances. 국경·해안·경로가 raster 확대에 의해 계단형으로 변하지 않는다. |
| 사운드 | 복제하지 않고 원본 tension/foley cues를 시간 동기화. 레퍼런스 혼합 트랙에서 effect stem과 BGM을 분리하지 않았으며, assistant의 직접 청취 비교는 불가능하다. |
| 정보 전달 | 이름·경유지·거리·마지막 총 네트워크를 순차 공개. Korean main text는 최종 기준 43px, English city name은 30px 정도다. 작은 보조 정보는 주요 메시지보다 작다. |
| 변화 빈도 | authored scene/effect cues가 약 1.55초 간격이고 최대 약 2.3초. 카메라·항공기·경로 motion은 그 사이에도 연속적으로 진행한다. 레퍼런스보다 차분한 documentary rhythm을 선택했다. |
| 영상미 | earth curvature, restrained cyan/gold, atmospheric rim, typography와 단일 시선 유도. 전문 제작자/사용자 취향에 대한 객관적 인증은 주장하지 않는다. |

## 아직 부족한 부분 / 검증 범위

- 오디오 도구가 assistant에게 음성 재생 입력을 제공하지 않아 청감으로 BGM/SFX의 질감과 레퍼런스를 직접 비교하지 못했다. 디코딩, loudness, clipping, stereo, cue time 검증과 실제 청취를 구분한다. 사용자 기기에서 소리 재생 검수가 필요하다.
- 비디오는 실제 Chromium에서 20초 재생 완료를 확인하고, 600프레임 전체 decode, 0.5초 contact sheets와 주요 원본 해상도 프레임을 시각 관찰했다. 실시간 자동 재생 검증과 assistant의 연속 실시간 시청 경험은 구분한다.
- 지구 radius 및 trajectory elevation은 cinematic scale이고 실제 항공 altitude simulation은 아니다. 지형 입력은 texture/topology relief이며 고해상도 측량 DEM을 기반으로 displacement mesh를 만든 것은 아니다.
- 모든 나라 자동화, UI, 60초, 자동 자막·TTS·I2V는 아직 포함하지 않았다. 마스터를 사용자가 승인한 이후에 확장한다.
