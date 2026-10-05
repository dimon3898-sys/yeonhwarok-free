# PREMIUM FLAT MAP 실측 벤치마크

2026-10-05 UTC. 최초 15초 검증 `project_c047b389d1f8/v001`, S002 부분 수정 v002, 사건 공개 시각을 고친 최종 **v003**의 실제 완료 기록입니다. v003은 450프레임 QC·사건 간격 검사·375×812 브라우저 전체 재생·13개 다운로드 검증을 통과했습니다. 75초 영상은 이번 업데이트에서 다시 렌더하지 않았습니다.

최종 결과: [15초 MP4](../deliverables/WORLD_SIMULATION_ENGINE/PREMIUM_FLAT_MAP_15S_v003/flat_map_premium_test_15s.mp4), [무음 MP4](../deliverables/WORLD_SIMULATION_ENGINE/PREMIUM_FLAT_MAP_15S_v003/flat_map_premium_test_15s_muted.mp4). 이 링크는 저장소의 배포 파일 상대 위치입니다. 공개 HTTP 다운로드 검증은 이 측정 기록에 포함하지 않습니다.

## 측정 조건

| 항목 | 실제 조건 |
|---|---|
| 백엔드 | `CPU_LOCAL`, 브라우저 WebGL 소프트웨어 렌더 + FFmpeg |
| CPU | Intel Xeon Platinum 8573C, 컨테이너 CPU quota 4 CPU |
| 영상 | HIGH, 15초, 5 Scene × 3초, 30 fps |
| 내부/최종 해상도 | 2160×3840 → 1080×1920, H.264/yuv420p/BT.709 |
| Flat | S001~S004, 12초/360프레임, LOCAL_MERCATOR |
| Earth | S005, 3초/90프레임, 보존된 MASTER V3 + 대기 전환 어댑터 |
| 시간 적분 | Flat 1 tap, Earth 7 taps; 둘 다 temporal Scene samples 1 |
| 오디오 | TTS OFF, 자막 OFF, BGM ON, 효과음 13개 |
| Scene 캐시 | 최초 실행: 5개 새 렌더, 재사용 0개 |

전체 실행 시간은 승인된 렌더 작업의 시간입니다. 개발·코드 작성·출처 조사·앞선 정지 프레임 개선·사전 GIS 다운로드·외부 공개 작업의 시간을 포함하지 않습니다. Story/Scene 생성 시간도 이 값에 합산하지 않았습니다.

## Scene별 실측

`native`는 해당 Node 렌더러 manifest의 `elapsedSeconds`, `Scene 전체`는 Python 관리자의 실제 호출·결과 보존 시간을 포함한 값입니다. 서로 다른 범위를 섞어 합산하지 않습니다.

| Scene / 영상 구간 | 백엔드 | native 렌더(초) | Scene 전체(초) |
|---|---|---:|---:|
| S001 / 0~3초 | FLAT_MAP_PREMIUM | 308.105 | 309.082 |
| S002 / 3~6초 | FLAT_MAP_PREMIUM | 255.100 | 256.469 |
| S003 / 6~9초 | FLAT_MAP_PREMIUM | 295.258 | 296.819 |
| S004 / 9~12초 | FLAT_MAP_PREMIUM | 335.058 | 336.681 |
| S005 / 12~15초 | MASTER V3 Earth 전환 | 1640.626 | 1642.213 |
| 합계 | 15초 | **2834.147** | **2841.264** |

| 단계 | 실측(초) |
|---|---:|
| Scene 렌더 관리 합계 | 2841.264163 |
| BGM/효과음 준비 | 2.126147 |
| 장면 조립·오디오 mux·자막 옵션 처리 | 2.496618 |
| 최종 전체 프레임 QC | 16.067373 |
| 그 외 자산 검증·작업 관리 | 2.378985 |
| **전체 렌더 작업** | **2864.333285초 = 47분 44.333초** |

근거: [project_result.json](projects-flat-validation/project_c047b389d1f8/versions/v001/renders/project_result.json), [scene_results.json](projects-flat-validation/project_c047b389d1f8/versions/v001/renders/scene_results.json). Scene별 native manifest는 같은 `renders/S001`~`S005` 폴더에 보존합니다.

## Flat과 V3 렌더 비용 비교

| 실제 이번 영상의 구간 | 영상 길이 | native 총 시간 | 영상 1초당 렌더 시간 |
|---|---:|---:|---:|
| Flat 4 Scene | 12초 | 1193.521초 | **99.460초** |
| V3 Earth 1 Scene | 3초 | 1640.626초 | **546.875초** |

이번 샘플에서 영상 1초당 Flat 비용은 Earth의 약 18.19%이며 Earth/Flat 비율은 **5.50배**입니다. CPU·HIGH·4K 내부 해상도는 같지만 장면 내용·셰이더·구름·대기·시간 적분 tap 수(1 대 7)가 다릅니다. 같은 구도를 두 렌더러로 동일 조건에서 반복한 통제 실험이 아니므로 모든 주제에 적용할 속도 배율이나 75초 제작시간으로 일반화하지 않습니다.

Flat의 12초가 전체 영상의 80%인데도 native 렌더 시간의 약 42.11%만 차지했습니다. 이 사례에서는 3초 Earth가 약 57.89%를 소비했습니다. 정보 설명은 Flat, 중요한 규모 공개만 V3로 선택할 때 비용을 줄일 수 있다는 실제 근거입니다. 최고 해상도를 유지한 CPU 렌더는 아직 빠른 제작 환경이 아닙니다.

## 지형 자산 캐시 실측

