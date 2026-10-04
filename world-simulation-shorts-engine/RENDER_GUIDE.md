# Render guide

먼저 기획·스키마·GIS·사건 구성 검수를 통과시키고 정확한 계획을 승인합니다. 렌더 API나 내부 RenderManager는 승인 파일과 계획 해시가 없거나 일치하지 않으면 실행하지 않습니다. 기존 MASTER V1/V2/V3를 재렌더하거나 덮어쓰는 경로는 사용하지 않습니다.

## 장면별 실행

장면마다 JSON·품질·자산 SHA·렌더러 버전으로 캐시를 확인하고, 정상 캐시가 없을 때만 Chromium/Three.js 렌더러를 실행합니다. 실제 3D 프레임은 FFmpeg로 MP4를 만들고 장면 감사·manifest·체크포인트를 별도 저장합니다. 현재 CPU 작업은 순차 실행하며 여러 전체 렌더를 동시에 시작하지 않습니다.

HIGH/CINEMA는 2160×3840 내부 프레임을 1080×1920으로 Lanczos 다운샘플링합니다. 결과는 H.264/yuv420p/30fps/BT.709 MP4입니다. HIGH는 시간 샘플 1개, CINEMA는 같은 V3 대기 셰이더에서 시간 샘플 2개를 사용합니다. CINEMA에서 대기/HERO 조명이 별도로 강해지는 것은 아니며 조명은 Scene의 Lighting Preset을 따릅니다. 실제 파이프라인 명령의 `--samples`와 품질별 캐시 분리는 [COMMAND_CACHE_REPORT.json](docs/evidence/cinema_temporal_samples_20261004T140155Z/COMMAND_CACHE_REPORT.json)에 기록되어 있습니다. 해당 증거는 GL 실행 전 명령·캐시 계약 검사이며 실제 CINEMA 영상미 비교나 렌더 시간 측정이 아닙니다. FAST는 540×960의 검토용이며 업로드 품질 증거로 사용하지 않습니다. 실제 8K 지구 자산을 평면 PNG 지도나 저해상도 자산으로 바꾸지 않습니다.

카메라 경계는 출처 있는 경로 geometry의 진행 위치에서 계산하며 임의의 도시/항구 좌표를 생성하지 않습니다. 마지막 전경은 실제 주 경로 샘플과 rig 투영을 기준으로 전체 연결망을 안전영역에 맞춥니다. 화면 앞 반구에 담을 수 없으면 `MULTI_HEMISPHERE_OVERVIEW`로 렌더 전 차단합니다. 현재 여러 전경 자동 분할을 지원하는 것처럼 표시하지 않습니다.

해상 경로의 이동 altitude와 경로 선의 표시 altitude를 구분합니다. 출처 있는 선박 경로는 수면 부근을 따르고 발광 core/head는 같은 경위도의 약 3km 시각 오버레이입니다. 확대된 선박 프록시는 지표를 관통하지 않도록 배치됩니다. 실제 항해 고도·선박 크기·수심 모델이 아닙니다. `routeDisplay`와 entity 감사의 `cartographic_visual_proxy`를 통해 이 구분을 기록합니다.

오디오 사전 검사는 선택적 TTS의 실제 발화 시간을 측정합니다. 명시적 `tts_language`가 우선하며, 미지정 시 Scene별로 한글이 있으면 한국어, 그 외에는 영어를 선택합니다. 나레이션이 장면보다 길면 비싼 그래픽 렌더 전에 실패하고 대본 축약·Scene 연장을 요구합니다. 장면을 합친 뒤 timestamp에 맞는 효과음·선택적 BGM·ducking·자막을 합성합니다. 기본 TTS는 eSpeak 오프라인으로 자연스러운 스튜디오 음성을 보장하지 않습니다.

외부 MP4 삽입은 사용권·길이뿐 아니라 기존 Scene의 사건을 실제로 표현하는지도 검수합니다. 출처와 사실 상태가 맞는 정보 오버레이는 해당 사건의 시간에 렌더할 수 있습니다. 실제 항로/출발/도착을 요구하는 Scene에 임의 영상을 넣고 사건이 발생했다고 기록하지 않습니다. 필요할 때 정보 Scene을 선택하거나 사건 기획을 먼저 수정하고 승인합니다.

## 결과 경로

```text
projects/project_<id>/
  prompt/ request_v001.json
  project.json
  revisions/ revision_<id>.json
  versions/v001/
    scene_plan.json
    scene_plan_readable.md
    script.txt
    approval.json
    status.json
    story/story_plan.json
    scene_json/S001.json ...
    assets/source_report.json, source_report.md
    audio/mix.wav, audio_report.json, subtitles.ass
    renders/S001/scene_S001_v001.mp4, .audit.json, .manifest.json
    renders/scene_results.json, checkpoint.json, project_result.json
    qc/qc_report.json, qc_report.md, contact_sheet.png
    final/final.mp4, final_muted.mp4
```

일부 파일은 해당 옵션이나 실행 단계에 따라 생성됩니다. 실패 로그는 `qc/failure_<job>.json`에 보존합니다. 수정한 결과는 새 `versions/v002/`에 생성합니다. 실패한 시도의 파일 이름에도 attempt suffix를 사용해 진단 자료를 보존합니다.

## 복구와 부분 수정

