# 변경 범위 검증 근거

기존 레퍼런스 분석·역사 데이터·106개 도형·기존 MP4 PASS는 보존하며 재실행하지 않는다.

이번에 무효화된 적용 범위는 다음과 같다.

1. 기존 GPU 어댑터의 원본 소스 3개 해시가 현재 CPU 소스와 다르다. 최신 연속 영토·지도·카메라 기능이 GPU 이미지에도 있다는 주장은 성립하지 않는다. 최신 원본 + 명시적 GPU 패치의 재생성 일치만 검사한다.
2. 6초·10초 계약으로는 600프레임 역사 입력을 승인할 수 없다. 새 20초 계약의 정상 입력, 역사 출처·기간·도형 변조 차단, 카메라·라벨·worker 전달을 검사한다. 기존 6/10의 기본 계약 값은 변경된 경계 함수에서만 확인한다.
3. worker·backend 소스가 변경되어 기존 이미지의 정확한 파일 해시 증거를 새 이미지에 적용할 수 없다. 변경된 reader 상한·receipt 연결과 보존된 publication barrier, 승인·비용·잠금 경계를 검사하고, 새 이미지에는 공통 게시 게이트를 적용한다.
4. 최신 runtime 의존 파일이 기존 이미지 closure에 포함되지 않았다. 기존 closure 파일을 삭제하지 않고 신규 의존성과 현재 해시를 연결한다. 누락된 기존 PNG는 기존 소스·방법으로 복원하며 새 영상이나 도형을 생성하지 않는다.
5. 자동 자연지리 라벨은 이번 3개 역할 라벨 설계에 포함되지 않아 새 입력에서 비활성화했다. 제목·기간·보간 고지의 기존 600개 배치 결과는 유지하고 실제 runtime에도 추가 라벨이 없는지만 확인한다.

실제 NVIDIA 렌더링·최종 화질·영상 인코딩 실행 결과는 PENDING_GPU다. 무료 검증 통과는 GPU 실행 승인이나 화질 PASS가 아니다.

6. 새 600프레임의 source preparation은 성공했으나 prepared result의 내부 검증 전달에서 UP2_INPUT_SIZE_LIMIT이 발생했다. 서버가 생성한 HISTORICAL_CONTINUOUS_600F_V1/600 prepared payload의 검증 호출만 24MiB로 제한 확장한다. 사용자 입력·기존 6/10·일반 JSON 저장의 기존 한도는 유지한다.

7. 600프레임 prepared object와 동일 wire를 중복 저장하면 기존 캐시 32MiB 한도를 넘는다. 새 history 캐시에만 검증된 wire 한 부를 저장하고 재사용 때 동일 object로 복원·검증한다. 일반 캐시 한도·권한·해시·잠금은 수정하지 않는다.

8. 모바일 Studio가 내부적으로 6/10초만 인식해 새 20초 preflight 표시를 거부한다. 명시적 HISTORICAL 20초/600 입력과 완전한 request wrapper를 수용하고 600프레임 표시를 추가한다. 기존 동의·정책·시작 버튼의 조건은 유지한다.

9. 최종 closure pin은 모바일 변경 후 갱신됐다. 이전 Controller 계약·캐시 PASS는 보존하고, 새 이미지 내부 473파일·외부 의존 및 Controller→Worker의 정확한 wire 전달만 실제 이미지에서 검사한다. 기존 이미지와 bytes가 달라 common publication gate의 새 이미지 admission이 필요하다.
10. 공통 게시 정책의 Worker/backend 전체 해시는 신규 600프레임 selector 변경으로 무효화됐다. 기존 정책·launch/publication AST 보존 증거를 기준으로 policy v2에 새 정확 해시와 600 계약을 추가한다. 승인·비용·권한·잠금·게시 검사 자체는 유지한다.

11. A1 실제 이미지에서 역사 registry JSON 누락으로 Controller import가 실패했다. 봉인된 473파일만 복사한 별도 closure에서도 ENOENT를 재현했다. 기존 REVIEWED_HISTORICAL.json을 byte 동일 추가하고 manifest/startup pin만 갱신한다. 설계·Controller·Worker·renderer 소스는 변경하지 않는다. A2는 실패한 실제 이미지 전달과 필수 게시 게이트만 검사한다.
