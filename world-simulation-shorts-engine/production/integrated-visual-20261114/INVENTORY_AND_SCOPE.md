# 범용 지도·영토·카메라 개선: 실제 코드 조사와 범위

원격 시작 HEAD: `0123dfdcce4bae8a5530dd24257229caa302adb6`.
원격 CHECKPOINT보다 최신인 이전 작업 폴더의 180프레임 검수·비교 보고서를 회수했다. 원본 폴더는 수정하지 않았다. 기존 체크포인트의 fullReview를 증거와 함께 보존한다.

## 기존 PASS

V1/V2/V3, 원본 3커밋/43파일 보존, 연속 도형/합성 14종, 56–85의 30연속 CPU 프레임, 두 기존 MP4, 레퍼런스 전체 프레임 분석: 모두 SKIP. 기존 PASS 무효화 0건. 이번 새 변경에 대한 검사만 수행한다. 새 변경이 기존 결과를 소급하여 무효화하지 않는다.

## 기능별 상태

| 기능 | 판정 | 실제 소유 코드·최소 변경 |
|---|---|---|
| 지형 영상·해안 마스크 | EXTEND | renderer.mjs: NASA BMNG 1분 native-grid pyramid, land coverage 재사용. opt-in source-only tone/coast contrast |
| 지형 음영·색상·텍스처 | EXTEND | baked relief와 기존 shader 유지, 어두운 저지대 가독성/기존 명암 구분. 새로운 높이·노이즈 생성 안 함 |
| 국가 경계 | REUSE | native country boundary layer 존재. 역사 입력은 nativeBoundaries=false 유지; 동시대 주변 경계 자료 미제공 |
| 대륙 구분선 | MISSING | Natural Earth physical-region 자료 출처 확인. 부정확한 라벨용 외곽을 법적·정밀 경계로 쓰지 않음. 식별 가능한 대륙 공통선만 점선, 뷰 밖은 생략 |
| 라벨·안전영역 | EXTEND | presentation_label_layer 재사용, 검증된 자연지리 명칭만 공통 선택. 역사 도시 근거 없으면 생략 |
| 반투명 영토 | EXTEND | 기존 Area V3, 지형이 남도록 색 강도 낮춤 |
| 연속 중간 도형·경계 | REUSE | continuous_territory_runtime/compile/py 및 기존 frames 재사용. 도형 계산 재개발·전체 검사 재실행 금지 |
| 이동 경계 강조·발광 | EXTEND | territory_effects_v2 + 기존 Area V3 contour, 현재 moving_boundary glowGain=0 결함. 활성 경계만 강조 |
| 카메라 키프레임·투영 | REUSE | geographic_camera_v1 + 정식 presentation compiler, source density admission 유지 |
| 확대/축소·중심 추적 | EXTEND | history_continuous_v1: 순간적인 boundaryBounds offset + 이산 fallback을 연속 정책으로 개선. 변화 영역과 source resolution에 따라 자동 결정 |
| 장면 시간 | REUSE | V3 TIMING_ANALYSIS 108프레임 push-in, 47프레임 reading 참조. 기존 26/106/48프레임 rhythm 유지, 사건 압축 금지 |

## 새 검증 최소 범위 (검증 전에 기록)

- 단계1: 변경된 지도 대표 0/79/131/179프레임. 지형·해안·소스밀도·라벨/선 충돌만. 과거 모델 PASS 재실행 없음.
- 단계2: 새 색 구분과 발광의 26/53/79/105/130/131 및 짧은 연속 경계 구간. 저장된 중간 도형을 그대로 사용함을 해시로 대조.
- 단계3: 새 카메라의 시작·이동·종료 대표와 기존 frame27 결함 주변의 짧은 연속 구간. 카메라/지도/라벨 상호작용만.
- 통합: 앞 3단계 통과 후 변경 상호작용만 점검. 이후 새 입력으로 신규 180프레임 MP4 1회 생성.
- 레퍼런스 전체 분석 재실행 없음. 저장된 시간 분석과 직접 비교용 표본만 사용.

## 확인된 한계

현재 가장 자세한 소스는 1분(0.0166667도), 추가 확대를 무조건 허용하지 않는다. 고밀도 소스 없이는 근접 지형의 레퍼런스 동등 품질을 주장할 수 없다. Natural Earth 국가 경계는 현대 경계로서 본 역사 샘플에 표시하지 않는다. 역사 도시는 시간·위치 근거가 없으므로 임의 추가하지 않는다.

## 실행 경로

기존 `capture_presentation.mjs` → `presentation_runtime.mjs` → native renderer / Area V3 / geographic camera. 새 생성기 없음. 무료 CPU GitHub Actions 사용; GPU/gCube/Studio 금지. 단계별 원격 저장 후 다음 단계. 기술 PASS와 최종 시각 품질/사용자 승인은 분리한다.

## Stage 3 exact change scope
The old camera audit remains valid for the old video. Only the newly derived camera path is evaluated: 180 source/viewport math samples, frames 0, 23–32, 53, 79, 105, 131, 179 in the unchanged formal CPU renderer. Existing geometry/topology tests are SKIP. The prior frame-27 jump is not a reason to rerun old tests; it motivates a separate globally qualified path. Same event and 48-frame hold timing. Source detail gates stay unchanged.
