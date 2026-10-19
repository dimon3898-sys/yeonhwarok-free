# WORLD ENGINE 야간 작업 결과

무료 개발·연결·검증과 GPU 후보 이미지 등록을 완료했습니다. 실제 5초 소프트웨어 MP4는 제작했지만 **VISUAL_NEEDS_REWORK**입니다. NVIDIA 검증·80초 렌더링·FINAL 승격은 하지 않았습니다.

## 1. 완료한 기능

- Studio 입력 → 원본 자료 admission → 분리 실행 관리자 → 전역 150프레임 Preview → 기존 SFX·FFmpeg·내보내기 경로를 연결했습니다. 기존 인증·Origin·CSRF·비용 정책·GPU admission·공통 lease·claim을 유지합니다.
- Scalar Territory·Core/Halo·지형 광원·국가 표식의 기존 소비자를 연결하는 별도 계약을 추가했습니다. 현재 역사 자료가 없는 선택은 차단합니다. 데이터가 없는 군대·점령·이동을 만들지 않았습니다.
- 새 source overlay는 원래 source record 20개와 원본 authority 4개를 보존합니다. 새 역할 기록은 0개이며, package manifest·payload SHA·역할·중복·synthetic 생산 거부를 검사합니다. 원래 Event/Flow 소비자와 새 시각 계층이 같은 catalog를 사용합니다.
- 실제 캡처에서 정지 카메라 구간이 선택되는 결함을 확인해 수정했습니다. 같은 소스·프로필에서 측정한 200프레임과 기존 카메라·layout 10개 파일의 SHA를 근거로 카메라·영토 변화가 함께 있는 구간을 선택합니다. 미관측 프레임은 UNKNOWN입니다. 카메라 경로나 Scene은 바꾸지 않았습니다.
- 새 미디어의 private 권한, 이미지 내부 import 경로, CLI 실제 누적 프레임 전달 결함도 수정했습니다. 새로운 GPU 검사 우회나 공개 제작 API는 없습니다.

소스: `e23613195c356ad53874030f983a30a0e30d639f`  
Manifest SHA: `ceca8be224e0b7e8ca73a429c7a36217d371fe09308d3829e9ff5b0d67a35fa7`  
브랜치: `development/universal-overnight-safe-20261019`

## 2. 남은 차단 기능

151개·기존 미연결 53개·기존 pending 33개를 전수 검토했습니다.

| 상태 | 수 |
|---|---:|
| SUPPORTING | 104 |
| BLOCKED | 18 |
| UNVERIFIED | 14 |
| 해당 없음 | 15 |

SUPPORTING은 연결·검증 근거이며 실제 영상 적용 완료 개수가 아닙니다. 잔여32개의 개별 원인·원래 entrypoint·다음 행동은 `REMAINING_FEATURES.json`과 한국어 설명에 있습니다.

주요 차단은 양측 전체 점령장, 날짜·역할에 근거한 군대 위치·이동, Scalar 전선의 native 지형 텍스처·coverage 계약, 고급 roll·추가 Detail의 안전한 표시 연결, 실제 NVIDIA 출력입니다. 공식 부분 전선8시점·근사5상태·12장면 연표·ASTRA 지역 자료는 보존했습니다. 부분선을 전체 점령 영역으로 만들거나 미지정 육지를 적군 영역으로 간주하지 않았습니다. 일별 실측 전선·원본 투영법·정밀 위치 정확도는 보증하지 않습니다.

`66430.mp4`는 확보하지 못해 직접 비교하지 않았습니다. 실제 레퍼런스는 원본 SHA 확인 후 기존 전체958프레임 분석을 재사용하고, 이번 비교 시점3개를 직접 디코딩했습니다. 현대 가상 레퍼런스와 근사 역사 장면의 스타일·가독성을 비교했으며 사건·시간축의 프레임 일치를 주장하지 않습니다.

## 3. 실제 5초 MP4

원본80초·2400프레임 중 **[1400,1550)**만 실제 캡처했습니다.

- 1080×1920 / 30fps / 150프레임 / H.264 / 5초
- 실제 카메라 bounds48종, RGBA101종, 원본 전역 프레임 순서 보존
- 기존 기준과 150프레임 RGBA·PNG·카메라 모두 BIT_EXACT
- 기존 CC0 SFX1개, 48kHz·유효240000샘플, 클리핑0, mux 전후 영상 픽셀·PTS 동일
- CPU SwiftShader 캡처·인코딩·디코딩 실측 **403.475초**. NVIDIA 성능이나80초 제작시간으로 환산하지 않습니다.
- MP4 SHA: `3899d87cbacfbb54f9a094ac0a37755b7a3dd5ba941634e37f4555d01de83f66`

