# 한국전쟁 20초 — 정식 생성 경로 감사

기준 저장소: dimon3898-sys/yeonhwarok-free. 원본 브랜치 `production/korean-war-20s-20261106` @ `ceee49fc512074e33179344663b02367c3e875d6`; 감사 대상 HEAD `d97cfb7834c6e5893b8c4bc39ab44ff427f5a319`. 이번 기록은 경로 교정 이후 읽기 전용 소스/증거 조사 결과다. 기존 PASS를 다시 실행하지 않았다.

## 결론

기존 엔진의 핵심 렌더러는 호출했지만, 중단한 작업은 정식 생성기의 전체 경로를 사용하지 않았다. 별도 프레임 선택/캐시 재사용/인코딩으로 만들어진 진단용 5초 영상 3개를 정식 출력으로 인정하지 않는다. Run42339382973은 cancelled로 종료했고, 20초 합성은 실행하지 않았다. GPU 실행0. 상세 보존 위치/해시는 CAPTURE_STOP_RECEIPT.json에 기록했다.

## 실제 중단한 경로

GitHub Actions → production/korean-war-20s-final-movie-v9/run_chunk_once.py → prepared 입력 재사용 → production/korean-war-20s-detail-v2/render_clip_cpu.mjs --frames → universal-presentation-v2/presentation_runtime.mjs 및 진단용 overlay → 별도 encode_chunk.py → 4×5초 계획. compose_sample.py는 실행하지 않았다.

이 경로는 새 렌더러를 전부 만든 것은 아니지만, Studio 제출·승인·worker·정식 capture·출력 영수증을 우회한다. 따라서 생성기 E2E PASS가 아니다. 기존 진단 PASS는 원래 범위에서만 보존한다.

## 소스에서 확인한 정식 경로

1. 기존 PART_01/02 전체 JSON을 `prompt` 객체에 그대로 넣는다. 요청 schema=`WORLD_ENGINE_NVIDIA_PRESENTATION_REQUEST_V1`, sceneId=`__timeline__`. 단일 scene 선택은5초만 선택하므로 이번10초 요청에 사용하지 않는다.
2. `production-studio-mvp-v1/server.py:326`: /api/preflight → /api/submissions → 별도 승인 후 /api/start. 실제 startup은 `studio-cold-start-v2/worker.py`에서 NvidiaPresentationController를 고정한다.
3. `codex-to-gcube-handoff-v1/controller/nvidia_controller.py:194`: 기존 source normalizer를 allow_ten_second_sample=True로 사용. `universal-presentation-v2/studio_adapter.py:77` → `presentation_prompt.mjs:257`의 analyzePresentationPrompt → `planner_scene_v1.mjs` compileScenePlan 및 `planner_engine_adapter_v1.mjs` compileExistingEnginePlan → native Scene JSON/renderRequests.
4. `studio_adapter.py:119`는 연속된300프레임 전체를 선택하고 runtime request를 구성한다. NVIDIA source preparation/admission 및 PLAN에 imageDigest, sourceClosure, runtime wire/hash를 결합한다. 단순 컴파일 PASS와 실제 배포 연결 PASS는 별개다.
5. `nvidia_backend.py:214` → `nvidia_worker.py:170` → `lease_supervisor.py:454` → `backend/capture_nvidia.mjs:85` → `capture_vulkan.generated.mjs` → `presentation_runtime_vulkan.generated.mjs`. 이 경로에서 실제 NVIDIA 검증/승인 및 캡처 영수증이 필요하다.
6. 정식 capture가0..299 전체 프레임을 렌더링하고 내부 FFmpeg로 VIDEO.mp4를 인코딩한다.300프레임/10초/1080×1920/30fps/전체 디코딩을 검사한 뒤 worker가 WORLD_ENGINE_STUDIO_VIDEO.mp4로 내보내고 작업을 COMPLETED로 기록한다. 선택 프레임 probe는 정식 MP4 완료로 인정하지 않는다.
7. 위 경로를10초 입력마다 사용해 두 개의 실제 출력과 영수증이 생긴 다음, 이미 존재하는 `universal-auto-video-v2/compose.py`와 기존 `detail-v2/evidence/local/COMPOSE_PLAN.json`을 사용한다. 기존 CLI는 `--plan --segments --destination`; 새 wrapper는 필요 없다. 출력은 WORLD_ENGINE_AUTO_VIDEO.mp4,600프레임/20초다. **소스상 합성 가능 경로이며, 이번 두 Studio 출력으로 실증한 결과는 아니다.**

경로 상대 위치의 기준은 `world-simulation-shorts-engine/recovery/`다. prompt 컴파일의 planner 모듈은 `world-simulation-shorts-engine/web/map_infographic_v1/`에 있다.

