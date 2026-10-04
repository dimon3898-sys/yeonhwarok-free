# 검증 범위

`tests/test_core.py`, `tests/test_advanced_edits.py`, `tests/test_audio_language.py`, `tests/test_revision_geometry.py`, `tests/test_planner_semantics.py`, `tests/test_subtitle_layout.py`는 실제 기획·GIS·승인·수정·오디오 모듈과 부분 수정의 3D 기하를 실행하는 동작 회귀 검사입니다. `tests/test_semantic_visibility.py`, `tests/test_visibility_gate.py`, `tests/test_semantic_planning.py`는 실제 생산 E006 실패, 현재 가시성에 대한 승인 검수, 범위가 제한된 수정과 정보 노출을 검사합니다. 후속 `tests/test_narration_bindings.py`, `tests/test_render_estimation.py`, `tests/test_retimed_route_metrics.py`는 처음 각각 9·15·3개의 계약 검사를 추가했습니다. 현재 나레이션 planned-route 검사 4개, `tests/test_geographic_claim_bindings.py` 4개와 `tests/test_short_narration_budget.py` 3개까지 포함한 **130개 전체 회귀**를 검사합니다. 기존 MASTER 영상은 재렌더하지 않으며 실제 영상 통합 테스트와 구분합니다.

갱신 전 이 문서와 품질 보고서의 원본 바이트는 [quality_docs_before_130_update/SNAPSHOT_MANIFEST.json](evidence/quality_docs_before_130_update_20261004T181126076353Z/SNAPSHOT_MANIFEST.json)에 새 배타적 파일로 보존했습니다.

기획 테스트는 서로 다른 세 주제를 사용합니다.

| 테스트 | 입력 | 길이 | 검사 |
|---|---|---|---|
| A | 런던→파리→로마 민간 항공 여행 | 20초 | 고정 V3 도시 이탈, 실제 GIS, 사건·카메라·경계 |
| B | 수에즈 운하 7일 폐쇄 가정 | 75초 | 출처 있는 해상 그래프, 우회, 가정/시뮬레이션, 두 Peak |
| C | 서울–싱가포르 가상 직접 연결 | 40초 | 실제 위치와 가상 관계 분리, 훅·변수·Peak·결말 |

음성보다 긴 대본, camera-only 이벤트, 3초 초과 의미 사건 공백, 과도한 동일 사건 반복, Peak 누락, 끊어진 인과관계, 위조 GIS 좌표/출처, FACT 무출처, SIMULATION 무가정, 불가능한 카메라 높이와 어두운 지리 설명을 의도적으로 넣고 게이트가 실패하는지 검사합니다. 판게아·전쟁·육상 경로는 현재 미설치 요구를 반환하는지 확인합니다.

승인·수정 테스트는 임시 프로젝트에 실제 계획을 저장합니다. 정확한 plan hash 승인, 승인 후 변경 차단, 수정 Diff의 범위, 앞뒤 경계 상태·미수정 Scene 보존, 오래된 Diff 승인 거부, 이전 파일 불변, 서버 재시작 상태 복구를 검사합니다. 원본 V3 자산과 GIS 원본 파일은 실제 SHA와 라이선스를 확인합니다. 캐시 키는 수정한 Scene, 자산·렌더러·품질의 변경만 감지하는지 검사합니다. GPU 계약은 승인/비용 제한 전에 worker가 생성되지 않고 provider 실행 실패 후에도 자신의 worker가 종료되는지 검증합니다. 이 GPU 검사는 가짜 provider를 사용하는 계약 테스트이며 실제 GPU 렌더나 실제 비용 측정이 아닙니다.

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

구조 수정 검사는 실제 Scene 삭제, 남은 ID 보존, 삭제 구간의 정확한 경계·항로 상태 연결, 후속 Scene의 원래 렌더 시계 보존, 살아남은 실제 원인 참조 복구를 확인합니다. 결론 지연은 사건·사운드·나레이션·네트워크를 실제로 후반에 옮기는지와 빈 자리에 출처 있는 지리 정보만 사용하는지를 검사합니다. 훅/결말 삭제, 모든 Scene 삭제, 마지막 Scene의 결론 지연 등 불가능한 수정이 차단되는지도 확인합니다. 임의 길이는 30fps의 정수 프레임 경계로 조립되고 Scene별 반올림이 전체 길이 오류로 누적되지 않는지 검사합니다.

