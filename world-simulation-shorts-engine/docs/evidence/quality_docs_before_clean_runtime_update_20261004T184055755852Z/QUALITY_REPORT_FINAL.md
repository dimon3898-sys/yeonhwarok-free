# World Simulation Shorts Engine — 진행 중 품질 검증 보고서

**상태: 20초 HIGH v002와 자연어 속도 수정 v003의 실제 부분 재렌더·최종 QC·전체 브라우저 재생·첨부 다운로드, 전체 130개 회귀 검사는 통과했습니다. 전체 프로젝트 완료는 아직 아닙니다.** 첫 v001의 QC 실패와 비용을 보존했습니다. v002와 v003은 각각 S002만 새로 렌더하고 4개 Scene을 재사용했습니다. 이 두 성공 버전은 TTS/자막 OFF이며, TTS/자막 ON인 새 20초 시험, 75초 HIGH 전체 실측과 공개 모바일 접속은 대기 중입니다. 브라우저 모바일 에뮬레이션을 실제 휴대폰 검증으로 해석하지 않습니다.

이 갱신 전 두 보고서의 정확한 바이트와 SHA는 [quality_docs_before_130_update/SNAPSHOT_MANIFEST.json](docs/evidence/quality_docs_before_130_update_20261004T181126076353Z/SNAPSHOT_MANIFEST.json)에 새 파일로 보존했습니다. 과거 증거를 최신 결과로 덮어쓰지 않았습니다.

## 완료 판정 현황

| 항목 | 현재 상태 | 근거/제한 |
|---|---|---|
| 자연어 → Story/Scene Plan → Scene JSON | 구현·동작 검사 완료 | 지원 도메인의 검증된 GIS 장소/항로 사용 |
| 정확한 계획 승인·버전·부분 수정·캐시 | 구조 검사·v002/v003 실제 부분 재렌더 **PASS** | 각 S002 신규 1개/캐시 4개; 미수정 4개 MP4 SHA 동일 |
| 전체 코어 회귀 | **130/130 PASS** | unittest 131.933초, 프로세스 wall 133.182935초, 검사 중 소스 변경 0 |
| 첫 20초 HIGH v001 | **최종 QC 실패, 보존** | 뉴욕→런던→두바이, 5개 새 Scene, 600프레임 |
| 교정 후 v002 | **PASS** | S002만 새 렌더, 4개 재사용, 실제 600프레임 QC·14/14 사건 |
| 자연어 속도 수정 v003 | **PASS** | S002 신규 1개/캐시 4개, 전체 600프레임 QC와 재생·13개 첨부 다운로드 |
| TTS/자막 ON 새 20초 시험 | **렌더 진행 중** | project_21a865e0dc8d/v001, job_4f9991fe994c; 완료 QC는 대기 |
| 75초 HIGH 전체 생성·CPU 벤치마크 | **PENDING** | 계획/기하/TTS 사전 검사는 전체 영상 렌더가 아님 |
| MASTER V3와 실제 주요 프레임 비교 | 검토 기록 있음, 약점 명시 | V3 재질·대기·깊이 유지, HERO 상면 pose/분리감은 상대적으로 약함 |
| v002/v003 전체 브라우저 재생·다운로드 | **PASS** | 각 375px 실제 브라우저, 13개 첨부 SHA 일치, Range 206, 끝까지 재생 |
| 공개 URL·실제 휴대폰 외부 접속 | **미검증** | 현재 공개 접속 URL 없음; localhost는 휴대폰 주소가 아님 |
| 클라우드 환경 설정 | 초안 저장, **게시 대기** | 검증된 재사용 환경 설정의 최종 게시 상태 추가 필요 |

## 기존 프로젝트 보존과 재사용

새 앱은 기존 `cinematic-world-map`과 분리된 `world-simulation-shorts-engine`에 구현했습니다. 기존 MASTER V1/V2/V3, 렌더러, GIS/그래픽 자산을 교체하는 구조가 아닙니다. 초기 보존 검사는 기준 파일 570개에서 불일치 0을 확인했습니다. 근거는 [original_preservation_pre_render_r01.json](docs/evidence/original_preservation_pre_render_r01.json)이며 최종 변경 이후의 보존 재검사와 Git 반영 검증은 별도로 남겨야 합니다.

V3의 Three.js/WebGL 3D 지구, 실제 8K 지표/야간광/구름 자산, 대기 셰이더, 3D 항공기·항로, 카메라와 색보정 구조를 읽어서 재사용합니다. V3의 완성 영상이나 서울→도쿄→싱가포르 고정 타임라인을 다시 재생하지 않습니다. 실제 생산 시험은 뉴욕→런던→두바이로 변경된 GIS·항로·Scene을 사용합니다.

