# WORLD ENGINE — Universal Auto Video V2 구현 상태

안전한 장편 실행 후보 구현·무료 검증·신규 이미지 등록·독립 pull을 완료했다.
최종 후보는 run `38844084599-1`, source `311a921`이다. 집중 검사 168개,
실제 SwiftShader draw/readPixels, 실제 인접 scene cut 419/420, native 경계 픽셀,
248개 이미지 파일 무결성 및 Secret Scan 0건을 확인했다.
**80초 NVIDIA MP4와 완전한 범용 제품은 아직 완료되지 않았다.** 지시서 8·12절의
유료 GPU 별도 승인 조건과 현재 계정 연결·단가 미확인 때문에 GPU 작업은 실행하지 않았다.
60분 목표, 외부 Dropbox 전달과 영상 품질 승인은 미검증이다.

기준은 `c1e9c099b22a8db1c5f21e7b029422e82f8efd33`, 작업 브랜치는
`development/universal-auto-video-v2-20261016`이다. 기존 이미지
`sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5`는
변경하지 않고 새 실행 계층의 부모로 사용한다.

## 1. 기존 기능 재사용과 중복 검사

기존 `compileScenePlan`, Scene V1 검증기, Area V3의 polygon·front 생성/평가와
GPU overlay, V5 native camera, ASTRA CPU 공급자·캐시·업로드·재질, Reference V2
source grade, 원래 FFmpeg 인코딩 설정, 저장소 어댑터, GPU admission과 공통
capture lease를 재사용한다. 기존 renderer나 camera solver를 복사하지 않는다.

통합 경로에서 원래 Area V3 compiler의 계획당 1,200프레임 상한을 확인했다.
이를 올리거나 장편을 원래 Area plan으로 위장하지 않았다. 새
`long_area_timeline.mjs`가 공급된 상태별로 원래 compiler/validator의 정적
1프레임 계획을 만들고, 원래 evaluator의 geometry·projection·line primitive를
재사용한다. 장편의 전역 Scene clock과 같은 quintic 가중치만 외부 확장으로
연결한다. 따라서 전체 장편 timeline까지 원래 Area compiler를 그대로 실행한다고
표시하지 않는다. 원본 geometry, shader, arc-length evaluator와 기존 cap은 유지한다.

기존 one-shot 실행 관리자는 고정 150프레임/7파일 결과 계약을 사용한다.
여러 장면을 처리하는 ledger만 새 namespace에 추가하고, PID/boot/start-time
확인과 저장소 보안 검증 등 기존 기능을 연결했다. 과거 claim·결과·완료 기록을
초기화하지 않는다. 자세한 출처와 SHA는 `REUSE_AUDIT.md`, `HISTORY_AUDIT.json`,
`SUPPLEMENTAL_SOURCES.json`에 기록한다.

## 2. 80~600초 범용 길이와 Scene 계약

`contracts.py`는 `durationSeconds × fps`를 정확한 정수 프레임으로 검증한다.
반올림으로 프레임을 추가하거나 버리지 않는다. 모든 장면 범위는
`[startFrame, endFrame)`이며 같은 전역 시간축을 사용한다. Scene 경계에서
camera·event 시간을 0으로 되돌리지 않는다.

| 길이 | 30FPS 프레임 | 이번 확인 범위 |
| --- | ---: | --- |
| 80초 | 2,400 | 실제 원본 자료 기반 기획·native 바인딩·분할 계약 |
| 120초 | 3,600 | 동일 코드의 타임라인·분할·합성 계약 검사 |
| 180초 | 5,400 | 동일 코드의 타임라인·분할·합성 계약 검사 |
| 300초 | 9,000 | 동일 코드의 타임라인·분할·합성 계약 검사 |
| 600초 | 18,000 | 동일 코드의 타임라인·분할·합성 계약 검사 |

전체 프레임 이미지 배열을 만들지 않는다. 장면별로 capture·encode하고 완료된
압축 segment를 보존한다. 원래 native camera fixture가 1080×1920/30FPS이므로
다른 FPS·해상도는 기획 계약으로 표현할 수 있지만, 실제 native 준비 단계에서
호환되지 않는 출력은 명시적으로 거부한다. 긴 영상의 NVIDIA 실행 성공이나
600초 결과 파일의 저장 한도 충족은 아직 검증하지 않았다.

## 3. 자연어 입력과 Scene JSON 생성