물리 사건 연결 검사는 생성된 계획의 항로 시작 사건이 실제 경로 시작 시간과 일치하는지, 항공기 출발을 실제 이동체 등장 시간에만 계산하는지, 도착을 실제 경로의 종료/진행률 1에서 계산하는지 확인합니다. 국가 위치 비교 계획에는 항공기나 출발 사건이 생기지 않아야 합니다. 장식적인 제목이나 나중의 이동체 재표시를 새로운 출발 사건으로 계산하지 않습니다.

초기 구조 회귀 스냅샷은 48개 검사를 통과했습니다. 그 시점의 전체 로그와 소스 SHA는 [core_advanced_tests_r01.json](evidence/core_advanced_tests_r01.json) 및 [core_advanced_tests_r01.log](evidence/core_advanced_tests_r01.log)에 보존되어 있습니다. 해당 unittest 측정은 8.337초이며 영상 렌더 시간이 아닙니다. 이후 기획·프레임·카메라 검사와 Scene별 TTS 언어 선택 검사를 포함한 57개가 통과했습니다. 당시 전체 로그와 소스 SHA는 [core_advanced_audio_tests_r02.json](evidence/core_advanced_audio_tests_r02.json) 및 [core_advanced_audio_tests_r02.log](evidence/core_advanced_audio_tests_r02.log)에 보존되어 있으며 실제 unittest 측정은 10.367초입니다. 오디오 언어 검사는 짧은 PCM을 출력하는 녹음 어댑터로 한국어/영어 추론, 명시적 언어 우선권, 측정 cue 배치를 확인하며 실제 음성 품질 검사는 아닙니다. 최종 실행/영상 검증 근거는 `QUALITY_REPORT_FINAL.md`와 각 프로젝트 QC 기록에서 별도로 확인합니다. 초기 스냅샷을 최신 소스의 동일 실행으로 주장하지 않습니다.

69개 통합 회귀 스냅샷은 **통과, unittest 측정 34.722초**입니다. [TEST_REPORT.json](evidence/core_revision_semantics_20261004T151631Z/TEST_REPORT.json)과 [unittest.log](evidence/core_revision_semantics_20261004T151631Z/unittest.log)에 실제 실행 시간, 실행 전후 전체 엔진·검사·셰이더 SHA와 기존 A20/B75 계획의 SHA를 보존했습니다. 실행 도중 소스 변경 0, 기존 두 생산 계획 변경 0을 확인했습니다. 앞선 48·57개 증거와 날짜 표현 검사를 확장하기 전의 69개 스냅샷도 보존합니다. 이 시간은 영상 렌더 벤치마크가 아닙니다.

자막 검사 추가 시점의 전체 실행은 **78/78 통과, unittest 측정 39.283초**입니다. [subtitle_layout/EVIDENCE_REPORT.json](evidence/subtitle_layout_20261004T160655Z/EVIDENCE_REPORT.json)과 [unittest.log](evidence/subtitle_layout_20261004T160655Z/unittest.log)에 프로세스 wall 41.147초와 해당 소스 SHA를 보존합니다. 추가 자막 9개 검사는 번들 Noto 44px의 실제 폭·글자 간격·outline, 단어/긴 단어 wrapping, ASS 시각, 활성 자막/라벨 겹침·누락 기하 경고와 unsafe layout 차단을 검사합니다. 실제 기존 shipping75 나레이션 cue에서 만든 ASS/layout의 최대 줄 너비 660.28px는 795px 안전 너비 안입니다. 인코딩 자막 글리프 인식이나 생산 장면과 겹침이 없음을 증명하는 검사는 아닙니다.

