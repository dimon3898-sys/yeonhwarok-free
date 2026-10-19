# 레퍼런스·5초·80초 비교 — 관측과 소스 원인 분리

## 실제 접근한 영상

| 입력 | 실제 확인 | 파일 식별 |
|---|---|---|
| 첨부 WORLD_ENGINE_REFERENCE_65379_COMPRESSED.mp4 | CPU 전체 958프레임 디코딩, 오류 0, 1080×2520, 31.813189초, VFR screen recording. 2fps 전 구간 contact sheet 시각 검토. AAC 존재만 확인하고 음색·클릭 리듬을 청취 검증하지 않음. | SHA256 `5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6` |
| 첨부 WORLD_ENGINE_MOVING_FRONTIER_GLOW_FIX_5S.mp4 (65422 검증 Candidate) | CPU 전체 150프레임 디코딩, 오류 0, 1080×1920, 30fps, 5초, 무음. 전체 2fps contact sheet 검토. | SHA256 `f3de1bdf9244171a47c6e5eccca6aae1370f58d8bf4721a7658b6bca2eed2ef6` |
| 66430 / 실제 80초 MP4 | 이번 첨부·접근 가능한 저장 파일에서 확보하지 못함. 실제 화면 비교와 출력 판정 NOT_VERIFIED. | 비공개 운영 정규화 입력/receipt도 미확보. |

원본 파일명과 실제 SHA를 우선한다. 과거 지시의 다른 번호나 14초 한국전쟁 Candidate를 이 31.8초 레퍼런스로 바꾸어 해석하지 않는다. 5초 Candidate도 source commit/media SHA가 다른 품질 F 전체와 자동 동일시하지 않는다.

## 레퍼런스 시간 흐름 관측

대략적인 관측 구간이며 정확한 사건 날짜·동일 프레임 대응을 주장하지 않는다. 휴대폰 상태바·검색/좋아요/댓글/메뉴·플랫폼 자막은 지도 콘텐츠 목표에서 제외했다.

| 화면 녹화 시간 | 실제 보이는 지도 변화 | 제한 |
|---|---|---|
| 약 0–4초 | 북쪽 붉은 영역과 남쪽 보라 영역, 국기/부대 표식, 불규칙한 밝은 경계 | 플랫폼 UI 영역을 제외해야 함. 역사적 실제 점령 자료로 사용하지 않음. |
| 약 4–12초 | 영역이 변화하며 카메라가 front를 pan/zoom으로 추적; 보라 영역 확대·붉은 영역 후퇴가 읽힘 | 날짜가 다른 current80s와 강제 frame alignment하지 않음. |
| 약 12–20초 | 경계·표식 변화 지속, 약17–20초 항공기 계열 전경 효과 | 물리/실제 부대 이동 검증이 아님. |
| 약 20–28초 | 북쪽으로 화면을 따라가며 보라 영역 확대와 붉은 영역 축소 | 회전량은 계측하지 않아 rotation 지원 여부를 이 영상만으로 확정하지 않음. |
| 약 28–31.813초 | 큰 국기/전환 그래픽이 지도 부분을 가리는 마무리 | 전체 screen recording 길이와 순수 지도 animation 유효 길이는 다름. 순수 지도 구간 끝은 프레임 단위 미계측. |

실제 영상은 녹색 relief 지표·푸른 바다·강한 red/purple 영역·밝은 gold 계열 경계를 보여준다. 이전 설명용 목표 포스터의 과장된 산맥 조명/구름을 영상에 실제 존재한다고 인용하지 않는다.

## 기능별 비교와 최소 연결 방향

아래 current80s 열은 **저장된 source/Scene 경로** 관측이다. 실제80s 영상 픽셀 관측이 아니다. 각 소스의 정확한 줄은 `SOURCE_EVIDENCE_INDEX.csv`와 Runtime Trace를 따른다.

