# 잔여 기능의 실제 조건

151개 ID와 원래 미연결 53개를 모두 유지했습니다. 현재 상태는 **SUPPORTING 104 / BLOCKED 18 / UNVERIFIED 14 / 해당 없음 15**입니다. 초기 실제 소프트웨어 지도 영상의 AAC 합성·픽셀 보존 검증으로 `STUDIO.SFX_MUX` 1개만 미검증에서 SUPPORTING으로 변경했습니다. 기술 연결과 사용자 영상 품질 승인은 다릅니다.

## BLOCKED 18개

역사 자료 또는 해당 자료와 네이티브 합성 계약이 필요한 항목이 16개입니다.

- Flow 6종과 별도 Flow Polish: 날짜·역할·출발/도착·실제 경로가 결속된 역사적 이동 계획이 없습니다. 이미 있는 generic Flow 소비자 검사만으로 군대 이동을 만들어 넣지 않습니다. 별도 승인 Polish 소비자 연결도 남아 있습니다.
- 완전한 Scalar 영토 2종과 고급 전선 조명 3종: 실제 양측 점령장·도메인·Scalar 계획이 없습니다. 8개 근사 부분 전선을 닫아 점령 다각형을 만들지 않습니다. 원래 고급 소비자 7개는 새 선택 경로에 연결했으나, 실제 네이티브 지형 텍스처·세력별 coverage·중복 부모 layer 부재 조건도 충족해야 합니다.
- 국가별 표식 2종: 원래 디자인과 안전한 크기 소비자는 연결했지만, 날짜·국가·역할·프레임별 실제 위치 자료가 없습니다. 국가 참전일이나 도시 좌표를 군대 위치로 바꾸지 않습니다.
- Causal Tracks·TRANSPORT Planner 2종: 원래 범용 컴파일러는 있으나 현재 고정 WAR 입력과 구별되는 실제 수송/접촉 하위 사건 자료 및 연결 계약이 필요합니다.

나머지 2개는 보호 중인 네이티브 표현 계약이 필요합니다.

- 지도 Roll: 지도 layer의 실제 overscan·회전된 지리 투영을 모든 보호 layout 소비자와 일치시켜야 합니다. 완성 화면 전체 회전이나 임의 crop으로 대체하지 않습니다.
- 추가 Detail Approach: 기존 첫 Detail Lock은 보존했습니다. 새 확대를 위해서는 실제 목표 구도·native static·Safe Area의 시각 Admission과 기존 Camera 최소 문맥 호환성이 필요합니다. 측량급 인증이 없다는 이유로 차단한 것이 아닙니다.

## UNVERIFIED 14개

- ASTRA 4개, 지도 재질/native factory 4개, 새 Detail Visual Admission 1개는 실제 NVIDIA 또는 해당 기능의 화면 검증이 남습니다. 실제 SwiftShader 그림·업로드·draw/readPixels 증거는 별도로 기록하며 NVIDIA 증거로 전환하지 않습니다.
- Dropbox offline·암호화 checkpoint·fresh-root restore·production-input adapter 4개는 기존 별도 구현이 존재하지만 현재 선택된 no-backup 프로필의 실행 증거가 아닙니다. 기존 Secret이나 백업 데이터를 재설정하지 않았습니다.
- 실제 기존 80초 입력·출력 1개는 `66430.mp4`와 원래 개인 작업 입력이 확보되지 않았습니다. 저장소 예시를 실제 사용자 입력으로 단정하지 않습니다.

## 새 자료를 연결할 경로

새 package-owned `EXTENSION_SOURCES.json`으로 기존 카탈로그를 수정하지 않고 검증 자료를 추가할 수 있습니다. 현재 신규 기록은 0개이며 실제로 없는 역사 자료를 넣지 않았습니다. 프롬프트가 검증 상태나 trusted catalog를 공급할 수 없습니다. Source ID 충돌·역할 변환·SHA 변경·생산 환경의 합성 Fixture는 거부합니다.

200프레임의 카메라 관측 캐시는 원래 소프트웨어 실행의 실제 출력·기존 Camera 10파일·기존 이미지 binding 13칸에 결속되어 있습니다. 알려지지 않은 프레임을 정지 상태로 간주하거나 새 카메라 위치·역사 좌표를 생성하지 않습니다. 이 캐시는 원본 80초 장면에서 확인된 5초 구간을 선택하는 데만 사용합니다.

전체 80초 실행과 FINAL 승격은 차단 상태로 유지했습니다. 기능별 정확한 ID, 기존 호출 위치, 실제 새 CPU 증거, 남은 자료·합성 조건은 `REMAINING_FEATURES.json`과 `FEATURE_LEDGER_151.csv`에서 확인할 수 있습니다.