확장된 동아시아 Natural Earth 지형 PNG를 다시 요청한 실제 검증에서 기존 cache key·PNG SHA·픽셀 크기가 일치했고, cache-hit 검증은 **0.805707087초**였습니다. 이는 재렌더 시간이 아니라 **디스크 자산 재사용 검증 시간**입니다.

근거: [ACTUAL_PRODUCTION_TERRAIN_CACHE_REUSE.json](docs/evidence/flat_expanded_terrain_seam_fix_20261005T091004836767Z/ACTUAL_PRODUCTION_TERRAIN_CACHE_REUSE.json).

디스크 terrain cache와 Scene MP4 cache는 지속됩니다. 투영 geometry와 GPU texture Map은 브라우저 프로세스 안에서만 재사용됩니다. 별도 브라우저 사이에 모든 국경·타일·라벨 geometry가 영구 캐시된다고 주장하지 않습니다.

## 부분 재렌더 검증 상태

**v002 부분 재렌더 실제 완료.** 자연어 요청으로 3~6초 S002의 `camera_speed`만 1.2배로 수정하고 Diff를 승인했습니다. 실제 `cached_scene_count=4`, `rendered_scene_count=1`입니다. S001/S003/S004/S005의 영상·audit SHA는 v001과 같으며 현재 렌더 시간은0입니다. S002는 새 영상 SHA를 갖고 code/assets SHA는 같으며 입력 Scene JSON만 다릅니다.

| v002 단계 | 실측(초) |
|---|---:|
| S002 신규 Scene 렌더 | 269.777719 |
| 오디오 준비 | 1.976935 |
| 조립·mux | 2.428360 |
| 전체 QC | 14.754390 |
| **부분 수정 작업 전체** | **290.543848초 = 4분50.544초** |

새 최종15초의450프레임 기술 QC와375×812 브라우저 전체 재생·13개 다운로드 SHA 검증도 완료했습니다. 브라우저 callback349.9ms 지연1건이 관찰돼 해당 버전의 stall0은 주장하지 않습니다. encoded frame freeze는0이며 기존4 Scene을 다시 렌더한 것은 아닙니다.

근거: [v002 실측](projects-flat-validation/project_c047b389d1f8/versions/v002/renders/project_result.json), [4 cached / 1 new SHA 증거](validation/flat_premium15_partial_revision_r02/actual_4cache_1new_source_video_audit_proof.json), [v002 재생·다운로드](validation/flat_premium15_v002_playback_download_r01/UI_END_TO_END_REPORT.json).

v001/v002에서 S004 지원 연결은 start_time10.05초, 실제 native 최초 표시10.0667초인데 E011은10.7초에 새 연결이라고 기록됐습니다. 최종 **v003은 S004의 target route/entity 시작만 event와 맞추어 실제 재렌더**했습니다. 나머지4 Scene은 v002와 영상·audit SHA가 같고 이번 렌더 시간0으로 재사용했습니다. 기존 v001/v002와 캐시는 보존했습니다.

| v003 단계 | 실측(초) |
|---|---:|
| S004 신규 Scene 렌더 | 333.022753 |
| 오디오 준비 | 1.816464 |
| 조립·mux | 2.574950 |
| 전체 QC | 17.785908 |
| **신선도 수정 작업 전체** | **356.784606초 = 5분56.785초** |

v003의 실제 E011 첫 표시10.733333초와 최종 공개13.7초 사이 간격은2.9667초이며, 전체 사건 간격 검사와450프레임 기술 QC를 통과했습니다. 모바일 재생은15초 끝까지 종료했고 dropped3/corrupted0/stall0입니다.13개 파일을 실제 attachment로 받아 원본 SHA와 비교했습니다.

근거: [v003 실측](projects-flat-validation/project_c047b389d1f8/versions/v003/renders/project_result.json), [최종 부분 재렌더 SHA 증거](validation/flat_premium15_final_v003_playback_download_r01/actual_v003_4cache_1new_source_video_audit_proof.json), [최종 재생·다운로드](validation/flat_premium15_final_v003_playback_download_r01/UI_END_TO_END_REPORT.json).

## 실제 작업 시간 이력

| 실제 완료 작업 | 전체 실행 시간 |
|---|---:|
| v001 최초5 Scene | 47분44.333초 |
| v002 S002만 속도 수정 | 4분50.544초 |
| v003 S004만 새 연결 공개 수정 | 5분56.785초 |
| **알려진3개 렌더 작업 누계** | **3511.661739초 = 58분31.662초** |

누계는 실제 완료한3개 작업 시간의 합입니다. 개발 시간·검수자의 작업 시간·기다린 시간·정지 프레임 fixture 제작·초기 GIS 다운로드를 포함한 프로젝트 총기간이 아닙니다. 최초 영상 전체 비용과 부분 재렌더 비용을 각각 남겨, 최종 영상을 다시 처음부터 만들었다고 오해하지 않게 합니다.

## 측정 한계

- 같은 15초를 순수 Flat과 순수 V3로 각각 다시 렌더하는 비교는 수행하지 않았습니다. 불필요한 전체 렌더를 피하고 이미 완료된 구간을 사용했습니다.
- 공개 호스팅·실물 스마트폰·스피커 직접 청취는 이 벤치마크의 검증 범위가 아닙니다.
- 새 버전은 수정 Scene만 렌더하고 나머지를 재사용합니다. 캐시 재사용 버전의 실행 시간을 최초 전체 제작 시간처럼 표기하지 않습니다.
- 현재 최고 해상도 지형 ROI는 동아시아입니다. 다른 지역은 기존 글로벌 자료와 별도 검증 자산의 품질·준비 비용을 확인해야 합니다.