HIGH는 내부 2160×3840에서 최종 1080×1920으로 Lanczos 다운샘플링하고 시간 샘플 1개를 사용합니다. CINEMA는 같은 대기 셰이더와 내부 해상도에서 시간 샘플 2개를 사용하는 설정입니다. [CINEMA 명령/캐시 증거](docs/evidence/cinema_temporal_samples_20261004T140155Z/COMMAND_CACHE_REPORT.json)는 GL 실행 전 실제 파이프라인 명령과 품질 캐시 분리를 확인한 계약 증거입니다. 이후 [실제 CINEMA 두 프레임 보고서](docs/evidence/cinema_two_temporal_samples_actual_20261004T174915Z/ACTUAL_CINEMA_REPORT.json)는 S004의 2개 실제 프레임을 2160×3840/temporalSceneSamples=2에서 렌더해 1080×1920 H.264로 인코딩했고 **104.468초**를 측정했습니다. 이는 0.066667초의 실제 통합 증거이며 전체 CINEMA 영상의 완료·렌더 벤치마크나 객관적인 영상미 개선 측정이 아닙니다. FAST 540×960은 계획 검토용으로만 사용합니다.

## 구현된 생성기 구조

자연어 입력은 제한된 오프라인 도메인 기획기로 Story/Scene Plan을 만든 뒤 스키마·출처·FACT/ASSUMPTION/SIMULATION·사건 밀도/다양성·Peak·인과관계·카메라 경계를 검사합니다. 검증된 계획의 정확한 hash를 승인해야 Scene 렌더가 시작됩니다. 렌더 결과는 Scene별 MP4, 감사, 체크포인트와 함께 보존하며 정상 캐시는 SHA·자산·렌더러·품질·문맥이 일치할 때만 재사용합니다.

조명은 Scene 목적에 맞춰 CINEMATIC_NIGHT, GEOGRAPHY_READABILITY, DAY_DOCUMENTARY, HERO 등의 프리셋을 선택합니다. 실제 GIS 항로에서 카메라 경계 위치를 구면 보간하고, 마지막 카메라는 주 경로 전체의 실제 9:16 투영·가림·안전영역을 검사합니다. 한 전경에서 보여줄 수 없는 네트워크는 `MULTI_HEMISPHERE_OVERVIEW`로 차단합니다.

부분 수정은 Diff 승인 후 새 불변 버전을 만듭니다. 삭제와 결론 지연도 실제 Scene/사건/나레이션/사운드를 수정하며 훅·Peak·결말·인과관계가 깨지면 차단합니다. `render_time_offset`과 `render_context`를 보존해 조립 시간만 바뀐 현대 Scene의 프레임을 재사용할 수 있습니다. 움직이는 해상 경로의 선박 추가와 희미한 연결망 추가는 실제 카메라의 순수 Three.js 기하 검사로 표시 가능한지 먼저 확인합니다. 이 검사도 최종 영상 렌더/QC를 대체하지 않습니다.

TTS/BGM/자막은 각각 선택 사항입니다. 무료 오프라인 eSpeak와 외부 나레이션/교체 가능한 공급자 인터페이스를 지원합니다. 언어 미지정 시 Scene별 한글/영어를 선택하며 명시적 언어가 우선합니다. 외부 나레이션 자막에는 사용자 제공 타이밍이 필요합니다. 실제 발화 시간이 Scene을 넘으면 비싼 그래픽 렌더 전에 차단합니다. eSpeak는 기계적인 음성이고 단어별 자동 정렬·ASR은 구현 근거가 없습니다.

자막은 번들 Noto Sans CJK KR 폰트 44px의 실제 너비, 0.4px 글자 간격과 2px outline을 포함해 단어/긴 단어를 나눕니다. ASS centisecond 시각과 보수적 layout bounds를 기록하고 안전영역 초과를 사전 차단합니다. 활성 자막 구간의 렌더 라벨 bounds와 겹치면 QC 경고를 냅니다. 누락된 라벨 기하에는 판정 불가 경고를 내며 인코딩 픽셀의 글자 인식이나 겹침 없음으로 주장하지 않습니다.

외부 MP4의 CINEMATIC_CLIP 슬롯은 사용권·길이·호환 사건을 검증합니다. 실제 출발/도착/네트워크 사건이 필요한 장면에 임의 외부 영상을 넣고 물리 사건을 발생했다고 기록하지 않습니다. 실제 HTTP 업로드·Diff·불변 버전 승인은 [clip_http_integration_r01/REPORT.json](docs/evidence/clip_http_integration_r01/REPORT.json)에 기록되어 있으나 해당 fixture는 기술 테스트 패턴이며 V3급 실영상 삽입/전체 렌더 합격이 아닙니다.

## 기획·회귀·오디오 기술 검사

서로 다른 세 주제의 실제 기획을 생성했습니다. 초기 측정 기록은 [planning_test_projects_r02.json](docs/evidence/planning_test_projects_r02.json), 이후 B/C 계획은 [latest_BC_plans_r01.json](docs/evidence/latest_BC_plans_r01.json)에 보존되어 있습니다. 당시 계획과 현재 소스를 동일한 실행으로 간주하지 않습니다.

