# SFX TIMELINE — 실제 v004 12초 결과

아래는 실제 렌더된 **18개 레이어의 삽입 시각**이다. 시간은 30fps, PCM은 스테레오 48kHz/576,000샘플/12초 기준이다. 독립 v002 WAV audit의 mix·SFX·BGM·narration·raw mix 5개 파일이 최종 v004와 바이트 동일하므로 레이어·variant·attack 근거를 그대로 연결할 수 있다. v005 효과음 전용은 동일한 영상·SFX cue를 사용하고 BGM을 끈 별도 버전이다. 삽입 시각과 음원의 10%-peak attack onset, 실제 시각 첫 가시성은 구분한다.

| SFX 삽입 초 | 0기준 프레임 | 연결 사건 | 레이어 | Category | 실제 Variant | Intensity | 시각 첫 가시성 초 | PCM onset−시각 (프레임) |
|---:|---:|---|---|---|---|---|---:|---:|
| 0.000000 | 0 | Opening (시각 사건 미연결) | core | IMPACT_MEDIUM | IMPACT_MEDIUM_02 | HIGH | — | — |
| 0.133333 | 4 | E001 / country_reveal | core | COUNTRY_REVEAL | COUNTRY_REVEAL_03 | LOW | 0.166667 | -0.994375 |
| 0.700000 | 21 | E002 / route_start | core | ROUTE_START | ROUTE_START_02 | MEDIUM | 0.700000 | +0.021250 |
| 1.200000 | 36 | E003 / entity_departure | core | AIRCRAFT_PASS | AIRCRAFT_PASS_02 | MEDIUM | 1.233333 | -0.979375 |
| 2.033333 | 61 | E004 / destination_preview | core | CITY_REVEAL | CITY_REVEAL_02 | LOW | 2.033333 | +0.005000 |
| 3.200000 | 96 | E005 / milestone_reveal | core | ROUTE_PROGRESS | ROUTE_PROGRESS_03 | SUBTLE | 3.233333 | -0.994375 |
| 4.433333 | 133 | E006 / country_reveal | core | COUNTRY_REVEAL | COUNTRY_REVEAL_02 | LOW | 4.433333 | +0.006250 |
| 5.133333 | 154 | E007 / arrival | core | ROUTE_COMPLETE | ROUTE_COMPLETE_03 | MEDIUM | 5.133333 | +0.005000 |
| 5.833333 | 175 | E008 / new_variable | core | NEW_VARIABLE | NEW_VARIABLE_01 | HIGH | 5.866667 | -0.994375 |
| 6.633333 | 199 | E009 / route_blocked | core | ROUTE_BLOCK | ROUTE_BLOCK_01 | HIGH | 6.633333 | +0.006875 |
| 6.666667 | 200 | E009 / route_blocked | post-hit | WARNING | WARNING_02 | SUBTLE | — | — |
| 8.200000 | 246 | E010 / route_reroute | core | ROUTE_REROUTE | ROUTE_REROUTE_03 | MEDIUM | 8.200000 | +0.020625 |
| 8.766667 | 263 | E011 / network_expand | pre-hit | ZOOM_IN | ZOOM_IN_01 | SUBTLE | — | — |
| 8.966667 | 269 | E011 / network_expand | core | MID_PEAK | MID_PEAK_02 | HIGH | 8.966667 | +0.016250 |
| 9.066667 | 272 | E011 / network_expand | post-hit | RADAR | RADAR_02 | SUBTLE | — | — |
| 11.033333 | 331 | E012 / final_reveal | pre-hit | ZOOM_IN | ZOOM_IN_02 | SUBTLE | — | — |
| 11.233333 | 337 | E012 / final_reveal | core | FINAL_REVEAL | FINAL_REVEAL_01 | PEAK | 11.233333 | +0.013125 |
| 11.333333 | 340 | E012 / final_reveal | post-hit | RADAR | RADAR_01 | SUBTLE | — | — |

13개 core = 시각 사건 연결 12개 + 0초 opening 1개다. Pre-hit 2개와 post-hit 3개를 더해 18개 layer, 15개 category, 18개 variant를 사용했다. 같은 variant 연속 반복 0회, 4초 이내 같은 variant 재사용 0회다. MID_PEAK와 FINAL_REVEAL은 사운드 Peak core 2개이며, Strict Retention의 이야기상 중간 Peak 1회·Final Reveal 1회와 구분한다. 모든 variant는 프로젝트의 원본 CC0-1.0 합성으로 레퍼런스에서 음원을 복제하지 않았다.

## 실제 프레임 동기화 — 최종 PASS