브라우저를 닫아도 서버의 작업 스레드와 디스크 상태는 유지됩니다. 서버가 종료되었다면 재실행 후 이전 프로젝트를 열고 생성/재개 버튼을 사용합니다. 완료 Scene의 SHA와 미디어 규격을 확인한 뒤 재사용하므로 처음부터 다시 계산하지 않습니다.

`첫 3초를 낮으로`, `Scene 3을 더 빠르게`, `32~38초에 배 두 척 추가` 같은 요청은 먼저 변경점과 영향 Scene을 표시합니다. 선박 추가는 실제 해상 Scene에만 적용하며 새 경로 추가는 기존의 검증된 경로가 있어야 합니다. 변경 승인 후 실제 시각 입력이 바뀐 Scene이 캐시 miss가 되고 나머지는 재사용됩니다. 경계 카메라·입출력 상태가 깨지면 계획 게이트가 막습니다.

`Scene 2 삭제`는 실제 장면을 제거하고 영상 길이를 줄입니다. 삭제 장면 뒤의 첫 이웃은 연결 카메라와 항로 진행률이 달라져 새 렌더가 필요할 수 있습니다. 나머지 Scene의 조립 시간만 바뀌었다면 `render_time_offset`에 저장한 원래 렌더 시계를 유지하고 기존 프레임을 재사용합니다. `render_context`에 저장된 조명 anchor와 첫 화면 훅도 캐시 검증에 포함하며 전체 Scene JSON SHA와 재사용 근거를 `.reuse.json`에 기록합니다.

`Scene 4에서 결론 공개하지 마`는 결론 사건·사운드·나레이션·확장 네트워크를 뒤쪽 Scene으로 이동합니다. 수정된 다음 Scene과 결론을 받는 마지막 Scene도 Diff에 표시됩니다. 옮길 뒤 Scene이 없거나 훅·Peak·사건 간격·나레이션 길이·경계 규칙이 실패하면 구조 수정은 차단됩니다. 삭제한 Scene을 다시 넣거나 결과를 자막 뒤에 숨긴 채 검수 합격으로 표시하지 않습니다.

프레임 진행이 장시간 없으면 해당 renderer가 자신의 browser/encoder를 정리하고 실패 기록을 남깁니다. 다른 작업이나 기존 산출물을 삭제하는 방식으로 복구하지 않습니다.

## QC와 측정

모든 인코딩 프레임을 실제 디코딩해 black/duplicate/coarse freeze를 검사합니다. 렌더 감사는 누락 자산·WebGL 오류·라벨/이동체 clipping·경로 역행/지구 관통·카메라 급변을 검사합니다. 해상도/FPS/길이/코덱/색 메타데이터와 오디오 존재·true peak도 확인합니다. 지리 설명 장면의 너무 낮은 노출은 재검수 대상으로 실패시킵니다.

완성 단계의 Retention Gate는 계획 사건 이름만 다시 세지 않습니다. 프레임 감사에서 실제 그려진 사건 ID·primitive의 첫 표시 시점과 최소 표시 시간을 확인하고, 같은 사건의 여러 프레임을 하나로 계산합니다. camera-only primitive, 빠진 사건, 허용 fade 이후까지 늦어진 onset, 실제 첫 훅 누락은 실패합니다. 이 감사도 정보 내용의 진위나 실제 시청 유지율을 직접 증명하지는 않습니다.

밝기 임계값은 해안선의 올바른 모양이나 정보 전달을 증명하지 않습니다. Retention 검사는 실제 관객 반응을 측정하지 않습니다. 자동 합격 후 전체 재생, 주요 프레임, 모바일 크기의 도시명·경로·대상 위치를 직접 확인해야 합니다. 실제 음성 청취가 없었다면 보고서에 청취했다고 쓰지 않습니다.

`renders/project_result.json`의 `metrics`는 그 실행의 실제 Scene 렌더, 오디오, 결합, QC, 총 시간을 기록합니다. 캐시 재사용 실행과 새 전체 렌더를 구분합니다. 20초 결과 시간에서 75초 HIGH를 추정한 값을 실측으로 보고하지 않습니다.

실제 완료 manifest/벤치마크 집계와 QC 통과 불변 버전의 배타적 ZIP 내보내기는 [BENCHMARK_EXPORT_GUIDE.md](docs/BENCHMARK_EXPORT_GUIDE.md)를 참고하세요. 해당 도구는 렌더를 실행하지 않으며 recovery 경로·원본 SHA·GitHub 파일 크기·분할 SHA를 기록합니다.

GPU_CLOUD는 교체 가능한 backend 계약입니다. provider adapter, 승인된 비용 추정과 최대 비용 제한이 없으면 GPU worker를 만들지 않습니다. 실제 adapter는 `finally`에서 자신이 만든 worker를 종료해야 합니다. CPU는 유료 API 없이 사용할 수 있습니다.

## 다운로드

완료 후 UI 다운로드 버튼은 `/download/<project>/<version>/final/final.mp4`에 요청합니다. 서버가 `Content-Disposition: attachment`를 설정하므로 실제 파일 다운로드 응답을 제공합니다. `/media/`는 Range 요청으로 브라우저 재생을 지원합니다. 실제 휴대폰에서 접근하려면 서버가 해당 휴대폰에서 도달 가능한 LAN/HTTPS 주소에 있어야 합니다. 내부 `/workspace` 경로만 전달하는 것으로 외부 다운로드가 제공되지는 않습니다.
