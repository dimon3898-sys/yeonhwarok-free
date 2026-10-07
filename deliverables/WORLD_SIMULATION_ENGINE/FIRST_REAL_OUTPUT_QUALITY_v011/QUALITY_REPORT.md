# FIRST REAL OUTPUT QUALITY v011

## 실제 입력과 분석 범위

사용자가 올린 `final (1).mp4`(설명상 `64290.mp4`)를 직접 분석했다. SHA256는
`646a4ffdc245f0b03cffc29921398e4eac41cdf6f8df69e3f7f57dc29980f668`이다.
12.000초, 1080×1920, 30fps, H.264, AAC stereo 48kHz다. 360프레임 전체를
디코딩하여 축소 화면의 밝기·변화량을 계산하고, 구간별 프레임과 장면 경계·마지막
프레임을 직접 보았다. `contact_0.jpg`~`contact_2.jpg`, `boundaries.jpg`가 원본 비교자료다.

모바일 검사는 270×480 축소 기준이다. 실제 Android 기기 재생 검사가 아니다.
오디오는 파형·피크·타임라인을 검사했다. 주관적 청취 품질을 합격 처리하지 않았다.
제공받은 것은 MP4이므로 before Scene JSON은 현 코드로 재구성한 비교용 자료다.
실제 GPU에 전달된 원본 JSON이라고 보고하지 않는다. AFTER는 수치·구조 검증이며
GPU AFTER 영상이나 픽셀 비교 결과가 아니다.

## 0~12초에서 확인한 문제와 변경

| 원본 timecode | 실제 화면에서 확인한 문제 | 새 12초 QA 변경안 |
|---|---|---|
| 0.00~1.10 | 어두운 지구에서 빠르게 접근하며 밝기도 바뀜. ROTTERDAM / 7 DAYS? / 거리 정보가 움직이는 지형과 경쟁 | Rotterdam 중심의 가까운 시작 구도. 첫 장면의 큰 줌 제거. 첫 이동 전 정착 후 미세한 접근만 허용 |
| 1.10~2.40 | 유럽 구도는 안정되지만 얇은 항로와 작은 배는 축소 화면에서 찾기 어려움 | 동일 경로 위 주 항로의 대비·head·trail 강화. 기존 선박 모델에 제한된 화면 크기 보정 |
| 2.40~4.80 | Rotterdam에서 지중해로 계속 이동. 밝은 육지·해양 반사가 지형/항로 대비를 낮춤. 9,689 km는 끝의 짧은 구간에만 보임 | 출발 구도 정착 → 가속/감속 이동 → 끝 정착. 유럽·지중해 관계를 담는 넓은 도착 구도. 반사·구름·노출 조정 |
| 4.80~5.90 | SUEZ CANAL이 5.10초 부근에서 읽히기 시작하는데 5.33초 부근부터 바로 크게 멀어짐 | Suez 도착 후 0.90초 카메라 정착. 도시·항로를 본 뒤 네트워크 구도로 이동 |
| 5.90~7.20 | 아프리카 풀백 중 항로/배를 찾기 어렵고 밝은 사하라 지형은 평평하게 보임 | 실제 지형/구름/도시광 텍스처 유지. 과한 표면 반사만 줄이고 주 항로에 국소 대비 적용 |
| 7.20~9.60 | 아프리카→인도양 회전·접근이 연속됨. 이 구간의 평균 프레임 변화량이 가장 큼. 9.20~9.40 부근 변화가 특히 빠름 | 기존 COUNTRY_APPROACH를 사용하되 과도한 저고도 접근을 줄임. 이동 시간을 충분히 확보하고 9.20 이후 도착 정착 |
| 9.60~10.60 | 새로운 풀백·낮/밤 변화가 즉시 시작되어 Singapore를 읽기 전에 화면이 바뀜 | 첫 0.60초 도착 구도 정착. 조명을 전체 시간축에서 연속적으로 변화시킴 |
| 10.60~12.00 | 지구가 작고 검은 여백이 큼. 관련 도시 라벨들이 비슷한 강도로 경쟁. +6,460 km 결과는 후반에 등장 | 최종 지구 크기 확대, 결과 구도의 마지막 0.60초 정착. 보조 도시 라벨을 약하게 처리. 기존 숫자/사실/사운드 시간은 유지 |

