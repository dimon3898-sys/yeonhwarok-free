# 일본 6초 독립 검수 및 인수 복구 결과

기술적 범용성은 **일본 단일 장면·도쿄→교토 예시 경로·CPU 6초 범위에서 PASS**다. 저장된 영상의 독립 프레임 시각 검수는 **PASS_WITH_NOTES**다. **사용자 최종 영상 품질 승인은 PENDING**이며 자동 승격하지 않았다.

## 작업 기준과 재사용

- 인수 HEAD: `949f1857c419d5dc2c71c2abb604845a625c5112`
- 브랜치: `fix/reference-6s-formal-admission-20261113`
- 기존 Actions: [43384049821](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/43384049821), completed/success, attempt 1.
- 실행 소스: `58514a75571dd183d2c15e32f9f70928d11368cd`.
- 기존 컴파일, CPU 180프레임, 1080×1920·30fps·6초·H.264, 전체 디코딩 PASS를 재사용했다. 원본 영상·JSON·렌더러·기존 레퍼런스 사용자 PASS는 변경하지 않았다.
- 검수 영상: [기존 VIDEO.mp4](../cpu-a1/VIDEO.mp4).
- 영상 SHA256: `a767fa9b3d83d931422593f0d7315d71ae9036e42ab403001e7804cd41af8c78` — 인수 시점 값과 일치.
- 기존 성공을 무효화할 증거는 발견되지 않았다. 기존 검사·렌더·컴파일을 재실행하지 않았다.

## 실제 화면 확인

원본 PNG 000·090·179와 기존 MP4에서 읽은 000~179 전체 프레임의 축소 화면, 주요 구간 17개 원해상도 크롭을 직접 확인했다. 프레임 번호는 0부터 시작한다. MP4는 읽기만 했고 새 영상 인코딩이나 렌더링은 하지 않았다.

| 항목 | 결과와 근거 |
|---|---|
| 지도·해안선 | PASS. 일본 육지·해안선·지형이 이어지며 지도 누락 사각형이나 검은 화면이 보이지 않음. |
| 도쿄·교토 위치 | 제공 좌표 기준 PASS. 도쿄 핀 끝은 간토·도쿄만 부근, 교토 핀 끝은 간사이 내륙에 고정. 거리·건물 수준 정확도는 주장하지 않음. |
| 경로 점진 표시 | PASS. 60~61은 선이 아직 없고 62부터 도쿄 쪽에서 출현, 65·70·75·80·85를 거쳐 89에 교토까지 연결. 실제 항공노선이 아닌 예시 연결임. |
| 카메라 | 프레임 연속성 검수 PASS. 0~59 도쿄 방향 이동·확대, 59~119 유지, 119~149 교토 방향 이동·확대, 이후 유지. 프레임 사이 순간 이동은 관찰되지 않음. |
| 장면 전환 | 단일 장면·`transitions=[]`로 다중 장면 전환은 해당 없음/NOT_VERIFIED. 내부 연출 경계 59/60·89/90·119/120·149/150의 화면 연속성은 확인. |
| 검은 화면·깨진 프레임 | 전체 180프레임 축소 화면과 주요 원본/크롭에서 발견되지 않음. |
| 마지막 30프레임 | 시각적 정지 PASS. 원본 렌더 데이터의 150~179 해시는 1개로 동일. 손실 압축 MP4의 디코딩 RGB 해시는 30개로 다르므로 픽셀 완전 동일을 주장하지 않음. 150 대비 최대 평균 채널 차이는 255단계 중 약 0.127, 개별 채널 최대 차이는 26. 화면 구성·위치의 움직임은 보이지 않음. |
| JSON 연출 일치 | PASS. 카메라 키프레임, 한글 도시명, 도쿄 CONTEXT/교토 HERO 핀, 경로 방향과 마지막 정지가 일치. |

검수 화면: `ALL_FRAMES_000_029.jpg`부터 `ALL_FRAMES_150_179.jpg`까지 6장, `ROUTE_DETAIL_1.jpg`~`3.jpg`. 경로 상세 크롭에서 일부 글자가 잘린 것은 검수용 크롭 영역에 의한 것으로 원본 영상의 글자 잘림을 뜻하지 않는다. 사용자 기기의 실시간 재생 감각은 NOT_VERIFIED다.

## 품질 메모와 판정 범위

1. 교토 HERO 핀이 커서 주변 지형을 가린다. 입력 JSON이 지정한 디자인과는 일치한다.
2. 이동체·방향 화살표가 작고 경로와 같은 노란색이어서 휴대폰 화면에서 구분이 약하다.
3. 넓은 구도에 바다 여백이 많아 도시 간 경로가 화면에서 작게 보인다. 두 번째 카메라 이동은 첫 이동보다 빠르다.

이는 시각적 보완 의견이며 확인된 렌더 실패는 아니다. 변경이나 재렌더를 수행하지 않았다. 일본 지리·경로 유형의 성공을 역사·전쟁·재난·장편·다중 장면·임의 지역·일본 NVIDIA 출력 전체의 성공으로 확대하지 않는다.

