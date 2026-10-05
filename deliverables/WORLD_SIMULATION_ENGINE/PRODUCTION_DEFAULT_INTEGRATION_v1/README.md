# Production Default Integration v1

승인된 PREMIUM FLAT v004를 기본으로 사용하고, 필요한 규모 공개에 MASTER V3 Earth를 사용하는 정식 기본 프리셋입니다. FAST는 장면 내부의 카메라·항로·강조 타이밍을 조절하며 완성 영상이나 TTS를 배속하지 않습니다. 기존 MASTER, 75초 영상, Scene, 캐시와 Git 이력은 보존했습니다.

## 검증 영상

- [12초 통합 영상 — TTS/BGM/SFX](production_default_integration_12s.mp4)
- [무음 영상](production_default_integration_12s_muted.mp4)
- [SFX OFF 비교 — TTS/BGM 유지](production_default_integration_12s_sfx_off.mp4)

세 파일은 1080×1920 / 9:16 / 30fps / H.264 MP4이며 같은 영상 화면을 사용합니다. 자막은 이번 샘플에서 OFF입니다. 모바일 브라우저 전체 재생과 실제 첨부 다운로드를 검사했습니다.

## 문서와 증거

- [Production Default](PRODUCTION_DEFAULT.md)
- [Pace System](PACE_SYSTEM.md)
- [SFX Library](SFX_LIBRARY.md)
- [QC Report](QC_REPORT.md)
- [실측 Benchmark](BENCHMARK.md)
- [Scene Plan](scene_plan_readable.md), [Scene JSON](scene_plan.json), [대본](script.txt)
- [출처·라이선스](source_report.md), [주요 프레임](contact_sheet.png)

프리셋은 검증 인증서와 영상·핵심 소스의 SHA-256으로 활성화됩니다. 새 기획의 사용자 승인 단계는 유지합니다. 이번 통합 검증 이후 75초 렌더나 새 실전 소재는 자동으로 시작하지 않습니다.

현재 검증된 native Flat 지형은 동아시아입니다. 다른 지역은 가독성을 확보한 기존 V3 Earth를 사용합니다. 오프라인 한국어 TTS는 기계적인 음질이며, 실물 휴대폰 테스트와 사람의 직접 청취는 수행하지 않았습니다.
