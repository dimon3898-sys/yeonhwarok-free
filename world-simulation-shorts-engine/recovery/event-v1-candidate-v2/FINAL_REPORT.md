# Event System V1 Candidate V2 — 검수 보고서

상태: `USER_VIDEO_REVIEW_REQUIRED`  
`event_final: false` · `user_video_approved: false`

이 문서는 Development Candidate의 내부 검증 기록이다. Public Review에는 MP4, Checkpoint PNG, `SHA256SUMS`만 제공한다. 이 문서, Source, Manifest, Diagnostic, Internal Plan은 Public Review 대상이 아니다.

전체 기술 검증·영상 제작·공개 다운로드 검증을 완료했다. 사용자 영상 승인 전 `EVENT_SYSTEM_V1_FINAL`로 승격하지 않는다. 이 보고서와 Manifest를 최종 commit한 뒤 `--require-persisted`로 HEAD/index 및 모든 필수 파일을 확인한다.

## 기준점과 수정 범위

| 기준점 | 영구 commit |
|---|---|
| Event Core | `00ad07e4a6041ea4cc6369bfce8871762f61f152` |
| Suez Data | `69e6ed83acac00bfa7ab1853722f873792a813e1` |
| Camera V5 Final | `29b8ee294360812b55ef577b62411de58159003b` |
| 기존 V1 Candidate | `1d5182f7effde2e776f9c9ac21b00f6d681a423a` |
| 실제 시각 측정에 사용한 V2 Source | `b575bdaf76bcabb957500b319bba8cc4e1ea6f68` |
| Candidate 저장 | `development/event-system-v1-20261012` HEAD; Manifest는 최종 `--require-persisted`로 HEAD/index와 실파일 검증 |
| 검수 MP4/PNG/SHA256SUMS 영구 commit | `1439ab604b305e39ee18af9538b167cedddfa277` |

수정은 Event Line 두께, Event Line의 자동 대비 색상·Event Glow, Metric Annotation 자신의 배치·요청 글자 크기의 세 범위로 제한했다. 기존 Event Core 전체나 Suez Data를 다시 만들거나 조사하지 않았다.

`evidence/SOURCE_SCOPE_AUDIT.json`의 독립 소스 감사는 `PASS`다. 기존 Camera/Renderer/native Visual의 원본 tracked 경로 1,893개, 데이터 경로 76개, 기존 V1 Candidate 경로 58개에서 변경 경로는 각각 0개다. Camera V5, Terrain, Region Color, Existing Boundary/Glow, Marker, Existing Labels, Title, Suez Geometry, `193.30 km` 값·출처는 이 범위 감사에서 그대로 보존되었다. 이 소스 감사는 이후 전체 프레임 픽셀 검증을 대신하지 않는다.

기존 모듈 변경은 `event_gpu_pipeline_v1.mjs`의 Event 전용 통합과 `event_layout_adapter_v1.mjs`의 새 Annotation 배치 helper 추가뿐이다. 기존 배치 helper의 동작은 유지했다. 일반 Event 스타일 선택 모듈 `event_style_v1.mjs`를 추가했다. Line geometry, Line GPU pass, Occlusion Policy, Timeline, Metric compilation/pass의 기존 소스는 V1 commit과 동일하다. 따라서 기존 허용 충돌은 `EVENT_GEOGRAPHIC_LINE ↔ PROTECTED_GEOGRAPHIC_MARKER`로 유지하며, Text/Title/Safe Area/Metric의 충돌 규칙을 완화하지 않았다.

## 1. Event Line 가시성

1080×1920 실제 production framebuffer에서 동일한 native 배경과 core-only Event draw를 짝지어 합성 alpha를 복원했다. 선분에 수직인 충돌 없는 단면 3개에서 half-alpha 교차점을 보간해 raster core FWHM을 측정했다. 설정상의 width와 실제 측정 width를 구분했다.