| 기획 검사 | 주제 | 길이 | 확인 |
|---|---|---|---|
| A | 런던→파리→로마 민간 항공 | 20초 | 고정 V3 도시 이탈, 실제 GIS, 카메라·사건·경계 |
| B | 수에즈 운하 7일 폐쇄 가정 | 75초 | 출처 있는 해상 그래프, 우회, 가정/시뮬레이션, 두 Peak |
| C | 서울–싱가포르 가상 직접 연결 | 40초 | 실제 장소와 가상 관계 분리, 새 변수·Peak·결말 |

자막 추가 시점의 전체 실행은 **78/78 통과**, unittest 측정 **39.283초**, 프로세스 wall **41.147초**였습니다. [subtitle_layout EVIDENCE_REPORT.json](docs/evidence/subtitle_layout_20261004T160655Z/EVIDENCE_REPORT.json)과 [unittest.log](docs/evidence/subtitle_layout_20261004T160655Z/unittest.log)에 보존되어 있습니다. 이후 실제 E006 가시성·승인·기획 의미 검수를 연결한 **92/92 통과, 256.541초**의 전체 회귀는 [semantic_gate_regression/TEST_REPORT.json](docs/evidence/semantic_gate_regression_20261004T164822Z/TEST_REPORT.json)과 [unittest.log](docs/evidence/semantic_gate_regression_20261004T164822Z/unittest.log)에 기록되어 있습니다. 어느 시간도 영상 렌더 벤치마크가 아닙니다.

후속 나레이션 사건 참조 9개, CPU 예측 15개, 진행률 정보 재타이밍 3개를 포함한 첫 **119개 실행은 3개 실패**했습니다. 새로운 성공 실측 연결 후 지원하지 않는 화살표 글리프가 Scene 정보에 포함되어 의미 사건 가시성 게이트가 차단한 것으로 확인했고 ASCII 문구로 교정했습니다. 실패 증거는 [final_core_tests_20261004T171115Z/TEST_REPORT.json](docs/evidence/final_core_tests_20261004T171115Z/TEST_REPORT.json)에 보존했습니다. 관련 교정 6개 검사 후 전체를 다시 실행한 결과는 **119/119 PASS**, unittest 측정 **271.545초**, 프로세스 wall **275.559833초**입니다. [최종 TEST_REPORT.json](docs/evidence/final_core_tests_20261004T171928Z/TEST_REPORT.json)과 [unittest.log](docs/evidence/final_core_tests_20261004T171928Z/unittest.log)에 실행 전후 스키마·엔진·테스트·서버·셰이더·UI의 SHA를 기록했으며 검사 중 소스 변경은 0입니다. 이 결과는 해당 SHA의 전체 동작 회귀이며 실제 영상 렌더, 유료 GPU, 관객 유지율, 실제 휴대폰이나 단어별 ASR 인증이 아닙니다. 나레이션 참조/예측/재타이밍 검사는 Scene 계약의 단위 검사이며 실제 TTS 단어 정렬이나 새 영상 렌더 결과가 아닙니다.

현재의 권위 있는 전체 실행은 **130/130 PASS**, unittest **131.933초**, 프로세스 wall **133.182935초**입니다. [final_core_tests_20261004T180346Z/TEST_REPORT.json](docs/evidence/final_core_tests_20261004T180346Z/TEST_REPORT.json)과 [unittest.log](docs/evidence/final_core_tests_20261004T180346Z/unittest.log)는 실행 소스 SHA·로그 SHA와 `source_changes=[]`를 보존합니다. 119개 이후 지리 FACT 대상 연결 4개, 계획된 항로/Scene 참조 4개, 실제 오프라인 짧은 대본 발화 예산 3개가 추가됐습니다. 같은 출처를 쓰는 서로 다른 장소의 FACT가 섞여도 차단하고, 후속 항로의 비교 정보와 현재 Scene의 실제 출발/도착 요구를 구분합니다. 실제 발화 예산 검사는 eSpeak WAV 시간을 측정하며 청취·단어별 동기화·새 영상 전체 렌더를 인증하지 않습니다. 이전 119개 실패와 각 합격 스냅샷은 유지합니다.

자막 검사는 실제 기존 shipping75 나레이션 cue에서 ASS/layout 메타데이터를 생성했습니다. 이전 한국어 25글자 너비 1,025.71px가 795px 안전 너비를 초과했고 교정된 최대 줄 너비는 660.28px였습니다. 근거는 위 자막 증거에 있으며 실제 자막 영상의 글리프·최종 생산 장면과의 겹침을 픽셀로 인증한 결과는 아닙니다.

독립적인 내보내기 도구 검사는 합성 임시 fixture로 **10/10 통과, 0.106초**를 확인했습니다. [deliverable_tools_unit_r01.json](tools/evidence/deliverable_tools_unit_r01.json)에 해시·경계를 기록했습니다. QC·승인·SHA 불일치 거절, recovery 출력 경로, 원본/기존 ZIP 보존, 캐시 시간 구분, 분할 SHA와 GitHub 크기 경계를 검사합니다. fixture의 MP4 바이트는 실영상이 아닙니다.

