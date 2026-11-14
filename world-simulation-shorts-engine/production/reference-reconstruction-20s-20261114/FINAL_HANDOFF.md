# WORLD ENGINE 몽골제국 20초 배포 인수 결과

상태: **READY_FOR_USER_GPU_START**. 무료 선행 검증과 설정 저장을 완료했다. 유료 GPU·Studio 렌더링은 0회이며, 실제 영상 성공이나 시각 품질 PASS를 뜻하지 않는다.

## 신규 완료

- 원격 `a30565c`와 기존 작업 폴더의 미커밋 변경·검사 증거를 대조하여 복구했다. 원본 로컬 커밋과 보존 stash를 유지했다.
- 기존 Controller·Worker·모바일·설계 PASS를 재사용했다. 빠져 있던 Controller 거부 11종과 runtime 거부 7종을 추가 확인했다. 기존 6초·10초 검사와 MP4는 다시 실행하지 않았다.
- 실제 게시 대상 이미지의 UID1000·읽기 전용·네트워크 차단·GPU 비활성 환경에서 FINAL 입력을 정식 Controller에 전달했다. HISTORICAL, 20초, 30fps, 600프레임, 1080×1920, 600개 카메라 상태, 라벨, 지도 소스, 106개 중간 도형이 보존됐고 Worker가 받는 JSON 바이트와 SHA256이 일치했다.
- Receipt 검사는 계약 및 합성 메타데이터 검사다. 실제 GPU 성공 Receipt·작업 ID·MP4는 생성하지 않았다. 입력 파일 SHA와 canonical prompt SHA는 서로 다른 대상을 해시하므로 별도로 기록했다.
- 이미지 A1에서 기존 `REVIEWED_HISTORICAL.json`이 파일 목록에서 빠진 결함을 확인하고 해당 기존 파일만 추가했다. A2는 검사 환경의 출력 디렉터리 누락 및 증거 저장 폴더 오류를 수정했다. 모든 실패 기록을 보존했다.
- A3 이미지 생성, 474개 runtime 파일 및 startup pin, Worker 존재·보호장치, 게시 후 digest 재획득 검사를 통과했다. 기존 게시 차단 검사는 유지했다.
- gCube #5373의 이미지 주소와 digest 환경변수 두 개를 저장했다. 다시 연 편집 화면의 입력 38개가 의도한 저장값과 일치했다. 포트8080·기존 인증값·GPU·스토리지·예산 정책은 유지됐다. 최종 상태는 종료, 노드 미할당, 최근 배포 시각은 2026-11-13 15:38:04 KST 그대로다.

## 변경 파일

초기 원격 HEAD 대비 복구·수정된 핵심 파일:

- `recovery/codex-to-gcube-handoff-v1/backend/capture_nvidia.mjs`
- `recovery/codex-to-gcube-handoff-v1/mobile/app.js`
- `recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json`
- `recovery/universal-presentation-v2/history_authored_v1.mjs`
- `recovery/universal-presentation-v2/studio_adapter.py`
- `recovery/studio-cold-start-v2/bootstrap.py`
- `recovery/studio-cold-start-v2/STARTUP_MANIFEST.json`
- `release-guard/REQUIRED_FIXES.json`
- `.github/workflows/world-engine-history20-image.yml`
- 본 작업 폴더의 부족한 계약 검사, 실제 이미지 검사, 패키징 목록, 실패 증거, 배포 설정, CHECKPOINT 및 사전검사 보고서.

기존 Controller·Worker의 600프레임 구현은 이미 저장된 버전을 재사용했다. 레퍼런스 분석·600프레임 설계·역사 데이터·106개 도형·FINAL 입력은 재작성하지 않았다.

## 고정 이미지와 입력

이미지:

```
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:history20-6970708eb71a-43551475182
```

digest:

```
sha256:f44f5c9a6d948fb7a08476465566d7363fc4c1008526a4ab67681537bd700795
```

`FINAL_20S_INPUT.json` SHA256:

```
cc492a5b584706f69bc6a2c208748be4a8cfec431939c3c70fb64b112252efa6
```

