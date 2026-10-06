# PRODUCTION RHYTHM MASTER v001 — 검증 보고서

**12초 검증 샘플의 생성·자동 QC·모바일 브라우저 재생·다운로드 검증을 완료했다.** 그래픽 재설계 대신 승인된 PREMIUM FLAT v004 재질과 MASTER V3 Earth를 유지하면서 속도 변화, 다음 사건 예고, 정보 타이밍과 원본 효과음의 리듬을 조절했다. 기술 검증 통과와 사용자의 최종 스타일 승인은 별개이며, 현재 **사용자 승인 대기**다. 75초 전체 영상은 이번 작업에서 렌더링하지 않았다.

| 결과물 | 실제 규격·옵션 |
|---|---|
| [본편: BGM + 효과음](production_rhythm_master_10_15s.mp4) | 내부 v004, 12.000초, 1080×1920, 9:16, 30fps, H.264/yuv420p, BT.709, AAC. TTS OFF·자막 OFF |
| [효과음 전용](production_rhythm_master_sfx_only.mp4) | 내부 v005. 동일 영상 트랙, BGM OFF·효과음 ON·TTS OFF·자막 OFF |
| [무음 영상](production_rhythm_master_muted.mp4) | 동일 영상, 오디오 없음 |
| [주요 프레임 시트](rhythm_contact_sheet.png) | 완성 MP4의 실제 프레임 검수용 |

4개 FLAT 장면과 2초 Earth 장면으로 구성된다. 내부 렌더는 2160×3840이며 1080×1920으로 다운샘플링했다. 출력 품질은 HIGH, 진행 리듬은 FAST_PLUS다. TTS·자막을 제거한 프로그램이 아니라 이번 샘플의 옵션을 OFF로 설정한 것이다. 프로그램의 모든 TTS 조합을 이번 샘플에서 새로 검증했다고 주장하지 않는다.

## 구현한 리듬

Scene Plan에 **23개 Micro Beat와 12개 component speed ramp**를 기록했다. 카메라·줌·진행 중인 경로 각각의 가속과 감속을 조절했으며, 영상 전체의 배속이나 발화 속도를 올리는 방식이 아니다. 12개 ramp는 4개 FLAT 장면에 적용하고, 마지막 Earth 장면은 기존 캐시를 유지했다. Micro Beat는 예고·움직임·감속·읽기 구간의 세부 설계이며 새 이야기 사건으로 세지 않았다.

민간 항공 연결은 국가 공개 → 항로 시작 → 출발 → 목적지 예고 → 남은 거리 정보 → 다음 국가 → 도착 → 가정된 목적지 변경 → 연결 보류 → 우회 → 두 번째 연결 → 전체 네트워크 공개로 진행된다. 실제 GIS 좌표를 유지하며, 가상 연결 보류·우회는 ASSUMPTION/SIMULATION으로 구분한다. 거리 정보는 수정된 항로 진행률의 남은 구면 거리에서 계산했으며 실제 운항시간·전쟁 결과 예측이 아니다.

최종 360프레임의 post-draw 가시성 기록에서 **12개 사건 / 11종류 / 평균 간격 1.0061초 / 최대 간격 2.2667초 / 첫 3초 4개**를 확인했다. 계획상의 평균은 1.0091초이며 실제 렌더 가시성 평균과 구분한다. 카메라만 움직인 구간, 같은 효과의 성장, 자막 단어 교체는 새 사건으로 세지 않았다. 같은 종류의 연속 사건 최대 길이는 1이다. Strict Retention의 이야기상 **중간 Peak 1회**와 **Final Reveal 1회**를 구분한다. 사운드에서 중요한 두 지점에 Peak core 2개를 사용한 것이 시각·이야기 Peak 2개를 자동 입증하는 것은 아니다.

## 사운드와 실제 동기화

원본 CC0-1.0 합성 효과음으로 **13개 core / 18개 layer / 15개 category / 18개 variant**를 사용했다. 12개 core는 시각 사건에 연결되고 1개는 0초 opening cue다. Pre-hit 2개와 post-hit 3개는 보조 레이어다. 동일 variant 연속 반복 0회, 4초 이내 같은 variant 재사용 0회이며, 이벤트당 최대 레이어 수는 3이다. 원본 레퍼런스 음원을 샘플링하지 않았다.