의미 사건의 실제 가시성 검사까지 연결한 통합 회귀 스냅샷은 **92/92 통과, unittest 측정 256.541초**입니다. [TEST_REPORT.json](evidence/semantic_gate_regression_20261004T164822Z/TEST_REPORT.json)과 [unittest.log](evidence/semantic_gate_regression_20261004T164822Z/unittest.log)에 해당 실행의 실제 시간과 SHA를 기록했습니다. 기록된 소스와 기존 A20/B75v001 계획 변경은 0입니다. 이 스냅샷은 후속 나레이션 이벤트 참조 검수 추가 전이며 최종 검증은 그 후의 전체 실행 기록 및 `QUALITY_REPORT_FINAL.md`에서 확인합니다.

후속 27개를 포함한 첫 전체 **119개 실행은 실패 3개, 132.913초**였습니다. [실패 TEST_REPORT.json](evidence/final_core_tests_20261004T171115Z/TEST_REPORT.json)과 [로그](evidence/final_core_tests_20261004T171115Z/unittest.log)를 보존합니다. 성공 실측이 새로 연결된 이후 설치 폰트가 지원하지 않는 화살표 문구로 의미 사건 게이트가 차단되는 결함이 확인되어 ASCII 정보 문구로 교정했습니다. 관련 교정 6개 합격 후 전체를 재실행한 결과는 **119/119 PASS**, unittest 측정 **271.545초**, 프로세스 wall **275.559833초**입니다. [최종 TEST_REPORT.json](evidence/final_core_tests_20261004T171928Z/TEST_REPORT.json)과 [unittest.log](evidence/final_core_tests_20261004T171928Z/unittest.log)에 실행 전후 스키마·엔진·테스트·서버·셰이더·UI SHA를 보존했으며 검사 중 소스 변경은 0입니다. 이 합격은 해당 SHA의 동작 회귀 검사로, 실제 렌더·유료 GPU·관객 유지율·실제 휴대폰·단어별 ASR 검증을 대신하지 않습니다. 이전 실패나 부분 검사 결과를 최신 전체 합격으로 바꿔 기록하지 않습니다.

현재의 권위 있는 전체 실행은 **130/130 PASS**, unittest 측정 **131.933초**, 프로세스 wall **133.182935초**입니다. [최신 TEST_REPORT.json](evidence/final_core_tests_20261004T180346Z/TEST_REPORT.json)과 [unittest.log](evidence/final_core_tests_20261004T180346Z/unittest.log)에 해당 실행의 소스 SHA·로그 SHA와 `source_changes=[]`를 기록했습니다. 이전 119개 실패/합격 및 92개 스냅샷을 보존하며 더 적은 실행 시간을 영상 렌더 속도 개선으로 해석하지 않습니다.

지리 FACT 연결 4개는 E004/E024의 싱가포르 대상과 수에즈 FACT가 같은 source_id를 쓰더라도 잘못 섞이지 않는지, 명시적인 `metadata.coordinate_claim_targets`와 좌표/설명/claim이 일치하는지 검사합니다. 잘못된 장소·누락/미등록 typed binding은 GL 가시성 계산 전에 차단합니다. 추가 나레이션 4개는 현재 Scene에 아직 활성화되지 않은 후속 항로의 비교 정보가 검증된 전체 계획의 출발/도착 좌표를 참조할 수 있는지 확인합니다. 같은 route ID가 다른 지리를 가리키면 차단하며 이를 현재 Scene의 실제 출발·도착·네트워크 활동이라고 주장하지 않습니다.

실제 발화 예산 3개는 무료 오프라인 한국어 eSpeak를 실행합니다. 20초 항공/가상 연결의 5개 Scene, 20초를 나눈 6개 짧은 Scene의 WAV 시간이 실제 Scene 예산을 넘지 않는지 확인합니다. 짧은 Scene의 S003/S005 두 기본 문구만 바뀌고 GIS·카메라·항로·사건·claim과 7.5초 이상의 문구는 유지되는지도 검사합니다. 이것은 실제 음성 합성/길이 검사이며 인간의 청취·단어별 ASR·새 MP4/자막 영상 완성 증거가 아닙니다.

