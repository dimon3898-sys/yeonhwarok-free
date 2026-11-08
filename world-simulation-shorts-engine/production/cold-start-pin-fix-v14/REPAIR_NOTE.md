# v13 CrashLoopBackOff 시작 해시 연결 누락

2026-11-08. 사용자가 첨부한 #5373 화면과 현재 gCube 이벤트에서 이미지 pull 성공 후 컨테이너 시작/종료 반복을 확인했다. 터미널과 SSH는 비활성이므로 앱 stdout의 실제 오류 코드는 확보하지 못했다. 화면의 최근배포 시각은11:56이지만 새 파드 이벤트는12:31~12:33이며, 화면의 시각만으로 실행을 같은 배포로 단정하지 않는다.

## 확정한 결함과 책임

v13의 새 RUNTIME_SOURCE_MANIFEST는 c70ec44c…141cdfd인데, 기존 이미지에서 상속한 bootstrap.py의 SOURCE_SHA는 f007273a…14eab1로 남았다. 시작 검증은 두 값의 일치를 필수로 요구한다. 같은 bootstrap/STARTUP_MANIFEST 바이트로 실행하면 COLD_START_MANIFEST_CONTRACT_INVALID가 발생한다. 이는 Studio/GPU 실행 이전에 반드시 거부되는 v13 패키징 결함이다. 실제 gCube stdout에서 해당 코드가 회수됐다고 주장하지 않는다.

Work가 v13 패키징에서 bootstrap의 고정 해시 갱신을 누락했다. 이전 검사는 런타임 소스와 helper import를 확인했지만 실제 시작 진입점을 거치지 않았다. v13의 배포 준비 판정은 무효화한다. JSON 크기 경계10개 PASS, 기존 데이터/Scene/렌더러 PASS는 그대로 유지한다.

## 최소 수정과 새 검사 범위

새 v14는 v13 이미지 위에 bootstrap.py와 STARTUP_MANIFEST.json 두 파일만 추가한다. bootstrap의 SOURCE_SHA 상수 한 개만 올바른 기존 런타임 해시로 바꾼다. startup manifest의 bootstrap 바이트수/해시와 ENTRYPOINT의 startup manifest 해시도 연동한다. v13의 nvidia_worker, 런타임361개 목록, 입력·지도·지형·렌더러·인코더·합성기·인증 로직은 변경하지 않는다.

새 CPU 검사는 한 줄 상수 변경 외 AST가 동일함, 실제 부모 verify_startup, 자식 worker.bootstrap, 잘못된 manifest hash 차단을 확인한다. 첫 시도는 /workspace의777 상위 디렉토리 때문에 보호장치에 차단됐으며 후보 변경 없이 root 소유 /opt의 새 시험 위치에서 미완료 검사를 완료했다. 기존 검사를 재실행하지 않았다.

설치 후에는 새 부모/자식 시작 연결과 source_contract를 확인한다. 이어 이미지 기본 ENTRYPOINT를 바꾸지 않고 tini→bootstrap을 CPU에서 실행한다. 네트워크와 NVIDIA 장치는 없으며 실제 인증 값도 사용하지 않는다. 의도적으로 Owner 설정을 비워 STUDIO_OWNER_CONFIGURATION_REQUIRED에서 종료해야 한다. 이는 시작 해시·프로세스 관계·lock·port·런타임 연결·frozen proxy 검증을 지난 증거이며, Studio 서버나 GPU 성공을 의미하지 않는다. 이 선행 검사가 실패하면 이미지 게시를 차단한다.

## 보존과 다음 작업

v11/v13 태그와 원본 브랜치, 실패 증거, 기존 PASS를 보존한다. 사용자에게 배포 중지를 안내한 뒤 실제 종료·노드 미할당을 확인했다. Work의 배포 시작·중지·렌더링은0회다. 새 이미지 검사/백업/게시 PASS 후 종료된 #5373의 이미지와 digest2개만 저장하고 재조회한다. 실제 GPU 시작·Studio 렌더링은 사용자만 수행한다.

기존 두 JSON은 그대로다. PART_01의 실제10초 MP4 다운로드 성공 이전에 PART_02로 넘어가지 않는다. HISTORICAL 차단, Studio 자동20초 합성 UI 미연결, 최종 MP4/레퍼런스 품질 미검증은 유지한다.
