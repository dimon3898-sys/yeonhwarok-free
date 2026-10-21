# ASTRA MASTER V2 — P0~P5 진행 결과

이 기록은 검증된 구현·입력 연결과 실제 소프트웨어 프레임 증거를 구분한다. 전체 16장 및 연속 구간 캡처는 이 문서 작성 시 진행 중이다. 영상 품질 승인과 80초 제작 준비 완료를 선언하지 않는다.

## 입력과 보존 기준

기존 80초 원본 Plan SHA-256:
`33596c97b433887afb7ced6847d4ef63d099a9b6633546d541890a45c9c6289e`

새 사건 프로필 SHA-256:
`21030c51ec52a716aa39ec2a10cc2bcfc1b315812351c328bb8745f99d2387c1`

새 자료 카탈로그 SHA-256:
`72f4a78f247652819440e13696d51181097b1ca3235678a664cad0b2db65febe`

새 파생 Scene SHA-256:
`c3d9bae65f433d584e9f70b1587cdf31e6d3bb5fa0b920eb18d970842e2afcef`

기존 원본 Scene의 geometry, 12개 chapter/event ID, 200프레임 단위 경계, native payload와 기존 8개 부분 전선은 보존한다. 변경은 새 namespace의 파생 자료와 확장 경로에 한정한다. 보호 여부의 최종 판정은 별도 원본 해시·Git 변경 검사 결과를 따른다.

## P0 — 역사 자료 및 사건 매핑: 부분 개선, 전체 통제 면은 미확보

공식 Army/GovInfo 원문과 지도 범례를 실제 검토했다. 서울 함락·수복, 중국군 첫 개입과 후속 공세, 재반격 사건일과 지도 기준일을 구분했고, 후반 자료 날짜 역행과 휴전 협상 문구 누락을 새 사건 자료에서 교정했다. 인천·서울 수복·북진·중국군 개입 장면에 앞선 부산 도식을 재사용하던 매핑을 제거했다. 자료가 없으면 이전 상태 대신 명시적인 `unknown`을 유지한다.

Appleman Map I의 1950년 6월 28일 저녁 한국군 부분 전선을 새로 등록했다. 실제 trace는 열린 선 3개, 원본 점 19개, 원본 edge 16개다. 지원 범위 밖 edge 2개를 제외했고 선 사이를 이어 만들거나 점령 면으로 닫지 않았다. 최대 fit 잔차 775.70m, held-out 잔차 3,661.88m를 통과했지만 원 투영법·전체 역사 위치 정확도는 미확인이다. 이 결과는 근사 부분 전선 검수용이며 정밀 통제선이나 양측 영토 면이 아니다.

2,400프레임의 새 자료 배분은 관측된 근사 부분 전선 1,110프레임, 도식적 held-core 430프레임, 사건별 공간 자료 미확보 860프레임이다. 전체 통제 상태와 연속 점령 변환 자료 확보 완료를 뜻하지 않는다.

## P1 — 새 입력 계약과 실제 파생 Scene: 구현·무료 검증

`WORLD_ENGINE_EVENT_DIRECTOR_REQUEST_V1`은 기존 Studio V1/V2 parser를 느슨하게 수정하지 않는 별도 opt-in 계약이다. 실제 Plan 원본 바이트, version·SHA·자료 경로, server-owned allowlist, strict 필드와 소비자 검증을 사용한다. 지원하지 않는 필드나 잘못된 해시를 무시하지 않는다.

실제 normalizer 결과는 `reviewReady=true`, `productionReady=false`, `renderAllowed=false`다. 요청된 10개 capability를 삭제하지 않고, 지원되는 소프트웨어 자료 검수 경로와 미충족 제작 capability를 함께 남긴다. 이 계약이 현재 운영 Studio나 기존 컨테이너 이미지에 이미 배포됐다는 주장은 하지 않는다.

## P2 — 카메라: Regional 경로 연결, 요청 Local은 차단 유지

기존 V5/reference evaluator와 native factory를 재사용한다. 12개 사건의 현재 자료와 지리 문맥을 사용하며, 실제 인천 도시 좌표는 지리 문맥으로만 사용한다. 새로운 군사 위치나 상륙 해안을 추정하지 않는다.

2,400프레임 CPU 검사는 기존 minimum 범위, 현재 공급된 geometry의 화면 범위와 chapter 경계 연속성을 확인했다. 실제 global frame 0과 300도 native draw/readPixels를 완료했다. 단, 이 결과는 별도 `REGIONAL_SOURCE_REVIEW`이며 사용자가 요청한 Local 확대가 아니다. 색상 원본 해상도·지리 정확도·사건 공간 자료가 부족해 Local admission은 계속 차단한다. 가짜 certificate, 강제 clamp 해제 또는 더 넓은 프리셋으로의 조용한 대체는 하지 않는다. 역사 장면의 roll은 0이다.

