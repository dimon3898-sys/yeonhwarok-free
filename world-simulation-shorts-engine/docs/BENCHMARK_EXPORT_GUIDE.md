# 실측 집계와 완료 프로젝트 내보내기

이 도구는 Python 표준 라이브러리만 사용합니다. 서버·렌더러·FFmpeg·유료 서비스를 실행하지 않습니다. 원본 프로젝트, 이전 ZIP, 캐시는 수정하지 않습니다. 경로에 공백이 있으면 아래처럼 따옴표로 감쌉니다.

## 실제 벤치마크 집계

앱 폴더에서 실행합니다.

```bash
python3 tools/aggregate_benchmarks.py projects
python3 tools/aggregate_benchmarks.py projects --output "/workspace/deliverables/benchmark_report_v001.json"
```

`--output`은 새 파일만 만들며 기존 보고서는 보존하고 오류로 중단합니다. 원본 프로젝트 안에는 보고서를 쓸 수 없습니다. 특정 프로젝트나 `projects/project_<id>/versions/v001`만 지정할 수도 있습니다.

완료 영상으로 집계하려면 정확한 계획 승인, 불변 계획 해시, 최종 자동 QC, 완료 체크포인트, 최종/무음/Scene MP4·감사 SHA가 일치해야 합니다. 실제 `renders/project_result.json`의 `metrics.measured=true` 값을 그대로 기록합니다. Scene별 품질·내부 해상도·시간 샘플, 실제 렌더 여부와 캐시 재사용 여부를 구분합니다. 캐시에 남은 과거 `elapsed_seconds`/native `elapsedSeconds`는 원래 렌더 시간으로만 표시하며 현재 렌더 시간에 더하지 않습니다.

아직 완성되지 않은 버전의 정상 Scene은 별도 `completed_scene_observations_for_incomplete_videos`에 기록할 수 있습니다. 해당 기록은 전체 MP4·QC 완료나 전체 렌더 시간을 뜻하지 않습니다. 실패/불일치/미완료 버전은 성공 벤치마크와 분리합니다. 20초 결과를 75초 시간으로 확대 계산하지 않습니다.

브라우저 도구의 실제 기획 시간은 별도 증거를 지정합니다.

```bash
python3 tools/aggregate_benchmarks.py projects --ui-evidence "validation/실제 검증 폴더/UI_END_TO_END_REPORT.json" --output "/workspace/deliverables/benchmark_with_ui_v001.json"
```

UI 증거의 `project_id`, `version`, `plan_hash`가 해당 계획과 같아야 합니다. `planning_seconds`는 버튼 클릭부터 기획 HTTP 응답까지의 실제 시간이며 독립적인 Story 생성 시간이나 전체 렌더 시간으로 해석하지 않습니다. UI/기획 시간은 렌더 총 시간에 합산하지 않습니다. 이 시간이 측정되지 않았다면 증거 목록은 비어 있습니다.

버전 안의 기존 `benchmark.json`도 연결할 수 있습니다. 프로젝트/버전/계획 해시, `measured: true`와 실제 측정 필드가 필요합니다. 지원 필드는 `planning_seconds`, `story_generation_seconds`, `scene_plan_generation_seconds`, `ui_seconds`, `ui_request_seconds`입니다. `scope`에 측정 경계를 기록합니다. 추정값, `synthetic: true`, `measured: false`, 실패한 UI 증거는 실측으로 넣지 않습니다. 이 도구는 파일 수정 시각이나 영상 길이를 이용해 누락된 시간을 만들지 않습니다.

## QC 통과 버전의 ZIP

```bash
python3 tools/export_project.py inspect "projects/project_<id>/versions/v001"
python3 tools/export_project.py export "projects/project_<id>/versions/v001" --output "/workspace/deliverables/project_v001.zip"
```