나레이션 사건 참조 검사는 존재/같은 Scene/claim 관계와 외부 cue 구간을 검사하고 TTS OFF를 측정 음성 동기화로 표시하지 않습니다. 실제 단어별 ASR/발화 anchor를 구현했다는 의미가 아닙니다. CPU 예측은 합성 임시 기록으로 성공 QC/승인/현재 renderer/native provenance·frames·Scene 시간의 자격, 실제 native elapsedSeconds와 cache-hit 0초 구분, video SHA 중복 제거, 동일 quality/시간 샘플/조명 bucket·명시적 fallback, 불명확한 품질/clip/CINEMA 배수 거절을 검사합니다. 반환은 항상 `measured=false`, `scope=uncached_scene_render_only`이며 총 audio/QC/캐시 재사용 시간을 예측하지 않습니다. 재타이밍 검사는 정보 hold나 Peak 시각 변경 뒤 실제 Scene-local 경로 진행률에 맞는 숫자가 다시 계산되고 실제 물리/총거리 이벤트를 바꾸지 않는지 검사합니다. 이 검사는 실제 새 MP4 렌더가 아닙니다.

가시성 검사 8개는 실제 뉴욕→런던→두바이 S002의 6.65초 E006이 화면 밖이라는 순수 Three.js 기하, 출처 있는 남은 거리 정보 교정, 물리 항로 사건의 자막-only 통과 차단, 인증 캐시 분리, 런타임 누락 실패 및 외부 clip의 전용 검수 위임을 확인합니다. 승인 게이트 3개는 저장된 passed 결과로 현재 인증 실패를 우회할 수 없는지, 잘못된 좌표가 renderer 사전 검사에 들어가지 않는지, 정규화된 저장 입력/정확한 승인에서 인증을 다시 실행하는지 검사합니다. 기획 의미 수정 3개는 E006을 같은 시간·원인·출처 있는 경로의 남은 거리1,568km로 수정할 때 S002의 시각 사건과 효과음만 바뀌는지 확인합니다. 다른4Scene, 카메라·경로·이동체·경계, 이전v001 파일은 보존되며 수정 승인으로v002가 생성됩니다. 수에즈의 실제 차단·도착 및 결말 노출, 독립 Scene 끝의 읽을 시간도 검사합니다.

사전 검사는 보존된 실제 Three.js 카메라·지구 가림·항로·이동체·효과·정보 레이어와 설치된 폰트의 글리프 폭을 매30fps 시점에서 계산합니다. 선언된 이벤트, camera-only나 제목만 있는 물리 이벤트는 인정하지 않습니다. 실제600프레임 A20v001 감사에서 누락된 E006을 같은 검사로 찾았고 나머지13개의 최초 표시 시각은 기존 실제 감사와 정확히 일치했습니다. [기존 실제 감사와의 비교](evidence/semantic_gate_regression_20261004T164822Z/visibility_forensics/semantic_forecast_vs_actual_A20_r01.json)는 새 영상 렌더가 아닙니다. 셰이더 밝기·텍스처·래스터화·영상미는 해당 계산으로 검증하지 않으며 최종 실제 QC가 계속 필요합니다.

물리 출발과 도착은 정보 문구로 바꾸지 않고 실제 좌표를 보여줍니다. 수에즈 차단·도착은 제한된 카메라 상승과 공유 경계 상태를 다시 검사하고20% 속도 수정 범위도 확인합니다. 보이지 않는 비필수 지리 강조에는 실제 진행률의 새로운 거리 정보를 표시하며, 독립 Scene 끝의 정보나 앞 자막에 가린 결말은 동기화된 시간 보정으로 읽을 구간을 확보합니다. 기존 onset·최소 노출·Retention 기준을 낮추지 않습니다. 국가 비교는 검증된 국가 초점에 카메라를 연결합니다. 수정 전 실패 자료와 교정 제안은 [visibility_forensics](evidence/semantic_gate_regression_20261004T164822Z/visibility_forensics)에 보존했습니다.

내보내기 도구의 별도 합성 fixture 검사는 **10/10 통과, 0.106초**입니다. [deliverable_tools_unit_r01.json](../tools/evidence/deliverable_tools_unit_r01.json)에 원본/기존 ZIP 보존, 실제 recovery 경로 선택, 승인/QC/해시·Scene 완전성, 캐시 시간/미완료 분리, 조각/전체 SHA, GitHub 100/25MiB 및 90MiB 분할 경계를 기록합니다. 이 도구 검사는 위 전체 코어 unittest 수와 별도이며 fixture MP4 바이트는 실제 영상이 아닙니다.