`planner.py`는 한국어/영어 주제에서 초·분·FPS·해상도·화면비를 읽고, 충돌하는
설정은 거부한다. 해시로 묶인 외부 catalog에서 주제를 선택한 뒤 기존 planner에
공급된 사실과 `scene_timing`을 전달한다. 외부 AI는 연결하지 않았으며
`externalAIConnected: false`를 기록한다. 알려지지 않은 주제는 자료 필요 상태로
종료한다. 자유로운 사실 조사나 모든 주제의 자동 기획이 완성되었다고 주장하지 않는다.

첫 catalog는 기존 한국전쟁 5개 도식적 상태만 사용한다. 발생, 부산 교두보,
북진, 서울 철수, 정전의 순서와 원본 geometry를 보존한다. 역사 자료 3종은
기존의 curated chronology 검토 기록이며, 본문 수집은 HTTP 403으로 실패했다.
새 `sourceManifest`에는 이 원래 기록과 null 본문 해시를 그대로 보존한다.
보간된 화면은 두 도식 상태 사이의 시각적 전환이며, 해당 날짜의 실제 점령선을
새로 확인했다는 뜻이 아니다. 정밀 일별 전선이나 실제 부대 경로 요청은 차단한다.

`fixtures/PLAN_80S.json`은 2,400프레임을 12개 작업 단위로 분할한 실제 첫 기획이다.
60프레임 도착, 60프레임 초기 표시, 각 555프레임의 네 상태 전환, 60프레임 최종
hold를 사용한다. 이 배분은 영상 시간이며 역사적 기간이 동일했다는 주장이 아니다.
체크인된 이미지 내부 fixture는 자기 image digest 순환 의존을 피하도록
`IMAGE_BINDING_REQUIRED`를 유지한다. 최종 이미지에 고정한 별도
`FIRST_PRODUCTION_80S_PLAN.json`과 canonical SHA를 영구 저장했다.
native 바인딩의 `READY`는 CPU 원본·설정 정합 검사 결과이며 유료 실행 승인이 아니다.

## 4. 분할 렌더링·캐시·자동 합성

`orchestrator.py`, `render_adapter.py`, `long_capture.mjs`는 전역 장면 범위와
원본 바인딩을 고정하여 장면 단위로 실행한다. `cache.py`는 Scene, source,
renderer/image, camera, timeline, material, encoder와 인접 경계 계약을 키에
포함한다. 완료 영상을 다시 해시 검증한 경우에만 재사용하고 실패한 결과에는
성공 receipt를 만들지 않는다.

현재 전역 legacy/native 바인딩은 보수적이다. 해당 바인딩이 바뀌면 관련 전체
segment가 무효화될 수 있다. 모든 변경에서 수정된 한 장면만 재렌더링한다고
과장하지 않는다. 경계 상태 변화는 인접 장면도 무효화한다.

`compose.py`는 입력 segment의 코덱·해상도·FPS·PTS·프레임·전체 디코딩을 검사한다.
동일한 코덱과 시간축 조건이 검증된 경우에만 무재인코딩 concat을 사용한다.
그 외에는 조건을 만족하는 입력을 lossless H.264로 정규화한다. 최종 전체 영상의
각 decoded RGB hash가 원래 segment 순서와 일치해야 성공한다. 실제 짧은 CPU
FFmpeg fixture의 합성 검사는 수행했지만, 80초 역사 영상의 최종 합성은 아직 없다.

## 5. GPU 최적화와 실제 근거

확인 가능한 중복부터 줄였다. ASTRA CPU 준비와 원본 검증은 작업 단위로 재사용하고,
GPU source upload는 장면/session 생성 시 한 번 수행한다. 같은 camera/reveal의
native coverage와 boundary snapshot은 한 항목 캐시를 사용한다. GPU texture를
80초 전체에 걸쳐 한 context에서 재사용한다고 주장하지 않는다. 현재 각 장면은
독립 session이므로 장면 간 GPU upload 비용은 남는다.

장편 clock은 시간을 1,200프레임 안으로 압축하거나 정수 frame으로 재양자화하지
않는다. 실제 global frame에서 원래의 `(frame-start)/(duration-1)`과 quintic
식을 사용하고, 초기 전선은 기존 V1 arc-length reveal evaluator로 평가한다.
후속 전환에서 이미 완료된 line reveal을 다시 시작하지 않는다. 원래 Area 상태
전환처럼 공급된 두 정적 snapshot의 alpha를 바꾸며, 새로운 전선 좌표나 일별
점령 경로를 생성하지 않는다. 정적 상태의 projected controls 캐시는 실제
projection 함수와 key에 묶이고 projection history는 한 항목만 유지한다.