6.433333초와 11.033333초에 각각 **0.166667초의 짧은 에너지 감소**를 넣었다. 해당 구간의 실제 PCM에서 BGM gain 약 0.56을 확인했고, 중요한 hit에 5개 BGM sidechain 이벤트를 적용했다. 이는 무음·전체 화면 정지·0.166667초 camera freeze를 뜻하지 않는다. 지도와 이동체의 지속 동작은 별도 시각 검수 대상이다.

v002에서 독립 검증한 mix·SFX·BGM·무음 narration·raw mix WAV **5개가 v004와 바이트 단위로 동일**함을 확인했다. 초기 오디오 보고서의 ‘최종 픽셀 동기화 미확인’ 표시는 해당 시점의 한계였으며, 최종 v004의 별도 [FRAME_SOUND_SYNC.json](qc/FRAME_SOUND_SYNC.json)에서 **12개 사건 모두 PASS**로 업데이트됐다. 실제 처음 보이는 post-draw 프레임과 isolated core PCM 10%-peak onset의 최대 차이는 **0.994375프레임**이고, core 삽입 시각의 최대 차이는 **1프레임**이다. 허용 범위는 ±1프레임, 음원 attack allowance는 최대 1ms다. 보조 pre/post 5개와 opening cue는 이 12개 core 비교에서 제외한다. 이 검사는 원본 제작 타임라인이나 광학적 의미 인식·직접 청취가 아니다.

최종 AAC를 다시 디코딩하여 mastered WAV와 비교한 **alignment lag는 본편·효과음 전용 모두 0 sample**이다. 상관계수는 각각 약 0.999980/0.999960이며 AAC 후단 padding을 제외한 원본 576,000샘플을 비교했다. 손실 압축을 WAV와 바이트 동일하다고 주장하지 않는다. 본편 완성 AAC QC는 −18.5 LUFS / true peak 약 −2.4dB, 독립 WAV 분석은 −18.93 LUFS / −2.49dBTP다. 효과음 전용 완성 AAC는 −17.8 LUFS / true peak 약 −2.5dB다. 파일·측정 범위가 달라 수치를 혼용하지 않았다. 상세 18개 실제 레이어는 [SFX_TIMELINE.md](SFX_TIMELINE.md)에 기록했다.

## QC와 모바일 검수

| 검사 | 확인 결과 |
|---|---|
| 최종 기술 QC | 본편·효과음 전용 모두 360프레임 PASS, 실패·경고 0 |
| 검정·완전 중복 프레임 | 0개. 근접 정지 판정 최장 0.633333초 |
| 자산·텍스트·경로 | 누락 자산, clipping, WebGL 오류, broken route 기록 없음 |
| Retention / Diversity | 계획 및 실제 렌더 가시성 Gate 통과. 실제 시청 지속률의 측정은 아님 |
| 프레임·오디오 연결 | 시각 사건 12/12, ±1프레임 범위 PASS. AAC zero-lag 비교 PASS |
| 모바일 브라우저 본편 | 실제 Chromium 375×812 viewport, 12초 끝까지 재생, 360 decoded / dropped 0 / corrupt 0 / stall 0 |
| 모바일 브라우저 효과음 전용 | 같은 viewport, 12초 끝까지 재생, 360 decoded / dropped 1 / corrupt 0 / stall 0 |
| 다운로드 | Range 응답 206 및 실제 파일 다운로드·SHA 일치 확인. 공개 호스트 배포와 별도이며 localhost 주소를 사용자 다운로드 링크로 제공하지 않음 |

최종 25개 주요 프레임을 직접 검수한 root 기록에서 FLAT 지형·해안선, 항공기·진행 경로·라벨의 가독성을 확인했다. 10–10.5초 기존 지리 연결 전환은 전체 화면 fog로 정보를 덮지 않으며, 캐시 Earth의 지리가 보인다. Earth의 기존 4개 지명 라벨을 유지했으며 이번 작업에서 새로운 Earth 라벨 계층을 개선했다고 주장하지 않는다. browser playback은 실제 브라우저 검증이고 **물리 스마트폰 하드웨어 시험은 아니다**. 이 문서 작성 단계에서는 영상 디코딩·렌더링을 다시 실행하지 않았다.

