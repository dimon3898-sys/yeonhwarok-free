# CINEMATIC WORLD MAP SHORTS ENGINE

20초 마스터 스터디 **THE INVISIBLE CORRIDOR**. 중립적인 가상 민간 물류 항공편이 싱가포르 창이(SIN) → 서울 인천(ICN) → 도쿄 나리타(NRT)를 이동한다. 실제 운항 스케줄, 속도 또는 수송 현황을 주장하지 않는다. 전체 자동생성기나 UI는 이번 범위에 포함하지 않는다.

기존 저장소 루트의 `README.md`, `index.html`은 수정하지 않았다. 전체 Git 체크아웃을 `/workspace/preserved-originals/yeonhwarok-free-before-cinematic-20261004.tar.gz`에 보존한 뒤 이 하위 디렉터리에 구현했다.

## 기술과 구조

- Three.js 0.170.0 / WebGL / GLSL: 곡률이 있는 실제 구면 지구, 실 GIS 벡터 국경·해안선, 지표 텍스처와 지형 명암, 대기 림, 도시 발광.
- `src/engine.js`: `MapRenderer`, `CameraController`, `CountryHighlighter`, `GeodesicCurve`, `RouteAnimator`, `EntityAnimator`, `EffectsEngine`, `SceneManager`, `Renderer`.
- 카메라는 C1 연속 Hermite 보간으로 지리 좌표·고도·기울기·yaw·roll을 연결한다. 구면상 높이가 있는 대권 경로가 순차적으로 생성되고 꼬리가 감쇠한다. 이동체는 오리지널 입체 항공기 모델이며 방향 벡터로 회전한다.
- Python / NumPy / SciPy: 32-bit float 원본 합성 stereo BGM 및 effects. `tools/sound.py`의 `SoundEngine`과 `assets/audio/cue_sheet.json`에서 시간 배치를 확인할 수 있다.
- Chromium / Playwright: 결정적인 시간 샘플로 2160×3840 내부 렌더. 180° 셔터에 가까운 2개 시간 샘플로 지도와 이동체 motion blur를 적용하고 텍스트는 그 뒤 선명하게 합성한다.
- FFmpeg: Lanczos 1080×1920 다운샘플, H.264 CRF 16 slow, 4:2:0 full-range, 30 fps, BT.709, MP4 faststart. 최종 음향은 AAC stereo 48 kHz 320 kbps.

`SceneManager.insert_cinematic_clip({start,end,source})`는 향후 지도 → 외부 영상 → 지도 삽입을 위한 시간 구간 등록/렌더 지점이다. `source`는 준비된 CanvasImageSource 또는 `(localSeconds) => preparedFrame` 콜백이며, Renderer가 해당 구간에서 실제 frame을 cover 합성한다. 영상 디코더는 호출측에서 프레임을 준비한다. 이번에는 외부 I2V 영상을 사용하지 않는다. 전세계 장면 자동화·TTS·60초 확장은 마스터 승인 이후 범위다.

## 설치

현재 클라우드 환경에는 Node 24, Python 3.12, FFmpeg, Chromium, Open Sans, Noto Sans CJK가 설치돼 있다. 다른 Linux 환경에서도 해당 실행 도구와 폰트가 필요하다. 예를 들어 Debian 계열의 패키지 이름은 `ffmpeg chromium fonts-open-sans fonts-noto-cjk`다. GPU는 필수가 아니며 소프트웨어 WebGL 렌더링을 사용하면 시간이 더 걸린다.

```sh
cd /workspace/yeonhwarok-free/cinematic-world-map
npm ci --ignore-scripts --no-audit --no-fund
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python3 -m pip install --no-input -r requirements.txt
```

Playwright 1.62.1도 잠금 파일에 고정돼 있으며 `npm ci`에서 함께 설치된다. Chromium은 시스템 실행 파일 `/usr/bin/chromium`을 사용하므로 별도 브라우저 다운로드가 필요 없다. `CHROMIUM_PATH`로 실행 파일을 지정할 수 있다. 제공된 assets는 체크섬 검증된 파일이므로 렌더 시 외부 네트워크 접근이 필요 없다.

## 실행과 렌더

작업마다 기존 체크아웃을 사용한다. 사용자 요청 없이 Git worktree를 만들지 않는다. 서비스 프로세스는 작업 사이에 살아 있다고 가정하지 않는다. 다음 서버는 별도 터미널에서 유지한다.