실제 기술 단위 증거는 [render_pipeline_unit_v001/UNIT_REPORT.json](docs/evidence/render_pipeline_unit_v001/UNIT_REPORT.json)에 있습니다. 실제 한국어 오프라인 합성, FFmpeg 주석 픽셀 변화와 합성음의 loudness를 확인했습니다. 600프레임 retention 계약 fixture는 합성 감사이며 실제 생산 영상과 구분합니다. [한국어 shipping75 TTS 사전 검사](docs/evidence/shipping75_tts_preflight_20261004T134541Z/INFERRED_PIPELINE_REPORT.json)는 실제 발화 시간 검사이며 75초 MP4 전체 렌더가 아닙니다. 직접 음성 청취는 주장하지 않습니다.

## 75초 해상 시험 — 출처·기획·실제 사전 검사

첫 미승인 B75 계획 `project_eb9417557bfa/v001`의 E004/E024는 싱가포르 표시/좌표에 수에즈 FACT F02를 연결하는 실제 결함이 있었습니다. [읽기 전용 감사](docs/evidence/shipping75_pre_render_claim_audit_r01.json)를 보존하고, 현재 기획기에서 `metadata.coordinate_claim_targets`와 장소·이벤트·좌표·출처의 일치를 검사하도록 교정했습니다. 이전 불변 계획을 덮어쓰지 않았습니다.

새 계획은 [project_594442ec2df9/v001](projects/project_594442ec2df9/versions/v001/scene_plan.json)입니다. 실제 375px 브라우저 [기획 보고서](validation/final_B75_shipping_planning_r02/UI_END_TO_END_REPORT.json)는 **23.797초**, 10개 Scene 표시, 승인 전 render request 0을 기록합니다. 계획은 41개 의미 사건·평균 1.8438초·최대 2.15초·첫 3초 4개·두 Peak, 오류/경고 0입니다. E004/E024는 Singapore 설명과 F03을 사용합니다. 7일 폐쇄는 A01 **ASSUMPTION**, 우회는 A01을 전제로 한 M01 **SIMULATION**입니다. 공개 그래프의 구면 길이는 15,530.53897178717/21,990.63187274913km이고 차이 6,460.09290096196km를 약 6,460km로 표현합니다. 실제 배송 지연·운임·선박 선택 예측으로 주장하지 않습니다. 원본 searoute 패키지·경로·항구/네트워크와 라이선스 SHA가 일치하고 두 항로의 125/124개 점이 원본 GeoJSON과 같습니다.

[shipping75_4k_preflight](docs/evidence/shipping75_4k_preflight_20261004T175751Z/S005.json)에서 S001/S005/S009/S010의 **6개 실제 2160×3840 still**을 렌더했습니다. 작업자가 네 Scene의 첫 장면·수에즈 차단/도착/대안 시작·후반 Peak·최종 전체 범위를 직접 검토했고 각 감사는 누락 텍스처/WebGL/경로 오류 없이 기록됐습니다. 이 여섯 still과 순수 기하 사전 인증은 75초 전체 움직임·편집·자막 겹침·최종 QC를 검증하지 않습니다.

[최신 실제 audio/TTS/ASS 사전 보고서](docs/evidence/shipping75_audio_preflight_latest_20261004T174346Z/MEASURED_PREFLIGHT_REPORT.json)는 **18.742555초** 실행, 실제 75초/48kHz/stereo 합성음, -18.0 LUFS/-2.5dBTP, 한국어 eSpeak 10개 발화 **2.648396–5.366729초**가 각 7.42초 예산 안임을 기록합니다. ASS 최대 줄 폭은 **775.2px ≤ 795px**, 당시 layout/binding 경고 0입니다. 이 사전 보고서는 원래 `project_eb9417557bfa/v001`에 속합니다. FACT 교정 후 새 B75의 10개 나레이션 문자열은 snapshot과 동일하며 보고서의 나레이션 payload SHA는 `b24ec35dc78c5ca9730a497453762010b12009968e5ff05da75ed234b9d8345c`입니다. 새 계획 전체 hash와 FACT 문맥은 달라 재검수/정확한 승인이 필요하며 기존 전체 보고서를 새 계획의 실행으로 주장하지 않습니다. **75초 MP4·전체 렌더 시간·사람의 청취·단어 정렬·생산 자막 겹침은 아직 검증하지 않았습니다.**

## 첫 실제 20초 HIGH 실행 — 실패도 보존

프로젝트는 `project_b89a30908047`, 버전은 `v001`입니다. [project_result.json](projects/project_b89a30908047/versions/v001/renders/project_result.json)과 [qc_report.json](projects/project_b89a30908047/versions/v001/qc/qc_report.json)에 실제 실행 근거를 보존했습니다. 최종/무음 파일은 존재하지만 **검수 실패 진단 산출물이며 승인된 최종 다운로드 영상이 아닙니다**.