초기 로컬 14초 fixture의 event 360프레임에서 원래 Area evaluator와 새 clock을
비교했고, 최종 CI에서는 동일한 패키지 자료로 생성한 14초 계획의 event 378프레임
전체를 비교했다. area/front geometry·alpha·reveal·선택 상태·날짜·hold가 정확히 일치했다.
독립 검수에서도 projection 없음/비선형 projection의 추가 56개 비교가 일치했다.
이 결과는 실제 CPU control 비교이며 GPU pixel BIT_EXACT나 장편 영상 품질 판정은 아니다.

`native_boundary_restore.mjs`는 source 합성이 덮어쓰는 원래 Boundary/Glow를
실제 native 경계 지지영역 안에서만 복구한다. opaque native canvas에 맞는
RGB8 GPU snapshot 한 장은 1080×1920에서 6,220,800 bytes다. CPU 전체 이미지
snapshot이나 프레임 history를 보관하지 않는다. 이 좁은 보호 corridor에는
기존 terrain도 남으므로 해당 부분이 순수 ASTRA라고 표시하지 않는다.

실제 원본 3종을 읽은 CPU 통합 검사는 `REAL_CPU_RUNTIME_INTEGRATION.json`에
기록되어 있다. 148개 source binding과 2,400프레임/12장면 계약을 확인했으며
browser/GPU 시작과 capture frame은 0이다. 이 CPU 로딩 수치는 GPU upload,
프레임 throughput, GPU 메모리나 전체 제작시간을 예측하지 않는다.
NVIDIA 병목이 측정되기 전에는 병렬 GPU 실행이나 readback 알고리즘 변경을 적용하지 않았다.

## 6. 터미널 없는 실행 가능 범위

공식 저장 자료에는 gCube의 workload 관리·배포·종료·schedule과 CLI SSH 명령
실행 경로가 있다. 하지만 이번 계정의 인증·SSH 접근·가격·schedule 권한은
확인되지 않았다. 공개된 인증 없는 rendering API는 추가하지 않는다.

새 작업은 detached worker로 실행되며 실제 PID identity와 상태를 기록한다.
터미널 종료 모의 검사는 통과했지만, 현재 Codex가 사용자 계정의 gCube를
완전히 자동 운영할 수 있다는 뜻은 아니다. 공식 control plane의 자격 증명과
네트워크 권한, workload 식별자, 사용자 비용 승인이 추가로 필요하다.

## 7. 실패 복구와 중복 실행 방지

개별 작업 lock과 기존 공통 GPU lease를 함께 사용하고 살아 있는 작업의 PID,
boot ID, start time을 확인한다. 실패한 scene만 새 attempt로 처리하며 기존
artifact·receipt·claim을 삭제하지 않는다. 같은 작업의 resume에는 원래 마감과
사용된 retry 횟수를 유지한다. 허용 retry는 전체 작업 기준 0~2이고 기본은 0이다.

터미널 단절과 컨테이너 교체는 다르다. 컨테이너 재시작 후 자동 렌더링은 없고
명시적 resume이 필요하다. private ledger/cache는 적절한 POSIX 영구 볼륨이 없으면
컨테이너 로컬이다. Dropbox에 내보낸 segment는 보존되지만 공유 JSON을 private
GPU provenance로 신뢰해 자동 편입하지 않는다. 컨테이너 교체 후 자동 복구에는
유지된 private ledger 또는 별도로 신뢰할 수 있는 운영자 hash/provenance 기준이 필요하다.

## 8. Dropbox 전달 준비

기존 `/world-storage` 어댑터의 경로 격리·no-follow·UID/GID·private directory·
exclusive copy·fsync·mounted readback 검사를 재사용한다. 최종 Public Review는
MP4, `SHA256SUMS`, 민감한 정보가 없는 `QUALITY_SUMMARY.json`만 포함한다.
원본 데이터·내부 진단·작업 로그는 넣지 않는다.

원래 어댑터의 파일당 4GiB 한도는 유지한다. 실제 출력 크기가 이를 넘으면 해당
export는 차단하며, 긴 영상 계약을 이유로 보안 제한을 제거하지 않는다.
현재 mount readback을 검증하는 코드와 실제 Dropbox HTTPS 다운로드의 HTTP 200·
byte count·SHA를 검증하는 코드는 준비되어 있지만, 새로운 80초 결과와 외부 URL은 없다.
mock HTTPS 성공은 외부 전달 완료로 표시하지 않는다.

