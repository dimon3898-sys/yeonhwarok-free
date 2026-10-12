# SUEZ DETAIL DATA ADMISSION V1 — 결과 보고

조사 기준일: 2026-10-13 (Asia/Seoul).

현재 판정은 `DETAIL_DATA_ADMISSION_BLOCKED`이다. 상세 데이터의 공식 문서와 원본 OSM 비교 자료는 확보했으나, 새 Terrain 원본 픽셀·완전한 GIS 정확도 근거·실측 coastline 정합을 확보하지 못했다. 따라서 `SAFE_DETAIL_EXTENT`를 인증하지 않았고 Static PNG와 V3 animation을 생성하지 않았다. 현재 네트워크 접근 차단은 데이터가 존재하지 않는다는 뜻이 아니다.

[BASELINES]

| 기준점 | Commit | 보존 결과 |
| --- | --- | --- |
| V5 Final | `29b8ee294360812b55ef577b62411de58159003b` | PASS |
| Event V2 | `8cbbbd64573ea87aa56decbc0fb5218071e45bbe` | PASS |
| Suez Data | `69e6ed83acac00bfa7ab1853722f873792a813e1` | PASS |
| V3 Block Evidence | `9cf4661a56db0334bc1d9e936a6671f643562112` | PASS |

`evidence/BASELINE_PROTECTION.json`의 모든 `changed_paths`는 빈 배열이다. Camera V5, Event V2, Renderer Visual, 기존 Suez navigation axis, `193.30 km`와 Suez Canal Authority 출처를 변경하지 않았다.

[DATA SOURCES]

| 역할 | 확인한 Source / Version | 실제 확보 및 한계 |
| --- | --- | --- |
| Terrain / Basemap | ESA/Copernicus Sentinel-2 L2A, Microsoft Planetary Computer 공식 collection 문서 | RGB B02/B03/B04 native grid 10 m 문서 확보. Suez item·원본 COG 픽셀·CRS/affine·정확도·asset SHA 미확보. 약관 링크의 법적 본문도 접근 차단되어 독립 검증 미완료 |
| Terrain / Basemap | USGS/NASA Landsat Collection 2 Level 2, 공식 collection 문서 | RGB native grid 30 m 문서 확보. Suez scene/Tier·QA·원본 픽셀·정확도·asset SHA 미확보. Public Domain 정책 본문 접근 검증 미완료 |
| Terrain / Basemap | Element 84 Earth Search Sentinel-2 L2A | 실제 catalog 접근 차단. 원본 픽셀·item 정보 미확보 |
| Coastline / Water GIS | ESA WorldCover 2021 v200 | 공식 GitHub/AWS registry 문서 확보. 10 m land-cover, CC-BY 4.0, DOI `10.5281/zenodo.7254221` 확인. Suez raster·CRS·물 경계·위치 오차 실측 미확보 |
| Coastline / Water GIS | JRC Global Surface Water v1.4 | 공식 Earth Engine catalog 확보. 1984–2021 Landsat 기반 30 m 자료, Copernicus 이용·출처 표시 조건 확인. Suez raster·정합/위치 오차 미확보 |
| Native Water / Coastline 비교 | 보호된 OSM 원본 XML snapshot | Great Bitter Lake relation 1410016 v21, Little Bitter Lake 1691290 v15, southern canal water relation 7682094 v5를 원본 node ID로만 조립. 유효 multipolygon 3개, 전체 coastline/water 연속 coverage 및 절대 위치 오차는 미인증 |
| Canal / Navigation | OSM relation 7719838 v17 | 기존 axis `5038117 → 925360882`, 원본 92 coordinates / 91 segments 유지. 원본 geometry와 Metric 교체 없음 |
| DEM | 기존 Copernicus GLO-30 원본 COG 4개 및 Float32 height atlas | 원본 grid·SHA·native sample bits·EPSG:4326·유효값 검사. 새 DEM 다운로드 없음. 기존 provenance의 최초 retrieval date와 license 기록 누락도 그대로 명시 |

문서/조회 response의 원본 byte와 retrieval receipts, URL, retrieval date, SHA-256을 각 `research` 하위에 저장했다. 문서 해상도를 실제 획득 데이터의 정확도로 간주하지 않았다. 확보하지 못한 asset의 SHA·CRS·extent·accuracy는 `null`/미확인으로 기록했다.

OSM water 비교는 5,642 / 1,501 / 1,292개의 원본 좌표를 보존했고, coastline 28 ways / 10,944 native node references를 확인했다. Source-relative simplification은 0, 생성·보간 좌표는 0이다. 이것은 절대 위치 오차 0을 의미하지 않는다. OSM `source=Bing`/`source=landsat` tag만으로 검증된 metre error bound를 만들지 않았다. OSM ODbL 1.0과 기존 attribution을 유지했다.