| 검사 | 관측값 | 판정 |
|---|---|---|
| 인코딩 | 1080×1920, 9:16, H.264, 30fps, 20.000초 | 규격 확인 |
| 프레임 | 600개 전체 인코딩 RGB 프레임 디코딩 | 기술 검사 실행 |
| black/exact duplicate/near freeze | 0 / 0 / 0.000초 | 해당 검사 통과 |
| clipping/WebGL/누락 자산/깨진 항로 | 기록된 오류 0 | 해당 검사 통과 |
| 최대 카메라 각도/위치 step | 1.4405° / 0.06860 지구 반경 | 기록된 임계 검사 통과 |
| 오디오 | -18.0 LUFS, -2.5 dBTP | 측정 확인, 직접 청취 아님 |
| 계획 Retention | 14 사건, 평균 1.4423초, 최대 2.42초, 첫 3초 4 사건 | 계획 단계 통과 |
| 실제 렌더 Retention | 13 사건, 평균 1.5667초, 최대 4.30초 | **실패** |
| 실제 국가 공개 사건 E006 | 6.65초, S002, 뉴욕 위치가 카메라 밖 | **실패 원인** |
| 전체 최종 QC | `ACTUAL_RENDER_RETENTION_GATE_FAILED` | **FAIL**, 완료 처리 안 함 |

원인은 대서양을 추적하는 카메라에서 6.65초에 뉴욕/미국 공개 이벤트가 실제 화면에 보이지 않은 것입니다. E006 누락으로 4.30초의 의미 사건 공백과 다음 사건의 인과 참조 실패가 함께 발생했습니다. 파일·대본·계획 단계 합격이 실제 사건 가시성을 보장하지 않는 결함을 최종 QC가 탐지했습니다.

교정은 보이지 않는 지리 공개를 같은 실제 항로의 진행률에서 계산한 남은 거리 정보로 바꾸고, 사건 ID/시각/인과 연결을 유지하는 방식입니다. 표시 가능한 지리·항로·이동체 primitive를 순수 Three.js의 실제 카메라·가림·안전영역으로 사전 인증하고 저장/승인/렌더 검수에서 다시 검사하는 게이트를 추가합니다. 저장된 `passed` 값을 강제로 넣어도 현재 인증 실패를 우회할 수 없어야 합니다. 교정 코드/단위 기하 검사와 **교정 영상의 실제 재렌더/QC**를 분리해 기록합니다.

## 교정 v002 — 실제 부분 재렌더와 QC 통과

같은 프로젝트의 `v002`는 S002의 E006만 출처 있는 남은 거리 정보로 교정했습니다. [v002 project_result.json](projects/project_b89a30908047/versions/v002/renders/project_result.json)에는 **S002 신규 렌더 1개, S001/S003/S004/S005 캐시 재사용 4개**와 실제 결과 SHA를 기록합니다. 전체 20초를 처음부터 다시 렌더한 실행이 아닙니다. 이전 v001은 삭제·덮어쓰지 않았습니다.

| 실제 v002 검사 | 결과 |
|---|---|
| 최종 파일 | 1080×1920, 9:16, 30fps, H.264, 20.000초 |
| 전체 인코딩 프레임 | 600개 실제 디코딩/QC |
| black/duplicate/near freeze | 0 / 0 / 0.000초 |
| 최종 자동 QC | **PASS**, publication_quality=true |
| 실제 의미 사건 | **14/14 표시**, 평균 1.4462초, 최대 공백 2.40초 |
| 첫 3초 사건 | 4개, camera-only는 사건으로 계산하지 않음 |
| 교정 E006 | 실제 6.70초부터 정보 표시, 38프레임/1.2667초 유지 |
| 오디오 | -18.0 LUFS, -2.5 dBTP; 직접 청취 아님 |

실제 [v002 QC 보고서](projects/project_b89a30908047/versions/v002/qc/qc_report.json)와 [contact sheet](projects/project_b89a30908047/versions/v002/qc/contact_sheet.png)를 보존했습니다. 실제 결과 파일은 [final.mp4](projects/project_b89a30908047/versions/v002/final/final.mp4), [final_muted.mp4](projects/project_b89a30908047/versions/v002/final/final_muted.mp4)이며 첨부 전송/전체 재생 근거는 아래 브라우저 섹션에 있습니다. 이 내부 파일 위치를 공개 휴대폰 다운로드 URL로 제시하지 않습니다.

