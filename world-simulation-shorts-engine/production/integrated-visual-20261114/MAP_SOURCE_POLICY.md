# 지도 변경 소스와 검사 범위

NASA BMNG 기존 native-density pyramid는 변경하지 않는다. shader는 원래 지형의 명암과 채도만 조정한다. 높이·가짜 산맥·노이즈를 추가하지 않는다. 해안선은 기존 land coverage 마스크의 대비로 강조한다. 영토 색상 alpha를 0.48→0.28로 줄여 지형을 남긴다.

Natural Earth physical labels: https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-physical-labels/ . 제공자 설명상 경계는 대략 1:50m 수준이며 정밀 경계가 아니다. 따라서 대륙 polygon 외곽 전체를 국경처럼 그리지 않는다. 입력 대륙 polygon 사이에 정확히 공유되는 선분만 추출했으며 빈 구간은 연결하지 않았다. 확인된 유럽·아시아 공통선만 청록 점선으로 표시 가능한 구조이고, 이 몽골 샘플에서는 뷰 밖이면 생략한다. 전체 대륙 경계 완비를 주장하지 않는다.

지명은 source polygon 내부의 representative point를 단순 라벨 앵커로 쓴다. 이는 도시/봉우리/사건 위치가 아니다. 한국어 원문 명칭을 사용하며 시작·종료 화면 안에 유지되는 최대 2개 지형만 선택한다. 역사 도시와 당시 주변국 국경은 자료 부재로 표시하지 않는다. 기존 역사 영토선은 유지한다.

Natural Earth는 public domain: https://www.naturalearthdata.com/about/ . 정확한 소스 URL·원본 및 파생 데이터 SHA256은 MAP_PREFLIGHT.json과 context.json에 기록.

검사 범위: 새 shader와 context layer, 더 옅은 영토를 적용한 0/79/131/179프레임. 기존 geometry·camera·timing 해시는 보존. 기존 model suite·전체 레퍼런스 분석은 SKIP. 화면 검수 전 PASS 아님.
