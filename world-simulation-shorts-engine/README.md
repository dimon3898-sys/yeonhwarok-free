# World Simulation Shorts Engine

자연어 주제를 검토 가능한 기획으로 바꾸고, 승인된 Scene JSON을 PREMIUM FLAT v004와 MASTER V3의 3D 지구 렌더러로 장면별 제작하는 프로그램입니다. 기존 `cinematic-world-map`의 코드·GIS·자산·MASTER V1/V2/V3는 읽기 전용 공용 라이브러리로 사용합니다. 새 프로젝트와 결과는 이 디렉터리에 별도로 저장합니다.

보존된 Production Default v1의 기본 Pace는 FAST였습니다. [기존 통합 영상 및 비교본](../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1), [QC 보고서](../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/QC_REPORT.md), [실측 시간](../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/BENCHMARK.md)은 그대로 유지합니다.

새 리듬 확장은 승인된 그래픽 위에 FAST_PLUS, 개별 동작 Speed Ramp, Micro Beat/Pause, 사건별 SFX Layer와 BGM Energy/Sidechain을 추가합니다. [12초 검증 샘플과 보고서](../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_RHYTHM_MASTER_v001), [구조·캐시·검수 범위](docs/RHYTHM_SYSTEM.md)를 제공합니다. 별도 기술 검증 인증이 유효하면 권장값은 FAST_PLUS / TTS OFF / 자막 OFF / BGM·SFX ON입니다. 기존 Pace와 음성·자막 ON/OFF는 유지하며, 저장된 계획은 자동 변경하지 않습니다. 이번 작업에서는 75초 영상과 MASTER를 렌더하지 않습니다. 직접 청취 및 실제 시청 지속률의 우열은 기술 인증과 구분하여 사용자 검수를 기다립니다.

## 실행

Python 3.12+, Node.js 20.11 이상, Chromium, FFmpeg/FFprobe가 필요합니다. 검증한 Node 버전은 24.19.0입니다. Python 의존성은 새 가상환경에 설치합니다. 기존 V3의 `package.json`, lockfile과 Python 환경을 수정할 필요가 없습니다.

```bash
cd /workspace/yeonhwarok-free/world-simulation-shorts-engine
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci --prefix ../cinematic-world-map
.venv/bin/python tools/bootstrap_runtime.py
.venv/bin/python server.py --host 127.0.0.1 --port 8090
```

이미 설치된 V3 Node 의존성은 다시 설치하지 않아도 됩니다. Linux의 `/usr/bin/chromium`을 사용하며, 다른 Chromium 설치 경로는 `CHROMIUM_PATH`로 지정할 수 있습니다. 서버와 같은 컴퓨터의 브라우저에서 `http://127.0.0.1:8090`을 엽니다. 이 주소는 휴대폰에서 접근할 공개 URL이 아닙니다.

`bootstrap_runtime.py`는 Ubuntu의 고정 URL·SHA가 기록된 eSpeak 패키지를 새 앱의 `tools/runtime/`에만 설치합니다. sudo·시스템 패키지 변경이 없고 기존 파일은 동일하면 재사용, 다르면 보존하고 오류로 중단합니다. 패키지가 이미 보존되어 있으면 `--offline`으로 실행합니다. 이 패키지 세트는 Linux x86_64 전용이며 `dpkg-deb`와 호환되는 시스템 라이브러리가 필요합니다. Mac/ARM 등에서는 별도 시스템 eSpeak, 외부 나레이션, TTS OFF를 사용합니다. eSpeak의 기계적인 음질이 설치 성공으로 개선되지는 않습니다.

같은 LAN의 휴대폰 사용 시 서버를 `--host 0.0.0.0`으로 실행하고 서버 컴퓨터의 LAN 주소로 접속합니다. 원격 클라우드 사용에는 해당 호스트의 허용된 포트 공개 또는 HTTPS 호스팅이 필요합니다. 현재 클라우드의 내부 경로·localhost 링크만으로 외부 휴대폰 접속이 제공되지는 않습니다.

## 사용