최신 부분 수정 검사는 32~38초의 선박 추가가 완료된 수에즈 참조 경로 대신 실제 움직이는 희망봉 경로를 선택하는지, 두 모델이 서로 구분되고 앞뒤 Scene에서 ID를 유지하는지 확인합니다. 실제 출발 전인 32·34초에는 보이지 않고 36·38초에는 두 모델이 프레임 안에서 분리됩니다. 승인 제안은 최초 등장 34.7초를 명시합니다. 추가 항로는 카메라에서 실제 보이는 `network_expand` 사건과 동기화된 사운드로 표현하며, 보일 수 없는 대서양 Scene 추가는 승인 전에 차단합니다. [교정된 기하 증거](evidence/core_revision_semantics_20261004T151631Z/revision_geometry_corrected)와 [기존 실패 증거](evidence/core_revision_semantics_20261004T151631Z/revision_geometry_prior_failures)를 각각 원본 SHA와 함께 복사해 보존했습니다. 이 검사와 증거는 canvas-free Three.js 계산이며 GL 이미지·대기·텍스처·최종 영상미를 검증하지 않습니다.

기획 의미 회귀는 최근 과거 연도와 현재 연도의 지난 날짜를 현대 지도에 대입하지 않는지 확인합니다. ISO·슬래시·한국어 연월일·영문 월 이름 날짜가 검사 대상이며, 현재 지도·날짜만 있는 현대 항공 주제·항공편 번호·75초 같은 길이 표현은 구분합니다. 역사 GIS 알고리즘을 추가한 것은 아닙니다. 해상 대사는 실제 차단 사건과 진행 단계에 맞춰 가정·우회·출처 있는 거리 차이·싱가포르 접근·예측 범위 제한을 공개하며 구현 용어와 연속 반복을 제거합니다. 서로 다른 20~183.5초 길이의 보수적인 발화 예산도 검사합니다. 상세 범위는 [PLANNER_SEMANTICS_NOTES.md](PLANNER_SEMANTICS_NOTES.md)에 기록합니다.

CINEMA 품질 계약의 별도 검사는 같은 V3 대기 셰이더에서 `--samples 2`를 전달하고 HIGH/FAST는 `--samples 1`과 기존 설정을 유지하는지 확인합니다. 같은 Scene·자산·렌더러라도 HIGH와 CINEMA의 캐시 키는 분리됩니다. [COMMAND_CACHE_REPORT.json](evidence/cinema_temporal_samples_20261004T140155Z/COMMAND_CACHE_REPORT.json)은 실제 `render_project`의 백엔드 경계에서 명령을 기록한 증거이며 Node/GL은 실행하지 않았습니다. 이를 CINEMA 영상 렌더 완료, 품질 비교, 실제 렌더 시간 측정으로 해석하지 않습니다. 이 검사는 위 57개 unittest 실행과 별도입니다.

후속 [ACTUAL_CINEMA_REPORT.json](evidence/cinema_two_temporal_samples_actual_20261004T174915Z/ACTUAL_CINEMA_REPORT.json)은 실제 GL에서 2160×3840 내부 해상도·temporalSceneSamples=2로 렌더한 **2개 프레임**, 1080×1920/30fps/H.264의 0.066667초 파일, **104.468초**를 기록합니다. source/asset/scene SHA와 두 감사 프레임을 보존합니다. 이 증거는 CINEMA 시간 샘플이 실제 통합된 것을 확인하며 전체 CINEMA MP4·전체 시간·V3 대비 영상미 향상을 인증하지 않습니다.

추가된 기획 검사는 실제 경로에서 도출한 대륙 간/해상 카메라 anchor, renderer와 같은 Scene-local smoothstep 거리, 마지막 전체 주 경로의 실제 9:16 framing, 스타일별 실제 조명/속도 변경을 검사합니다. 육상 운송과 역사 GIS가 현대 항공 영상으로 변환되지 않는지, 알 수 없는 스타일이 거절되는지도 확인합니다. 파생 카메라 좌표를 새 지명 좌표로 해석하지 않습니다.

