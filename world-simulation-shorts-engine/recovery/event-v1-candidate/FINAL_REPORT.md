# Event System V1 Candidate 최종 보고

상태: **EVENT_SYSTEM_V1_CANDIDATE / USER_VIDEO_REVIEW_REQUIRED**
`event_final=false`. 사용자 영상 승인 전 FINAL 승격은 하지 않았습니다.

## 결과

| 요청 단계 | 결과 | 근거 |
|---|---|---|
| 1–3 Occlusion 정책·Layer·Static 보호 | PASS, 장시간 검증 전 소스 저장 | 최초 구현 23f35d9, Static 체크포인트 9c43796; evidence/STATIC_LINE_MARKER_PROTECTION.json |
| 4 V5 전체 250프레임 Event OFF | 250/250 BIT_EXACT | evidence/off250-r2/REPORT.json |
| 5 Event ON 보호검사 | 150/150 PASS; 보호영역·ROI 밖 변경 픽셀 0 | evidence/on150-r2/REPORT.json |
| 6 Synthetic A/B | 56 focused 검사 PASS; A/B 기존 ON 16개 픽셀 해시·control 일치 | evidence/FOCUSED_REGRESSION.log, SYNTHETIC_A_B_GPU.json, SYNTHETIC_A_B_BASELINE_COMPARISON.json |
| 7 Collision Synthetic Fixture | FORWARD/REVERSE PASS; Text/Title/Panel/Safe Area/Metric 계속 차단 | evidence/COLLISION_SYNTHETIC_GPU.json |
| 8 64306 Event Grammar | 저장된 의미 문법 기준 PASS | evidence/grammar64306/REPORT.json |
| 9 Suez Silent Proof | 5초, 1080×1920, 30fps, H.264 150프레임, 오디오 0; 전체 디코딩 PASS | evidence/video/REPORT.json, VIDEO_DECODE_VALIDATION.json |
| 10 Checkpoint PNG | 네이티브 9장; 영상 원본 RGBA·PNG 해시와 일치 | evidence/checkpoints/REPORT.json |
| 11 Candidate 영구 저장 | 소스·fixture·media·독립 Manifest 개발 브랜치에 저장 | development/event-system-v1-20261012; manifests/ |
| 12 Secret Scan | Gitleaks 8.24.3 작업 파일 및 개발 Git 변경 이력 모두 발견 0, exit 0 | evidence/SECRET_SCAN.json |
| 13 보고 | 이 보고서 | FINAL_REPORT.md |

OFF는 새 Event 경로와 변경 없는 V5 경로의 실제 RGBA·PNG를 비교하고, 두 개의 저장된 전체 250프레임 inventory에도 대조했습니다.
ON은 고정된 V5 Final camera 상태에서 Event 0–149를 모두 렌더했습니다. 모든 기존 보호영역은 픽셀 동일하며, 내부 arc-length는 가림 영역에서도 계속 진행합니다. Line Hold와 Information Hold도 안정적이고 Event OFF 복원도 동일합니다.
영상 제작 시 150개 원본 RGBA 해시는 ON 보호검사와 모두 일치했습니다. Checkpoint 9장도 해당 영상 원본 프레임과 일치합니다.

## 보존된 기준점과 정책

- Event Core: `00ad07e4a6041ea4cc6369bfce8871762f61f152`
- Suez Data: `69e6ed83acac00bfa7ab1853722f873792a813e1`
- V5 Final: `29b8ee294360812b55ef577b62411de58159003b`

전체 Event Core 재구현, Suez 원본 검색·재조사, Camera/Renderer/기존 Visual 수정은 하지 않았습니다.
원래 Core 경로에서 수정한 구현은 Event Line GPU pass와 Event composition caller뿐이며, 새 policy module을 추가했습니다. Metric compiler, Timeline, Line geometry/arc-length 구현, Glyph API와 기존 layout/collision API는 그대로입니다.
Suez 92좌표 / 91세그먼트와 공식 `193.30 km`, Metric anchor 및 provenance도 원본 바이트를 보존했습니다.