provider catalog·asset·정확도 문서 접근은 현재 destination policy에서 proxy `CONNECT 403`으로 차단됐다. 환경 draft는 기존 도메인을 보존하고 공개 데이터/문서 도메인 20개를 추가한 상태로 저장했지만, 현재 runtime policy에 적용되지 않았다. Review/Save/Publish 뒤 실제 catalog·asset·license·품질 문서 접근을 다시 확인해야 한다. proxy/TLS 우회는 수행하지 않았다.

[DEM]

Native sampling resolution: `EXISTING_SUFFICIENT_FOR_ALL_RESEARCH_CANDIDATES`.

Whole-canal real DEM coverage: `INSUFFICIENT_SPATIAL_COVERAGE`.

기존 7,200×7,200 height atlas의 51,840,000 samples는 모두 finite이며, 네 원본 COG의 sample bits와 일치한다. Native spacing은 1 arc-second이며 연구 확대에서도 1 screen pixel / native sample 한도를 통과한다. 그러나 등록된 북쪽 edge가 약 31°N이어서 31.2757°N까지 이어지는 전체 axis를 덮지 못한다. 원본 node 92개 중 81개와 projected axis length의 **80.7758%**만 실제 DEM footprint에 포함된다.

`requireRealDEM=true`라면 전체 실제 height coverage를 위해 `NEW_DATA_REQUIRED`이다. 현재 Detail profile의 `requireRealDEM=false`에서는 기존 부분 DEM과 native Terrain fallback을 명시적으로 유지할 수 있으므로, sampling resolution만을 이유로 새 DEM을 받지 않았다. 전체 Detail extent에 대한 무조건적인 `DEM_EXISTING_SUFFICIENT` 판정은 하지 않았다. DEM 선택 여부는 Terrain/GIS/geometry/layout 품질 검사를 면제하지 않는다.

북쪽 coverage 부족을 확인한 뒤에만 공식 AWS Open Data registry의 Copernicus DEM 2021 공개 Source를 추가 조사했다. 전체 axis에 필요한 최소 추가 grid cell은 `N31E032`이나 실제 object 존재·원본 byte SHA는 S3 접근 차단으로 미확인이다. 후보 full viewport는 더 많은 cell이 필요하고 ocean tile이 없을 수 있으므로 목록만으로 full coverage를 선언하지 않았다. 새 DEM 원본을 획득하거나 기존 height를 변경하지 않았다.

[DETAIL CANDIDATES]

1080×1920, safe area `[48,72,1032,1848]`, 변경하지 않은 92-coordinate axis와 5.75 px line halo reserve를 이용해 후보를 계산했다. 요청 coverage는 20% → 35% → 50%이며, 최소 확대 후보부터 검사한다. 이 값은 특정 국가의 Camera zoom 상수가 아니다. 각 extent는 전체 geometry bounds와 출력 aspect/safe area에서 계산한 연구 후보이며 인증된 framing이 아니다.

Bounds 순서: `[west, south, east, north]`, EPSG:4326. Coverage는 **safe area 기준 폭 / 높이**이다.

| Candidate | Extent bounds | Projected canal length | Coverage | 새 Terrain ratio | 기존 Terrain ratio X / Y — 참고용 | GIS quality | Decision |
| --- | --- | ---: | --- | --- | --- | --- | --- |
| D0 current | `[23.250000,16.472168,38.150000,39.827832]` | 120.281 px | 2.085% / 6.227% | null | 1.208 / 1.370 | metre error·coast alignment 미확인 | DATA_LIMITED |
| D1 | `[30.125582,26.966870,34.765030,34.239178]` | 386.294 px | 6.696% / 20.000% | null | 3.880 / 4.400 | metre error·coast alignment 미확인 | DATA_LIMITED |
| D2 | `[31.119750,28.525221,33.770863,32.680826]` | 676.015 px | 11.719% / 35.000% | null | 6.790 / 7.700 | metre error·coast alignment 미확인 | DATA_LIMITED |
| D3 | `[31.517417,29.148562,33.373196,32.057485]` | 965.735 px | 16.741% / 50.000% | null | 9.699 / 11.001 | metre error·coast alignment 미확인 | DATA_LIMITED |