`tools/bootstrap_runtime.py --offline`는 보존된 Ubuntu 패키지 5개의 실제 SHA와 라이선스 파일을 확인하고 격리된 eSpeak 한국어 런타임을 검증합니다. 기존 파일은 덮어쓰지 않고 실제 한국어 WAV를 stdout으로 합성해 동적 라이브러리·voice data의 동작을 확인합니다. 이 검증은 패키지 설치/합성 검증이며 직접 청취나 스튜디오 음성 품질을 의미하지 않습니다. Linux x86_64 이외의 플랫폼과 호환되지 않는 시스템 라이브러리는 지원 범위에서 구분합니다.

실제 격리 런타임은 기존 561개 파일 재사용·덮어쓰기 0, 한국어 시험 WAV 110,782 bytes로 검증했습니다. 임시 디렉터리에서 기존 설치 파일 충돌·손상된 패키지 해시·오프라인 패키지 누락이 기존 자료를 보존하며 실패하는지도 확인했습니다. 근거는 [bootstrap_runtime_offline_r01.json](evidence/bootstrap_runtime_offline_r01.json)입니다.

렌더 파이프라인의 기술 단위 근거는 [render_pipeline_unit_v001/README.md](evidence/render_pipeline_unit_v001/README.md)와 [UNIT_REPORT.json](evidence/render_pipeline_unit_v001/UNIT_REPORT.json)에 있습니다. 실제 FFmpeg 한국어 주석 실행·인코딩 픽셀 차이, 실제 오프라인 한국어 음성, 실제 20초 원본 합성음의 -18.0 LUFS/-2.5 dBTP를 기록합니다. 해당 테스트 패턴 MP4는 지구 영상이 아니며 V3와의 영상미 비교나 최종 공개용 결과로 사용하지 않습니다. 600프레임 rendered-retention fixture는 합성 감사 데이터로, 누락 사건·camera-only를 거절하는 검사 동작의 증거입니다. 실제 생산 렌더의 사건과 동일하다고 주장하지 않습니다.

## 실제 통합 검증과의 차이

이 테스트 합격만으로 제작 완료를 선언하지 않습니다. 실제 E2E 테스트는 자연어 입력, 승인, Scene별 MP4, 오디오·옵션, QC, 첨부 다운로드, 부분 Scene 재렌더를 실행하고 프로젝트의 `qc/`, `renders/project_result.json` 및 `QUALITY_REPORT_FINAL.md`에 기록합니다. 실제 20초/75초 렌더 시간과 캐시 재사용 시간을 구분합니다.

첫 실제 뉴욕→런던→두바이 20초 HIGH v001은 600프레임 H.264 MP4를 생성했지만 E006 미표시, 4.30초 의미 사건 공백과 그에 따른 인과 참조 실패로 최종 `ACTUAL_RENDER_RETENTION_GATE_FAILED`를 반환했습니다. 실패한 파일/보고서와 8,513.319232초의 초기 실행 비용은 보존하며 성공한 최종 영상으로 제출하지 않습니다.

교정 v002는 실제 S002 1개만 새로 렌더하고 4개 Scene을 캐시로 재사용해 최종 QC를 통과했습니다. [project_result.json](../projects/project_b89a30908047/versions/v002/renders/project_result.json)은 현재 실행만 1,656.629831초, 전체 600프레임 디코딩, 실제 14/14 사건·평균 1.4462초·최대 공백 2.40초·첫 3초 4사건을 기록합니다. 이 시간은 캐시 없는 새 20초 전체 렌더 시간으로 표시하지 않습니다. [실제 브라우저 보고서](../validation/production_NY20_v002_playback_download_r01/UI_END_TO_END_REPORT.json)는 13개 실제 첨부 다운로드의 HTTP/저장 SHA 일치, Range 206, ended=true/20초 전체 재생, 브라우저 600프레임 디코딩·dropped/corrupted 0을 확인합니다.