장면 경계의 원본 근접 프레임에는 대규모 하드 컷보다 다음 동작의 즉시 재시작이
주요 문제였다. 이를 실제 MP4 근거 없이 좌표 reset 결함이라고 단정하지 않았다.
AFTER에서는 각 경계 양쪽의 실제 native pose를 비교하여 위치·방향·화각 연결을 검사한다.

S002의 축소 luma >235 비율은 최대 약 1.424%다. 전체 화면이 흰색으로 clipping된
영상이라는 의미는 아니다. 관찰된 문제는 밝은 지형과 해양 반사에 의한 국소 대비 저하다.
RGB 프레임 변화량은 카메라 외에도 조명·구름·텍스트를 포함하므로 카메라 속도와
동일한 측정값이라고 보고하지 않는다.

## FAST_PLUS: 사건 시간과 카메라 시간을 분리

단순 영상 배속을 사용하지 않는다. Scene 길이, Route 진행, Entity 사건, 텍스트/SFX
timestamp는 유지하고 카메라에만 독립된 정착·속도 곡선을 적용한다.
sinusoidal velocity의 적분으로 가속 → 이동 → 감속 → 정착을 구성한다.
연속 줌과 추적 oscillation을 줄이고, 정착 중에도 실제 사건과 항로는 계속 진행한다.

12초 QA의 정착 구간은 다음과 같다(초, scene-local):

| Scene | 이동 전 정착 | 이동 후 정착 | 구도 역할 |
|---|---:|---:|---|
| S001 | 0.432 | 0.600 | Rotterdam 출발·훅 읽기, 큰 줌 제거 |
| S002 | 0.432 | 0.600 | 유럽에서 지중해/항로 관계 연결 |
| S003 | 0.900 | 0.350 | Suez 도착 먼저 확인, 이후 확장 |
| S004 | 0.100 | 0.400 | 긴 지리 이동에 시간을 확보, 도착 후 정착 |
| S005 | 0.600 | 0.600 | Singapore 읽기 → 결과 공개 → 정착 |

## 카메라·조명·Route·Entity

* 카메라: 기존 검증된 3D 카메라/좌표계를 재사용한다. 시작·끝 상태를 연결하고
  final height를 4.8에서 3.0으로 줄여 지구를 더 크게 구성한다.
* 조명: 동일 MASTER V3 shader와 텍스처 위에 제한된 조정을 적용한다. 노출 1.14,
  cloud opacity 최대 0.22, 해양 specular 기여 0.55배. day/night와 HERO 기여는
  전체 시간축에서 연속 변화한다. 도시광·대기층·구면 지형은 유지한다.
* Route: 원래 3D 항로를 보존하고 같은 구면 경로·동일 progress 위에 화면 기준
  3px/1080 주 항로 보강을 겹친다. 기존 depth/occlusion을 사용하므로 지구 반대편
  항로가 보이게 하는 우회가 아니다. 보조 경로는 약하게, trail은 끝이 강하게 fading.
* Entity: 기존 cargo_ship 모델·35m grounding 검사 유지. 18px/1080 목표에 대해
  scale 최대 0.012로 제한한다. 항상 최소 크기를 보장한다는 주장 대신 과대 아이콘을
  방지하는 bounded 보정이다. 실제 픽셀 가독성과 장난감처럼 보이지 않는지는 GPU 검수 대상.
* 텍스트: 기존 크기/내용/안전영역을 유지한다. 작은 국소 backplate와 대비로 보강한다.
  임의 슬로건·새 대형 설명문은 추가하지 않는다. 보조 도시 라벨은 약하게 처리한다.

## SFX/BGM

실제 AAC 출력과 재구성한 동일 baseline audio의 zero-lag 상관계수는
0.9999825559431194다. 실제 peak는 -2.246dBFS이며 PCM clipping은 발견되지 않았다.
확인한 사건·사운드 시간은 유지한다. 카메라를 늦추면서 사건/SFX까지 지연시키지 않는다.
이번 입력에서 확인하지 못한 사운드 결함을 추측하여 음악·효과음을 새로 설계하지 않았다.
오디오 청취 만족도와 새 영상에서의 체감 싱크는 실제 GPU 샘플에서 확인해야 한다.

## 안정화 구조 보존과 적용 범위