`GEOGRAPHIC_OCCLUSION_POLICY`의 유일한 허용 쌍은 EVENT_GEOGRAPHIC_LINE ↔ PROTECTED_GEOGRAPHIC_MARKER입니다. Line은 기존 Marker보다 아래에서 렌더하고, Marker의 전체 기존 보호 사각형에서는 Event Line coverage만 가립니다. 이 coverage 처리는 원본 geometry, projected arc-length, reveal clock을 바꾸지 않습니다.
Marker anchor/position/size/design은 변경되지 않았습니다. Text/Title/Panel, 전체 Safe Area 및 Metric의 보호/배치 규칙은 계속 엄격합니다. 기존 untyped 보호 사각형도 예외 없이 차단합니다.
공통 Event 코드에는 특정 국가·운하·Metric 값·지리 좌표 예외가 없습니다.

## 검증 중 발견·교정한 항목

기록은 덮어쓰지 않고 개발 브랜치에 보존했습니다.

1. Static synthetic fixture의 PlaneGeometry가 화면 좌표계에서 backface culling되어 실제 정적 선이 없었습니다. fixture만 DoubleSide로 교정했고, 정적 선의 실제 픽셀 존재 검사와 exact 보호 검사를 유지했습니다.
2. 기존 Event caller가 Location Label의 175px 폭 제한을 새 Metric에 그대로 전달해 full glyph wrap을 거부했습니다. 기존 Native glyph API로 측정한 전체 Atlas는 197×45px였습니다. Event 전용 예약 폭을 기존 Safe Area와 동일한 native padding에서 산출하도록 caller만 보정했습니다. Font/size/outline/baseline, 기존 Visual token 및 Metric Core는 그대로이고, 전체 예약 Atlas는 기존 strict collision API를 통과합니다. 이 보정 후 OFF 250프레임과 ON 150프레임을 다시 실행했습니다.
3. Collision fixture의 독립 투영 산술과 native projection 사이에 약 2.27×10⁻¹³px 차이가 있었습니다. 독립 화면 산술 비교만 10⁻⁹px 한도로 검증하며, vertex 수·원본 geometry/primitive JSON·Camera/layout·protected pixels의 exact 검사들은 유지했습니다.

## 영상과 검수 범위

[5초 Silent Proof](public-review/SUEZ_EVENT_SYSTEM_V1_CANDIDATE_5S_SILENT.mp4)
[최종 Hold PNG](public-review/09_INFORMATION_HOLD_F149.png)
[검수 파일 SHA256SUMS](public-review/SHA256SUMS)

영상 SHA-256: `f241edccc90d12bdd5a4a64e8602e321a0dc065d17ccff2c4a40e39207480dad`.

64306 검사는 영구 보존된 원래 의미 문법 감사(geographic line → brief full-line hold → fixed measured glyph reveal → information hold)를 기준으로 실제 ON 150프레임과 75개 Metric frame metadata를 검사했습니다. Atlas·baseline·anchor·full reservation은 고정이고 glyph coverage는 순차적입니다. Reference의 원본 재검색이나 새 직접 영상 대조는 하지 않았으며, 현재 timing은 저장된 GENERATOR_RULE입니다.
Secret Scan은 redacted Gitleaks 기본 규칙으로 개발 변경 이력과 텍스트 파일을 검사했습니다. 생성된 바이너리 media 본문은 검사 대상이 아니며 Git 텍스트 변경과 LFS pointer는 검사했습니다.
현재 머신에서 실제 검증·제작했으며, 새 클라우드 태스크 복원이나 별도 fresh render를 검증한 것으로 표시하지 않습니다.

## 저장과 다음 상태

구현·검사 절차·주요 결과·Proof·Manifest는 각 장시간 단계 전에 또는 단계 완료 직후 개발 브랜치에 commit/push했습니다.
기존 Core/V5/Data Manifest는 역사적 기준으로 보존하고 새 Candidate의 Source/Fixture/Evidence/Runtime/Build/Dependency/Import/Hash Manifest를 별도로 작성했습니다. 최종 저장 후 `validate_manifests.py --require-persisted`로 HEAD/index와 실제 파일 바이트를 다시 검증합니다.
공개 검수용 디렉터리에는 MP4, PNG와 SHA256SUMS만 있습니다. main, 기존 V5 Public Review와 FINAL 기준점은 변경하지 않았습니다.

다음 단계는 사용자 영상 검수입니다. 승인 전 `EVENT_SYSTEM_V1_FINAL` 승격과 후속 Plugin 단계는 진행하지 않습니다.
