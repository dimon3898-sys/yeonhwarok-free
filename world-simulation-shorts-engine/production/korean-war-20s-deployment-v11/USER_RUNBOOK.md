# 한국전쟁 20초 정식 생성기 — 휴대폰 실행 안내

무료 배포 준비 완료: GENERAL 정식 생성 경로에 한정한다. gCube #5373 설정 저장·재조회 완료, 현재 종료·노드 미할당. Work의 GPU 기동·Studio 렌더링·배포 시작·중지는 모두0회다. 아직 한국전쟁 정식 MP4의 품질 PASS는 없다.

## 확정 이미지와 다운로드

이미지는 이미 저장했다. 사용자가 설정을 추측해 바꿀 필요가 없다.

```text
기존 레지스트리: GitHub / ghcr.io
이미지 입력칸: dimon3898-sys/world-simulation-shorts-engine:kw20-native-v11-42345505600
전체 이미지: ghcr.io/dimon3898-sys/world-simulation-shorts-engine:kw20-native-v11-42345505600
확정 digest: sha256:bb97c55401f25abba360f648b7f240be900ab44cbed2d9926a4ccc5a3be68726
포트: 8080
Storage: dropbox → /world-storage
GPU: Tier2 RTX 4080 SUPER ×1 /16GB
```