## 레퍼런스 대비 해석

A는 이미 진행 중인 지리 설명의 6.5초 발췌다. 작은 지리 대상 가독성 reveal 뒤 방향 정보와 상태 표식이 추가된다. 후반 4.333/5.067/5.400초 cluster 평균 **0.533초는 전 구간 사건 rate가 아니다**. B는 서로 다른 종류의 새 그래픽 onset 7개, onset 간 평균 **1.694초**, 최대 **2.833초**를 확인했다. 점진적 tint·등장 시각은 약 ±0.1–0.2초 불확실성을 유지한다. 두 파일의 끝 2초 CapCut 카드는 사건·의도적 micro-pause·보상에서 제외했다.

공통으로 채택한 원리는 다음 대상 예고 → 가속 → 지리가 읽히는 감속 → 새 정보 → 짧은 결과 인지다. A는 지도 지명과 설명 자막이 공존하고, B는 주로 아래 중앙의 나레이션 조각이므로 둘을 모두 좌표에 연결된 map label로 해석하지 않는다. 현재 샘플은 자막 OFF이며 필요한 장소·거리·상태 정보만 사용한다. 레퍼런스의 대본·국가 순서·색칠·무기/폭발·음원을 복제하지 않았다.

레퍼런스 오디오는 혼합 PCM이므로 transient를 실제 SFX 개수로 바꿔 본 샘플의 18개 layer와 비교할 수 없다. **직접 청취가 불가능하며, 원본보다 소리가 좋다는 판단과 실제 유지율 향상은 검증되지 않았다.** 원본 이미지를 직접 확인한 분석과 본 샘플의 native post-draw 이벤트 QC는 서로 다른 방법이며 동일한 자동 detector의 비교값이 아니다.

## 실제 제작 시간과 캐시

| 실제 실행 | 새 장면 / 캐시 | 장면 렌더 | 해당 버전 전체 |
|---|---:|---:|---:|
| 본편 v004 | 4 / 1 | 981.003초 | 996.576초 (약 16분 36.6초) |
| 효과음 전용 v005 | 0 / 5 | 0초 | 13.830초 |

본편 오디오 준비 1.561초, 조립·오디오 mux 1.787초, QC 10.593초이며 전체 값은 기타 준비·기록 시간을 포함한 실제 실행값이다. 효과음 전용은 오디오 준비 1.582초, 조립·mux 1.207초, QC 9.708초다. 이전 캐시 장면의 제작시간은 이 버전 실행시간에 포함하지 않는다. v005의 5개 장면 MP4와 해당 캐시 실제 SHA가 v004와 동일하고, 본편·무음·효과음 전용의 H.264 elementary stream SHA는 모두 동일하다. 효과음 전용을 위해 영상 렌더를 새로 하지 않았다.

실제 작업 시작 **2026-10-06 00:07:03.780636 UTC**부터 패키징·검증 기록 **01:15:23.961487 UTC**까지의 wall time은 **4,100.180851초 / 68분 20.181초**다. [TOTAL_WORK_TIME.json](evidence/TOTAL_WORK_TIME.json)에 실제 시작·기록 시각을 저장했다. 이 범위에는 레퍼런스 분석, 구현, 테스트, 프레임 검수, 진단용 부분 렌더, 최종 12초 렌더, 효과음 전용 캐시 시험과 패키징이 포함된다. 본편 완료 기록은 **01:01:39.113931 UTC**, 효과음 전용 완료 기록은 **01:03:31.680086 UTC**다. 코드 작성만의 시간은 독립 측정하지 않아 null이며 CPU compute time으로 바꿔 말하지 않는다. 본편 996.576초·효과음 전용 13.830초는 이 wall 구간 안의 하위 실행값이므로 **4,100.180851초에 다시 더하지 않는다**. Git 공개는 이 패키징 기준 기록 뒤의 작업이며 공개 후 시간은 별도로 측정한다.

## 보존과 출처