주제·길이·스타일·품질과 오디오 옵션을 입력하고 **기획 생성**을 누릅니다. 훅, 사건 순서, FACT/ASSUMPTION/SIMULATION, 카메라·조명·필요 모듈을 확인한 뒤 **기획 승인 및 영상 생성**을 누릅니다. 완료된 MP4는 서버의 첨부 다운로드 응답으로 받을 수 있습니다. 수정 요청은 변경점을 먼저 보여주고 승인 후 새 버전을 만듭니다. `장면 2 삭제`, `14초 장면에서 결론을 공개하지 마` 같은 구조 수정도 지원하며, 훅·Peak·인과관계가 깨지는 수정은 승인·렌더 게이트가 차단합니다.

지명·운하 상태 라벨도 Scene별로 대비를 수정할 수 있습니다. `Scene4와Scene5 지명과 운하 상태 라벨의 대비를 높여.`는 선택Scene의 appearance만 바꾸고 지리·대본·경로·다른Scene은 보존합니다. 상태문구는 안전폭 때문에 기존 크기를 유지합니다. 조명을 낮/밤으로 바꾸면 검증된 지명·상태 색도 함께 바뀌고 camera-only 수정은 라벨을 유지합니다. 라벨수정과 실제camera/lighting/경로추가/이동체수정을 섞은 인식 가능한 명령은 `UNSUPPORTED_COMBINED_LABEL_EDIT`로 분리해서 요청하도록 안내합니다. 지원문법은 제한되어 있고 정확한 Diff승인이 계속 필요합니다.

지원 예:

- `런던에서 파리, 로마로 이어지는 민간 항공 여행` — 20초
- `만약 수에즈 운하가 7일 동안 막힌다면?` — 75초
- `만약 서울과 싱가포르를 직접 연결한다면? 가상 도시 연결` — 40초

현재 자연어 기획기는 검증된 장소 목록과 지원 시나리오를 사용하는 오프라인 도메인 기획기입니다. 임의의 모든 자연어 질문을 연구하거나 실제 물류·경제·기상 결과를 예측하는 시스템은 아닙니다. 새로운 GIS 위치와 플러그인은 출처·검수와 함께 추가합니다. 판게아 분리, 전쟁 VFX, 실제 기상 변화 등 미구현 연출은 필요한 모듈을 반환하고 렌더링하지 않습니다.

현재 스타일은 네 가지이며 실제 조명·카메라 속도/프리셋을 바꿉니다.

| 스타일 | 반영 방식 |
|---|---|
| 긴장감 있는 세계 시뮬레이션 | 기본 야간·가독성·HERO 리듬 |
| 시네마틱 지리 다큐멘터리 | 위치 설명·비교·전경의 지표 가독성 우선 |
| 차분한 여행과 탐험 | 기본 속도의 85%, 주간 중심 조명 |
| 역동적인 국제 네트워크 | 기본 속도의 110%, 네트워크/궤도 프리셋 |

지원하지 않는 스타일은 조용히 무시하지 않고 `UNSUPPORTED_STYLE`로 알려줍니다. 현재 장소/경로 자료는 현대 GIS입니다. 육상 운송은 `LAND_ROUTING`, 과거 지도·국경·지형은 `HISTORICAL_GIS`/시간 모듈이 필요하며 현대 지구의 항공 경로로 대체하지 않습니다. 최종 전경 한 장면에 안전하게 담을 수 없는 반구 전체 이상의 연결망은 `MULTI_HEMISPHERE_OVERVIEW`로 반환합니다. 뒤쪽 도시를 가짜로 앞에 표시하지 않습니다.

## 품질과 오디오

| 설정 | 용도 | 출력 | 내부 렌더 |
|---|---|---|---|
| FAST | 기획 프리뷰 | 540×960, 30fps | 프리뷰 설정 |
| HIGH | Shorts 제작 | 1080×1920, 30fps | 2160×3840, 시간 샘플 1개 |
| CINEMA | 중요 장면·HERO | 1080×1920, 30fps | 2160×3840, 시간 샘플 2개 |

H.264/MP4, BT.709, 실제 8K 지구 텍스처, 별도 구름·대기·3D 항로·3D 항공기를 사용합니다. CINEMA는 HIGH와 같은 V3 대기 셰이더에 두 시간 샘플을 사용하며 대기나 HERO 조명을 별도로 강화하는 모드가 아닙니다. FAST 통과는 업로드 품질 통과를 의미하지 않습니다. 자동 QC 후에도 전체 재생과 주요 프레임의 영상미 확인이 필요합니다.

