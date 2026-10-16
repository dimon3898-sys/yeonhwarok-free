# REFERENCE VISUAL MASTER V2 실행 결과

새 V2 후보의 구현·CPU 검사·실제 SwiftShader 검사·GHCR 등록·별도 runner digest pull을 완료했다. 실제 NVIDIA 실행과 영상 품질 최종 승인은 아직 수행하지 않았다. 카메라 유지 구간의 추가 소프트웨어 증거는 별도 기록한다.

## 1. 레퍼런스와 기존 F의 차이

실제 첨부 파일은 `WORLD_ENGINE_REFERENCE_65379_COMPRESSED.mp4`이며 SHA-256은 `5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6`이다. 요청의 `65395.mp4` 별도 원본은 확인되지 않았다. 첨부 원본 전체31.813189초·958프레임을 실제 디코딩했고 오류0을 확인했다. 전체 시간대의64개 표본과 주요 원본 크기 장면을 시각 검토했다. 958장을 모두 사람이 검수했다고 주장하지 않는다.

상단/하단 휴대폰 UI, 소셜 버튼, 채널 정보, 자막은 제외했다. 마지막 약3.8초는 국기/outro이므로 점령 확장 비교에서 제외했다. 현재 장면과 같은 사건 진행 구간은 약5.181813–10.181813초다. 가려진 픽셀은 지도 결함으로 취급하지 않았다. 원본·UI·추출 레퍼런스 PNG는 Public Review나 Docker 이미지에 넣지 않았다.

레퍼런스에서는 기존 보유 영역과 밝은 신규 점령 띠, 백색 이동 전선, 금빛 실제 외곽선이 구분된다. 기존 F는 보유/신규 점령 색상이 같아 이 관계가 약했다. 실제 F NVIDIA MP4는 이번 작업 환경에서 확보하지 못했다. F 비교는 저장된 실제 SwiftShader 픽셀과 불변 소스를 사용했으며 실제 GPU 영상 비교로 표시하지 않는다.

## 2–5. 확인한 결함·수정·재사용·파일

| 항목 | 실제 구현과 범위 | 주요 새 파일 |
| --- | --- | --- |
| 점령 | 기존 분류기/초기·현재 경계/시간축 재사용. 신규 점령에만 밝기1.12·불투명도.84 적용. 보유/패배 영역은 기존 재질 유지 | `gain_style_core.mjs`, `gain_territory.mjs` |
| 지도 | 기존 지원 마스크·거리 블렌딩 재사용,48px 후보. 실제 지원 내부에만 육지 대비1.2·노출1.04, 유효 해양 노출1.2·teal .12. NoData/범위 밖 fallback 유지 | `source_grade_core.mjs`, `source_grade_pass.mjs`, `reference_source_material.mjs` |
| 경계 | 기존 이동 전선 알고리즘 유지. 백색 프로필은 기존 공개 한도 안에서 조정. 검증된 동일 frame G+B 실제 영역 union에만 유한 금빛 외곽광. 내부 공유 경계·R-only 주변 육지에는 금빛 생성 안 함 | `native_domain_coverage.mjs`, `frontier_ref2.mjs`, `coverage_outer_glow.mjs` |
| 표식 | 기존8개 디자인·국기·위치·회전·역할 유지. 기존 SAT/layout으로 전150프레임 검증한 정적1.14배 | `unit-size-profile.mjs` |
| 카메라 | 기존 Core 수정 없이 Scene key 후보.96–105프레임10프레임 위치/extent/roll 유지,18프레임 진입·이탈. 사건·객체 시간은 계속 진행 | `camera-profile.mjs` |
| 실행 | 독립 profile/job/capture signature, 기존 GPU lease·하드웨어 검사·인코더·내보내기·연결 독립 관리자 재사용 | `ref2_runtime.mjs`, `ref2_adapter.mjs`, `prepare_ref2.py`, `capture_ref2.mjs`, `job_ref2.py`, `launch_ref2.py` |

기존 FINAL·V4·카메라·원본 데이터·소스·아트·영상·이미지는 수정/삭제0건이다. 변경은 새 namespace와 새 workflow 추가로 제한했다. 원본160개와 고정 부모31개 파일의 이미지 내부 해시를 검증했다. 새 실행 manifest는56개 source/tool/dependency 바인딩을 검증한다. 기존 manifest를 재생성하지 않았다.

## 6–7. A/B와 무료 검증

기본 A=기존 F, B=점령만, C=지도만, D=전선/표식, E=카메라만, F=통합이다. A–D는 같은 기존 카메라, E/F는 같은 후보 카메라를 사용했다. 사건·지리·해상도는 고정했다. 실제 SwiftShader `draw/readPixels`는12개 주 프레임과 표식 제거 ablation2회이며 전체150프레임 영상 검증은 아니다. 실제 이미지 내부에서 다시 검사했다.

- 새 집중 CPU 검사136 PASS,0 FAIL,0 SKIP. 기존104개 전체 suite는 반복하지 않았다.
- A의0/75/149 원본 RGBA는 저장된 기존 F와 BIT_EXACT.
- 실제 GL 점령 합성,10개 지원/NoData/음수 육지/수심/해안/graded source 사례,6개 외곽광 사례 PASS. 합성 해안 fixture는 실제 해안 정확도 인증이 아니다.
- 전150프레임 기존 SAT 기준 표식 충돌·critical collision·Safe Area 위반0. 크기104→118.56px, 실제 아트 CPU bounds 폭105.59–108.08px. 확대 표식의 실제 픽셀 폭 계측은 사각 측정 영역 중첩 때문에 **SKIP**이며 PASS로 바꾸지 않았다.
- A75/E75는 유지 구간 전이므로 PNG가 동일하다.96–105 구간의 카메라 차이와 사건 진행은 동일 immutable 이미지를 이용한 별도 읽기 전용 SwiftShader 검증으로 보완한다. 재튜닝·재빌드는 하지 않는다.
- Secret Scan0. 무료 표준 public Actions만 사용했으며 유료 GPU 실행0건이다.