| 실제 core 폭 | 기존 V1 | V2 |
|---|---:|---:|
| 중앙값 | 5.01557 px | 6.99875 px |
| 최소–최대, 단면 3개 | 5.00944–5.05520 px | 6.99362–7.00439 px |
| 설정 width | 5 px | 7 px |

기존 geometry·progress·Marker mask를 그대로 사용하는 Event pass에서 한 단계 두껍게 조정했다. V2 Event Glow는 선택 색상과 같은 계열이며 radius 1.25 px, gain 0.10으로 제한했다. Halo를 포함한 관측 폭은 core 폭으로 보고하지 않는다. V2의 halo 포함 관측 support 중앙값은 9.78526 px다.

실제 선택 스타일의 line-only draw에서 Primary 지형 pixel 539,887개 중 592개가 변경되었다. 비율은 0.10965%다. 전체 화면 변경은 702 pixel, 0.03385%다. 이 측정의 보호영역 변경 pixel과 허용 Event ROI 바깥 변경 pixel은 각각 0이다. 이 수치는 해당 측정 프레임의 Event Line 범위이며, 전체 150프레임 보호검사는 별도로 수행한다.

## 2. Primary 배경과 자동 대비

자동 선택은 실제 native framebuffer의 변경 전 display-sRGB를 사용한다. 변경하지 않은 전체 projected Event geometry에 0.5 px 이내인 raster center에서 Primary coverage B 채널 ≥254, native Boundary/Glow 제외, 보호 그래픽의 추가 2 px guard 제외 조건으로 표본을 얻는다. 이 Fixture의 실제 유효 표본은 38개다. sRGB는 luminance와 D65 OKLab 계산을 위해 한 번만 linear sRGB로 변환한다. country 이름, metric 값, 특정 geographic 좌표 분기는 사용하지 않는다.

아래는 동일한 Primary 배경 pixel에 실제 렌더한 여섯 일반 후보의 측정값이다. p10은 낮은 대비 구간을 평가하기 위한 10백분위다. 종합 점수는 luminance p10, OKLab chromatic p10·평균 색 거리, Primary material의 chromatic 거리와 작은 Cyan/Teal 우선 tie 항을 함께 사용한다. 점수는 지각 평가를 위한 이 구현의 상대 순위 값이다.

| 후보 | 실제 luminance ratio p10 | 실제 OKLab chromatic distance p10 | 실제 종합 점수 |
|---|---:|---:|---:|
| BRIGHT_CYAN | 3.46331 | 0.16932 | 1.21970 |
| **BRIGHT_TEAL** | **3.76429** | **0.15990** | **1.24602** |
| CLEAR_AZURE | 2.23216 | 0.19532 | 1.00011 |
| BRIGHT_VIOLET | 1.98286 | 0.24915 | 1.05690 |
| BRIGHT_CORAL | 1.87263 | 0.15426 | 0.75033 |
| BRIGHT_AMBER | 3.43143 | 0.08113 | 0.97427 |

자동 runtime 선택, 독립 Primary-only 선택, 실제 렌더 비교의 winner는 모두 `BRIGHT_TEAL`로 일치했다. 선택 core display-sRGB는 `[0.07, 1.00, 0.84]`, core alpha는 0.94, shader 중심 합성 alpha는 0.946이다. 이는 Suez/Egypt 전용 고정 색상이 아니라 실제 Primary 배경과 material을 평가한 일반 팔레트의 선택 결과다. Region Color·기존 Boundary/Glow 시스템은 수정하지 않았다.

기존 V1과 비교하면 actual luminance ratio p10은 **3.84861 → 3.76429**로 소폭 낮아졌다. luminance 대비가 개선됐다고 주장하지 않는다. 이번 변경의 개선은 금색 계열 배경과의 chromatic 분리이며, 실제 OKLab chromatic distance p10은 **0.00511 → 0.15990**, 실제 종합 점수는 **0.92476 → 1.24602**로 증가했다. 최종 가시성 판단은 휴대폰 사용자 검수에서 확인한다.

## 3. Metric의 시각적 연결

