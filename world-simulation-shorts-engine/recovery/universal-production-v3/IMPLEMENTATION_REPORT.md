# WORLD ENGINE — Universal Production V3 구현 보고서

기록일: 2026-10-16, Asia/Seoul. 새 V3 후보는 **107개 집중 CPU 검사, 실제
SwiftShader draw/readPixels, 이미지 빌드·GHCR 등록·독립 digest pull을 통과했다.**
증거는 [FREE_VALIDATION.json](FREE_VALIDATION.json), [IMAGE.json](IMAGE.json)과
[CI run 38851322860](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/38851322860)에 있다.
실제 검사는 5개 시점이며, 전체 2,400프레임·12개 모든 chapter의 영상 검사나
NVIDIA 실행은 아니다. 80초 영상, 영상 품질, 계정·비용 통제는 아직 검증하지 않았다.

## 1. 기준점·재사용·변경 범위

작업 브랜치는 `development/universal-production-v3-20261016`, 보호 기준은
`e09be5d368eefa9548d63901dfe13a217a7ca02d`다. 부모 범용 V2 이미지의 immutable
참조는 다음과 같다. 이는 **기존 이미지**이며 새 V3 이미지의 digest가 아니다.

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:5f17537fa8e5387de39ed8999e4c8d7ce2fe8a3593a71a5a3c1ae033f22dd014
```

기존 ASTRA 자료·CPU/GPU 업로드·지원 마스크·재질, Area V3 polygon/front,
V5 카메라·기존 native 표식, 범용 Scene/작업 관리자, GPU 필수 검사·공통 lease,
장면 캐시·실패 복구, FFmpeg 합성·검증, Dropbox 저장 어댑터를 재사용한다.
완료된 ASTRA 조사·수집이나 기존 168개 집중 검사를 다시 개발·반복하지 않았다.

추가는 이 namespace와 독립 workflow 안으로 제한했다. 기존 FINAL, V4,
승인된 카메라·renderer·shader·원본 geometry·기존 이미지·영상·claim 변경은
0건으로 유지한다. 기준 파일과 해시는 [BASELINE_LOCK.json](BASELINE_LOCK.json),
부모 의존성은 [PARENT_CLOSURE.json](PARENT_CLOSURE.json)에 기록했다.

주요 추가 파일은 다음 역할을 맡는다.

| 파일 | 추가한 책임 |
|---|---|
| `scene_planner.py` | 출처가 있는 12개 사건 장, 도식 기준일, 독립 source clock 및 정확한 작업 범위 |
| `production_visual_profile.mjs` | 명시된 area 소유 의미·색상·전환 파라미터, 자료 밖 소유권 생성 차단 |
| `production_area_pass.mjs` | 기존 Area GPU pass를 통한 소유 영역 색상과 백색·금빛 실제 front 스타일 |
| `production_camera.mjs`, `production_native_camera.mjs` | 기존 native API로 chapter별 안전 framing·접근·잠금, 원래 카메라 source 보존 |
| `production_adapter.mjs` | 실제 ASTRA → 제공된 영역 → 제공된 전선 → 사건/도식 날짜 → 원래 표식 합성 |
| `long_runtime.mjs`, `long_capture.mjs`, `render_adapter.py`, `orchestrator.py` | 해시 검증된 V3 실행 경로를 기존 전역 시계·작업·인코딩 경로에 연결 |
| `operations.py` | 공식 gCube 증거에 근거한 인증 read와 별도 승인 stop, 미확인 과금 자동 시작 차단 |
| `source_manifest.py`, `ci.py`, `Dockerfile` | 보호 closure 검증, 무료 집중 검사, 신규 이미지·독립 pull 조건 |
| `software_probe_production.mjs` | 실제 SwiftShader A/B, 전역 프레임과 실제 작업 경계 픽셀 비교 |

## 2. 역사 근거와 12장 구성

전체 구성과 화면에 표시할 자료 기준일은 [STORYBOARD.md](STORYBOARD.md),
원문 접근·날짜·공간 근거의 구분은 [HISTORY_VERIFICATION.md](HISTORY_VERIFICATION.md)에
있다. 발발 → 북한군 남하 → 낙동강 방어선 → 인천상륙 → 서울 수복 → 북진 →
중국군 첫 교전 → 전선 남하 → 재반격 → 교착 → 1951–1953 변화 → 정전의
12개 사건 chapter를 80초에 배치했다.

공간 자료는 기존의 **5개 도식 snapshot**만 있다: 1950.06.25, 1950.09.01,
1950.11.24, 1951.01.04, 1953.07.27. 일곱 chapter에는 해당 사건 날짜의
새 전선 geometry가 없다. 이 구간은 과거 도식을 그 기준일과 함께 참고 화면으로
유지하며, 누락된 상륙 경로·반격·국지 변화나 일별 점령선을 생성하지 않는다.
정전 도식도 측량된 1953년 군사분계선으로 소개하지 않는다.

날짜의 curated chronology 검토와 공식 원문 직접 검증은 다르다. 실제 공식
원문 요청은 proxy CONNECT `403 Forbidden`으로 차단됐고 새 공식 본문·지도
확보는 0건이다. 이를 origin 기사의 HTTP 응답이나 공식 본문 검증 성공으로
바꾸지 않았다. 접근 제한을 우회하거나 같은 조사를 반복하지 않았다.

중국군 첫 교전의 10월 25일 정보에 미래의 11월 24일 전선을 당시 전선처럼
붙이지 않는다. 사건 날짜와 실제 표시 중인 도식 날짜를 각각 표시한다.
검증된 역사적 부대 좌표가 없어 국가별 부대·국기 위치나 이동 경로를 새로
추가하지 않았다. 기존 native 표식은 실제 참전 부대의 위치 증거가 아니다.

## 3. 자연어 입력·Scene JSON·80–600초 범용화

자연어 입력은 기존 offline 사실 catalog와 제한된 parser를 재사용한다.
한국전쟁 주제·길이를 해석하고 출처가 있는 Scene을 생성하는 경로이며,
외부 AI API가 연결된 임의 주제 자동 조사·기획 완료 상태는 아니다. catalog나
공간 자료가 없는 사건을 사실처럼 채우지 않는다.

동일한 `durationSeconds`, `fps`, 해상도, `[startFrame,endFrame)` 계약과
분할·캐시·합성 경로를 80/120/180/300/600초에 적용한다. 30fps의 총 프레임은
각각 2,400/3,600/5,400/9,000/18,000이다. 이 길이들의 무료 계약 검사와
실제 NVIDIA 장편 렌더링 성공을 구분한다. 600초 실제 실행은 검증하지 않았다.

현재 80초 구성은 12개 사건 장과 12개 작업 범위다. 사건 장은 각 200프레임,
작업 경계는 실제 움직이는 첫 도식 전환 내부의 445프레임으로 조정했다.
`[200,445)` 작업은 두 사건 장에 걸치므로 렌더러는 작업 시작일이 아니라
각 **전역 프레임**의 사건 제목·날짜·source clock을 선택한다.
세부 계약은 [SCENE_CONTRACT.md](SCENE_CONTRACT.md)에 있다.

## 4. 실제 연결한 지도·영역·전선·카메라 표현

기존 ASTRA 재질 factory·upload·NoData/지원 범위 처리와 native GIS coverage를
사용한다. 새 화면 전체 위에 ASTRA 이미지를 덮거나 지역 밖 수치·해안 geometry를
만들지 않는다. Area와 front 합성보다 앞에 ASTRA source가 놓인다.

영역 색상은 source-bound ownership 기록이 있는 원본 held-core polygon에만
적용한다. 바깥 국토를 상대 세력 점령지로 추정하는 enemy complement를 만들지
않는다. 기존 Area contour shader에 별도 백색 중심·금빛 주변광 스타일을 전달하며
새 전선 좌표·화살표·장식용 이동 경로를 생성하지 않는다.

이는 V2의 실제 ASTRA 및 기존 Area 표현을 재사용한 연결이다. **기존 V2 scalar
winner-gain classifier와 모든 전선·군대 효과를 완전히 동등하게 구현했다는
주장은 하지 않는다.** 현재 자료에 명시된 영역 밖 소유권과 미확인 역사 부대
위치를 만들어 V2 장면을 복제하지 않았다. 선 두께 파라미터는 렌더링된 실제
픽셀 폭 측정 결과와 구분한다.

카메라 core를 변경하지 않고 원래 factory·projection·scale·layout API로 별도
chapter framing을 적용한다. 제공된 전체 geometry와 기존 표식의 보호 영역,
기존 detail lock을 검사한다. 사건 날짜+제목과 실제 snapshot 날짜는 원래 40px
glyph/annotation pass를 사용한다. 최신 실제 SwiftShader에서 검사한 5개 시점의
제목·도식 날짜 배치가 통과했다. 미검사 chapter의 모든 글꼴 조합과 전체 영상의
모바일 가독성을 승인한 결과는 아니다.

## 5. 분할 렌더링·캐시·중단 복구·합성

기존 독립 실행 관리자와 공통 GPU lease를 재사용하며, V3는 별도 작업 ID와
해시 프로필을 사용한다. 원래 claim·완료 영상·캐시를 초기화하지 않는다.
장면 결과는 실제 파일 SHA와 프레임·전체 decode 검증 이후에만 완료 캐시에
등록된다. 변경된 Scene·소스·renderer·재질·시계·경계 상태에 따라 캐시를 무효화한다.

완료한 구간을 보존하고 실패한 구간만 유한 횟수로 다시 처리한다. 기존 완료
결과도 다시 사용할 때 현재 파일 해시를 재검증한다. 중간 실패를 성공으로
표시하지 않으며, 손상 결과는 보존한 채 명시적인 복구 경로를 사용한다.

Python이 전체 프레임을 메모리에 보관하지 않는다. 기존 bounded streaming
FFmpeg·SHA·파일 복사 경로를 사용한다. 최종 합성은 H.264, 정확한 프레임 수·
순서·timestamp 및 전체 decode를 검증하고, 장면별 decoded sequence와 비교한다.
소스/metadata 경계 일치는 실제 화면 연속성 승인과 별개다.

Dropbox의 비공개 장면 복구 MP4+SHA와 신뢰할 수 있는 private anchor를 구분한다.
컨테이너가 교체되어 private ledger까지 사라진 경우 shared 파일만으로 NVIDIA
provenance를 자동 인증하지 않는다. 지속되는 POSIX ledger 또는 별도로 신뢰된
복구 anchor가 필요하다. 기존 어댑터의 파일당 4GiB 제한도 우회하지 않는다.

## 6. GPU 성능 최적화와 60분 목표

확인된 기존 ASTRA 업로드·단일 coverage cache·자원 dispose·장면 캐시 및
streaming 인코딩을 재사용했다. 측정 없이 GPU 병렬 작업을 늘리거나 해상도·
프레임 수·재질 품질을 낮추지 않았다. 새 카메라 경로는 실제 조건에 따라 추가
native redraw를 요구할 수 있으므로 오히려 비용 증가 여부를 측정해야 한다.

기존 65422의 실제 GPU 영상 성공은 사용자 보고로 존재하지만, 현재 재사용할
수 있는 NVIDIA 단계별 속도·VRAM 실측 기록은 없다. 따라서 80초 예상 제작시간·
성능 개선률·비용을 확정하지 않는다. 60분 목표에서 다른 비용이 0이라고 해도
프레임당 최대 1.5초라는 산술 상한일 뿐, 실제 성능 예측이 아니다.

기획, ASTRA 로딩·업로드, GIS/영역/전선, draw/readback, 저장, 인코딩·합성,
Dropbox 내보내기·외부 다운로드 시간을 실제 80초 실행에서 분리 측정해야 한다.
현재 전체 제작시간·평균 frame time·최대 병목·VRAM·인코딩 시간·캐시 효과와
60분 목표 달성 여부는 모두 **미검증**이다. 120초 이상은 별도 산정 대상이다.

## 7. 터미널 없는 자동 실행과 gCube 운영 경계

공식 gcube-cli 0.4.2의 저장된 증거와 기존 감사 결과를 재사용해 allowlisted
인증 read와 별도 승인 stop 어댑터를 추가했다. 실제 계정 통신·권한·SSH 접속은
검증하지 않았다. 자세한 기능별 상태는 [OPERATIONS_CAPABILITIES.json](OPERATIONS_CAPABILITIES.json),
제약과 절차는 [GCUBE_AUTOMATION.md](GCUBE_AUTOMATION.md)에 있다.

현재 보안 secret/account/workload selector와 실제 API 권한·TCP/SSH 경로가
없다. `GCUBE_API_TOKEN`은 안전한 환경 secret으로 제공되어야 하며 채팅이나
저장소에 값을 넣지 않는다. 환경 설정 초안의 저장은 실제 Publish·네트워크
적용·인증 성공을 의미하지 않는다.

공식 SSH 접속 방식의 존재와 Codex의 원격 실행 연결도 구분한다. 승인된
private-key 선택, pinned known-hosts, 실제 host/port와 TCP 허용, 유한 시간의
고정 명령 executor는 아직 연결하지 않았다. gCube 모바일 웹 터미널에 접속할
수 있다는 사실만으로 이 환경의 자동 원격 명령 실행이 가능해지지 않는다.
문서의 in-image worker 명령은 이 미연결 원격 실행기를 구현했다는 증거가 아니다.

공식 증거에서 누적 지출의 provider 강제 hard cap을 확인하지 못했다.
`maxPrice`는 시간당 가격 유래 값이고, 로컬 timeout·STOP schedule은 과금 종료
보장이 아니다. schedule PUT도 원자적 revision 조건 없는 전체 교체라 실행을
차단했다. 배포/start/register는 현재 실제 유료 실행 경로로 열지 않는다.
따라서 **계정·비용 상한·종료 정책까지 갖춘 무인 운영 완료 상태가 아니다.**

사용자가 중간 샘플이나 장면별 터미널 명령을 검수하는 운영을 목표로 삼지
않는다. 최종 80초 한 편을 검수하는 흐름이지만, 그 전에 필요한 보안 설정·
유한 비용/시간/재시도 승인과 공식적으로 가능한 실행/종료 연결은 별도로 필요하다.

## 8. Dropbox 전달 준비와 실제 전달 상태

기존 `/world-storage` export 어댑터를 재사용한다. 공개 검수 폴더에는 완성 MP4,
`SHA256SUMS`, 안전한 품질 요약만 두며 내부 source·진단·민감한 log는 분리한다.
장면 복구 파일은 비공개 recovery 단위로 보존한다.

mount 내 쓰기·readback과 실제 Dropbox 외부 동기화는 별개의 증거다. 실제
다운로드 URL로 HTTP 200을 확인하고 다운로드 SHA를 원본과 대조한 경우에만
외부 전달 완료로 판정한다. 이번 V3의 80초 MP4·실제 Dropbox URL·외부 다운로드·
모바일 재생 결과는 아직 **없다**. 저장 코드가 있다는 이유로 전달 PASS를
선언하지 않는다.

## 9. 무료 검사·실제 결함·해결 상태

[FOCUSED_TEST_RESULTS.json](FOCUSED_TEST_RESULTS.json)의 현재 기록은 새 영향
범위 **107개 고유 CPU 검사 PASS, FAIL/SKIP 0**이다. 최초 집계 이후 변경된
범위만 재검사했고 반복 실행 수를 더해 검사 수를 부풀리지 않았다. 부모의
기존 168개 전체 검사는 재실행하지 않았다. operations mock은 실제 계정·GPU
검증이 아니며 probe selector 검사도 실제 browser draw와 구분한다.

무료 CI에서 실제 확인한 차단은 다음과 같다.

| 확인된 문제 | 안전한 수정·검증 | 현재 한계 |
|---|---|---|
| 선택적으로 패키징된 이미지에는 없는 checkout alias를 source-only 검사에서 요구 | 86개 동결 closure의 축소 checkout으로 재현하고, 실제 이미지의 canonical helper + strict staged 검증 경로 사용 | [CPU_DEPLOYED_LAYOUT_REPRO.json](CPU_DEPLOYED_LAYOUT_REPRO.json)에 실제 image paired 검증 PASS 기록 |
| 실제 browser에서 `AREA_ANNOTATION_LAYOUT_BLOCKED` | 최대 다른 chapter atlas가 아닌 현재 label 측정값을 사용하고, 원래 `.place` 보호 검사 안에서 free-band/장애물 edge 후보를 추가 | 수정 후 실제 SwiftShader와 새 이미지 내부의 5개 시점 probe PASS |
| 사건 정보가 generic 설명으로 축약될 위험 | 실제 사건 날짜+제목과 활성 snapshot 날짜를 각각 원래 annotation pass에 연결 | 검사한 실제 draw에서 연결 확인; 전체 chapter·모바일 영상 품질은 미승인 |

`software_probe_production.mjs`는 실제 Chromium SwiftShader에서 다음을 통과했다.

- 실제 프레임 `0, 444, 445, 1449, 2399`의 draw/readPixels, ASTRA upload와
  source grade, 공급된 원본 좌표 및 현재 projection의 geometry safe area.
- 프레임 1449에서 camera·geometry·chapter/date 해시가 같은 BEFORE/AFTER 비교.
  실제 변경 픽셀은 **339,499개**, 기존 보호 graphic 변경과 safe area 밖 변경은
  각각 **0개**였다. 이는 스타일 변화의 계측이며 시각 품질 최종 승인이 아니다.
- 실제 작업 경계 `[200,445)` → `[445,600)`에서 source clock은 393 → 400으로
  진행했다. 전역 프레임 444와 445 각각의 분할 렌더는 같은 프레임의 비분할
  global-range 렌더와 **BIT_EXACT**였다. 경계에서 시계를 초기화하지 않았다.
- 프레임 0의 실제 native boundary support **105,979픽셀 중 변경 0개**.
  이 검사는 사건 overlay와 추가 focus가 활성화된 모든 프레임의 boundary
  보호를 증명하지 않는다.
- 빌드 전 부모 컨테이너에 새 확장 경로를 연결한 검사와 새 이미지 내부에서
  실제 probe PASS, 입력 준비 cache 재사용과
  source 불변성 확인. 7개 실제 software PNG와 SHA 증거를 CI에서 검사했다.

source frame clock과 사건 날짜를 구분하며 CPU/SwiftShader를 NVIDIA PASS로
바꾸지 않는다. 7개 PNG는 두 A/B와 다섯 시점 증거이며 7개의 독립 영상이 아니다.
해시와 검증 metadata는 영구 기록했고 PNG 자체는 CI 임시 증거로 취급한다.
runtime 필수 입력이나 사용자가 검수할 새 샘플 영상으로 제공하지 않는다.

초기 실패 run `38849732244-1`, `38850429198-1`은 보존되어 있으며 성공 증거로
사용하지 않는다. 수정 효과는 실제 성공 run `38851322860-1`에서 확인했다.
현재 V3 영상 품질은 승인하지 않았다.

## 10. 보존·보안·원격 체크포인트

기존 보호 파일 변경은 0건이다. 원본 5개 geometry의 좌표·순서·정밀도와
승인된 자료·V2 동작은 보존한다. 기존 이미지를 덮거나 GPU 검사를 우회하지
않았다. 현재 source secret scan은 default 규칙·빈 ignore·inline allow 비활성
조건에서 **실제 credential 0건**이며 [SOURCE_SECRET_SCAN.json](SOURCE_SECRET_SCAN.json)에
기록되어 있다. 성공 CI의 실제 이미지 default secret scan도 **0건**이다.
문서의 최종 저장 상태에 대한 source scan은 해당 저장 시점의 별도 기록으로 남긴다.

기록된 checkpoint A는 `92ca410e1e5e0733063aad02be11969bfd853906`이고,
preflight checkpoint는 `227257bd6925081e36bd50e51ae5893d95bbfcda`다.
실제 이미지 source commit은 **`df9a4f414fc4515b11b87258a2daa21d3f4b8e3a`**다.
build 증거는 `302b012`, 독립 pull 증거는 `d536342`에 원격 저장되어 있다.
이 보고서의 저장 커밋은 Git의 해당 파일 이력으로 식별한다. 필수 source·
fixture·계약은 namespace에 영구 저장하며 temp-only 파일을 runtime 필수
입력으로 사용하지 않는다.

## 11. 신규 GPU 후보 이미지 상태

무료 실제 SwiftShader와 source/hash/보호/보안 조건을 통과한 뒤 새 이미지를
빌드·등록하고 독립 runner에서 immutable digest pull을 검증했다. 기존 이미지와
태그는 보존했다.

| 항목 | 현재 보고 상태 |
|---|---|
| 최신 실제 SwiftShader | 빌드 전 및 새 이미지 내부 PASS, 5개 시점 |
| 신규 V3 이미지 태그 | `production-v3-e09be5d-38851322860-1` |
| 신규 immutable digest | `sha256:10f7cc1da15d5a94ddd5653c2a8d8b5f3658b8c0a0d9260cab729404d38c8deb` |
| 실제 image inventory·포함 source 버전 | strict **272개**: 부모 248개 보존 + 신규 24개, unexpected 0; source `df9a4f414fc4515b11b87258a2daa21d3f4b8e3a` |
| 독립 digest pull·무결성 | PASS, 별도 runner의 실제 digest pull과 strict inventory 검사 |
| 실제 NVIDIA 80초 렌더 | 미실행 |

실제 실행할 후보 참조는 다음과 같다.

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:10f7cc1da15d5a94ddd5653c2a8d8b5f3658b8c0a0d9260cab729404d38c8deb
```