실제 비교 PNG에서는 밝은 점령 띠·백색 전선·금빛 외곽선과 더 큰 국기 표식이 구분된다. 지도 대비 변화는 비교적 작다. ASTRA 경계 RGB jump 결과는 감소/유지/증가가 섞여 있어 **전체 seam 개선 PASS를 선언하지 않는다**. 예: terrain rectangle1px .007163→.007967, surface rectangle4px .012885→.012503. NoData/범위 밖 원본 유지와 합성 순서는 별도로 검증됐다.

## 8–10. 보호 해시와 새 이미지

- 브랜치: `development/reference-visual-master-v2-20261016`
- 구현 CPU checkpoint: `cc66bf4e28427978c04659aede32fe95a94eb46c`
- 실제 이미지 소스: `e9feafc785fbd138cbac3ca4db090380968dc37e`
- GHCR 태그: `reference-v2-233bca7-38831714161-1`
- digest: `sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5`
- 실행 주소: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5`
- 새 source manifest SHA: `28de18a52014ba56e91c31f91af40bc4f81c81b92e0fcf85bd83a651f7da3606`
- 기존 Quality manifest SHA 유지: `cd025141c88f1d5fa196fc58c3026565ceb386b09926f7036638d78ecb3385ff`
- 기존 원본160 source contract SHA 유지: `5938d0f33168daae415d9573701cafe290bcdd9850a14f4cb61c966560640180`
- linux/amd64, 실제 이미지 크기1,571,616,864bytes. 새 이미지 등록/별도 runner pull PASS.

실행 증거: [Actions38831714161](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/38831714161). 상세 수치는 `IMAGE.json`, `AB_COMPARISON.json`, `runs/38831714161-1/build.json`, `pull.json`에 저장했다. 나중 보고서 커밋을 이미지 소스 커밋으로 오인하지 않아야 한다.

## 11. 남은 문제와 경계

실제 NVIDIA 텍스처/화면·VRAM·속도·150프레임 MP4·Dropbox 외부 동기화·모바일 재생·레퍼런스 동급 품질은 미검증이다. CPU 계산의 추가 업로드 pack 한도256MiB는 실제 NVIDIA 총 VRAM 계측이 아니다. 기존 F의 비활성 영역 crop은 그대로 존재하며 전체 국가 항상 표시를 주장하지 않는다. 새 카메라의 추가 crop vertex-frame은0이고 활성 전선/모든 표식은 보호한다. 기존 C1 재사용이며 C2 연속성을 새로 보장하지 않는다.

10개 요청 파라미터 중 사건 transition은 `SCENE_OWNED`만, Event Hold는0만 지원한다. 비지원 값은 명시적으로 거부한다. 카메라 읽기 hold는 사건 hold와 다르다. 허용 범위/기본값은 `PARAMETERS.md`에 기록했다. 재질·시간축·실제 해안·카메라 영상 품질을 기술 테스트만으로 최종 승인하지 않는다.

## 12–14. 사용자 다음 행동과 결과 회수

사용자가 별도 GPU 실행을 승인한 뒤에만 `GCUBE_EXECUTION.md`의 새 태그/설정으로 RTX4080SUPER16GB·shm2GiB·기존 Dropbox `/world-storage`·normal/gpu-required를 사용한다. Command override는 비워 기존 정상 서비스를 유지한다.

```sh
/usr/bin/python3 -B /opt/world-engine-reference-v2/job_ref2.py inspect
/usr/bin/python3 -B /opt/world-engine-reference-v2/job_ref2.py status
/usr/bin/python3 -B /opt/world-engine-reference-v2/job_ref2.py start --confirm-new-job
```

기존 작업 기록이 있다고 나오면 기록을 삭제하지 말고 runbook의 명시적 history acknowledgement를 따른다. 활성 기존 작업과 공통 GPU lease는 우회할 수 없다. 새 작업이 시작된 뒤 터미널이 끊기면 `status`로 확인한다.

완료 `.result`의 고유 새 내보내기 폴더에서 MP4·PNG5장·SHA256SUMS와 별도 receipt를 확인한다.150프레임·1080×1920·30fps·5초·무음과 전체 디코딩을 확인하고 원본 SHA를 검증한다. Dropbox 쓰기 성공과 외부 동기화는 다르므로, GPU 종료 전에 실제 외부 링크 HTTP200·다운로드 SHA 일치·휴대폰 재생을 확인한다. 소스/receipt/diagnostic은 Public Review 밖에 둔다.

현재 Public Review는 실제 소프트웨어 PNG10장과 SHA256SUMS만 포함한다. 외부11개 URL은 HTTP200·원본/다운로드 SHA 동일을 확인했으며 `DOWNLOAD_VERIFICATION.json`에 개별 URL을 기록했다. 새 GPU MP4를 생성했다고 보고하지 않는다.

최종 품질 승인과 FINAL 승격은 수행하지 않았다. 사용자 검수와 실제 GPU 실행 승인 대기에서 멈춘다.