Metric 자신의 placement는 visible Event geometry, Marker occlusion으로 가려지지 않는 line support, measured text atlas bounds, 모든 protected graphics, Safe Area를 바탕으로 후보를 선택한다. 원본 Event geometry·arc-length reveal을 자르거나 다시 시작하지 않으며, 기존 graphic을 옮기지 않는다. 기존 Glyph/Font API를 사용한다. 전체 measured atlas를 예약해 Metric-Text/Marker/Title/Safe Area 충돌을 검사한다.

| 항목 | 결과 |
|---|---|
| `193.30 km` 값·출처 | 변경 없음 — 소스/데이터 감사 PASS |
| 요청 font size 및 실제 측정 | 36 → 40 px; native atlas 197×45 → 217×49, ink 178×29 → 197×33 px |
| 최종 Metric box / measured bounds | `[673.631804, 678.544450, 217, 49]`; 기존보다 왼쪽 22.25 px, 위쪽 2 px |
| visible line과 실제 간격 | Full atlas 중심선 거리 38 → 15.75 px; 보호 footprint 간격 32.8 → 10 px. Ink 중심선 거리 48 → 26.75 px |
| Metric collision | 0 — 전체 ON150 및 독립 segment–box 계산 PASS; 전150프레임 placement 동일 |
| native graphic / Marker pixel·anchor 동일성 | ON150 PASS; 보호영역·Marker·ROI 밖 변경 pixel 0, native signature와 모든 예약 동일 |

## 시각 측정 이력

측정 실패 기록을 지우거나 덮어쓰지 않았다. 모든 시도는 별도 evidence directory에 남아 있다.

| 기록 | 결과와 처리 |
|---|---|
| `evidence/visual-measurement/REPORT.json` | FAIL: 측정 도구가 raw fixture intent를 compiler에 전달하여 `EVENT_INTENT_VERSION_REQUIRED`. 도구에서 canonical Event intent를 사용하도록 수정했다. |
| `evidence/visual-measurement-r2/REPORT.json` | FAIL: `ACTUAL_RENDERED_PALETTE_WINNER_DIFFERS_FROM_AUTOMATIC_SELECTION`. 실제 합성 비교와 자동 선택의 일치를 확인하지 못했으므로 완료로 처리하지 않았다. |
| `evidence/visual-measurement-r3/REPORT.json` | FAIL: 같은 winner 불일치. 부분 측정도 해당 보고서에 보존했다. |
| `evidence/visual-measurement-r4/REPORT.json` | PASS: 실제 core raster center를 사용하도록 자동 표본 영역을 맞춘 뒤 runtime/독립/실제 winner가 모두 BRIGHT_TEAL로 일치했다. native 배경 hash 동일, geometry 동일, GL error 0. |

Sampler 수정은 palette나 score formula를 바꾸지 않았다. 중심 합성 alpha 0.946과 실제 Primary core 표본으로 측정 영역을 맞췄다. r4의 native base RGBA SHA-256은 `029f654df98487f1b90937068f17b6a277d9ebc29a6649636c16dd53debd7081`이며, 저장된 native 기준 framebuffer와 동일했다. r4 보고서 SHA-256은 `d61aec44bb7d64d518586e977d1022ded562effb8a1e0e4fb5d1f220e6692d85`다.

## 전체 검증과 영구 저장

