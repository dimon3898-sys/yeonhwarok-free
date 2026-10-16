# Universal Auto Video V2

장편 실행 후보 구현과 무료 검증·GHCR 등록·독립 pull 완료. 실제80초 NVIDIA 영상,
60분 목표, Dropbox 외부 전달과 영상 품질은 미검증이다.

- 최종 보고: [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)
- 최종 기계 판정: [FINAL_RESULT.json](FINAL_RESULT.json)
- 사용할 이미지: [IMAGE.json](IMAGE.json)
- 80초 실행 계획: [FIRST_PRODUCTION_80S_PLAN.json](FIRST_PRODUCTION_80S_PLAN.json)
- canonical plan SHA: [FIRST_PRODUCTION_REQUEST.json](FIRST_PRODUCTION_REQUEST.json)
- 비활성 승인 template: [OPERATOR_APPROVAL_TEMPLATE.json](OPERATOR_APPROVAL_TEMPLATE.json)
- 승인 후 운영 절차: [OPERATOR_EXECUTION.md](OPERATOR_EXECUTION.md)
- source/runtime manifest: [UNIVERSAL_FILES.json](UNIVERSAL_FILES.json)
- 최종 보호·계획 해시: [FINAL_INTEGRITY_CHECK.json](FINAL_INTEGRITY_CHECK.json)
- 최종 소스 Secret Scan: [SOURCE_SECRET_SCAN.json](SOURCE_SECRET_SCAN.json)
- 영구 저장 파일 해시: [SHA256SUMS](SHA256SUMS)

주제 기획은 제공된 사실 catalog 범위에서 동작한다. 현재 역사 fixture는 기존5개
도식 상태와 ASTRA/source material + Area V3 전환 + V5 도착/lock을 사용한다.
V2 scalar 전선·부대 확대·사건별 새 camera 연출은 이 역사 경로에 적용하지 않는다.
개발 후보를 완전한 범용 제품이나 사용자 영상 품질 승인으로 표시하지 않는다.

유료 GPU 작업은 사용자 승인 후 별도로 실행한다. 이전388430 중간 이미지는
실제 scene-cut 증거 부족으로 최종 후보에서 제외했으며 삭제하지 않았다.