- [gCube #5373 열기](https://gcube.ai/demand/ns74a360e2/workload/5373)
- [1구간 JSON 다운로드](https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_01.json)
- [2구간 JSON 다운로드](https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_02.json)
- [무료 검증·게시 Actions 성공](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/42345505600)
- [새 이미지·입력·증거 백업](https://github.com/dimon3898-sys/yeonhwarok-free/releases/tag/kw20-native-image-backup-42345505600)

복사용 원본 주소:

```text
https://gcube.ai/demand/ns74a360e2/workload/5373
https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_01.json
https://github.com/dimon3898-sys/yeonhwarok-free/releases/download/kw20-native-image-backup-42345505600/KOREAN_WAR_20S_PART_02.json
```

두 입력은 기존 V4 바이트를 그대로 보존한 파일이다. 1구간 SHA256은 `5a80189cee9e6930671a80c56c1f46021101d8ffd7e23b773c900c7e7c68adaf`, 2구간은 `53a618173b3e07c572a3104548979c857a3c081d165ce70c4fc01ff51f3e8c77`이다.

## 담당 범위

사용자가 gCube 배포, Studio 실제 렌더링, 다운로드, 배포 중지를 직접 한다. Work는 유료 GPU나 Studio 제작 시작을 실행하지 않는다. 두 개의 실제 정식 MP4가 확보된 다음 기존 WORLD ENGINE 합성기로 무료 CPU 연결을 수행할 수 있다.

## 입력과 영상의 범위

| 순서 | 입력 파일 | 장면 | 출력 |
| --- | --- | --- | --- |
| 1 | KOREAN_WAR_20S_PART_01.json | 낙동강 방어선 관련 사건 문맥 → 인천상륙작전 | 10초·300프레임 |
| 2 | KOREAN_WAR_20S_PART_02.json | 인천에서 서울 진격의 개략 방향 → 서울 수복 | 10초·300프레임 |

두 구간 모두1080×1920·30fps·무음이다. 기존 GENERAL 입력을 그대로 사용한다. 현대 지형·국가 지리 자료와 제공된 사건 라벨을 이용하는 설명 지도이며, 1950년의 정확한 전선·소유권·해안선 변화는 생성하지 않는다. HISTORICAL 차단을 해제하지 않는다.

## 실행 순서

1. JSON 두 개를 먼저 휴대폰에 다운로드한다. 파일 내용을 수정하거나 바깥에 별도의 요청 JSON을 덧붙이지 않는다. Studio가 기존 요청 형식으로 감싼다.
2. https://gcube.ai/demand/ns74a360e2/workload/5373 에서 확정된 이미지, RTX4080S×1, 종료 상태를 확인하고 사용자가 **배포**를 누른다. 포트8080·Storage `/world-storage`·기존 인증 값은 준비된 설정을 그대로 사용한다.
3. 실행 상태가 되면 워크로드 상세의 **HTTP 서비스 / 서비스 URL**로 접속한다. 매 배포의 현재 화면에 표시되는 주소를 사용한다. 종료 상태에서는 실제 주소/접속 성공을 확인할 수 없다.
4. 기존 Owner/Studio 인증 절차를 완료한다. 설정 화면이 나오면 기존 Owner 코드로 진행한다. 인증 코드를 GitHub나 채팅에 게시하지 않는다.
5. Studio **입력 JSON 선택**에서 PART_01을 선택하고 **사전검사**를 누른다. 처음 화면에6초가 표시될 수 있으나 이 입력의 사전검사 후 반드시 **10초·300프레임·전체2장면**으로 확인돼야 한다. 기본6초 예제 버튼을 누르지 않는다.
6. 사전검사의 모든 항목이 PASS이고 승인 비용·만료 시각을 확인한 뒤에만 동의 체크 후 **제작 시작**을 한 번 누른다. `STORAGE_EXPORT_MOUNT` 실패, source/hash 오류, HISTORICAL 차단이면 시작하지 않는다.
7. **COMPLETED / COMPLETE / 300프레임 / 완료2장면**을 확인한다. 결과 영역의 `WORLD_ENGINE_STUDIO_VIDEO.mp4`, `QUALITY_SUMMARY.json`, `SHA256SUMS`를 모두 다운로드하고, 작업 ID가 포함된 완료 화면을 보관한다. 1구간 파일임을 구분해 둔다.
8. 같은 방식으로 PART_02를 불러와 사전검사→제작 시작을 한 번 수행한다. 동시에 두 작업을 시작하지 않는다. 2구간의 MP4·검증 파일·작업 ID도 보관한다.
9. 두 구간의 다운로드가 완료되고 휴대폰에서 각각10초로 재생되는지 확인한 다음 사용자가 gCube **배포 중지**를 누른다. 종료 상태와 노드 해제를 확인한다. Studio 작업 종료·시간 제한은 gCube 배포 중지와 다르다.
10. 이 Work에 1구간/2구간 MP4와 각 `QUALITY_SUMMARY.json`, `SHA256SUMS`, 작업 ID를 구분해서 첨부한다. Work는 실제 파일의 형식·프레임·해시와 생성기 증거를 확인한 뒤 기존 합성기만 사용해20초로 연결한다. 합성 때문에 GPU를 켜 둘 필요가 없다.

## 기록 보존과 오류 대응

정식 capture의 단계 기록 → 기존 NVIDIA worker의 ActiveCheckpointMirror → 기존 안전한 내보내기 기능 → `/world-storage/capture-checkpoint-<작업ID>/CAPTURE_CHECKPOINT.json` 순서로 연결된다. 민감정보를 제외한 진행/오류 스냅샷을 저장하며, 원시 private 파일 전체를 저장하는 기능은 아니다. 기록은 표본 간격으로 갱신되므로 마지막 연산 전체의 저장을 보장하지 않는다.

기존 실제 저장소는 Dropbox `/WORLD_ENGINE`과 연결된 이력이 있다. 이번 새 배포의 실제 mounted readback과 외부 회수는 사용자가 배포한 뒤 확인해야 한다. 무료 검사에서 운영 중인 GPU/마운트를 실행해 확인했다고 주장하지 않는다.

오류·정체가 생기면 **제작 시작을 다시 누르지 않는다.** 다음을 먼저 보관한다.

- 작업 ID, 사용한 PART 번호, 오류 코드, 단계, 처리 프레임, 완료 장면 수가 보이는 화면
- `CAPTURE_CHECKPOINT.json`과 생성된 진단 다운로드 파일
- 시작 시각과 마지막 진행 변경 시각
- gCube 이미지 태그·배포 상태·컨테이너 이벤트; 원시 로그에는 인증 값이 섞일 수 있으므로 공개 게시하지 않는다.

오류가 지속되면 증거를 저장한 뒤 사용자가 배포를 중지하고 이 Work에 전달한다. 삭제된 컨테이너의 private 파일이나 stdout/stderr는 나중에 복구되지 않을 수 있으므로, 중지 후 회수를 기대하지 않는다. 성공한 구간은 보존하고 실패 구간만 원인 확인 후 다룬다.

## 기존 합성 경로

`world-simulation-shorts-engine/recovery/universal-auto-video-v2/compose.py`의 기존 CLI를 사용한다. 기존 `COMPOSE_PLAN.json`은 clip-01 `[0,300)`, clip-02 `[300,600)`의 순서와 접합 경계 조건을 가진20초 계획이다. 실제 출력의 파일 경로/해시를 담는 segments 목록은 다운로드 후에만 작성한다. 진단용5초 영상·선택 프레임·새 편집 효과는 입력하지 않는다. 음향이나 미지원 연출을 외부 편집으로 덧붙이지 않는다.

정식 생성기 MP4 두 개와 합성 결과의600프레임·전체 디코딩·순서 보존을 확인한 뒤 레퍼런스64306.mp4와 실제 품질을 비교한다. 배포 준비 PASS와 영상 품질 PASS는 별개다.

공식 서비스 접속/중지 안내 참고: https://data-alliance.github.io/gai-platform-docs/user-guide/platform-guide/ollama-api/

## 검증 범위와 남은 기능

- 정식 `NvidiaPresentationController._normal`의 기존 컴파일러·source admission을 두 입력이 통과했다. 기존 Scene과 정확히 일치하며 각각10초·300프레임이다. 실제 Studio HTTP 제출/시작과 GPU 하드웨어 사전검사는 실행하지 않았다.
- 알려진 `UP2_AREA_SOURCE_OUTSIDE_VIEWPORT`에는 기존 V8 수정과 검증 증거를 그대로 사용했다. 선택된 다중 폴리곤의 일부가 화면 밖일 때만 검증된 조건으로 제외하며 기본 엄격 검사는 유지한다. 기존 전체 프레임/픽셀 PASS를 다시 실행하지 않았다.
- 21개 설치 파일,361개 runtime source 목록,시작 manifest,기존 진단·합성 경로8개 해시가 배포 이미지와 연결됨을 확인했다. 새 이미지 백업과 GHCR digest는 동일하다.
- 첫 패키징은 백업 예약 확인 파일 누락으로 게시 전에 멈췄다. 입력 연결 PASS는 보존했다. 사라진 임시 runner 이미지만 동일 소스로 재구성했으며, 수정한 백업 절차는 성공했다. 이미지 빌드2회·GHCR 게시1회·GPU0회다.
- Studio에서 두 작업을 자동 연결하는 UI는 미연결 상태다. 기존 합성기의 두 실제 MP4 입력 경로를 이용하며 새 합성기나 별도 영상 편집을 만들지 않는다.
- 실제 저장소 mounted readback, 현재 GPU의300프레임 완주,실제600프레임 합성과 레퍼런스64306.mp4 대비 품질은 사용자 실행 후의 검증 항목이다.
