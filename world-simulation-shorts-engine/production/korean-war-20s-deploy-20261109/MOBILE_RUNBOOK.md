# 한국전쟁 20초 — 휴대폰 실행 안내

실행 가능 여부는 같은 폴더의 최종 CHECKPOINT와 배포 영수증을 먼저 확인한다. 이 안내 파일 자체는 이미지 게시나 gCube 저장 완료의 증거가 아니다. 실제 RTX 5090 호환성·영상 품질은 GPU_PENDING이다.

## 1. 배포 시작과 Studio 접속

1. [gCube 워크로드 #5373](https://gcube.ai/demand/ns74a360e2/workload/5373)을 연다.
2. 저장된 이미지 태그·digest, RTX 5090 ×1, HTTP 8080, Storage `/world-storage`, 공유 메모리 3GB, 빈 Container Command를 최종 배포 영수증과 대조한다.
3. 사용자가 **배포 시작**을 누른다. 노드·컨테이너 준비 후 워크로드의 HTTP 8080 접속 링크로 Studio를 연다. 배포 전에 임의의 Studio URL을 만들지 않는다.
4. 기존 Owner 인증으로 로그인한다. 인증값은 입력 JSON이나 보고서에 넣지 않는다.

## 2. PART01 — 낙동강 방어 → 인천상륙작전

1. [KOREAN_WAR_PART01_STUDIO.json](KOREAN_WAR_PART01_STUDIO.json)을 휴대폰에 내려받는다. GitHub에서 파일 본문이 열리면 **Download raw file**을 선택한다.
2. Studio의 **입력 JSON 선택**으로 이 파일을 고른다. **검증된 6초 예제 불러오기**는 선택하지 않는다.
3. **사전검사**를 누른다. 화면이 **10초 GPU 검수 · 1080×1920 · 30fps · 300프레임**으로 바뀌고 사전검사 통과가 표시되어야 한다. 6초·180프레임이면 제작을 시작하지 않는다.
4. 표시된 비용·시간·만료·자동 재시도 0회를 확인하고 제작 동의 체크 → **제작 시작**을 누른다.
5. 완료되면 **WORLD_ENGINE_STUDIO_VIDEO.mp4 다운로드**, **QUALITY_SUMMARY.json 다운로드**, **SHA256SUMS 다운로드**를 각각 누른다. 휴대폰에서 PART01로 구별해 보관한다. 파일 이름을 바꿔도 파일 내용은 변경하지 않는다.

## 3. PART02 — 인천 → 서울 수복

1. [KOREAN_WAR_PART02_STUDIO.json](KOREAN_WAR_PART02_STUDIO.json)을 내려받고 **입력 JSON 선택**에서 교체한다.
2. **사전검사** → 10초·300프레임 확인 → 제작 동의 체크 → **제작 시작** 순서로 진행한다.
3. 완료 후 같은 MP4·QUALITY_SUMMARY.json·SHA256SUMS 3개를 내려받아 PART02로 구별한다. PART01 파일을 덮어쓰지 않는다.

두 JSON은 Studio 파일 입력용 `WORLD_ENGINE_PRESENTATION_PROMPT_V2`다. 기존 검증 요청의 내부 `prompt`를 그대로 추출했다. 서버는 이 입력에 정식 NVIDIA 요청 형식을 붙이고 컴파일러 → NVIDIA worker → 기존 렌더러 → MP4 경로로 전달한다. 서버가 최종 이미지·소스·비공개 자료를 결합하므로 JSON에 digest나 내부 설치 경로를 수동으로 추가하지 않는다.

| 파일 | SHA256 |
|---|---|
| PART01 | `ffcbf85fa99a82a903f49e3cedbdecf69c5cac90b968e8780560637f20623792` |
| PART02 | `3f569901e1ff0ed45f7dd3cabe17d89ad0666179981ef98e59051d1a3dde6611` |

## 4. 진단 기록과 정체 시 보존

완료 화면에 표시되는 진단 기록 다운로드도 보관한다. 오류·정체가 생기면 새 제작을 반복하지 않고 **작업 ID, 상태, 단계, 처리 프레임/전체 프레임, 완료 장면/전체 장면, 경과 시간, 오류 코드, 발생 시각**이 한 화면에 보이게 캡처한다. `UP2_COMPLETE_TIMELINE_DATA_REQUIRED`이면 `issues.code`, `issues.field`, `blockedSceneIds` 목록도 보관한다.

gCube의 현재 이미지 digest와 로그 다운로드, 영구 저장소의 해당 작업 진단 기록도 보존한다. 완료 MP4·진단 기록의 외부 다운로드가 확인되기 전에는 컨테이너 내부 파일만 남았다고 가정하지 않는다. 영구 저장 경로와 readback 확인은 최종 배포 영수증을 따른다. 자동 재시도는 0회이며, 정체 상태에서 제작 시작을 다시 누르지 않는다.

## 5. 기존 합성기로 20초 연결

현재 Studio에는 두 개의 별도 작업을 합치는 모바일 버튼이 없다. 휴대폰에서는 두 MP4와 각각의 SHA256SUMS·QUALITY_SUMMARY.json을 이 Work에 첨부하고 아래 문구를 보낸다. 직접 Python이나 터미널을 설치할 필요는 없다.

```text
한국전쟁 PART01과 PART02의 실제 Studio 결과입니다. 각 SHA256SUMS를 대조하고, 저장된 compose_parts.py와 기존 compose.py로 PART01 → PART02 순서로 20초·600프레임 MP4를 연결해줘. GPU와 렌더러는 실행하지 말고 원본 2개는 보존해줘.
```

Work 실행 명령은 다음과 같다. `<...>`는 전달된 실제 다운로드 파일 경로와 Studio SHA값으로 채우며, 사용자가 휴대폰에서 이 명령을 실행하는 것이 아니다.

```bash
python compose_parts.py --part01 '<PART01.mp4>' --part01-sha256 '<PART01_SHA256>' --part02 '<PART02.mp4>' --part02-sha256 '<PART02_SHA256>' --destination '<새_합성_출력_폴더>'
```

이 명령은 기존 WORLD ENGINE 합성기를 그대로 호출한다. 각 입력의 300프레임·10초·1080×1920·30fps·H.264·무음을 검사하고, 출력 전체 600프레임을 디코딩해 입력 프레임 순서와 일치하는지 확인한다. 결과는 `public-review/WORLD_ENGINE_AUTO_VIDEO.mp4`, `QUALITY_SUMMARY.json`, `SHA256SUMS`이며 실제 영상의 장면 연속성·품질 확인은 별도로 남는다. 새 렌더링이나 GPU는 필요 없다.

## 6. gCube 중지

최종 MP4를 내려받아 확인한 뒤 gCube 워크로드에서 **배포 중지**를 누르고 **종료·노드 미할당**을 확인한다. 휴대폰 브라우저를 닫는 것은 과금 중지가 아니다. 두 원본과 진단 자료를 모두 내려받은 상태에서 Work의 CPU 합성을 기다려야 한다면 먼저 gCube를 중지해도 합성은 가능하다.