초기 v002 audio audit는 canonical event의 +1프레임 정책·실제 WAV만 확인했고 최종 픽셀/인코딩 연결을 미확인으로 표시했다. 최종 v004 [FRAME_SOUND_SYNC.json](qc/FRAME_SOUND_SYNC.json)은 실제 post-draw 의미 요소가 처음 보인 시각과 isolated core PCM의 10%-peak onset을 비교하여 **12/12 PASS**, errors·warnings 0을 기록했다. 최대 절댓값은 PCM onset **0.994375프레임**, core 삽입 **1프레임**이다. 허용 정책은 ±1프레임/30fps이고 최대 음원 attack allowance는 1ms, 실제 최대 10%-peak attack은 약 0.708333ms다. 표에서 음수는 시각 요소의 첫 가독 기록보다 core PCM이 조금 먼저 시작됐다는 뜻이다. 모든 core가 시각과 동일한 프레임이라고 표현하지 않는다.

Opening은 특정 의미 사건에 묶이지 않아 별도로 측정하며, pre/post 5개는 준비·잔향 레이어이므로 core 동기화 Gate에서 제외했다. 전체 시각 효과를 optical computer vision으로 인식한 검사나 직접 청취 결과가 아니라 native post-draw visibility receipt와 실제 isolated PCM 비교다.

최종 AAC를 디코딩한 본편·효과음 전용 모두 mastered WAV 대비 **lag 0 sample / 0초**를 확인했다. 576,512개의 decoded sample 중 후단 512 padding을 제외한 576,000개를 비교했고, zero-lag Pearson은 본편 약 0.999980, 효과음 전용 약 0.999960이다. AAC는 손실 압축이므로 WAV와 byte identity를 주장하지 않는다. [ENCODED_TRANSPORT.json](evidence/ENCODED_TRANSPORT.json)에 실제 H.264 트랙 동일성·AAC 비교를 기록했다.

## 짧은 에너지 감소와 BGM 조정

| 연결 | 시작 초 | 실제 길이 | PCM에서 확인한 BGM 중간 gain | 해석 |
|---|---:|---:|---:|---|
| E009 연결 보류 전 | 6.433333 | 0.166667초 | 약 0.56 | 짧은 준비 구간. 전체 영상 정지나 완전 무음이 아님 |
| E012 최종 공개 전 | 11.033333 | 0.166667초 | 약 0.56 | Pre-hit 후 주요 core로 이어짐. 화면 freeze를 입증하는 수치가 아님 |

중요한 core와 연결한 BGM sidechain 이벤트는 5개이며 minimum gain은 0.72다. BGM energy curve·pause attenuation·sidechain을 적용한 실제 stem을 재구성하여 원본 PCM과 비교했고 최대 오차는 설정 tolerance 2×10⁻⁸ 이하다. 믹스의 전체 소리 크기와 이 relative gain을 혼용하지 않는다.

독립 WAV 본편은 −18.93 LUFS/−2.49dBTP, 최종 AAC QC는 −18.5 LUFS/true peak 약 −2.4dB다. SFX 원본 stem은 −31.64 LUFS/−12.57dBTP이지만 최종 mastered SFX-only MP4는 −17.8 LUFS/true peak 약 −2.5dB이므로 원본 stem 수치가 MP4 음량을 뜻하지 않는다.

효과음 전용 v005의 실제 파이프라인 시간은 **13.830초**이고 5개 장면 모두 캐시를 사용하여 새 영상 렌더는 0회다. 본편 v004와 동일한 H.264 영상 트랙을 유지했다. 패키징·검증 기준 전체 wall time **4,100.180851초** 안의 하위 실행값이며 별도로 더하지 않는다. 범위·기록 시각은 [TOTAL_WORK_TIME.json](evidence/TOTAL_WORK_TIME.json)에 있고, Git 공개 후 시간은 포함하지 않는다.

직접 청취는 지원되지 않는다. 파형·라이선스·attack·시각 timestamp·AAC 정렬은 검증했으나 소리가 고급스럽거나 레퍼런스보다 우수하다는 청감 판단은 검증하지 않았다. 레퍼런스 오디오는 나레이션·BGM·효과음이 섞인 track이므로 그 onset 수를 실제 SFX layer 수와 비교하지 않는다. 최종 사용자 청취·승인을 기다린다.

근거: [AUDIO_AUDIT.json](evidence/AUDIO_AUDIT.json), [V004_AUDIO_EQUIVALENCE.json](evidence/V004_AUDIO_EQUIVALENCE.json), [FRAME_SOUND_SYNC.json](qc/FRAME_SOUND_SYNC.json), [ENCODED_TRANSPORT.json](evidence/ENCODED_TRANSPORT.json), [본편](production_rhythm_master_10_15s.mp4), [효과음 전용](production_rhythm_master_sfx_only.mp4). 링크는 실제 로컬 공개 패키지에 복사된 파일의 상대 위치다. 로컬 파일 존재와 공개 HTTP 다운로드 검증은 구분하며 publishing은 보고서 작성 시 진행 전이다.