모든 후보에서 전체 axis와 halo가 safe area 안에 있고 Marker의 geographic anchor도 safe area 안에 있다. 전체 운하 일부를 crop하지 않았다. Marker full rendered visibility, country/location/title 충돌, Metric placement space와 text safe area는 인증되지 않은 새 frame을 렌더하지 않았으므로 `NOT_MEASURED_UNADMITTED_FRAME`이다.

새 Terrain 원본을 획득하지 못했기 때문에 실제 candidate Terrain ratio와 visible pixelation·water/land/coast mismatch는 측정할 수 없다. 표의 기존 Terrain ratio는 변경하지 않은 현재 raster를 각 확대 후보에 투영한 참고 수치이며, 새 10 m/30 m 후보의 실측 수치가 아니다.

Admission에 필요한 데이터 품질은 다음 단계가 미완료다: 실제 Terrain payload와 native grid/coverage, locked Renderer의 baked-relief data compatibility, 관련 country GIS 및 canal axis의 hash-bound positional/simplification metre evidence, 독립 coastline alignment measurement, 새 extent의 protected graphic/text/Metric measured layout. 문서의 grid resolution만으로 이 항목들을 통과시키지 않았다.

[SAFE DETAIL EXTENT]

**NOT AVAILABLE**.

Bounds / center / width degrees / height degrees: 인증값 없음.

Projected canal length / coverage / Terrain quality / GIS quality: 위 연구 후보의 분석값만 있으며 인증값 없음.

가독성 요구를 만족하는 최소 확대 후보 D1은 기하학적으로 전체 axis를 유지하지만 실제 데이터 품질이 `DATA_LIMITED`여서 `ADMITTED`가 아니다. D2/D3도 동일하게 미인증이다. `SAFE_DETAIL_EXTENT`를 임의로 저장하거나 가장 가까운 후보를 강제 선택하지 않았다.

[DETAIL DATA PROFILE]

`DETAIL_DATA_PROFILE.json` — version `DETAIL_DATA_PROFILE_V1`.

Profile ID: `DETAIL_DATA_PROFILE_PENDING_NATIVE_SOURCE_ACQUISITION`.

Mode: `PRODUCTION_DATA_RESEARCH_NOT_ADMITTED`.

`availableDataResolution`은 공식 문서로 확인한 native grid와 `actualPayloadVerified=false`를 함께 기록한다. `safeScaleRange=null`, `terrainDetailVerified=false`, `gisDetailVerified=false`이며 admission certificate가 아니다. 원본 source hash, profile binding, immutable Event geometry binding, protected Marker/Metric style, native policy, DEM scope와 renderer compatibility precondition을 분리해 보존한다.

일반 API는 국가명/고정 좌표 분기 없이 Event geometry·safe area·current extent·candidate data profile로 후보 생성과 quality audit을 수행한다. 기존 policy의 최대 Terrain **1 px/native texel**, 최대 GIS **1 px verified geometry error**, 요구 coverage **100%**를 그대로 사용한다. 부정확한 정보를 0으로 채우거나 threshold를 낮추지 않았다.

[LOCAL ADMISSION]

Policy respected: **PASS**.

Detail admitted: **NO**.

기존 `LocalDetailAdmission`의 contract와 threshold를 수정하지 않았다. 필요한 Terrain/GIS/DEM provenance/quality 입력이 완전하지 않으므로 legacy result는 `NOT_EVALUATED_INCOMPLETE_INPUTS`다. 현재 legacy LOCAL contract의 Event representation이 point-only인 반면 보호된 V2 axis는 LineString / 91 segments라는 제한도 기록했다. 기존 Event Line을 point로 바꾸거나 LOCAL 경로에 force-allow 하지 않았다.

Profile 기반 새 static-regional input의 품질 인증과 기존 LOCAL runtime permission은 별개다. `safeClosest=null`, `localUsed=false`, effective scale은 `REGIONAL`이다. Terrain spectral RGB를 검증되지 않은 baked relief로 재분류하지 않았다.

API tests: **26/26 PASS** (fail/skipped/cancelled 0). 최종 API에 대한 기존 Profile 재검사도 PASS이며 D0–D3 모두 `DATA_LIMITED`다.

Synthetic 자료는 `SYNTHETIC_DETAIL_AUDIT_PASS`로만 판정하며 production READY를 만들 수 없다. 제공된 DEM 계약은 optional coverage 여부와 관계없이 검증한다. 순수 API가 실제 원본 파일과 native 렌더 픽셀을 인증하는 것은 아니므로, 실제 source bytes/feature hash·정확도·fresh native layout 증거는 신뢰 가능한 별도 생산자가 검증해야 한다. 현재 생산 증거가 없는 항목은 모두 미인증으로 유지했다.

[STATIC PROOF]

PNG: 미생성.