## P3 — 영토·전선: 새 부분선 실제 표시, 연속 점령 morph 미완료

새 부분 전선은 기존 Area V3와 기존 백색 중심·금빛 외곽 스타일로 연결했다. global frame 300의 실제 소프트웨어 probe에서 3개 fragment가 모두 draw되고 `1950.06.28 근사·부분 전선` 한계 문구를 표시했다. 6월 한국군 자료를 기존 UN 전선 분류로 바꾸지 않았다.

전체 owner field, 양끝 통제 면, 고립 영역·구멍·다중 성분의 대응과 이동 근거는 아직 없다. 기존 단조 scalar에 억지로 바꾸거나 partial line을 해안으로 닫지 않는다. source-bound control guard는 null 상태와 잘못된 객체·프레임을 검증하는 방어 계층이다. 기존 영토·전선·조명 GPU owner가 완전한 통제 field를 실제로 공유해 draw했다는 증거가 아니며, 역사적 owner morph draw는 0이다.

## P4 — ASTRA·표식·오디오: 실제 재질 참조 확인, 미검증 효과 차단

기존 ASTRA 재질 factory와 설정 함수를 그대로 사용한다. 실제 합성 `outputTexture`를 canvas·소유자·global frame·카메라 bounds에 묶어 전달하고, 오래되거나 삭제된 texture와 draw 실패·dispose 후 접근을 거부한다. 실제 frame 0·300 probe에서 ASTRA upload/material 선택과 같은 프레임의 합성 texture 참조를 확인했다. 완성 이미지 위에 지도를 덮는 방식은 사용하지 않는다.

역사적 LightV3는 신뢰 가능한 통제 scalar가 없어 `SCALAR_CONTROL_SOURCE_REQUIRED`, draw 0이다. 도시 위치를 군대 위치로 바꾸지 않아 역사 군대 표식 manifest도 비어 있다. 오디오 의미와 cue 대응은 미검증이므로 `enabled=false`, `gain=0`, `cues=[]`를 유지하며 외부 UI의 임의 SFX 활성화를 거부한다.

## P5 — 실제 출력: 두 probe 완료, 전체 캡처·검수는 별도

확인한 실제 proof는 `proof/PROBE_0000.json`과 `proof/PROBE_0300.json`이다. 두 결과 모두 Chromium SwiftShader의 실제 WORLD ENGINE draw/readPixels이며 NVIDIA 검증이 아니다. frame 0은 발발 사건과 `점령선 자료 미확보`를, frame 300은 서울 함락·남하 사건과 새 근사 부분선을 표시한다.

0~75초의 16개 실제 정지 프레임과 지정된 연속 구간 캡처의 전체 성공, MP4 인코딩·디코딩, 다운로드 무결성, 모바일 시각 검수는 root의 별도 완료 receipt가 있어야 판정할 수 있다. 연속 진단 영상이 있어도 M1의 요청 Local이나 M2의 점령 면 확장·전선 동기 이동이 충족됐다고 표시하지 않는다. M2의 양끝 면과 변환 근거 부족은 계속 차단 사유다.

## 무료 검사 및 다음 필요한 개발

현재 통합 집중 검사 집계는 Python 47개 + Node 37개, 총 84개 PASS다. 소프트웨어 GPU handoff 모의 검사는 실제 NVIDIA 실행으로 보고하지 않는다. 151개 기능 표는 REQUIRED 53 / SUPPORTING 70 / NOT_APPLICABLE 28을 유지하며, 기존 미연결 53개 중 REQUIRED 5개만 별도로 추적한다.

다음 데이터 작업은 이미 확보된 인천·서울 날짜별 진지 지도에 검증된 기준점을 추가해 지리 등록하고 실제 범례의 선 조각을 추출하는 것이다. 그 결과도 완전한 통제 면·연속 변환 증거와는 별도로 평가한다. 요청 Local은 실제로 충분한 상세 표면·해안 자료와 안전한 ROI admission이 확보된 뒤 재검증한다. 사용자에게 이미 있는 지도를 다시 업로드하거나 전체 자료 수집을 대신하라고 요구할 필요는 없다.

현재 요청은 새 이미지 빌드나 운영 이미지 교체를 요구하지 않는다. 유료 GPU, 전체 80초 MP4, 기존 FINAL 변경·승격은 실행하지 않는다. 최종 시각 품질은 사용자가 실제 출력으로 승인한다.

**현재 전체 판정: 부분 개선 및 실제 검수 출력 준비. 요청된 모든 고급 역사 연출의 제작 준비 완료는 아님. `USER_REVIEW_REQUIRED`.**