`linux/amd64`, 이미지 크기는 1,581,978,049바이트이며, source manifest SHA는
`e1efd170f05d297ba222995af2557dc8d5d338f870c7d92c5a82f456f5d804e6`이다.
이미지·build·pull 원본 증거는 [IMAGE.json](IMAGE.json)에 연결되어 있다.

첫 실제 실행용 [FIRST_PRODUCTION_REQUEST.json](FIRST_PRODUCTION_REQUEST.json)은
이 이미지에 연결된 [FIRST_PRODUCTION_80S_PLAN.json](FIRST_PRODUCTION_80S_PLAN.json)을
기록한다. canonical plan SHA는
`b5c7b222122f7be0219cb745cab513a5a18ce9c211e2ced4347c146ba2ffe384`,
실제 plan 파일 SHA는
`6fb40abd4970c2595877c4bfb469d8ad0d62e552a03651748b8a1c41a993c28b`다.
software fixture와는 image binding/status 필드만 다르고 geometry·타임라인·
카메라·재질·chapter 입력은 같다. plan/image SHA 연결은 유료 실행 승인이나
역사 자료의 정밀도를 높이는 인증이 아니다.

## 12. 남은 조건·사용자 다음 행동·판정

현재 개발 증거와 실제 제품 완료를 분리한다. 12장 기획·범용 타임라인·V3 연결·
캐시/복구·합성/전달 호출 및 집중 CPU 검사, 실제 SwiftShader 통합과 후보 이미지
등록·독립 pull은 완료되었다. 실제 NVIDIA 80초 MP4, 60분 목표, 실제 Dropbox
외부 전달·모바일 재생·영상 품질·사용자 승인은 미완료다. 공식 원문 접근은
여전히 proxy CONNECT 403으로 차단되어 있고 일곱 사건 날짜의 추가 전선 자료도
없다. 정밀한 12단계 실제 전선 재현이나 완전한 무인 운영으로 소개하지 않는다.

