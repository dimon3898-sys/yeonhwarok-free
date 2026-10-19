# Studio·운영·오디오 연결 감사

감사 기준은 `c0f2868e9cab8a269c2bd8552dc09920e5e53863`이며 현재 운영 이미지 범위는 `8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da`이다. 이번 범위는 정적 소스·명시적 이미지 manifest·보관된 독립 pull 증거를 읽었다. 새 GPU·SwiftShader draw, 컨테이너 실행, 유료 작업, 사용자 private job 조회는 하지 않았다.

## 중요한 호출 계약

- 실제 Studio 입력은 JSON 구조화 prompt 또는 직접 Scene JSON이다. 자유문장만으로 카메라·전선·점령·효과를 조작하는 일반 AI가 아니다.
- 모바일 UI는 제출마다 최상위 `sfx={enabled,gain}`을 만들어 보낸다. 서버는 이것을 prompt 내부 `sfx`보다 우선한다. UI 최초 slider는70%, 서버 normalize 기본은65%다. 따라서 JSON 내부gain65%를 붙여넣어도 slider70%를 그대로 두면 실제 제출은70%다. UI에는 custom cues/exportWav editor가 없다. 이들은 exact API/structured wrapper 경로에 존재하지만 UI가 outer sfx를 덮어쓰는 점을 반드시 구분해야 한다.
- 기본 SFX 자동 배치는 각 `productionV3.eventChapters` 시작의 EVENT_TRANSITION이다. 모든 전선 이동·점령 완료·군대 표식에 자동으로 적절한 종류의 소리를 추론하는 것은 아니다. 6종류 cue는 실제 eventId와 그 이벤트 범위 내 global frame으로 명시 제공 가능하다.
- 현재 시간 구간 수정은 **SFX만**이다. 효과음 끄기/켜기/음량70% 및 명시 revision JSON을 지원한다. 예시로 자주 요구된 “25~35초 카메라 확대·이동 느리게”는 이 구현에서 `STUDIO_VISUAL_REVISION_UNSUPPORTED`이며 이 요청을 성공 예제로 제시하면 안 된다.
- 별도 backend cache는 장면·원본·공통timeline·재질·camera·이웃 경계 hash를 검사한다. 이것을 Studio 자유문장 시각 부분수정이 이미 연결됐다는 근거로 쓰면 안 된다.

## 운영 image 구분

- 현재8ef393는 HTTPS 초기등록/프록시 fix + Studio51파일 + 동결 부모엔진373파일을 포함한다. 근거는 `studio-https-proxy-fix-v1/runs/39085567166-1/pull.json`의 nested imageHashes다. 운영 이미지 포함은 렌더 경로 선택 및 hardware output과 다르다.
- 현 경로는 장면마다 검증 MP4와 SHA를 결과 마운트로 내보내며 mount readback 후 다음 장면으로 이동한다. 외부Dropbox sync/download은 별도 미검증이다. 개인 trust anchor가 사라지면 공유 MP4+SHA만으로 NVIDIA provenance를 복구할 수 없다.
- 후기 `studio-durability-v1`, `studio-dropbox-offline-v1`, `studio-dropbox-gpu-production-v1`에는 암호화 Scene/cache 외부백업·장면전 fail-closed barrier·fresh-root복구·offline OAuth가 실제로 구현되어 있다. 별도c3bdd이미지 계층이며 현재8ef393에 선택되지 않는다. 따라서 미구현이 아니라 **현재운영 NOT_WIRED**다.
- 독립 `world-engine-connect`용 모바일PKCE와 GitHub sealedbox Secret 저장 코드는 별도 사이트 범위다. Secret 등록이 gCube 전달·현재Studio백업활성화와 같지 않다. 다른저장소의 최신Pages배포를 이번코드만으로 단정하지 않는다.

## 보호·증거 한계

- 원본owner인증, fixedHTTPSOrigin/Host, CSRF, nativeNVIDIAadmission, 소스/imagehash, 명시동의·비용·만료·retry한도, claim/중복실행차단을 재사용한다. HTTP웹health가 NVIDIA렌더PASS는 아니다.
- 앱maxWallSeconds 및 validUntil은 GPU과금종료 기능이 아니다. current정책값·소유자비밀값·private상태경로·raw로그는 공개자료에 넣지 않는다.
- 현재 STUDIO_JOB_NOT_FOUND는 “해당job ID를현재state에서찾지못함”이다. 브라우저localStorage의 이전ID 때문일수있으나 그오류하나로 전체작업부재·데이터유실·원인을단정하지않는다.
- 원격실제80초job의 PLAN/AUDIO/영수증/최종MP4를 이번감사에서 읽지않았다. 저장소preset이 실제사용입력과동일하다고 주장하지않는다. 그영역은 NOT_VERIFIED로 유지한다.
- 전체저장소 `engine/audio.py`의TTS·외부내레이션·BGM·ASS자막은 실제구현이 존재한다. 해당4개본문의Git blob이감사base와일치함을확인했다. 현재Studio는GPU계획을무음으로유지한뒤전용SFX만추가하므로 해당레거시오디오는 현재Studio에서NOT_WIRED다. 전역미구현으로표시하지않는다.

## 문서/코드 범위

이번에 작성한 것은 `parts/studio_operations.json`과 본 notes뿐이다. 기존 소스·FINAL·Candidate·Asset·Secret·운영image는 변경하지 않았다. 기록은 정적 감사이며 새 테스트PASS나 하드웨어 검증 주장으로 사용하면 안 된다.
