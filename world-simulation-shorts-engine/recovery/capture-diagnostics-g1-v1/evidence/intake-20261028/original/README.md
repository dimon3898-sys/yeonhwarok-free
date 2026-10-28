# WORLD ENGINE 재설계 묶음

1. WORLD_ENGINE_MASTER_V2.md: 보존형 복구·출시 설계.
2. ASTRA_WORK_ORDER_V2.txt: Astra Work에 전달할 복사용 실행 지시서.
3. CHECKPOINT.json: 기준 이미지, 실패 상태, 승인 상태를 구분한 인수인계.
4. evidence/: 변경 없는 기존 exporter와 합성 6조건 재현 결과. GPU 원인 증명은 아님.
5. DESIGN_REVIEW.json: 문서 간 일관성·안전 조건에 대한 작성 검수. 운영 구현 PASS가 아님.

이 묶음은 런타임 패치나 완성 영상이 아니다. GitHub/gCube를 변경하지 않았다.
Astra에는 압축을 풀어 전체 묶음을 전달하거나, master와 work order 및 checkpoint를 함께 제공한다.
