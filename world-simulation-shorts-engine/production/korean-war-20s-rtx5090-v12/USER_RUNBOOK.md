# 한국전쟁 20초 — RTX 5090 저장 설정과 사용자 실행 안내

2026-11-08 KST. RTX 5090 배포 설정 저장·재조회 완료. 현재 종료·노드 미할당. Work의 GPU 기동·Studio 렌더링·배포 시작·중지는 모두0회다. 실제 5090 실행 PASS와 최종20초 품질 PASS는 아직 없다. Studio에서 두 작업을 자동 합성하는 UI는 미연결이다.

이 문서는 이전 v11 안내 중 RTX4080 선택 및 Work가 합성한다는 안내를 대체한다. 사용자가 배포·렌더링·다운로드·기존 합성기 실행·중지를 직접 한다. 원본 v11 문서는 증거로 보존한다.

## 저장된 값

```text
Workload: #5373 / world-engine-test
GPU: TIER2 RTX 5090 ×1 / VRAM32GB
vCPU:12 / RAM:63GB / Disk:937GB / replica:1
이미지: ghcr.io/dimon3898-sys/world-simulation-shorts-engine:kw20-native-v11-42345505600
digest: sha256:bb97c55401f25abba360f648b7f240be900ab44cbed2d9926a4ccc5a3be68726
HTTP:8080
Storage:dropbox → /world-storage
Container Command:빈 값
공유 메모리:3GB
```

기존 ENTRYPOINT·인증·환경변수를 유지했다. 환경변수15개 중 비용 policy의 `gpuHourlyRate`만360→1300으로 바꿨다. 정책 상한은7200초,10000KRW,재시도0,만료2026-11-27T23:59:00+09:00 그대로다. 이 값은 실행을 허가하거나 자동으로 배포하는 설정이 아니다. gCube 표시 가격은910~1300원/시간(VAT 별도)이며 배포 시 실제 표시 조건을 확인한다.

## 휴대폰에서 받을 입력

