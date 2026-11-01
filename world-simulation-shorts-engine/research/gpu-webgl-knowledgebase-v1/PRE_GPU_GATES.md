# 향후 GPU 실행 전 최소 기준

이는 새 테스트 목록이나 이번 실행 승인이 아니다. 기존 PASS의 유효 범위를 유지하면서 다음 실행에 필요한 결정만 남긴다.

| 조건 | 현재 상태 | 필요한 최소 행동 |
|---|---|---|
| 라벨355·10초 UI/API·CPU300·Namibia·Studio preflight | **SKIP:** 기존 PASS 재사용 | 해당 파일/판정 변경 증거 없으면 재실행하지 않음 |
| capture 진단·source integrity·surface 옵션·기존 이미지 백업 | **SKIP:** 각 변경의 기존 집중 PASS 재사용 | 같은 복원/게시를 반복하지 않음 |
| latest failure.code/stage | **PASS:** 정확한 job export에서확보 | [원문](evidence/latest-job/CAPTURE_DIAGNOSTIC.json) 유지 |
| latest 실제 image/argv·native 오류 | **BLOCKED:** 현재 export에 없음 | 기존 private receipt/플랫폼 증거 우선 확보; 없으면 정보 보존 준비 |
| 진단 실행 경로 호환성 | **BLOCKED:** 기존 JS는 오래된 profile pin, 실제 capture CLI는 단축 모드 미지원 | 기존 경로의 적용 가능성과 승인 범위 확정 전에 GPU 기동하지 않음 |
| 유료 실행·종료·비용 한도 | **NOT_RUN:** 연구에 GPU 승인 없음 | 별도 실행에서 구체 승인과 중지 가능 경로 확보 |
| 실제 WebGL2·NVIDIA native proof | **NOT_RUN:** 이번 연구 실행0회 | 동일 capture 조건에서만 판정. CPU PASS로 대체하지 않음 |
| 300프레임 MP4·라벨·영구 다운로드 | **NOT_RUN:** 최신 실패는 해당 단계 전 | 목표 결과가 실제 생성된 뒤에만 PASS |

## 변경 영향과 무결성

기준 운영 커밋은 `296402e71257c7847d0045215ca0cdaf3dd700d2`다. 기존 복원은 profile 옵션 한 줄과 필요한 manifest/bootstrap 해시만 바꿨다. 연구 파일은 별도 `research/gpu-webgl-knowledgebase-v1/`에만 추가하며 기존 manifest를 갱신하지 않는다.

| 향후 실제로 바꾸는 대상 | 연결 확인 범위 | 변경하지 않을 항목 |
|---|---|---|
| capture generated source | 실제 source SHA와 연결 generated manifest, 이후 runtime/startup pin | 검증 우회·무관한 source 전체 재생성 |
| profile_contract.mjs | 해당 runtime source row와 SOURCE_SHA/startup 연결 | GENERATED capture manifest는 참조 관계가 없으면 그대로 |
| 진단 출력 보존 경로 | 민감정보 allowlist·최대 크기·실패 시 기존 cleanup/HTTP 의미 | 인증·Owner·기존 판정·렌더러 기능 |
| 이미지 내용 | 실제 변경이 필요한 경우만 고유 태그·고정 부모·검증한 이미지의 게시 동일성·전체 백업 | 기존 성공 태그·이미지·main 덮어쓰기 |
| gCube 설정 | 실제 imageDigest와 관련 expected digest 설정 구분, `/world-storage`, 빈 command,8080 보존 | GPU 자동 기동·기존 데이터 삭제 |

출처: [시스템 소스 색인](system/SOURCE_INDEX.json), [이전 최소 복원 CHECKPOINT](https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/webgl-surface-restore-v1/CHECKPOINT.json), [캡처 source integrity CHECKPOINT](https://github.com/dimon3898-sys/yeonhwarok-free/blob/296402e71257c7847d0045215ca0cdaf3dd700d2/world-simulation-shorts-engine/recovery/capture-source-integrity-v1/CHECKPOINT.json).

관측 전에는 특정 가설을 고치지 않는다. 변경으로 특정 PASS가 무효화된 근거가 있을 때만 그 범위를 명시하고 집중 검증한다. 최신 WebGL2 실패 때문에 CPU 컴파일·라벨·PNG·MP4 경로를 일괄 재검증하지 않는다.