주요 프레임은 [actual20_v002_manual_visual_review_r01.json](docs/evidence/actual20_v002_manual_visual_review_r01.json)에 직접 검토 기록이 있습니다. 교정 거리 문구, 3D 지구·구름·도시 불빛·대기·입체 항공기·가려지는 항로, 밝은 지리 설명, 마지막 세 도시 연결과 제목을 확인했습니다. 검토한 프레임에서는 누락/경로 깨짐/명백한 clipping을 발견하지 않았습니다. 검토자의 판단은 V3 렌더 수준을 유지한 사용 가능한 다큐멘터리 시뮬레이션이며 객관적인 시청 유지 예측은 아닙니다. **HERO 기체가 상면에 가까워 기존 V3 quarter-front pose보다 지표와 덜 극적으로 분리되는 약점**은 남겨 두었습니다. 원래 밤 스타일보다 주간 지리 장면이 밝고, 도시 실사 근접/I2V 영상은 이 시험에 없습니다.

## 자연어 수정 v003 — 해당 Scene만 실제 재렌더

사용자 수정 요청 **“Scene 2 카메라를 조금 더 빠르게”**를 승인해 `v003`을 생성했습니다. [natural_partial_rerender_actual20_v003_r01.json](docs/evidence/natural_partial_rerender_actual20_v003_r01.json)은 **S002 새 렌더 1개/나머지 캐시 4개**, 이전 결과 보존, 미수정 S001/S003/S004/S005의 인코딩 MP4 SHA가 v002와 완전히 동일하고 S002 SHA만 달라진 사실을 기록합니다. [v003 project_result.json](projects/project_b89a30908047/versions/v003/renders/project_result.json)에는 전체 600프레임 디코딩/QC **PASS**, 실제 의미 사건 14/14·평균 1.4462초·최대 2.4초·첫 3초 4개를 기록합니다. 최종 파일은 1080×1920/30fps/H.264/20초입니다. 실제 브라우저 전체 재생·13개 첨부 SHA 확인도 아래에 기록합니다. TTS와 자막은 이 버전에서 OFF입니다.

## TTS/자막 ON인 새 20초 시험 — 실패 보존과 교정 진행

첫 ON 시험 `project_0e34af2d35a4/v001`은 실제 S003 음성의 길이가 Scene 예산을 넘어 `NARRATION_EXCEEDS_SCENE`으로 **그래픽 렌더 전에 안전하게 차단**됐습니다. [VOICE_DURATION_AUDIT.json](docs/evidence/aviation20_voice_duration_audit_20261004T175738Z/VOICE_DURATION_AUDIT.json)은 모든 5개 한국어 WAV를 실제로 측정해 S003 **3.9888125초**, S005 **3.9673542초**가 허용 3.92초를 넘는 것을 확인합니다. 실패 계획·음성·상태를 보존했고 발화 속도나 Scene 길이를 임의 늘리지 않았습니다.

4초 이하 짧은 Scene의 해당 두 기본 대사만 간결하게 교정했습니다. 실제 offline voice 예산 검사 3개는 20초 항공/가상 연결의 5개 Scene과 6개 짧은 Scene을 측정하고 변경 전후 GIS·카메라·항로·사건·claim이 동일하며 긴 Scene 문구는 유지되는지 확인합니다. 새 실제 계획은 [project_21a865e0dc8d/v001](projects/project_21a865e0dc8d/versions/v001/scene_plan.json), TTS/자막/BGM 모두 ON입니다. [브라우저 기획 보고서](validation/final_A20_tts_planning_r03/UI_END_TO_END_REPORT.json)는 3.471초 기획과 승인 전 렌더 0을 기록합니다. 승인된 job `job_4f9991fe994c`는 진행 중이며, 나레이션이 달라진 S003/S005 두 Scene 신규 렌더와 나머지 세 Scene 캐시를 예상합니다. **실제 완료·최종 QC·TTS/자막 포함 MP4 다운로드는 아직 주장하지 않습니다.**

## 실제 CPU 시간과 환경

[cpu_runtime_hardware_r01.json](docs/evidence/cpu_runtime_hardware_r01.json)은 논리/affinity CPU 5개, cgroup `400000 100000`으로 **CPU quota 4코어 상당**, 메모리 제한 32 GiB, NVIDIA 실행 파일/장치 없음, CPU_LOCAL/Chromium SwiftShader를 기록합니다. 실제 GPU 렌더나 GPU 비용 측정은 없습니다.

아래는 첫 v001의 실제 실행 측정이며 **QC 실패한 실행 시간**입니다. 캐시 Scene 0개, 새로 렌더한 Scene 5개였습니다.

| 측정 | 실제 시간 |
|---|---:|
| Scene 렌더 합계 | 8,491.015683초 |
| 오디오 준비 | 3.573649초 |
| 결합·오디오 mux·자막 단계 | 2.283334초 |
| 자동 QC | 14.969875초 |
| 실행 총 시간 | 8,513.319232초, 약 141.889분 |

기획/UI 시간은 이 렌더 총 시간에 포함시키지 않았습니다. 독립적인 작업 시작부터 종료까지의 wall time, 세션 중단/재개 누적 시간과 부분 교정 실행은 별도로 측정해야 합니다. [production_transport_interruption_r01.json](docs/evidence/production_transport_interruption_r01.json)은 도구 연결 복구 후 같은 background job이 계속 진행됐다는 증거이며 서버 프로세스 크래시 복구 시험은 아닙니다.