- [gCube #5373](https://gcube.ai/demand/ns74a360e2/workload/5373)
- [1구간: 낙동강 방어선 관련 사건 → 인천상륙작전](https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_01.json)
- [2구간: 인천에서 서울 진격 → 서울 수복](https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_02.json)
- [기존 이미지·입력·검증 증거 백업](https://github.com/dimon3898-sys/yeonhwarok-free/releases/tag/kw20-native-image-backup-42345505600)

```text
https://gcube.ai/demand/ns74a360e2/workload/5373
https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_01.json
https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_02.json
```

1구간 SHA256: `5a80189cee9e6930671a80c56c1f46021101d8ffd7e23b773c900c7e7c68adaf`

2구간 SHA256: `53a618173b3e07c572a3104548979c857a3c081d165ce70c4fc01ff51f3e8c77`

기존 입력을 그대로 사용한다. 각각1080×1920·30fps·10초·300프레임·2장면·무음·GENERAL이다. HISTORICAL을 강제로 활성화하지 않는다. 현대 Natural Earth 지리와2004 NASA BMNG 지형 래스터를 사용하며, 검증되지 않은1950년 전선·영토·해안선·고도 DEM은 생성하지 않는다.

## 사용자가 직접 실행할 순서

1. 먼저 두 JSON을 휴대폰에 다운로드한다. JSON 내용과 요청 형식을 임의 변경하지 않는다.
2. 위 gCube 상세에서 RTX5090×1, 이미지 `kw20-native-v11-42345505600`, 종료 상태를 확인한 다음 사용자가 **배포**를 누른다. 재고·가격이 달라졌거나 다른GPU로 표시되면 진행하지 않는다.
3. Running이 된 뒤 상세에 새로 표시되는 HTTP8080 서비스 주소로 접속한다. 종료 상태에는 실행 중 Studio 주소가 없으므로 주소를 추측하지 않는다. 기존 Owner/Studio 인증을 사용한다.
4. Studio의 실제 GPU 진단이 NVIDIA RTX5090, WebGL2/Vulkan 하드웨어 검증, GPU-required 조건을 만족하는지 확인한다. 영구 저장소 사전검사가 PASS인지 확인한다. 소프트웨어 렌더러, 드라이버 오류, Storage 오류가 있으면 제작을 시작하지 않는다.
5. **입력 JSON 선택**에서 PART_01을 선택하고 **사전검사**를 누른다. 결과가10초·300프레임·2장면인지 확인한다. 처음 표시될 수 있는 기본6초 예제를 실행하지 않는다. 모든 사전검사가 PASS일 때만 동의 후 **제작 시작**을 한 번 누른다.
6. COMPLETED/COMPLETE,300프레임,완료2장면을 확인한다. `WORLD_ENGINE_STUDIO_VIDEO.mp4`, `QUALITY_SUMMARY.json`, `SHA256SUMS`를 다운로드한다. 작업ID·PART번호·완료화면을 함께 보관한다. 1구간 원본은 보존하고 합성용 복사본 이름만 `PART01.mp4`로 정한다.
7. PART_02도 같은 순서로 사전검사→제작 시작→완료 확인→다운로드한다. 동시에 두 작업을 돌리지 않는다. 2구간 합성용 복사본은 `PART02.mp4`로 정한다.
8. 두 원본MP4와 증거가 휴대폰/PC에 실제 저장됐고 각각10초로 재생되는지 확인한다. **GPU가 필요 없는 아래 PC CPU 합성을 선택한다면 여기서 먼저 사용자가 gCube 배포 중지를 누르고 종료·노드 해제를 확인한다.** 합성을 위해 GPU를 켜둘 필요가 없다.
9. 아래 기존 WORLD ENGINE CLI로 사용자가20초 합성을 수행한다. Studio에 자동 합성 버튼이 있다고 가정하지 않는다. CLI 환경이 없다면 두 원본을 보존하고 합성은 BLOCKED로 남긴다. 별도 영상 편집기로 대체하지 않는다.
10. `WORLD_ENGINE_AUTO_VIDEO.mp4`, `QUALITY_SUMMARY.json`, `SHA256SUMS`, `COMPOSE_COMPLETE.json`을 보관한다. 완료 응답은600프레임·technical PASS여야 한다. 실제 시각 품질은 UNREVIEWED이므로 최종MP4를 본 뒤 레퍼런스64306.mp4와 비교한다. 8번에서 중지하지 않았다면 보존 직후 사용자가 gCube를 중지하고 종료 상태를 확인한다.

## 오류 시

재시작·재렌더링을 누르지 않는다. 작업ID,PART번호,오류코드,단계,프레임,완료장면수,마지막 갱신 시각과 화면을 저장한다. 진단 다운로드와 `/world-storage/capture-checkpoint-<작업ID>/CAPTURE_CHECKPOINT.json`도 보관한다. 인증 값이 포함될 수 있는 원시 로그를 공개 게시하지 않는다. 증거를 확보한 뒤 사용자가 배포를 중지한다. 삭제된 컨테이너의 private 원문·stdout/stderr 회수를 다시 시도하지 않는다.

기록 경로는 기존 ActiveCheckpointMirror의 제한된 진행/오류 스냅샷이다. 전체 private 작업 파일을 영구 보존한다는 의미가 아니다. 새 배포의 실제 마운트 readback 및 외부 회수는 아직 미검증이다.

## 기존 합성기 — 사용자 PC의 CPU CLI

휴대폰 Studio만으로는 이 단계가 연결되지 않는다. Python3·Git·FFmpeg/ffprobe가 이미 있는 Linux/macOS 또는 WSL 터미널이 필요하다. Work는 이 명령을 실행하지 않았다. 새 렌더러/편집기가 아니라 기존 합성기만 실행하는 안내다.

빈 작업 위치에서 아래를 실행한다. 같은 이름의 폴더가 있으면 덮어쓰지 않고 중단한다.

```bash
git clone --no-checkout https://github.com/dimon3898-sys/yeonhwarok-free.git world-engine-kw20-5090
cd world-engine-kw20-5090
git checkout --detach 44164d508b4aedca6993a3bb5001ba9fb74ebe2a
```

이 폴더에 실제 정식 Studio 결과 복사본 `PART01.mp4`, `PART02.mp4`를 둔다. 진단용15초 영상이나 다른 파일은 사용하지 않는다. 각 Studio의 QUALITY_SUMMARY·SHA256SUMS와 파일이 일치하는지 확인한다. 다음 명령은 영상 생성 없이 실제 두 파일의 해시와 순서를 목록에 기록한다.

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib, json
rows = []
for i in (1, 2):
    p = Path(f'PART{i:02d}.mp4').resolve(strict=True)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            h.update(data)
    rows.append({'sceneId': f'clip-{i:02d}', 'startFrame': (i-1)*300,
                 'endFrame': i*300, 'path': str(p), 'sha256': h.hexdigest()})
with Path('KW20_SEGMENTS.json').open('x', encoding='utf-8') as f:
    json.dump(rows, f, indent=2)
    f.write('\n')
PY
```

두 파일이 모두 준비됐을 때만 기존 합성기를 실행한다. 출력 폴더가 이미 있으면 덮어쓰지 않고 중단한다.

```bash
python3 world-simulation-shorts-engine/recovery/universal-auto-video-v2/compose.py --plan world-simulation-shorts-engine/production/korean-war-20s-deployment-v11/COMPOSE_PLAN.json --segments KW20_SEGMENTS.json --destination KW20_COMPOSE_5090_01
```

성공 결과는 `KW20_COMPOSE_5090_01/public-review/WORLD_ENGINE_AUTO_VIDEO.mp4`다. 같은 폴더의 QUALITY_SUMMARY.json과 SHA256SUMS, 상위의 COMPOSE_COMPLETE.json을 함께 보관한다. 실패 시 COMPOSE_FAILED.json과 diagnostics를 보존하고 반복 실행하지 않는다. 합성기는 전체 디코드·PTS·프레임순서·파일해시를 검증한다. 이 기술 검증은 역사적 정확성·시각 품질·GPU 실행 사실을 대신 증명하지 않는다.