최초 영상과 같은 픽셀 결과는 보호 검증입니다. 디자인 품질이 높아졌다는 뜻이 아닙니다. 단색 도식 영역·직선 경계·표식 보호 사각형·큰 고정 텍스트·역사 군대 표식 부재·hold가 남아 레퍼런스 품질은 미달입니다. 첫50프레임의 앞 단계 북진 문맥이 현재 장면 날짜보다 앞선다는 원래 도식 한정도 유지했습니다.

중간 [1450,1600) 실험은 실제 정지 카메라로 확인해 최종 선택에서 제외했습니다. 해당 실험은 실행환경 연결 중단 후20프레임을 보존하고130프레임만 이어 제작한 복구 증거와 함께 `proof-coherent-static`에 보존했습니다. 최초·중간·최종의 소스 정체성은 각각 유지합니다.

## 4. 검증·원격 저장

- 집중 CPU **143 PASS / 0 SKIP**. 직접 영향 검사는 재실행하고 변하지 않은 결과는 test SHA 확인 후 재사용했습니다. 기존 전체 검사·ASTRA 수집·전체 원본 파싱은 반복하지 않았습니다.
- 새 manifest 파일 27개 + 부모 manifest 파일 55개 검증. 실제 컨테이너 소스 로더377개 binding·150개 server binding 및 카메라 증거 authority 통과.
- 기존 FINAL·Candidate·Scene·Asset·렌더러·Camera V5·Area·Flow·Event·Planner 변경0건. Secret Scan0건. 필수 runtime·asset의 temp-only0개. 최종 미디어·핵심 증거·실행한 후처리 소스는 Git에 보존합니다.
- 신규 고유 이미지 빌드·GHCR 등록·독립 runner digest pull PASS. 정상 이미지·태그는 보존했습니다.

태그: `overnight-v3-e23613195c-39276669808-1`  
Digest: `sha256:7d45f95a7dd30a8e66a8cf6ef521e8ed38981e1fd07bd992eee4aea0ba78a645`  
무료 CI: https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39276669808

실제 소프트웨어 영상은 소스 checkout에서 실행한 결과입니다. 등록된 컨테이너의 NVIDIA 영상 실행은 GPU_PENDING입니다. 실제 후보 digest를 넣은 정규화 Scene도 별도 source authority 검사를 통과했지만 렌더링·비용 승인은 부여하지 않았습니다.

## 5. 휴대폰 다운로드

- [5초 MP4](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/refs/heads/development/universal-overnight-safe-20261019/world-simulation-shorts-engine/recovery/universal-overnight-v3/public-review/WORLD_ENGINE_OVERNIGHT_PREVIEW_5S.mp4)
- [레퍼런스 비교 PNG](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/refs/heads/development/universal-overnight-safe-20261019/world-simulation-shorts-engine/recovery/universal-overnight-v3/public-review/REFERENCE_VS_SOFTWARE_PREVIEW.png)
- [SHA256SUMS](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/refs/heads/development/universal-overnight-safe-20261019/world-simulation-shorts-engine/recovery/universal-overnight-v3/public-review/SHA256SUMS)
- [Scene·프롬프트·151/53 판정·검증 보고서 ZIP](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/refs/heads/development/universal-overnight-safe-20261019/world-simulation-shorts-engine/recovery/universal-overnight-v3/handoff/WORLD_ENGINE_OVERNIGHT_HANDOFF.zip)

공개 검수 폴더에는 MP4·PNG·SHA만 넣습니다. 문서 ZIP은 별도 handoff에 두고, Secret·private 작업 claim·원본 진단 로그·렌더러 코드는 포함하지 않습니다. commit-pinned HTTP200·원본/다운로드 SHA 실제 검증 결과는 별도 `reports/DOWNLOAD_VERIFICATION.json`에 기록합니다. ZIP 내부 SHA도 검증합니다.

## 6. 내일 할 일

휴대폰에서 MP4와 비교 PNG를 검수하고 이 대화에 결과만 남기면 됩니다. 지금은 gCube 설정 변경·새 배포·토큰 복사·터미널 실행이 필요하지 않습니다. 기존80초 승인 금액을 이번 작업에 재사용하지 않았습니다.

**USER_VIDEO_REVIEW_REQUIRED · VISUAL_NEEDS_REWORK · NVIDIA_GPU_PENDING**  
사용자 검수와 별도 비용 승인 없이80초 렌더링·FINAL 승격을 진행하지 않습니다.