- 실제 GPU profile: `GCUBE_NVIDIA_CONTINUOUS_HISTORY_20S_V1`
- runtime profile: `HISTORICAL_CONTINUOUS_600F_V1`
- 역사 주제: 몽골제국 1206~1209 → 1210~1215
- 지도: `NASA_BMNG_EURASIA_PYRAMID_V1`
- 출력: 1080×1920, 30fps, 20초, 600프레임, 무음 H.264
- source manifest: `0908dd2844f3aa6b076b8e8043d62d191661c299402df9fe6f5a61450365d572`
- runtime wire: `e6e1bacd6efa13dbdf49091f9934a60372822a741b742d0a4a3c718cf83e6cd5`

## GitHub 저장 지점

| 단계 | 커밋 |
|---|---|
| 기존 미커밋 코드·검사 증거 복구 | 592a3abd815aecf0075bade8943be81ce8b42cd3 |
| 부족한 신규 거부 검사 및 연결 검증 | 412b753556926675111da32b4da634933171bf48 |
| 기존 역사 registry 누락 수정 | 147988e11548c7968911720a5e02057677634de7 |
| 최종 A3 빌드 입력 | 6970708eb71a073b6793b8a77a577d3b6d4bfee0 |
| 게시 이미지·실제 이미지 검사 증거 | d1f17a251c02b628c6f7051cb425a4d0fe2d8b33 |
| gCube 저장·재열기·digest 사전검사 | 350972e2a4852c27c1bf47ca367ef88625713241 |

이 보고서와 최종 CHECKPOINT의 커밋은 브랜치 최신 HEAD에서 확인한다. 파일 내부에 자기 커밋 SHA를 고정하려고 반복 커밋하지 않는다.

## 남은 항목과 다음 실행

무료 선행 차단은 없다. NVIDIA 장치 연결, 실제 600프레임 렌더·디코드, 결과 Receipt, 저장소 읽기/쓰기와 다운로드, 실제 소요시간·비용, 영상의 레퍼런스 대비 품질은 **PENDING_GPU**다. 사용자 별도 승인 전에는 실행하지 않는다.

1. 별도 GPU 실행 승인 후 사용자가 gCube #5373에서 배포한다.
2. Studio의 입력 JSON 선택에서 **본 폴더의 FINAL_20S_INPUT.json**을 넣는다. 기본 6초 예제나 이전 JSON을 사용하지 않는다.
3. 사전검사에 HISTORICAL·20초·600프레임·30fps·1080×1920이 맞게 표시되는지 확인한 뒤 영상 1개만 승인한다. 값이 다르거나 실패하면 실행하지 않는다.
4. 완료 후 MP4와 진단 기록을 다운로드한다. 출력 파일명은 `WORLD_ENGINE_STUDIO_VIDEO.mp4`, 실제 출력 디렉터리는 작업 결과의 `exportDirectory`에 기록된다.
5. 다운로드 직후 gCube를 수동으로 중지한다. 실패·정체 시 가능한 진단 기록을 보존하고 중지하며 자동 재시도하지 않는다.

GPU 사양은 RTX5090×1, CPU12, RAM63GB, 공유 메모리3GB이다. 관측 요금은 시간당910~1300원(VAT 별도), 30분 점유 시455~650원(VAT 포함 약501~715원)이다. 이는 점유시간 계산이며 실제 렌더 시간 측정값이 아니다. Worker의 작업 시간 상한은600초이고, 기존 운영 정책은30분·재시도0·2000원 상한을 유지한다. 앱의 작업 종료는 gCube 과금 중지를 보장하지 않으므로 워크로드를 직접 중지해야 한다.

상세 근거는 `DEPLOY_PREFLIGHT.json`, `image-a3/RELEASE_APPROVAL.json`, `image-a3/HISTORY_IMAGE_TRANSPORT.json`, `gcube-readback/DEPLOYMENT_GATE.json`을 사용한다. 이전 시점의 BLOCKED/PENDING 기록은 감사 이력으로 보존하며 최신 인수 기준은 본 보고서와 CHECKPOINT다.