| 필수 항목 | 상태 | 증거 / 최종 값 |
|---|---|---|
| 변경 범위 / country-specific hardcode 소스 감사 | PASS | `evidence/SOURCE_SCOPE_AUDIT.json`; 10 Event 모듈에서 guard finding 0 |
| 실제 width / palette / Primary contrast 측정 | PASS | `evidence/visual-measurement-r4/REPORT.json` |
| V5 전체 Event OFF 250 frames BIT_EXACT | PASS | `evidence/off250/REPORT.json`: 250/250 RGBA·PNG 일치 |
| Event ON 150 frames 보호검사 | PASS | `evidence/on150/REPORT.json`: 모든 보호 pixel·ROI 밖 변경 0 |
| Line geometry / progress 동일 | PASS | ON150의 모든 path·fraction·length·direction·occlusion은 V1과 exact |
| Marker pixel / anchor 동일 | PASS | ON150 native layout/camera 및 Marker 전체 예약 pixel 동일 |
| Synthetic A/B | PASS | `evidence/SYNTHETIC_A_B_GPU.json`; 양 Fixture 보호/ROI/hold/OFF 복원 PASS |
| Collision Synthetic Fixture | PASS | `evidence/COLLISION_SYNTHETIC_GPU.json`; 양방향 허용 mask 및 모든 금지 충돌 PASS |
| Metric collision 0 | PASS | `evidence/METRIC_VISUAL_RELATION.json`; measured full atlas strict 검사 |
| 64306 Event Grammar | PASS | `evidence/grammar64306/REPORT.json`; 저장 semantic 기준, 150프레임·75 Metric 프레임 순차 glyph 검사 |
| 5초 silent V2 Candidate | PASS | `evidence/video/REPORT.json`; 1080×1920, 30 fps, 150 frames, 5초, audio 0; strict decode PASS. 원본 RGBA150개는 ON150과 일치 |
| Checkpoint PNG | PASS | `evidence/CHECKPOINT_SOURCE_MATCH_VIDEO.json`; 9/9 native PNG/RGBA가 영상 생성 원본 프레임과 동일 |
| Candidate Source / Fixture / Manifest 영구 저장 | PASS | Development branch의 저장된 구현·기존 영구 Fixture·독립 Manifest; 최종 `--require-persisted`로 HEAD/index body 확인 |
| 필수 temp-only 파일 0 | PASS | 최종 Manifest closure의 필수 temp-only 목록은 빈 배열. 다운로드 확인용 사본/Scanner는 런타임 필수 입력이 아님 |
| Secret Scan | PASS | `evidence/SECRET_SCAN.json`; pinned Gitleaks 8.24.3, 작업 텍스트128개 및 개발 Git 변경 이력, exit0/발견0/스캔 중 변경0 |
| Public Review allowlist | PASS | MP4 1, PNG 9, SHA256SUMS 1; 그 외 파일 0 |
| 실제 다운로드 URL HTTP 200 | PASS | `evidence/HTTP_DOWNLOAD_VERIFY.json`; 11/11 전체 body GET HTTP 200 |
| 다운로드본과 원본 SHA-256 동일 | PASS | 11/11 다운로드 = 원본 = commit body, bytes 동일; checksum 목록의 media 10개 모두 검증 |

## 사용자 검수 파일

영상 파일명: `SUEZ_EVENT_SYSTEM_V1_CANDIDATE_V2_5S_SILENT.mp4`  
SHA-256: `94d5210b792bed0324bbed10bda5bad304b43be613b13094764e6a29ecad796f` (551,691 bytes).