`inspect`는 승인·QC·해시와 선정 파일을 읽기만 합니다. `export`는 동일 검사를 통과한 뒤 새 ZIP을 배타적으로 생성합니다. 원본 프로젝트 안의 ZIP 출력과 기존 ZIP 덮어쓰기는 거절합니다. 자동 QC 통과는 영상미 승인과 실제 청취를 증명하지 않으며 `aesthetic_review_required`를 내보내기 기록에 유지합니다.

포함하는 파일은 최종 MP4/무음 MP4, Scene Plan/읽기용 계획/대본, 승인·Story, 출처 보고서, QC JSON/보고서/contact sheet, Scene JSON, 실제 성공한 Scene MP4·감사·manifest·완료 체크포인트·재사용 증거와 생성된 오디오/자막입니다. `renders/project_result.json`과 Scene 결과 manifest도 포함합니다. 큰 공용 지구 텍스처·폰트·런타임·캐시·실패/partial 영상은 제외합니다. 출처 보고서와 native source SHA를 사용해 기존 V3 공용 자산을 연결해야 하므로 ZIP은 공용 자산까지 담은 단독 설치 패키지가 아닙니다.

복구된 결과가 `final/attempt002/`나 `qc/attempt002/`에 있다면 result에 기록된 실제 경로를 선택합니다. 오래된 실패 파일 이름을 보고 추측하지 않습니다. ZIP에서는 최종 파일을 `final/final.mp4`, `final/final_muted.mp4`, QC를 `qc/`에 정리하고 `EXPORT_MANIFEST.json`에 원본 상대 경로·크기·SHA를 기록합니다. Scene 파일은 실제 성공한 attempt 이름을 유지합니다. 원본이 복사 도중 바뀌면 오류로 중단하고 새로 생성된 불완전 ZIP을 진단용으로 남깁니다. 다른 새 출력 경로로 다시 실행합니다.

## GitHub 용량과 분할

공식 GitHub 자료에 기반한 확인 기록은 [github_file_limits_r01.json](evidence/github_file_limits_r01.json)에 있습니다. 일반 Git 파일은 50 MiB부터 경고, 100 MiB가 제한이며 브라우저 파일 업로드 제한은 25 MiB입니다. 내보내기 결과는 실제 ZIP 바이트와 일반 Git/브라우저 업로드 크기 적합성을 표시합니다. Git LFS 계정 용량이나 인증 가능 여부는 이 도구가 검증했다고 주장하지 않습니다.

```bash
python3 tools/export_project.py export "projects/project_<id>/versions/v001" --output "/workspace/deliverables/project_v001.zip" --split-mib 90
python3 tools/export_project.py split "/workspace/deliverables/project_v001.zip" --max-part-mib 90
python3 tools/export_project.py verify "/workspace/deliverables/project_v001.zip.parts.json"
```

분할은 원본 ZIP을 보존하고 `project_v001.zip.part001` 등의 새 파일과 `.parts.json`을 만듭니다. 각 조각은 최대 90 MiB이며 기존 조각·manifest가 있으면 보존하고 중단합니다. `verify`는 각 크기/SHA와 순서대로 합친 전체 ZIP SHA를 읽기만 검증합니다. 조각은 독립적인 ZIP이 아니므로 `.parts.json`의 순서대로 바이트를 이어 붙여야 합니다. 검증만으로 GitHub 업로드나 외부 다운로드가 완료되는 것은 아닙니다.

## 도구의 경계 검사

```bash
python3 -m unittest discover -s tools -p 'test_deliverable_tools.py' -v
```

검사는 임시 폴더의 명시적인 합성 fixture를 사용하며 기존 프로젝트를 렌더·수정하지 않습니다. recovery 경로 우선권, 원본 보존, 이전 ZIP 거절, 실패 QC/오래된 승인/해시 변경/누락 Scene 거절, 경로 이탈 방지, 캐시 시간 구분, UI 해시 매칭, 미완료 영상 분리, 분할 SHA·손상·경로 검증, 100/25/90 MiB 경계를 확인합니다. fixture의 MP4 바이트는 실제 영상이 아니며 이 테스트 통과는 실영상 QC/영상미 또는 공개 다운로드 성공을 증명하지 않습니다.