“Scene 2 카메라를 조금 더 빠르게” 자연어 수정 v003도 실제 완료했습니다. [부분 수정 근거](evidence/natural_partial_rerender_actual20_v003_r01.json)와 [project_result.json](../projects/project_b89a30908047/versions/v003/renders/project_result.json)은 S002 1개 새 렌더/4개 재사용, 미수정 MP4 네 개의 동일 SHA·S002 새 SHA, 이전 결과 보존과 **현재 실행 1,707.246737초**를 기록합니다. 전체 600프레임 QC PASS, 실제14/14 사건·평균1.4462초·최대2.4초·첫3초4개입니다. [v003 실제 브라우저](../validation/production_NY20_v003_playback_download_r01/UI_END_TO_END_REPORT.json)는 13개 native attachment SHA 일치·Range206·끝까지20초 재생·600프레임 decoded/presented·dropped/corrupted/stall 0을 기록합니다. v002/v003은 TTS와 자막 OFF이며 이 결과로 ON 파이프라인 전체 완성을 주장하지 않습니다.

첫 TTS/자막 ON A20 `project_0e34af2d35a4/v001`은 S003 `NARRATION_EXCEEDS_SCENE`으로 그래픽 전에 차단됐습니다. [실제 WAV 전체 감사](evidence/aviation20_voice_duration_audit_20261004T175738Z/VOICE_DURATION_AUDIT.json)는 S003 3.9888125초·S005 3.9673542초가 허용3.92초를 넘음을 기록합니다. 짧은 두 Scene 문구만 간결하게 고친 새 `project_21a865e0dc8d/v001`은 TTS/자막/BGM ON이며 승인된 job_4f9991fe994c가 렌더 중입니다. 두 변경 Scene 신규/세 Scene 캐시는 예상이며 최종 QC·실제 ON MP4 다운로드는 아직 대기입니다.

B75 기존 계획의 싱가포르↔수에즈 FACT 잘못된 연결은 [사전 감사](evidence/shipping75_pre_render_claim_audit_r01.json)에 보존했고 새 `project_594442ec2df9/v001`은 올바른 F03/설명·typed target binding을 사용합니다. [실제 브라우저 기획](../validation/final_B75_shipping_planning_r02/UI_END_TO_END_REPORT.json)은 23.797초/10Scene/승인 전 render0, 계획 자체는41사건/두Peak/오류·경고0입니다. 7일은 ASSUMPTION이고 6,460km는 두 공개 그래프의 구면 거리 차이로 실제 지연 예측이 아닙니다. [shipping75_4k_preflight](evidence/shipping75_4k_preflight_20261004T175751Z/S005.json)의 네 Scene에서6개4K still을 실제 렌더했지만 이는75초 전체 움직임/QC 증거가 아닙니다. [실제 audio/TTS/ASS 사전 검사](evidence/shipping75_audio_preflight_latest_20261004T174346Z/MEASURED_PREFLIGHT_REPORT.json)는 원래 B75 계획의10개한국어 음성이2.648396–5.366729초로7.42초 예산 안이며18.742555초실행, 실제75초48k stereo/-18LUFS/-2.5dBTP·ASS775.2px≤795를 기록합니다. 교정 B75의 나레이션 문자열은 보존 snapshot과 동일해도 전체 계획/FACT hash는 다르며 새 문맥 검수와 정확한 승인이 필요합니다. 이 사전 검사를75초 최종MP4·전체렌더벤치마크·사람청취·단어정렬·생산자막겹침 합격으로 표시하지 않습니다.

75초 HIGH 최종 MP4/전체 CPU 시간·실제 휴대폰/공개 호스팅·GitHub 최종 전달·직접 청취는 아직 검증하지 않았습니다.

브라우저의 375px 모바일 에뮬레이션과 실제 휴대폰의 외부 접속은 별도 검증입니다. localhost 테스트는 외부 모바일 접속 성공을 증명하지 않습니다. 자동 프레임/파형 검사도 인간의 직접 음성 청취나 전문 영상미 평가를 증명하지 않습니다. 미실행 검사는 성공으로 표시하지 않습니다.