카메라의 경로상 좌표는 출처 있는 GIS 경로를 구면 보간해 계산한 촬영 위치이며 새 도시나 항구 좌표가 아닙니다. 최종 카메라는 전체 주 경로의 실제 투영 범위를 맞춰 잡습니다. 이동체 크기는 지도에서 읽히도록 확대된 3D 시각 프록시입니다. 해상 경로는 실제 수면 부근의 이동 경로와 가독성을 위해 약 3km 위에 그린 경로 오버레이를 구분합니다. 발광 선의 표시 높이를 선박의 실제 고도로 설명하지 않습니다.

TTS/BGM/자막은 개별 ON/OFF입니다. TTS 기본 어댑터는 무료 오프라인 eSpeak이며 음성은 기계적으로 들릴 수 있습니다. 언어를 지정하지 않으면 각 Scene 대본의 한글 여부로 한국어/영어를 선택하며 명시적 `tts_language`가 우선합니다. 외부 나레이션 파일과 명시적 타이밍을 사용할 수 있고, `TTSProvider`를 교체할 수 있습니다. 자막은 Scene 또는 측정된 나레이션 구간 기준이며 자동 단어 정렬·ASR을 주장하지 않습니다. 효과음과 음악은 원본 합성음으로 라이선스가 기록됩니다.

## 기록과 검증

프로젝트별 `projects/project_.../versions/v001/`에 계획, Scene JSON, 오디오, 장면 MP4, QC, 출처 보고서, 최종 MP4가 보존됩니다. 이전 버전을 덮어쓰지 않습니다. Scene의 실제 시각 입력·자산·렌더러·품질·조명 문맥이 같고 기존 MP4·감사 해시가 정상일 때 캐시를 재사용합니다. 삭제로 조립 시간이 바뀐 Scene은 보존된 렌더 시계로 기존 프레임을 유지할 수 있으며 현재의 전체 Scene JSON 해시는 별도로 기록합니다.

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

테스트 범위는 [docs/TEST_SCOPE.md](docs/TEST_SCOPE.md), 실제 제작 근거와 아직 남은 제한은 `QUALITY_REPORT_FINAL.md` 및 테스트 프로젝트의 `qc/` 기록에서 확인합니다. CPU 렌더 시간은 각 실제 실행의 `renders/project_result.json`에 측정합니다. 측정하지 않은 75초 HIGH 시간을 성공 기준처럼 제시하지 않습니다.

기존 코어의 [독립 venv175개 전체](docs/evidence/final_core_mixed_label_guard_clean_runtime_20261005T011907404139Z/REPORT.json)/[로그](docs/evidence/final_core_mixed_label_guard_clean_runtime_20261005T011907404139Z/unittest.log)는 PASS입니다. 기존 75초 HIGH 테스트 v003도 완성되어 [최종 MP4](../deliverables/WORLD_SIMULATION_ENGINE/SUEZ_CLOSURE_75S_TTS_v003/SUEZ_CLOSURE_75S_TTS_v003.mp4)로 보존했습니다. 이번 Flat 검증에서는 해당 영상을 재렌더하지 않습니다. 전체 재생·다운로드 검증과 실물 휴대폰·공개 앱 호스팅 검증은 구분합니다.

175개 Python검사 후 라벨 Diff값 표시만 바꾼UI는 [별도375px GET-only 검수](validation/mobile_label_diff_display_r02/LABEL_DIFF_DISPLAY_REPORT.json)를 통과했습니다(API POST0·worker제어0; poll은 테스트browser에서만 정지). 새전체175개검사나 실물폰검증은 아닙니다. [공개tunnel feasibility](docs/evidence/public_tunnel_readonly_probe_20261005T013145606003Z/REPORT.md)는 origin 도달 전CONNECT403으로 설치·tunnel생성 없이 종료했으며 공개앱URL은 아직 없습니다.