v002의 아래 시간은 **현재 교정 실행만의 실제 측정**입니다. 4개 캐시 Scene의 이전 렌더 시간은 다시 더하지 않았습니다.

| v002 부분 교정 측정 | 실제 시간 |
|---|---:|
| S002 신규 Scene 렌더 | 1,634.626000초 |
| 재사용 Scene | 4개, 현재 신규 렌더 시간 0초 |
| 오디오 준비 | 1.928998초 |
| 결합·오디오 mux·자막 단계 | 2.458342초 |
| 자동 QC | 16.411102초 |
| 교정 실행 총 시간 | **1,656.629831초, 약 27.610분** |

27.610분을 캐시 없는 새 20초 영상 전체의 렌더 시간으로 표시하지 않습니다. 첫 실패 실행 8,513.319232초까지 포함한 두 pipeline 측정의 산술 합계는 10,169.949062초(약 169.499분)이며, 기획·대기·세션 공백까지 포함한 독립 wall time 측정은 아닙니다. 비용이라고 표현한 것은 CPU 실행 시간이며 실제 청구 금액을 계산하거나 측정한 것이 아닙니다.

| v003 자연어 속도 수정 측정 | 실제 시간 |
|---|---:|
| S002 신규 Scene 렌더 | 1,687.772212초 |
| 재사용 Scene | 4개, 이전 인코딩 SHA 동일 |
| 오디오 준비 | 1.926333초 |
| 결합·오디오 mux 단계 | 2.205478초 |
| 자동 QC | 14.450082초 |
| 현재 실행 총 시간 | **1,707.246737초, 약 28.454분** |

v003 시간도 현재 1개 신규 Scene/4개 캐시 실행만의 실측이며 새 20초 전체 렌더·75초 영상·청구 금액으로 바꾸어 해석하지 않습니다. TTS/자막 ON인 새 A20 시험의 완료 시간은 아직 대기입니다.

75초 HIGH의 15~40분 목표는 아직 검증하지 못했습니다. 위 20초 시간을 75초로 확대 계산한 값을 실측으로 제공하지 않습니다. 실제 75초 실행이 끝나면 새 렌더/재사용 Scene, 오디오·QC·전체 시간을 별도 추가합니다. CINEMA는 위 실제 두 프레임/104.468초의 근거가 있으며 전체 영상 렌더 시간은 아직 없습니다.

## 모바일·다운로드·환경 게시

초기 320/375/430px UI 검사는 가로 넘침·JS 오류 없음, 전체 gate 실패 시 렌더 승인 차단과 Scene Plan 첨부 바이트/hash 일치를 확인했습니다. [world-ui-test-results.json](docs/evidence/world-ui-test-results.json), [world-ui-contract-results.json](docs/evidence/world-ui-contract-results.json)에 보존되어 있습니다.

완료 v002의 실제 375×812 브라우저 검사는 [UI_END_TO_END_REPORT.json](validation/production_NY20_v002_playback_download_r01/UI_END_TO_END_REPORT.json)에 **PASS**를 기록합니다. 최종/무음 MP4·보고서·contact sheet·계획·대본·5개 Scene을 포함한 **13개 파일을 실제 브라우저 attachment로 다운로드**했고 모두 HTTP와 저장 파일 SHA가 일치했습니다. 최종 MP4는 26,913,103 bytes, SHA `86708c1c0f68e74db8570ad2e42910d8b89d6310b4b78c8e429964a4306b4d00`; 무음은 26,193,149 bytes, SHA `daab3edd9317b6b7d46489ea9cc0ae19af965986a4ad2d86b3dc0d7ef96d90db`입니다. MP4 Range 요청은 HTTP 206/정확한 1,024 bytes를 반환했습니다.

[full_playback.json](validation/production_NY20_v002_playback_download_r01/full_playback.json)은 실제 영상이 끝까지 재생되어 ended=true/current_time=20.0초, 브라우저 디코딩 600프레임·dropped/corrupted 0·presentation stall 없음·재생 오류 없음을 기록합니다. 실제 재생 경과는 20.0725초였습니다. WebAudio 샘플 디코딩도 확인했으나 인간의 직접 청취나 물리 스피커 출력을 주장하지 않습니다. 접속은 테스트 host의 localhost이며 **실제 휴대폰 하드웨어/공개 인터넷 호스팅 검증은 아직 아님**을 분리합니다.