## 9. 무료 검사와 보안 검사

최종 CI는 **168 PASS: Python 137 + Node 31**, 15개 집중 명령 모두 exit0이다.
부분 재검증·독립 검수를 중복 합산하지 않았다. 기존 완료된 전체 104/151/233개
suite는 반복하지 않았다. 실제 짧은 CPU FFmpeg·storage readback·PTY 종료 검사와
mock hardware 검사를 실제 NVIDIA 검사로 표시하지 않는다.

최종 run의 pre-build 및 built-image 두 환경 모두 실제 Chromium/SwiftShader에서
0/419/420/1200/2399 프레임을 draw/readPixels했다. 실제 fixture의 서로 다른
`scene-0003 [120,420)` frame419와 `scene-0004 [420,675)` frame420을 각각
원래 전체 시간축과 비교하여 RGBA BIT_EXACT를 확인했다. host CI는 원본 plan SHA,
두 scene ID·범위·활성 전환·pixel hash를 독립 검증한다. native Boundary 지지영역의
변경 픽셀은 표본 두 frame 모두0이다. active 표본 geometry는 viewport와 safe area에
모두 들어온다. 전체 2,400프레임의 NVIDIA 영상 검사라는 뜻은 아니다.

중간 run `38843019699-1`의299/300은 같은 scene 안이었다. 기존 장면 경계 PASS
주장을 철회하고 해당 등록 이미지를 `NOT_FINAL_CANDIDATE`로 보존했다.
`SUPERSEDED_IMAGE_38843019699.json`에 범위를 명시했다. 실패·중간 기록을 삭제하지 않았다.

최종 실제 이미지의 기본 Gitleaks 검사 결과는0건이다. 이전 checksum/파일명 오탐은
`SECRET_SCAN_CLASSIFICATION.json`에 분리 기록했다. 검사 규칙·ignore·allowlist를
완화하지 않고 의미에 맞는 모듈 이름으로 수정했다.
최종 소스·보고서·workflow 검사는 `SOURCE_SECRET_SCAN.json`, 원본 보호와 실제
이미지 Manifest/실행 계획 대조는 `FINAL_INTEGRITY_CHECK.json`에 기록했다.
영구 저장 파일 전체의 해시는 `SHA256SUMS`로 확인한다.

## 10. V2·FINAL 보호와 실제 시각 경로

기존 FINAL·V4·camera·ASTRA·전선·영상 파일은 수정하지 않는다. 구현은 새 recovery
namespace와 독립 workflow/profile에 추가한다. 최종 strict 이미지 검사에서 원래160개 파일과 frozen V2 57개를 검증했다.
전체 기존 tracked 파일 변경0건이며 기존 정상 이미지와 과거 claim을 유지한다.

현재 역사 실행 경로는 `REFERENCE_V2_SOURCE_WITH_AREA_V3`다. 기존 ASTRA/V2
source material을 원래 Area V3 영토·전선에 연결하고, 원래 geographic marker와
label을 다시 그린다. camera는 기존 V5 도착 후 lock 유지다. 되돌아가는 역사
polygon 상태를 현대 가상 장면의 일방향 scalar gain으로 대체하지 않았다.

따라서 다음은 이번 역사 경로에 적용하지 않는다: V2 scalar gain, V2 scalar
백색·금빛 전선, V2 unit scale, V2 focus-hold camera, 장면별 새로운 사건 추적 camera.
검증된 역사적 부대 위치가 없으므로 국기·군대 표식도 임의로 생성하지 않는다.
기존 V2 F는 asset/data closure의 출처이며 모든 F 화면 효과가 실행된다는 표시가 아니다.
이 차이는 `visualReuse`에 기록되어 있다. 완전한 V2 연출 동등 품질은 아직 승인하지 않는다.

## 11. 신규 이미지 태그와 digest