## 기존 검증과 현재 결과

- V2 CHECKPOINT의 source 준비,4개 source/geometry/admission 검사,4개 static 검사와 이전 V1 PASS는 그대로 보존한다. 여기서 재실행하지 않았다.
- 두 입력은 각10초/300프레임의 GENERAL 사건 지도다. 기존 분석의 scene 순서는 naktong→incheon, advance→seoul이다. 입력/분석/스토리보드/GeoJSON/NASA crop 포인터는 INPUT_REUSE_MANIFEST.json에 있다.
- 최신 우회 run: completed/cancelled. 중단용 run42342653711: success, cancel API202. 보존된 완성 진단 영상15초와 중간 프레임은 품질 참고 자료일 뿐 정식 생성기 출력이 아니다.
- 이번 한국전쟁 정식 Studio 제출→실행→MP4 완료 증거:0개. 최종20초 MP4:없음. 레퍼런스64306.mp4에 대한 생성기 최종 품질 PASS:없음.

## 미지원·미연결·미확인 구분

| 구분 | 확인 결과 |
| --- | --- |
| 일반 CPU 정식 capture | capture_presentation.mjs:24에서 최대240프레임. 직접 runtime을 호출해300프레임을 만드는 것은 그 계약의 정상 실행이 아니다. |
|10초 NVIDIA 정식 경로 | 코드에300프레임 지원이 존재한다. 현재 gCube 배포가 이 소스/한국 데이터와 일치하는지는 미확인. |
|한국 데이터/이미지 연결 | V2 SOURCE_SEAL에17개 파일+지형 asset+입력2개가 고정돼 있다. 진단 컨테이너의 read-only mount는 실제 운영 이미지에 통합됐다는 증거가 아니다. |
|지형 viewport 오류 | 상세 multipart 지형으로 clip1 frame192에서 UP2_AREA_SOURCE_OUTSIDE_VIEWPORT 실제 실패 기록이 있다. V8 수정과 제한 검사 PASS는 진단 overlay 범위이며 정식 배포 해결 증거가 아니다. |
|역사 전선/영토 | HISTORICAL은 studio_adapter.py:277에서 UP2_HISTORICAL_G3_REMAINS_BLOCKED. 현재 GENERAL은 현대 지리 배경+제공 사건/개략 방향이며1950년 전선·소유권 재현이 아니다. |
|지형의 의미 | NASA BMNG 영상 crop과 Natural Earth 지리 문맥. 실제1950년 해안선이나 새 고도 지형을 입증하지 않는다. |
|라벨/해안 효과 | 현재 소스에 표시 라벨 소비 코드가 있다. 오래된 README의 라벨 미지원 문구를 현행 전체 미지원으로 취급하지 않는다. V6/V8 해안/발광 개선은 별도 진단 후보이며 운영 지원 확정 아님. |
|음향 | 확인한10초 NVIDIA profile은 SILENT. 외부 편집으로 대체하지 않는다. |
|10초+10초 자동 연결 | 기존 compositor는 존재한다. 확인한 Studio API에는 두 작업 자동 연결 endpoint가 없으며 해당 연결은 미확립. 기존 compositor를 이용한 별도 명시적 단계만 소스상 확인. |
|범용성 | 공급된 데이터의 bounded compiler 존재와 임의 역사 주제의 자동 조사/정확한 전선 생성 능력은 다르다. 현재 자료만으로 후자를 PASS 처리하지 않는다. |

## 다음 최소 작업과 중단 조건

첫 미완료 단계는 **실제 배포의 image digest/source manifest/한국 sourceId 등록을 대조하고, 알려진 viewport 실패가 정식 경로에 남아 있는지 판정하는 것**이다. 기존 소스 준비 검사나 픽셀 PASS 전체를 다시 돌리지 않는다. 실제 배포의 상태·인증 접근과 영구 저장 경로도 아직 확인하지 못했으므로 실행 준비 완료를 선언하지 않는다.

알려진 FAIL과 연결 미확인이 해결되기 전에는 GPU 승인 요청/실행 또는 새 영상 제작으로 넘어가지 않는다. 수정·새 이미지 통합이 필요하다고 판명되면 필요한 최소 범위와 기존 PASS에 미치는 영향을 먼저 특정한다. 현재 사용자는 생성기 재개발을 금지했으므로 미지원 기능을 임시 렌더러나 외부 편집으로 보충하지 않는다. 두 정식10초 요청이 실행 가능한 상태가 된 후 각 유료 실행의 이미지·입력·비용/시간 상한·재시도 범위를 제시하여 별도 승인받는다.
