# 무료 모바일 운영 검증 산출물

외부 웹앱은 아직 생성하지 않았다. 개인 GitHub 로그인·무료 할당량/과금 차단 확인·2-core Codespace 생성 후 비공개7860 포트를 사용한다. 자세한 절차와 검증 범위는 [배포 보고서](../../../world-simulation-shorts-engine/deployment/DEPLOYMENT_REPORT.md)와 [운영 안내](../../../world-simulation-shorts-engine/deployment/README.md)에 있다.

실제12초 검증 영상:

- [BGM+SFX MP4](deployment_validation_12s.mp4)
- [무음 MP4](deployment_validation_12s_muted.mp4)
- [SFX 전용 MP4](deployment_validation_12s_sfx_only.mp4)
- [주요 프레임](contact_sheet.png)
- [전체 QC](native_v001/qc_report.json)
- [Scene Plan](native_v001/scene_plan_readable.md)
- [출처/라이선스](native_v001/source_report.md)

규격은1080×1920/30fps/H.264/12.000초이다. 내부2160×3840. TTS/자막 OFF. 기존 테스트 계획을 새 버전으로 보존하며 Scene 하나만 새로 렌더하고4개를 캐시로 읽었다. 오디오 변경본은5개 모두 재사용했고 영상 decode 해시와 무음 MP4가 같다. 75초나 MASTER 영상은 재렌더하지 않았다.

`native_v001/`과 `audio_only_v002/`에는 검증 export manifest·Scene JSON·각 Scene MP4·audit·QC·출처를 보존했다. 원본 작업/로그인/비밀키/비공개 자산은 포함하지 않는다. 모든 파일은 GitHub 일반 Git100MiB 한도 미만이다.

`PREPUBLICATION_VERIFICATION.json`은 게시 전 검사 기록이다. 게시 후 실제 HTTPS 응답과 전체 파일 SHA 검증은 별도 `PUBLIC_DOWNLOAD_VERIFICATION.json`에서 확인한다. 이 GitHub 다운로드와 로컬375px 검증은 실제 휴대폰으로 Codespaces에 접속한 검증과 구분한다.