v003 [UI_END_TO_END_REPORT.json](validation/production_NY20_v003_playback_download_r01/UI_END_TO_END_REPORT.json)도 **PASS**입니다. 375×812 실제 Chromium 브라우저에서 같은 13개 파일을 native attachment로 다운로드했고 HTTP/저장 SHA가 모두 일치했습니다. 최종은 **26,931,116 bytes**, SHA `37a80234e229bb514996f3f784c2ee4914a9dc5fb1edbcc12b515952e939db37`; 무음은 **26,211,174 bytes**, SHA `7a1a7ff859f171a4adab7b3d05a4a2dc8ca622f593a305a579784ff5ef359e71`입니다. Range 206/1,024 bytes, 20초 끝까지 ended=true, 600개 decoded/presented frames, dropped/corrupted/stall/JS 오류 0, 경과 20.2874초를 기록했습니다. 직접 청취·실제 휴대폰 하드웨어·공개 접속은 이 검사에도 포함하지 않았습니다.

앱의 HTTP 첨부 다운로드와 QC 통과 버전 ZIP 내보내기 구조는 구현되어 있습니다. ZIP은 실제 최종 QC/승인/SHA를 통과한 버전만 받아들이며 기존 파일을 덮어쓰지 않습니다. 사용법은 [BENCHMARK_EXPORT_GUIDE.md](docs/BENCHMARK_EXPORT_GUIDE.md)에 있습니다. GitHub 공식 제한 확인은 [github_file_limits_r01.json](docs/evidence/github_file_limits_r01.json)에 보존했습니다. 일반 Git 제한 100 MiB, 경고 50 MiB, 브라우저 업로드 25 MiB이며 90 MiB 이하 분할과 전체 SHA 검증을 지원합니다. LFS 계정 할당량과 최종 GitHub 반영·브라우저 다운로드는 별도 확인 대상입니다.

현재 클라우드 환경의 재사용 설정 초안은 게시되지 않았으며 공개 앱 URL도 확인되지 않았습니다. 공용 HTTPS 호스팅/허용된 포트 전달·접근 방식이 준비된 뒤 실제 휴대폰에서 접속·기획 승인·상태 재개·MP4 다운로드를 검증해야 합니다. 내부 `/workspace` 경로 또는 localhost 링크만으로 외부 다운로드 완료를 선언하지 않습니다.

## 지원 범위와 남은 약점

- 현재 기획기는 검증된 장소 카탈로그와 지원 도메인 패턴을 사용하는 제한된 오프라인 방식입니다. 모든 질문의 자동 인터넷 조사나 물류·경제·기상 예측기는 아닙니다.
- 해상 우회는 검증된 로테르담–싱가포르 수에즈/희망봉 그래프를 사용합니다. 선박은 수면 부근 경로를 따르고, 발광 선은 동일 경위도에서 약 3km 표시 오버레이로 분리합니다. 확대된 선박/항공기 크기는 지도 시각 프록시이며 실제 크기·항해 고도 예측이 아닙니다.
- 육상 운송 그래프, 역사 GIS, Time/Geography Morph, 전쟁 VFX, 실제 기상/재난 시뮬레이션 등은 미설치 플러그인 요구로 차단합니다. 현대 항공 경로로 억지 대체하지 않습니다.
- 밝기 임계/기하/프레임 QC는 전문적인 영상미, 실제 관객 유지율이나 인간 청취를 직접 인증하지 않습니다. v002의 실제 주요 프레임 검토는 기록되어 있으나 HERO pose의 상대적 약점과 외부 I2V/도시 근접 표현 부재는 남습니다.
- 첫 국가 공개 가시성 결함은 v002의 실제 부분 재렌더·최종 QC·전체 브라우저 재생으로 교정됐습니다. CPU가 느리고 75초 HIGH의 실제 전체 시간을 아직 측정하지 못했습니다.
- v003 자연어 속도 수정은 실제 부분 렌더/QC/전체 브라우저 재생·다운로드를 통과했습니다. 성공한 v002/v003은 TTS/자막 OFF이며 ON인 새 A20은 렌더 중입니다. 전체 130개 회귀 검사는 통과했으며 75초 전체 영상·공개 휴대폰 사용과 GitHub 최종 전달은 대기입니다.

## 최종 완료 전에 채울 근거

1. 진행 중 새 A20 TTS/자막 ON 시험의 실제 Scene 재렌더/재사용 목록·시간·최종 QC·전체 재생·다운로드. 이미 통과한 v002/v003 OFF 버전과 구분합니다.
2. V3 비교에서 남은 HERO pose 약점과 주간 지리 장면의 균형, 최종 제출 버전의 실제 프레임/전체 재생 검토.
3. 실제 75초 HIGH Scene/오디오/자막/QC/총 시간과 성공한 MP4.
4. 기록된 130/130 합격의 소스 SHA와 최종 전달 소스가 일치하는지 확인. 이후 구현을 변경하면 해당 변경의 필요한 회귀 근거를 추가합니다.
5. 최종 보존 재검사·환경 설정 게시·저장소 반영과 정확한 다운로드 주소.
6. 공개 접속 경로와 실제 휴대폰의 생성·상태 복구·최종 MP4 다운로드 검증, 직접 청취의 실행 여부.

이 근거가 없거나 자동 QC·영상미 기준이 실패하면 최종 완료로 표시하지 않습니다.
