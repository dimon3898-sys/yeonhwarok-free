# WORLD ENGINE — 제한적 복구 검수

**전체 상태: 부분 구현·검증 완료 / Studio 제작 게이트 미통과.**
기준 커밋 `5cc9b98c628324814e1e63f9d0f8c6254ee84174`에서 독립 브랜치
`development/reference-director-v2-20261022`로 이어서 작업했습니다.
첨부 지시서 전체와 지정된 기존 보고서를 읽고, 허용된 독립 작업을 수행했습니다.

## 실제 완료한 작업

- 선택형 `REFERENCE_SIMILARITY_2D_V1`: 실제 native 카메라의 이동·확대·회전,
  공통 screen/inverseScreen, 회전 viewport 4코너 source envelope 및 실제
  지형 역샘플링을 구현했습니다. 완성 프레임 회전이나 overlay만의 회전이
  아닙니다. 기본 API, source admission, 최소 detail 제한은 보존했습니다.
- 범용 PIN/LABEL/AREA/LINE/METRIC 입력 계약과 native-frame consumer 호출
  계층을 새 namespace에 추가했습니다. 기존 Area/Event/glyph 모듈을
  재사용하며, 국가·사건·원본 프레임 시점은 핵심 로직의 조건문이 아닙니다.
- 기존 coarse context와 source-ID/style 선택을 입력 데이터로 명시했습니다.
  원본 국가 MultiPolygon을 삭제하거나 정밀 형상으로 위장하지 않았습니다.
- 공식 환경 도구에서 기존 설정을 유지하며 조사 도메인 5개를 **초안에만**
  저장했습니다. 실제 적용 정책은 재확인 결과 아직 바뀌지 않았습니다.

## 실제 검증과 남은 게이트

| 구분 | 실제 결과 |
| --- | --- |
| 직접 영향받는 기존 검사 | 수정되지 않은 기존 검사 68 PASS. 이전 전체503개를 이번에 재실행했다고 주장하지 않음 |
| 새 program/glyph 계약 | 25 PASS |
| 자료 선택·비변형·차단 검사 | 4 PASS. 정밀 자료 확보 PASS가 아님 |
| 평면 기본/비활성 opt-in | Namibia/Nepal의 확대 전후 8개 상태가 원본 golden과 픽셀 정확 일치 |
| 활성 회전/역투영 | 세 위도·12개 자세,53개 실제 native draw/readPixels 프레임 검증 통과. 실제 소스 역샘플링과 GIS mask 검사 포함 |
| 메타데이터 거부 | 누락 native spacing·잘못된 CRS·미선언 NoData의3종 거부와 기존 상태 보존을6개 실제 프레임으로 확인 |
| 기본 globe | **미확정**. 원본 자체도 같은 factory 연속 draw에서 소수 픽셀이 변함. 수정 영향과 정확 일치를 확정하지 못함 |
| 새 graphic consumer | 단색 배경·합성 fixture·projection stub의 5개 실제 SwiftShader draw/readPixels 통과. Native 지도 결합이나 Studio 성공으로 간주하지 않음 |
| 정밀 데이터 | **DATA_DETAIL_BLOCKED**. 장소 식별·Point·정밀 Polygon·실제 ordered LineString·정밀 basemap 미확보 |
| Phase3 | **미실행**. 선행 두 게이트가 모두 통과하지 않아 12개 reference 시점·두 전체 profile fixture·A/B/C Studio MP4를 제작하지 않음 |

실제 backend는 SwiftShader이며 **NVIDIA 하드웨어 PASS가 아닙니다**.
자동 검사, 실제 native unit draw, 완전한 Studio 제작 경로, 사용자 영상 품질
승인은 각각 별개입니다. 새 MP4 및 새 Docker 이미지/digest는 없습니다.

## 실패 원인 판정의 정정

첫 비교에서 원본/수정 globe 사이 12개 픽셀 차이를 발견하고 제작을 중단했습니다.
기본 GLSL을 원본과 byte 단위로 분리 보존하는 후속 변경을 했지만, 재검사에서
차이가 남았습니다. 이어 **수정하지 않은 원본도 동일 factory의 연속 draw에서
변한다**는 실제 대조 증거를 확보했습니다. label·전선·glow를 제외한 원본
raw-source mode에서도 재현됩니다. 따라서 차이를 수정 코드의 확정된 회귀
원인으로 단정한 초기 해석을 철회했습니다. 실제 차이와 실패 기록은 보존했고,
원본 globe sampling/backend 내부의 정확한 최초 원인은 아직 미확정입니다.
허용 오차를 완화해 PASS로 바꾸지 않았습니다.

## 보호 파일과 원본 복구

작업 전 307/307 원본 SHA를 확보했습니다. 지시서가 유일하게 허용한
`web/map_infographic_v1/renderer.mjs`만 변경했습니다. 최종 검사는
**306개 원본 일치 + 1개 명시적 승인 변경**, 기타 기준 tracked 파일
6,876개 불변입니다. 기존4개 worktree와5개 cache root의1,135개 metadata
entry도 보존했습니다. 캐시 내용 전체 재해시를 수행했다는 의미는 아닙니다.

- 원본 SHA: `e4c80a478fe7b849c9f260eaffa436bea32af78596673dd2e046e25412363b38`
- 수정 SHA: `9f60a7e4a6299b23b6c9070be4b830a3bbad25f5e1b321e5eff383ce35fb4995`
- 원본 backup과 변경 diff, 변경 전 원격 checkpoint와 적용 receipt를 함께
  보존했습니다. 기존 기준 해시나 이전 Studio seal을 갱신하지 않았습니다.
- G1/G2/FINAL/기존 Candidate/Scene/Asset/영상/캐시/Secret 삭제·초기화 없음.
  유료 GPU/API/배포,80초 제작,FINAL 승격 없음.

## 검수 자료 읽는 순서

1. `PROJECTION_IMPLEMENTATION_REPORT.md`, `PROJECTION_EXTENSION_DESIGN.md`
2. `NATIVE_PIXEL_VERIFICATION_REPORT.md`와 `NATIVE_DEFAULT_GLOBE_REGRESSION.md`
3. `COMPOSITION_CONNECTION_REPORT.md`, component unit contact sheet
4. `PHASE2_DATA_ACQUISITION_REPORT.md`, `reports/DATA_DETAIL_GATE.json`
5. `AFFECTED_REGRESSION_REPORT.md`, 보호 결과, `REMAINING_CAPABILITIES.md`
6. `NEXT_EXECUTION_POINT.md` — 게시 후 조사·통합·제작 재개 순서

공개 ZIP에는 새 코드·원본 backup·diff·실행 기록·실제 새 unit PNG·라이선스
공지·SHA가 포함됩니다. 업로드한 원본 레퍼런스 영상/추출 이미지와 private
자료·Secret은 포함하지 않습니다. ZIP CRC와 내부 SHA 및 외부 HTTP 다운로드
검증 결과는 각 별도 receipt에서 확인해야 합니다.

**사용자에게 필요한 다음 행동:** 환경 설정에서 저장된 네트워크 변경을
검토·저장 후 Publish 합니다. 게시만으로 장소·라이선스·자료 품질이 검증되는
것은 아니므로, 실제 접근·자료 검증을 거친 뒤에만 다음 게이트로 진행합니다.
최종 영상 품질은 사용자 승인 전까지 PASS로 선언하지 않습니다.