SHA: 없음.

Download URL: 없음.

`SAFE_DETAIL_EXTENT_ADMITTED`가 성립하지 않아 Static PNG를 만들지 않았다. 따라서 HTTP 200 / downloaded SHA 검증을 주장하지 않는다. Public Review에 Source, Diagnostics, Internal Data를 공개하지 않았다. V3 Camera animation과 Event animation도 실행하지 않았다.

[PROTECTION]

V5 Final: **PASS**.

Event V2: **PASS**.

Suez Data: **PASS**.

V3 Block Evidence: **PASS**.

보호 기준점의 tracked files 변경 0. 기존 Terrain sharpen/upscale 0, GIS generated/interpolated coordinates 0, Canal geometry 변경 0, `193.30 km` 및 Metric Source 변경 0, Camera/Renderer/Event style 변경 0. 신규 조사·profile·audit·절차는 별도 recovery 디렉터리에, 범용 API와 집중 검사는 새 모듈·새 테스트 파일에 저장한다. 기존 파일은 변경하지 않는다.

[PERSISTENCE]

Branch: `development/event-system-v1-20261012`.

Commit: 이 보고서와 `DATA_RESEARCH_MANIFEST.json`을 포함하는 Development branch commit. 정확한 최종 commit은 작업 완료 응답 및 Git에서 확인한다 (자기 commit hash를 같은 파일에 재귀적으로 기록하지 않는다).

Required temp-only files: **0**. 영구 저장 inventory의 repository path·byte hash를 commit blob과 대조하며, task 내부의 필수 입력은 모두 저장한다. 기존 setup tools는 영구 recipe로 재현하며 credential/임시 process state를 필수 데이터로 취급하지 않는다.

공식 provider 문서와 acquisition receipts, 원본 OSM 비교 derivative 및 deterministic extraction recipe, 기존 DEM read-only audit, generic Detail profile/API/audit 절차와 측정 결과를 Development branch에 저장한다. 실제 신규 Terrain/GIS raster 원본은 확보하지 못했으므로 runtime source로 등록하지 않는다. Large binary를 새로 만들거나 기존 영구 저장 정책을 변경하지 않았다.

[SECRET SCAN]

저장 전 검사: **PASS — Gitleaks 8.24.3, embedded default rules, 발견 0**. 최종 저장 대상의 byte scope를 저장 직전에 다시 검사한다.

완료 조건은 API key / token / password / credential / private key 발견 0이다. 공개 데이터 접근용 credential을 요청하거나 저장하지 않았다. `evidence/SECRET_SCAN.json`에 pinned scanner hash·redacted result·검사한 파일의 SHA를 저장한다. 저장 후 Git history 및 manifest/commit byte 일치 검사도 별도로 수행한다.

[DECISION]

**DETAIL_DATA_ADMISSION_BLOCKED**.

`DETAIL_DATA_VERIFIED`, `GIS_DETAIL_VERIFIED`, `TERRAIN_DETAIL_VERIFIED`, `SAFE_DETAIL_EXTENT_ADMITTED`가 미완료다. 전체 axis의 analytic safe-area visibility와 baseline/policy 보호만으로 `DETAIL_ADMISSION_READY`를 부여하지 않았다.

[NEXT]

**DETAIL_DATA_ACTION_REQUIRED**.

환경 설정의 공개 source 도메인 변경을 Review/Save/Publish하고 실제 source 접근을 확인한 뒤, 원본 Terrain/GIS를 획득하여 동일한 threshold로 native grid·hash·CRS·coverage·quality/accuracy·coast alignment·locked-renderer compatibility를 검사해야 한다. 필요성이 확인된 경우에만 full real DEM coverage를 보완한다. 그 뒤 admitted static frame에서 Marker/Label/Metric bounds를 측정해야 `SAFE_DETAIL_EXTENT`와 Static PNG를 인증할 수 있다.

이번 결과 제출 뒤 종료한다. V3 Camera animation 자동 재개, Event V2 수정, Camera V5 수정, FINAL 승격, 다음 Plugin 시작은 수행하지 않는다.

환경 draft의 검토·저장·게시 절차는 [cloud-environment-onboarding:setup](skill://plugin_connector_1p_ed5feb9070a08191b08c81c47947bc16/setup/SKILL.md)의 "Saving persists configuration; it does not execute scripts, apply runtime changes, or publish."에 따른다. 현재 runtime 적용 전이므로 실제 원본 자료 요청은 차단 상태이며 환경 설정에서 Review/Save/Publish가 필요하다. 이 절차는 데이터 품질 Admission을 대체하지 않는다.