새 HTML/JS presentation adapter와 페이지 선택 seam만 추가했다. 기존 MASTER/FLAT
소스, proxy/security, NVIDIA GPU profile/probe/fallback, diagnostic journal/frame predicate,
JPEG decoder, FFmpeg lazy startup, checkpoint/retry, 모바일 UI 소스는 보존한다.
원본 파일 39개의 hash 일치 근거는 `PRESERVED_SOURCES.json`에 있다.
새 page/source hashes가 Scene JSON/cache와 Diagnostic 기록에 들어간다.

자동 적용은 **새로 생성하는 shipping 12~15초 QA + FAST_PLUS**에 한정한다.
이 실제 품질 후보의 GPU 검수 전에는 기존 일반 production 요청·저장 Scene·기존 버전을
자동 승격하지 않는다. FAST/NORMAL/CINEMATIC은 유지한다. 20초 후보는 copy-only
native replay를 추가로 검사했으며 기존 일반 20초 planner 결과는 그대로다.

보조 거리 문구 일부의 짧은 노출 시간은 이번에 임의로 연장하지 않았다. 카메라 정착과
대비 수정 후에도 모바일에서 읽히지 않으면 다음 실제 AFTER 입력의 근거로 retiming한다.
PWA/standalone 및 웹 UI 밝기 개선은 TODO이며 이번 작업에서 구현하지 않았다.

## 검증과 다음 실제 QA

`NATIVE_COMPARISON.json`은 360개 native pose의 전후 카메라 지표와 경계 연결,
strict geometry/frustum/label gate 결과다. WebGL draw 및 실제 AFTER pixel은 NOT_RUN이다.
전체 회귀 및 최종 컨테이너 결과는 `CONTAINER_VERIFICATION.json`을 확인한다.
새 이미지는 모든 필수 CI 검사 성공 후에만 immutable tag로 게시한다.

다음 실제 GPU 검사는 새 프로젝트의 같은 수에즈 주제, 12초 QA, HIGH, FAST_PLUS,
TTS OFF, Subtitle OFF, BGM ON, SFX ON으로 한 번 수행한다. 원본 MP4와 함께
도시·항로를 읽는 시간, 어지러움, Suez/Singapore 도착 정착, 밝은 지형 대비,
최종 지구 크기, 선박 크기, SFX 체감 싱크를 확인한다. Diagnostic ZIP과 완성 MP4를
다운로드한 뒤 workload를 중지한다. 이 작업에서 실제 gcube workload를 실행하거나
75/80초 영상을 생성하지 않았다.

## 최종 게시 및 검증 결과

새 public image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v011-quality`

Digest: `sha256:730da5b4b784dfeed43b9d9953c071914c04bca612fd114b82a7232a6cb212a5`

Code revision: `a1c43c03b7d3caaf3a34ecda021ac9c30fa5bac7`

[최종 Docker 검증·게시·익명 pull 기록](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37691273088/job/113031768691)

컨테이너 전체 **734 PASS / 0 FAIL / 0 SKIP**: core 497(기존 482 + 신규 15),
proxy/security/GPU logic 206, 진단 31. 로컬에서 권한 때문에 SKIP한
UID1000 descriptor 검사도 최종 이미지 root 실행에서 통과했다. 실제 이미지 내부
필수 자산 61개 검사, 부팅·health·owner login·Secure cookie·61초 유지, 실제
entrypoint의 GPU 없는 환경 차단, anonymous Docker pull 및 OCI revision 검사 PASS.

HIGH synthetic media fixture는 실제 360 JPEG, 5 Scene MP4, concat, BGM/SFX,
QC, checkpoint/retry를 통과했다. 실측 fixture 전체 시간은 46.868초다.
지도 렌더 속도나 RTX4080S GPU 성능이라고 보고하지 않는다. 선택형 subtitle 경로는
PASS, QA에서 너무 긴 TTS는 기존 정책에 따라 명시적으로 거부되며 기능은 보존된다.

실제 AFTER GPU 그림·모바일 체감·전체 지도 화질은 아직 **미검증**이다. 이번 작업에서
RTX4080S를 켜지 않았다. 기존 저장 프로젝트를 retry하여 이 새 품질안을 적용하지 말고,
승인된 다음 GPU 검사에서는 같은 주제의 **새 12초 QA 계획**을 생성한다.