독립 보존 검사에서 역사적 기준 SHA가 있는 **1,012개 고유 파일 / 3,197,249,828바이트**가 일치했다. MASTER V1/V2/V3·완성 75초 baseline 124개, 기존 pre-generator 570개, 승인된 그래픽·Earth texture·GIS·지형·font 25개가 보존됐다. 이전 구현 134개 멤버는 원본 archive에 보존돼 있으며, 리듬 구현 과정에서 변경한 14개 멤버를 ‘현재 코드까지 모두 불변’이라고 표현하지 않는다. 최종 source lock 28개가 일치하고, 기존 Git 기준 commit은 현재 이력의 ancestor로 유지된다. 과거 digest가 없는 중간 파일은 존재·현재 SHA inventory만 확인했으며 시간상 byte identity를 소급 주장하지 않는다.

Natural Earth 국가·해안선·지명·지형은 public domain, Earth day/night/cloud는 Solar System Scope **CC BY 4.0**(출처 표시 필요), 새 효과음은 프로젝트 원본 절차적 합성 **CC0-1.0**이다. FLAT relief는 Natural Earth의 cartographic shaded texture이며 새 DEM/물리 지형 시뮬레이션을 만들었다고 주장하지 않는다. 항공기 크기는 지도 가독성을 위한 cartographic proxy다. [source_report.md](source_report.md)에 원본 URL·저작자·라이선스·SHA를 기록했다. 업로드한 레퍼런스 영상·이미지·오디오는 공개 패키지에 포함하지 않는다.

## 남은 한계와 승인 범위

최종 소리의 질감·볼륨 선호·레퍼런스 대비 우위는 사용자의 실제 청취가 필요하다. 물리폰·스피커·다양한 브라우저 하드웨어 시험, 실제 시청 지속률 A/B 측정, 75초 확장은 하지 않았다. 기존 Earth texture 연결부·축척 proxy·네트워크 overview의 미세 라벨 한계는 그래픽 동결 범위에 남아 있다. 이번 완료는 12초 기술·전송 검증의 완료다. 기술 인증에 따라 새 기획의 권장 기본값은 FAST_PLUS로 반영했다. 청감·스타일 최종 승인은 대기하며, 기존 저장 계획을 변경하거나 75초 렌더를 자동 시작하지 않는다.

GitHub 공식 문서와 공식 limit variables를 실제 HTTP 200으로 확인한 결과, 일반 Git 경고 기준은 50MiB, 개별 파일 상한은 100MiB, 브라우저 업로드 상한은 25MiB다. 본편·효과음 전용·무음 파일은 각각 17,682,618 / 17,414,582 / 17,260,953바이트로 모두 상한 아래이며 Git LFS·분할 ZIP이 필요하지 않다. 확인 기록은 [GITHUB_FILE_SIZE_CHECK.json](evidence/GITHUB_FILE_SIZE_CHECK.json)에 있다. 용량 확인과 실제 GitHub 공개·다운로드 검증은 별도이며, 이 보고서 작성 시 publishing은 아직 완료되지 않았다.

근거 파일: [본편 QC](qc/qc_report.md), [실제 프레임 동기화](qc/FRAME_SOUND_SYNC.json), [독립 WAV 검증](evidence/AUDIO_AUDIT.json), [v004 오디오 동일성](evidence/V004_AUDIO_EQUIVALENCE.json), [AAC·H.264 전송 검증](evidence/ENCODED_TRANSPORT.json), [효과음 전용 캐시](evidence/CACHE_PROOF.json), [보존](evidence/INDEPENDENT_PRESERVATION.json), [모바일 본편](evidence/mobile_main.json), [모바일 효과음 전용](evidence/mobile_sfx_only.json), [시각 검수](evidence/DIRECT_VISUAL_REVIEW.json), [Scene Plan](scene_plan.json). 파일 링크는 실제 로컬 패키지로 복사된 산출물·근거의 상대 위치다. [TOTAL_WORK_TIME.json](evidence/TOTAL_WORK_TIME.json)은 이미 실제 기록한 패키징·검증 기준 wall time이며 Git 공개 후 시간과 분리한다. 로컬 패키지 파일 존재를 공개 HTTP 다운로드 완료로 대신하지 않는다.