| 목표 | 레퍼런스 / 5초 증거 | current80s 선택 경로 | 확인된 차이 / 최소 후속안 |
|---|---|---|---|
| 영토 변화 전달력 | reference4–28초에서 색 면적 변화. 5초에는 red/purple 상보 영역과 밝은 이동 경계가 보임. | source-bound Area snapshots, blue/cyan held cores; 후기 partial archival 구간은 fill 비움 | scalar counterpart engine과 데이터 의미가 다름. 검증된 양측 ownership 없이는 색상 전체 분할을 새로 만들 수 없음. 별도 presentation adapter 검토. |
| 전선 발광 | irregular boundary에 밝은 core/halo, 5초에도 강조됨 | V3 자체 white/gold front style은 존재. scalar moving-front terrain-light factory는 미호출 | 같은 색이어도 다른 pass. geometry를 보존하는 line-expression bridge를 별도 검증해야 함. “전선 기능 전체 없음”은 오판. |
| 카메라 | reference pan/zoom의 사건 추적, 5초 별도 keyframe profile | V5를 보존한 conservative chapter pan/widen, closest-detail floor 유지 | 5초 roll/zoom keyframe을 그대로 상속하지 않음. 독립 장편 admitted camera profile 필요. |
| 지형·바다·해안 | 녹색 relief/푸른 바다. 5초 source material 사용 | ASTRA height/surface/signed-depth + support-distance blending 연결 | ASTRA 미연결이라고 단정할 수 없음. 실제80s coast/seam/noData pixels는 미검증. physical terrain mesh/ocean physics 아님. |
| 국가/군대 표식 | reference 국기/units, 5초 national tablets | current80s unitPositions 비어 있고 native marker/labels 유지 | historical anchors 부족 + selected adapter 차이. 기존 아이콘 재사용은 가능해도 위치를 창작할 수 없음. |
| 텍스트/정보 밀도 | reference 플랫폼 UI는 제외. 5초 content no-text | currentV4 date/title/partial qualifier 선택 | 공개 근사 원문 자료를 정밀 점령 사실처럼 오해하지 않게 유지한 차이. 현재 prompt로 no-text화 불가. |
| 반복/정적 구간 | reference 연속 변화; 5초150frames | `HOLD_SUPPLIED_SNAPSHOT`/`ARCHIVAL_FRONT_HOLD`는 관측 날짜 snapshot을 유지 | 소스 hold 설계는 확정. 실제80s가 얼마나 정적으로 보이는지는 MP4 확보 후 판정. |

## A–F 원인 분류

- **A 이미지 코드 미포함:** 일부 standalone GPU adapter·후기 backup 등에는 해당. 5초 고급 모듈 전체 누락이라는 설명은 반증됨.
- **B 포함됐으나 미호출:** scalar territory gain, moving-light, national tablets, reference camera 경로.
- **C preset/Scene 선택:** frozenV4, Area palette, conservative camera, partial-front hold·fill suppression.
- **D 데이터/asset:** historical unit anchors와 완전 양측 ownership 부재. 아이콘 코드가 있는 것과 역사 배치 근거는 별개.
- **E 실제 렌더 오류/품질 문제:** 80초 MP4 미확보로 미확정. 끊김/텍스처 seam/성능 오류를 추측하지 않음.
- **F 증거 부족:** 실제 승인 정규화 Scene, runtime capture identity, 완성80s 및 외부 전달 검증.

## 후속 소형 게이트 제안 — 이번에는 실행하지 않음

향후 별도 구현·GPU 비용 승인 이후에만, 동일한 검증된 데이터/Scene/시간축을 고정한 소형 비교에서 import/factory identity → terrain/Area/front layer order → territory/front sync → icons/camera safety → decode/SHA/외부 다운로드를 확인한다. 먼저 실제 기존80s를 확보해 source 경로 가설과 화면을 연결한다. 근거 없는 역사 영토·부대 생성이나 기존 FINAL 변경은 대안이 아니다.

이번 감사는 CPU **기존 영상 디코딩만** 수행했다. GPU·SwiftShader draw·신규 영상 제작·품질 PASS 선언은 0건이다.