태그: `universal-v2-c1e9c09-38844084599-1`
이미지: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:5f17537fa8e5387de39ed8999e4c8d7ce2fe8a3593a71a5a3c1ae033f22dd014`
소스: `311a92137d00ba88220c1caa243c9ff0389e4121`
Manifest SHA: `982cf2c0a5f435afe936605c0aeb76cbf40b6990da41d27c0ea0bd5ef22eb756`

빌드·등록 및 별도 runner의 immutable digest pull이 PASS다. 실제 생성된 Manifest
바이트를 `UNIVERSAL_FILES.json`에 그대로 저장했으며 docs HEAD에서 재생성하지 않았다.
`IMAGE.json`, `runs/38844084599-1/build.json`, `pull.json`이 근거다.

이전 `universal-v2-c1e9c09-38843019699-1`은 보존하되 최종 후보로 권장하지 않는다.
사용할 후보는 위388440 digest다. NVIDIA 영상 품질 PASS나 FINAL Baseline은 아니다.

## 12. 80초 제작시간 추정 근거

확인된 NVIDIA 단계별 시간이나 총 VRAM 측정은 없다. 사용자에게서 전달된 기존
5초 하드웨어 성공은 존중하되, 이를 80초 처리시간으로 선형 확대해 확정하지 않는다.
기획, ASTRA 로딩, upload, GIS/Area 계산, draw/readback, PNG 기록, FFmpeg,
합성, export, 외부 다운로드의 계측 필드를 준비했다.

2,400프레임을 3,600초에 끝내려면 기타 비용이 전혀 없을 때도 평균 최대 1.5초/
프레임이어야 한다. 실제 허용 예산은
`(3600 - 실측된 비렌더링 전체 비용) / 2400`이다. 이는 목표의 계산식이며 실제
평균 렌더링 시간이나 완성 예상시간이 아니다. GPU 단가를 확인하지 않아 비용을 계산하지 않았다.

## 13. 60분 목표 검증 상태

**NOT MEASURED / NOT ACHIEVED YET.** 80초 NVIDIA 영상이 아직 실행되지 않았으므로
전체 제작시간, 평균 프레임 시간, 최대 병목, 캐시 개선률, VRAM, 인코딩·Dropbox
외부 검증 시간을 확정할 수 없다. 120초 이상 제작시간도 별도 실측이 필요하다.

## 14. 실제 GPU에서 남은 검사

승인된 RTX 4080 SUPER 16GB에서 80초 작업을 한 번 실행하고 다음을 확인해야 한다.
장면별 NVIDIA admission과 WebGL2 upload/draw, 실제 ASTRA·NoData·해안·영토·
Area 전선의 시각 품질, 전체 2,400프레임과 경계 연속성, VRAM/공유 메모리,
전체 MP4 디코딩, 1080×1920·30FPS·H.264·무음, Dropbox 외부 HTTP 200·SHA,
모바일 재생과 사용자 완성본 검수다. 사용자에게 중간 5초 샘플 검수를 요구하지 않는다.

## 15. 확인한 문제와 해결 또는 제한

- 무료 run `38839536262-1`은 배포 이미지에 원래 저장소의 helper 경로가 그대로
  존재한다고 가정해 `storage.py` import가 실패했다. 새 adapter에서 실제 배포된
  frozen helper alias를 찾고 정확한 SHA와 module origin을 확인하도록 수정했다.
  발견된 배포 파일이 손상되거나 symlink이면 다른 경로로 숨겨 넘어가지 않는다.
  테스트 임시 출력도 읽기 전용 `/opt` 소스가 아닌 trusted private 경로로 분리했다.
- 무료 run `38840090587-1`은 실제 browser 경로에서
  `PLANNER_SCENE_NON_CANONICAL_GEOMETRY`로 실패해 이미지 빌드 전에 차단됐다.
  Python canonical JSON의 geometry key 순서와 원래 validator의 JSON 순서 비교가
  충돌한 것이 원인이다. 원래 입력 SHA를 먼저 검증한 뒤 새 serialization adapter가
  key 순서만 복원한다. 좌표 순서·수치·source·timeline은 바꾸지 않으며 unknown
  metadata를 버려 통과시키지 않는다. 이 두 실패 run과 build 미실행 기록은 보존한다.
- key 순서 복구 후 드러난 원래 Area 계획의 1,200프레임 cap은 상한 변경 대신
  위의 외부 global clock으로 처리했다. 정적 endpoint는 기존 Area 검증을 통과하고,
  원래의 quintic alpha와 arc-length reveal을 재사용한다. 실제 장편 프레임을
  단축된 프레임 번호로 매핑하지 않는다. 이 수정 후 실제 SwiftShader와 이미지
  등록은 run `38843019699-1`에서 실행됐으나, 아래 경계 검증 범위 결함 때문에
  그 중간 이미지는 최종 후보 자격을 부여하지 않았다.
- run `38843019699-1`의 299/300은 같은 `[120,420)` 장면 안의 인접 프레임이다.
  실제로 측정한 pixel 일치를 보존하되 장면 cut 연속성 주장에서는 제외했다.
  probe가 실제 split plan에서 서로 다른 인접 장면을 선택하고, host CI가 다시
  그 관계를 독립 확인하도록 수정했다. 최종 run `38844084599-1`에서 실제
  419/420 장면 cut의 pre-build·built-image RGBA 일치를 확인했다.
- 기존 one-shot 150프레임 계약으로 장편을 처리할 수 없어 독립 coordinator와
  범용 scene capture를 추가했다. 기존 one-shot 코드는 변경하지 않았다.
- 기존 renderer/source 조합에서 source pass가 native Boundary/Glow를 덮는 문제는
  실제 native 경계 corridor만 GPU snapshot으로 복구하는 확장으로 처리했다.
  opaque canvas와 호환되지 않는 RGBA8 대신 RGB8을 사용한다.
- 기존 planner의 source 정규화에서 누락되는 원래 403/null body hash를 새 outer
  sourceManifest에 보존했다. 단순 schema PASS를 사실 검증으로 표시하지 않는다.
- 무제한 topic, 정밀 일별 역사, 역사 부대 위치, 새 장면별 camera 연출은 현재
  자료/바인딩 범위를 넘으므로 명시적으로 제한했다. 허위 사실이나 임의 위치를 추가하지 않는다.
- 전역 source 변경 시 캐시가 넓게 무효화되는 점과 컨테이너 private ledger 소실
  이후 자동 복구 제한은 공개했다. 보안·정합성을 줄여 캐시 재사용률을 높이지 않는다.
- gCube의 계정 연결·단가·정지 권한·실제 Dropbox 동기화는 아직 외부 검증 항목이다.
  로컬 render timeout은 GPU 과금 종료를 보장하지 않는다.

## 16. 사용자에게 필요한 정확한 다음 행동

제공된 immutable image와 `FIRST_PRODUCTION_80S_PLAN.json`을 기준으로
실제 GPU 실행 승인 범위를 정해야 한다. workload/account, 확인된 GPU 단가와 통화,
최대 비용, 최대 wall time, retry 상한과 승인 만료를 명시해야 한다. 인증은 승인된
secret 설정으로만 제공하며 채팅·Scene JSON·이미지·공개 폴더에 기록하지 않는다.

터미널 없는 실행에는 공식 gCube CLI/API와 SSH 접근을 가진 trusted worker,
필요한 네트워크 허용과 workload 식별자가 추가로 필요하다. private ledger의
지속 보존 또는 신뢰된 복구 기준, 기존 Dropbox `/world-storage`, 공유 메모리,
normal startup, NVIDIA graphics/utility 설정을 확인한다. 공식 STOP schedule을
사용할 경우 기존 schedule을 보존하고 실제 정지 상태를 확인해야 한다.

이번 개발 작업은 유료 GPU 실행을 승인하지 않는다. 실제 80초 완성본과 외부
다운로드를 확인한 뒤 사용자가 최종 영상을 검수한다. FINAL 승격과 다음 개발은 자동 실행하지 않는다.

## 최종 실행 경계

`FIRST_PRODUCTION_REQUEST.json`은 검증된 fixture와 실제 rendering 입력이 같고
image 바인딩만 추가됐음을 기록한다. `OPERATOR_APPROVAL_TEMPLATE.json`은
`approved:false`이며 미확정 단가·비용·만료를 null로 둔다. 실행 승인이 아니다.
계획 파일을 UID/GID1000의 private 경로로 복사한 뒤 운영자 승인 파일을 설정한다.
사용자가 GPU 터미널에서 개별 장면을 직접 실행하도록 요구하지 않는다.
계정 연결 후 trusted control-plane worker의 공식 인증 SSH로 detached start/status를
실행하는 절차는 `OPERATOR_EXECUTION.md`에 있다. 현재 계정 자동 제어·과금 종료는
연결되지 않았으며 먼저 read-only 권한·단가·STOP 일정을 확인해야 한다.

판정: **UNIVERSAL_VIDEO_V2_GPU_CANDIDATE_READY_PRODUCT_INCOMPLETE**.
다음: 보안 계정 연결 및 실제 단가·최대 비용·시간·재시도 상한 승인.
이번 작업은 여기서 멈추며 유료 GPU 실행·FINAL 승격을 자동 진행하지 않는다.
