# ASTRA V2 재개 및 검수 계약

이 경로는 `QUALIFIED_SOURCE_REVIEW` 전용입니다. 유료 GPU admission, 기존 Studio의 배포 이미지 변경, 전체 80초 MP4, FINAL 승격을 수행하지 않습니다. 기존 Studio 입력창이 새 요청을 지원한다고 주장하지 않습니다.

## 보존한 원본

- Git 기준: `ede3fa2b31a71a32f1dee66040f8100cee0d9d90`.
- 원본 80초 Plan 바이트 SHA: `33596c97b433887afb7ced6847d4ef63d099a9b6633546d541890a45c9c6289e`.
- 새 파생 Scene SHA: `c3d9bae65f433d584e9f70b1587cdf31e6d3bb5fa0b920eb18d970842e2afcef`.
- 기존 12장면·200프레임 경계, legacy geometry, native payload, 원본 8부분 전선은 유지합니다. 새 6월 28일 ROK 부분 전선은 별도 소비자에 연결하며 UN 전선으로 바꾸지 않습니다.

## 입력 재생성

개발자가 새 비공개 디렉터리에서 수행하는 재개 절차입니다. 모바일 사용자가 명령을 실행할 필요는 없습니다.

1. 기존 `../story-director-16frames-v1/EXACT_REPLAY_INPUTS.md`의 고정 source closure와 원래 `prepare_ref2.py --prepare-activation --variant F` / `prepare_source_preview.py`를 재사용합니다. 새 private root는 소유자 전용 0700으로 생성합니다. 원본 ASTRA ZIP은 기존 Git 파일을 사용하며 다시 다운로드하지 않습니다.
2. `PREPARED.json`의 원본 Plan SHA가 위 값이며 `renderStarted=false`, `full80sRenderAllowed=false`인지 확인합니다. 다른 80초 Submission을 같은 원본으로 대체하지 않습니다.
3. `fixtures/HISTORY_*`, `source-review/ADDITIONAL_FRONT_BINDINGS.json`, 기존 source closure로 실제 파일 해시를 확인합니다. 새로운 다운로드/GCP/geometry가 없으면 자료 조사를 반복하지 않습니다.
4. `tools/build_derived_scene.mjs <새 PLAN.json>`은 현재 source/profile/catalog/compiler와 파생 파일이 모두 일치하는지 확인합니다. 다른 기존 결과를 덮어쓰지 않습니다. 새 입력 버전은 별도 보존·검증해야 합니다.
5. `tools/build_preflight.py <새 PLAN.json>`은 실제 strict normalizer를 실행합니다. 이 작업의 정상 판정은 `reviewReady=true`, **`productionReady=false`**, `renderAllowed=false`입니다. 필요한 capability를 제거해 production PASS를 만들지 않습니다.
6. `capture_review.mjs --prepared=<새 PREPARED.json>`은 기존 WORLD ENGINE 카메라·GIS·ASTRA·Area·전선·Glyph 경로에서 실제 draw/readPixels합니다. 출력이 있는 경우 다른 픽셀로 덮어쓰지 않습니다. `.private/ACTUAL_CAPTURE_LOCK.json`에 살아 있는 PID가 있으면 중복 실행하지 않습니다.
7. `capture_boundaries.mjs <새 PREPARED.json>`은 같은 선택 소스와 시간축으로 장면/자료 경계 인접 프레임을 확인합니다. 이미 그린 동일 프레임은 SHA 확인 후 그 증거를 재사용했다고 명시합니다.
8. `tools/package_actual_review.py`는 실제 PNG의 SHA를 확인하고 지정된 세 구간만 인코딩·전체 디코딩 검사합니다. clean 영상과 전역 프레임 번호를 표시한 검수용 파생 영상을 구분합니다.

원본 Plan/activation/upload bundle은 보존된 코드·자료로 재생성할 수 있습니다. 새 역사 source pixel trace·GCP·부분 GeoJSON·모든 새 구현 및 최종 검수 산출물은 이 개발 브랜치에 저장합니다. 고유 필수 원본의 temp-only 의존성은 0입니다. `.private/frames`는 이미 공개·SHA 검증한 MP4/PNG를 만들기 위한 재생성 가능한 중간 파일이며 새로운 역사 원본이 아닙니다.

## 완료와 미완료의 구분

실제 16장과 세 **자료 검수 영상**은 전체 요청 연출의 성공 증거가 아닙니다. 특히 M2의 양측 점령 면·전환 근거가 없으므로 역사적 영토 확장을 그리지 않습니다. 요청한 LOCAL 카메라 대신 자동으로 다른 프리셋을 통과시키지 않습니다. 별도로 선택한 Regional 자료 검수는 그 한계를 명시합니다.

최종 품질은 `USER_REVIEW_REQUIRED`이며, 데이터·LOCAL·morph 차단을 사용자 품질 승인으로 자동 해제하거나 FINAL로 승격하지 않습니다.