| 파일 | 원본 SHA-256 | 실제 다운로드 URL | HTTP | 다운로드 SHA 일치 |
|---|---|---|---|---|
| 01_EVENT_READY_F000.png | `fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673` | [다운로드](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1439ab604b305e39ee18af9538b167cedddfa277/world-simulation-shorts-engine/recovery/event-v1-candidate-v2/public-review/01_EVENT_READY_F000.png) | 200 | PASS |
| 02_LINE_REVEAL_F001.png | `fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673` | [다운로드](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1439ab604b305e39ee18af9538b167cedddfa277/world-simulation-shorts-engine/recovery/event-v1-candidate-v2/public-review/02_LINE_REVEAL_F001.png) | 200 | PASS |
| 03_LINE_REVEAL_F030.png | `e69fd05cddef1960525c0f2cb6b9e66aec0d7615088bbb401a2a139fbbe41691` | [다운로드](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1439ab604b305e39ee18af9538b167cedddfa277/world-simulation-shorts-engine/recovery/event-v1-candidate-v2/public-review/03_LINE_REVEAL_F030.png) | 200 | PASS |
| 04_LINE_REVEAL_F059.png | `5733e7b7ece8d31e74f8cd5b834d069a3fd44a96bce7b437c02712f642f02c56` | [다운로드](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1439ab604b305e39ee18af9538b167cedddfa277/world-simulation-shorts-engine/recovery/event-v1-candidate-v2/public-review/04_LINE_REVEAL_F059.png) | 200 | PASS |
| 05_LINE_HOLD_F074.png | `5733e7b7ece8d31e74f8cd5b834d069a3fd44a96bce7b437c02712f642f02c56` | [다운로드](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1439ab604b305e39ee18af9538b167cedddfa277/world-simulation-shorts-engine/recovery/event-v1-candidate-v2/public-review/05_LINE_HOLD_F074.png) | 200 | PASS |
| 06_METRIC_REVEAL_F075.png | `5733e7b7ece8d31e74f8cd5b834d069a3fd44a96bce7b437c02712f642f02c56` | [다운로드](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1439ab604b305e39ee18af9538b167cedddfa277/world-simulation-shorts-engine/recovery/event-v1-candidate-v2/public-review/06_METRIC_REVEAL_F075.png) | 200 | PASS |
| 07_METRIC_REVEAL_F090.png | `2a9cb208e83a41c1057ebad160be19cfed939a6a249572d9242319f455fe812d` | [다운로드](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1439ab604b305e39ee18af9538b167cedddfa277/world-simulation-shorts-engine/recovery/event-v1-candidate-v2/public-review/07_METRIC_REVEAL_F090.png) | 200 | PASS |
| 08_METRIC_REVEAL_F104.png | `23113988703b43de8d3dd27f11bb8fcd84e9dc9a0bba2c4876e759cbb8a8bb5a` | [다운로드](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1439ab604b305e39ee18af9538b167cedddfa277/world-simulation-shorts-engine/recovery/event-v1-candidate-v2/public-review/08_METRIC_REVEAL_F104.png) | 200 | PASS |
| 09_INFORMATION_HOLD_F149.png | `23113988703b43de8d3dd27f11bb8fcd84e9dc9a0bba2c4876e759cbb8a8bb5a` | [다운로드](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1439ab604b305e39ee18af9538b167cedddfa277/world-simulation-shorts-engine/recovery/event-v1-candidate-v2/public-review/09_INFORMATION_HOLD_F149.png) | 200 | PASS |
| SHA256SUMS | `4bb766645073f81b897aa3adc2b3941d88ae2372d5cafbf96f1e2a82afe0b27b` | [다운로드](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1439ab604b305e39ee18af9538b167cedddfa277/world-simulation-shorts-engine/recovery/event-v1-candidate-v2/public-review/SHA256SUMS) | 200 | PASS |
| SUEZ_EVENT_SYSTEM_V1_CANDIDATE_V2_5S_SILENT.mp4 | `94d5210b792bed0324bbed10bda5bad304b43be613b13094764e6a29ecad796f` | [다운로드](https://raw.githubusercontent.com/dimon3898-sys/yeonhwarok-free/1439ab604b305e39ee18af9538b167cedddfa277/world-simulation-shorts-engine/recovery/event-v1-candidate-v2/public-review/SUEZ_EVENT_SYSTEM_V1_CANDIDATE_V2_5S_SILENT.mp4) | 200 | PASS |

최종 사용자 보고 뒤 `USER_VIDEO_REVIEW_REQUIRED`에서 멈춘다. 사용자 영상 승인은 아직 없으며, Event Final 승격은 하지 않았다.

검증 한계: 64306은 저장된 Core의 의미 문법 감사를 기준으로 검사했고 원본 영상의 새 직접 대조는 하지 않았다. 현재 머신의 실제 검증·제작이며 별도 새 클라우드 복원 렌더를 주장하지 않는다. Secret Scan은 텍스트와 Git diff를 검사하며 바이너리 media 본문은 텍스트 탐지 대상이 아니다. 검수 URL은 media commit `1439ab6`의 고정 주소이며 이후 문서/Manifest 저장으로 media 바이트를 변경하지 않는다.