## 기존 진단 기능의 실제 범위

| 영역 | 확인된 구현 | 한계 |
|---|---|---|
| 실패 단계·코드 | CPU harness의 stage/originalMessage/stack, worker phase, GPU operation/frame/firstFailure/cleanupFailure | CPU harness 일부 단계는 큰 범주로 묶임. |
| JSON 입력 | INVALID·CONFLICT·UNSUPPORTED·NEEDS_INPUT 및 필드·이유·수정 예시 | 정해진 입력 계약과 문법 범위. 모든 자연어 이해 기능이 아님. |
| 지도·자료 | 소스/자산/카탈로그 SHA, 좌표, 지형 범위, 카메라 coverage, 캐시 무결성 | 역사적 사실의 진실성 자동 인증과 구분. |
| CPU 오류 | 진행 로그, 브라우저 오류, receipt, 프레임 증거, timeout/cleanup/media 오류 | early preparation은 capture receipt 생성 try 바깥. 외부 harness/log에 의존하는 경로 존재. |
| GPU 기록 | WebGL·source·draw·readback·PNG·encoder·export·cleanup 단계, atomic checkpoint, 안전한 진단 내보내기 | 공개 export는 허용된 코드와 안전한 정보만 보존. 모든 원문·스택이 보존되지는 않음. |
| 자동 원인 판정 | 알려진 코드와 오류 범주 매핑, 미분류 상태 표시 | **GPU 일반 근본 원인 자동 판정은 NOT_VERIFIED**. |
| 영구 보존 | 원격 Git 증거, Actions artifact, 실행 중 checkpoint mirror와 cleanup 후 export | 마운트 쓰기 성공은 외부 백업 증명이 아니며 삭제된 컨테이너 복구를 보장하지 않음. |

기존 G1 기록의 14개 CPU 계약 사례와 실제 과거 GPU incident `7001b1f3` 기록을 읽었다. G1은 `gpuRootCause=UNKNOWN`, `gpuExecuted=false`를 명시한다. 과거 GPU 기록에도 `UNCLASSIFIED_EXCEPTION`과 누락 증거 플래그가 있다. 이를 최신 GPU 전체 오류 진단 PASS로 승격하지 않았다.

확인된 최소 보완 범위는 `DIAGNOSTICS_AUDIT.json`에 남겼다. 이번에는 진단 기능을 재개발하지 않았다.

- 일본 workflow가 원래 SHA256SUMS의 `REQUEST.json`, `RUNTIME.json`을 보존 목록에 포함하지 않았다. REQUEST는 현재 `RUNTIME_REQUEST.json`과 해시가 완전히 같아 대응할 수 있다. 준비된 RUNTIME 스냅샷은 미보존/NOT_VERIFIED이며 새로 만들지 않았다.
- 입력 파싱·초기 준비가 일부 try 바깥에 있어 구조화된 실패 파일이 항상 생성되지는 않는 정적 코드상 한계가 있다.
- CPU worker는 자식 프로세스 실패를 일반 코드로 기록하는 경로가 있다. 최소 개선은 기존 bounded receipt 오류 연결이며 대규모 진단 재작성은 필요하지 않다.
- 이 보존/진단 한계는 기존 MP4의 이번 시각 검수를 차단하지 않는다. 향후 별도 수정 시 그 변경 범위만 검증해야 한다.

## CHECKPOINT 갱신 및 다음 단계

과거 로컬 `UP2_PRIVATE_ROOT_ANCESTOR_UNSAFE` 실패는 `COMPILE_FAILURE.json`과 `CHECKPOINT_BEFORE.json`에 그대로 보존했다. 상위 CHECKPOINT에 과거 차단, 이후 Actions 성공, 기술 PASS, 독립 시각 검수, 사용자 승인 대기를 각각 분리했다. 기존 `lastError`는 남기고 `HISTORICAL_LOCAL_ENVIRONMENT_BLOCK_ONLY`로 명확히 표시했다.

현재 최초 미완료 단계는 **기존 일본 VIDEO.mp4에 대한 사용자 최종 품질 검토**다. GPU 실행은 다음 단계로 지정하지 않았다.

| 이번 작업 | 횟수/범위 |
|---|---|
| 제품·렌더러·컴파일러 코드 변경 | 0건 |
| CPU 렌더·MP4 인코딩·컴파일 재실행 | 모두 0회 |
| 기존 PASS 검사 재실행 | 0회 |
| 기존 MP4 프레임 읽기 | 미완료 시각 검수용 1회 |
| 신규 이미지 빌드·gCube 시작·GPU 실행 | 모두 0회 |
| GPU 비용 | 0원 |
| 변경 파일 | 일본 CHECKPOINT 및 신규 검수 증거·보고서만 |
| 반복 작업 판정 | 기존 성공 재실행 없음. 최초 미완료 검수만 수행. |

원본/검수 해시는 `SOURCE_EVIDENCE_INTEGRITY.json`과 `SHA256SUMS`에 기록했다. 이 보고서와 같은 커밋의 Git 변경 목록으로 원본 보호와 변경 범위를 확인할 수 있다.