```sh
python3 -m http.server 8010 --bind 127.0.0.1 --directory /workspace/yeonhwarok-free/cinematic-world-map
```

```sh
cd /workspace/yeonhwarok-free/cinematic-world-map
python3 tools/sound.py
python3 tools/master_audio.py
node tools/render.mjs --still=0,3,6,9,14,19.96
node tools/render.mjs --seconds=5 --name=preview_5s_muted --samples=2
python3 tools/mux.py --name preview_5s --seconds 5
# 프레임·영상 검수 후 다음 단계로 진행한다.
node tools/render.mjs --seconds=10 --name=preview_10s_muted --samples=2
python3 tools/mux.py --name preview_10s --seconds 10
node tools/render.mjs --seconds=20 --name=master_cinematic_20s_muted --samples=2
python3 tools/mux.py --name master_cinematic_20s --seconds 20
python3 tools/validate.py outputs/master_cinematic_20s.mp4
node tools/playback.mjs master_cinematic_20s.mp4
```

무음 버전은 audio stream이 없는 동일 영상이다. 프리뷰와 최종 렌더를 동시에 실행하지 않는다. 도구는 프레임 진행률을 출력한다. MP4 컨테이너는 FFmpeg가 정상 종료해야 완결되므로 실행 중 48-byte 파일 크기만 보고 실패로 판단하지 않는다.

## GIS와 자산 / 라이선스

`assets/SOURCES.json`에는 다운로드 URL, SHA-256와 라이선스를 기록했다. 지리 이미지를 생성형 AI로 만들지 않았다.

| 자산 | 출처 / 권리 |
|---|---|
| 국가 경계·해안선 1:50m GeoJSON | Natural Earth 공식 `nvkelso/natural-earth-vector` 저장소. Public domain. 포함된 `assets/gis/natural-earth-license.html` 참고. |
| Blue Marble 계열 지표 4096×2048, topology 2048×1024 | `vasturiano/three-globe` 예제 배포 자료. 해당 저장소 MIT 배포 허가를 보존: `assets/three-globe-MIT.txt`. 지표 텍스처는 위성·지형 기반이며 topology는 정확한 측량 고도로 해석하지 않는다. |
| 도시 불빛 2048×1024 | `mrdoob/three.js` 예제 지구 texture. 저장소 MIT 허가: `assets/three-MIT.txt`. 발광은 미세한 시각 연출이며 현재 도시 인구·전력량 데이터가 아니다. |
| Three.js 코드 | MIT, 잠금 파일에 버전과 패키지 integrity 보존. |
| 항공기 모델·마커·경로·effects·타이포그래피 구성 | 이번 작업의 오리지널 코드 기반 자산. 외부 아이콘/영상/AI 이미지 없음. |
| BGM·sound effects | 원본 절차적 합성. 생성된 음악·효과 waveform은 CC0-1.0. 외부 음원 샘플 없음. |
| Open Sans / Noto Sans CJK | 시스템 폰트. Open Sans Apache-2.0, Noto Sans CJK SIL OFL-1.1. 라이선스 사본 포함. |

국경은 Natural Earth의 cartographic generalization과 de facto 표현을 따른다. 법적 국경 판단이나 항공 항법용 지도는 아니다. 1:50m 벡터는 이번 대륙 규모 시퀀스에 적합하며 공항 수준 극단적 확대를 지원하는 상세 GIS는 이번 범위가 아니다.

## 산출물

`outputs/master_cinematic_20s.mp4`, `outputs/master_cinematic_20s_muted.mp4`, `outputs/preview_01.png`, `outputs/preview_02.png`, `outputs/preview_03.png`.

분석과 검수 기록: `docs/REFERENCE_ANALYSIS.md`, `QUALITY_REPORT.md`. 화면 관찰과 수치 검증을 청감·취향 판단과 구분하며, 최종 업로드 판단은 사용자의 실제 기기 재생으로 확인한다.

현재 제작에서는 검수된 동일 설정의 5초/10초 구간을 `tools/concat.py`로 무재압축 연결해 중복 렌더를 줄였다. 합쳐진 최종 600프레임을 다시 전체 디코딩해 연결 지점을 검증한다.