1. 확정된 새 이미지와 plan SHA를 검수한다. 5개 snapshot 참고 영상으로
   진행할지, 정확한 추가 전선 자료가 필요한지 결정한다. 없는 자료를
   영상 연출이나 AI 추론으로 보충하지 않는다.
2. 환경 설정을 검수·Publish하고 안전한 계정 secret/selector를 제공한 다음,
   허용된 read-only 계정·workload·가격·종료 정책 검사를 한다.
3. 실제 GPU 단가/통화, 최대 비용·wall time·재시도·만료시각과 provider 측
   비용 통제/종료 조건을 사용자 승인으로 확정한다. 현 누적 hard-cap 제약을
   해결하지 않은 채 자동 유료 start를 실행하지 않는다.
4. 승인된 연결 경로가 준비된 뒤 image-bound 단일 80초 작업을 실행한다.
   사용자는 장면별 샘플이 아니라 완성본 한 편을 검수한다. 정확한 worker
   명령과 조건은 [OPERATOR_EXECUTION.md](OPERATOR_EXECUTION.md)에 있다.
5. 실제 MP4 전체 decode, 2,400프레임·1080×1920·30fps·H.264·무음,
   source/전선/날짜/카메라·모바일 품질, Dropbox HTTP 200 및 다운로드 SHA,
   실제 작업 종료·과금 기록을 각 증거로 확인한다.

판정: **FREE_VALIDATED_GPU_CANDIDATE_READY_DATA_ACCOUNT_BUDGET_PENDING**.
유료 GPU 배포·NVIDIA 실행·80초 영상 생성·FINAL 승격은 수행하지 않았다.
추가 역사 자료, 실제 계정·접속, 승인된 비용·종료 정책을 해결한 뒤 실제 영상
제작으로 연결한다. 최종 사용자 영상 승인 전 FINAL을 실행하지 않는다.