전체 저장소를 체크아웃하고 `cinematic-world-map`을 이 프로그램의 형제 폴더로 유지합니다. 회귀 테스트의 253KB 기술 패턴 MP4와 출처 기록은 `library/uploads/asset_ee0d2ae58134/`에 포함되며, 실제 영상에 넣는 I2V 자산이 아닙니다.

설계는 [ARCHITECTURE.md](ARCHITECTURE.md), 모듈 추가는 [PLUGIN_GUIDE.md](PLUGIN_GUIDE.md), 렌더·복구는 [RENDER_GUIDE.md](RENDER_GUIDE.md), 사용자 작업은 [USER_GUIDE.md](USER_GUIDE.md)를 참고하세요.

## 선택형 PREMIUM FLAT / 2.5D

`FLAT_MAP_PREMIUM`은 기존 MASTER V3 Earth와 별도의 WebGL 렌더러입니다. 실제 Natural Earth 국경·해안선과 출처를 기록한 native shaded-relief 지역 텍스처를 사용합니다. 국가 강조, AUTO FOCUS, 다음 사건 카메라 예고, 진행 경로, 3D 이동체와 Map VFX를 기존 Scene·승인·부분 재렌더·캐시에 연결합니다. Production Default 검증 인증이 활성화되면 새 기획의 일반 지도 장면은 승인된 v004를 사용하고, 중요 Peak와 세계 규모 공개에는 V3 Earth를 사용합니다. 기존 저장 기획은 자동 변경하지 않습니다. 현재 native Flat 지형 검증 범위는 동아시아이며 다른 지역은 가독성 조명을 적용한 기존 V3 Earth로 처리합니다.

## Production Default 선택

PACE_FAST_PLUS / PACE_FAST / PACE_NORMAL / PACE_CINEMATIC은 카메라·경로의 실제 진행 시간을 조절하며, 렌더 품질 FAST/HIGH/CINEMA와 별개입니다. 전체 MP4나 TTS를 배속하지 않습니다. SFX도 TTS·BGM·자막과 독립적으로 켜고 끌 수 있습니다. 지도에 필요한 짧은 라벨과 숫자만 표시하고, 이벤트 시점에 맞춘 효과음 변형과 반복 방지, 음성 우선 ducking을 사용합니다.

[Production Default](docs/PRODUCTION_DEFAULT.md), [Pace](docs/PACE_SYSTEM.md), [효과음 및 라이선스](docs/SFX_LIBRARY.md)에 선택 규칙과 검증 범위를 기록합니다. 기존 Scene JSON에는 새 필드를 강제로 추가하지 않습니다. 활성화 여부는 `/api/production-default`에서 확인할 수 있으며, 인증과 핵심 소스가 다르면 활성화하지 않습니다.

[사용 및 Scene 설정](docs/FLAT_MAP_PREMIUM_GUIDE.md), [지형 준비와 캐시](docs/FLAT_TERRAIN_CACHE.md), [실측 시간](FLAT_MAP_BENCHMARK.md), [샘플 품질 검수](FLAT_MAP_QUALITY_REPORT.md)를 참고하세요. 검증 범위는 약 15초 혼합 샘플이며 75초 전체 제작은 샘플 승인 이후입니다. 제공하는 지역 PNG만으로 샘플을 실행할 수 있습니다. 다른 지역의 native crop을 준비할 때만 별도 699MB 원본 TIFF가 필요하며, 해당 원본은 Git에 포함하지 않습니다.

## 출처와 라이선스

지구 day/night/cloud 텍스처: Solar System Scope, CC BY 4.0. V3에 보존된 출처·SHA를 재사용합니다. NASA 기반이라는 이유로 저작자의 CC BY 조건을 제거하지 않습니다. 도시: Natural Earth Public Domain. 공항: OurAirports/DataHub ODC-PDDL. 해상 그래프: searoute-py 1.6.0 Apache-2.0, 항해용 지도가 아닙니다. 폰트: Open Sans Apache-2.0, 한글 Noto Sans CJK KR SIL OFL 1.1. 각 프로젝트의 `source_report.md/json`에 원본 URL, 저작자, 라이선스와 해시를 기록합니다.

전체 회귀 검사 **255개 PASS**(293.622초), 핵심 소스·승격 인증서·MP4 전후 해시 동일. [실제 검사 결과](../deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/REGRESSION_REPORT.json).
