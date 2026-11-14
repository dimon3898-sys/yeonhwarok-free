# 실제 6초 GPU 성공 기준과 신규 입력 호환성

기준 브랜치: `fix/reference-6s-formal-admission-20261113`  
조사 기준 HEAD: `015ddb60ceee25641ca89e52745618a06220dd5f`  
판정: **기존 6초 GPU 성공 증거 확인 / 몽골 HISTORICAL 180 입력 호환성 BLOCKED**.

## 가장 상세한 실제 성공 기록

기존 증거 폴더: `world-simulation-shorts-engine/recovery/aviation-gpu-execution-evidence-20261030/`.
`RESULT.json`, `GPU_EVIDENCE_OBSERVATIONS.json`, `ENVIRONMENT_OBSERVATIONS.json`, `INPUT_RECONSTRUCTION.json`, `DROPBOX_PERSISTENCE_INDEX.json`을 재사용했다. 증거 보존 커밋은 `fdc4294fd2bcd528229a0f030b803c353cd3a2c4`다. 기존 GPU 실행·디코딩 검사를 반복하지 않았다.

- 작업: `studio-03d9b670cd764ce5823ea4720af1b410`, 2026-10-30 01:14:36.720358Z 생성, 01:16:44.006993Z 완료.
- 실제 결과: COMPLETED, 180/180프레임, 2개 장면, capture exit 0, cleanupVerified true.
- GPU: gCube #5373, RTX 4080 SUPER, NVIDIA 580.159.03. Pod `dep5373-7498c68478-2fvkw`, node `wn7e9b3dce`.
- Native WebGL2 ANGLE NVIDIA Vulkan 1.4.312, GPU 안정성 pixel-draw 증거 6개, 프레임 readback 180개, GL error 0, RGBA 고유 해시 162개. Software fallback 성공으로 취급하지 않았다.
- MP4: 1080×1920, 30fps, 6초, H.264 무음, 180프레임, 2,208,937바이트. 기존 fullDecode PASS.
- MP4 SHA256: `99b6181372b98dc9e8032dafb0443367cd4222eb7850f9f006ec706728fab8e7`.
- 이번 read-only Dropbox 메타데이터 조회에서도 동일 보관 경로에 2,208,937바이트 MP4가 존재한다. 새 다운로드·디코딩·해시 재계산은 하지 않았다. 기존 receipt의 externalDownloadVerified는 false이므로 사용자 다운로드 완료를 새로 주장하지 않는다.

## 성공 당시 설정 이미지와 소스 대응

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine:g2-diagnostics-v1-27f9fa5c133a-40767632198
sha256:9378a86d81341172b48910606d44ca389afd28f5e96b615ceec6fa84321b62da
sourceCommit: 27f9fa5c133a65ed08824cf047116128bd9dfe5e
```

정식 빌드 기록은 `recovery/capture-diagnostics-g2-v1/COMPLETION_RECEIPT.json` 및 `evidence/ci-40767632198/`이다. 게시 run 40767632198에서 tag와 digest의 원격 manifest body 동일성이 이미 검증됐다. 이미지 config ID와 위 OCI manifest digest를 혼동하지 않았다.

이 이미지는 성공 당시 설정 및 환경 관측값에 연결된다. 원본 GPU receipt의 imageDigest는 null이고 실제 Pod imageID는 회수되지 않았으므로, **Pod가 사용한 digest의 독립적 attestation까지 확보했다고 선언하지 않는다**.

빌드 후 runtime manifest SHA는 `a4ef7cdca49e64881f737d4c88d949dafa502868fa6a1df7d392170e0170f314`, startup manifest SHA는 `3cac42a8da8fd76994b20035666e3f15c94779073deb0d0d4ae515a0b2da8407`, generated manifest SHA는 `2fc89c792de8ebb49eae00241bf5cc10acd78c80934dbc1ada21c9d62d21438e`다. 빌드 커밋에 체크인된 runtime manifest 전체 해시는 빌드 후 manifest와 다르지만, 이번에 검사한 `controller/common.py`의 바이트 수와 SHA256은 게시 이미지 증거 manifest에도 정확히 일치한다. 전체 manifest 동일성으로 과장하지 않았다.

## 실제 실행 환경에서 확인된 값

- Chromium 155.0.8059.79, Playwright 1.62.1, Node v24.19.0.
- 선택된 실행 인수: `--disable-dev-shm-usage --headless=new --enable-gpu --enable-webgl --use-gl=angle --use-angle=vulkan --enable-features=Vulkan --disable-vulkan-surface --disable-software-rasterizer`.
- Sandbox CHROMIUM_SANDBOX, rootTestOnly false. 종료된 GPU 프로세스 전체 argv는 미회수.
- Chromium 설정 `/usr/bin/chromium`, 사후 resolved 경로 `/opt/google/chrome/google-chrome`. 원본 프로세스 `/proc/exe`는 미회수.
- `GPU_BACKEND=vulkan`, `WORLD_ENGINE_RENDER_MODE=gpu-required`, `NVIDIA_DRIVER_CAPABILITIES=all`.
- `WORLD_ENGINE_STUDIO_STATE_ROOT=/var/lib/world-engine-studio-v2/auth`, `WORLD_ENGINE_NODE_DEPS=/opt/rtx-package/repo/cinematic-world-map`.
- 배포 image digest 환경값 두 개는 위 9378…62da다.
- `VK_ICD_FILENAMES` 관측값 null. EGL selector 설정은 기록되지 않았다. 이를 EGL 미설정 또는 현재 노드 정상의 증거로 해석하지 않는다.
- NVIDIA ICD library `libGLX_nvidia.so.0`, file_format 1.0.1, API 1.4.312. Vulkan loader 1.3.275.0-1build1.
- sourceCommit의 `controller/nvidia_backend.py`는 UID/GID 1000, private directory 0700 소유권을 요구한다. 실제 성공 프로세스의 전체 권한 스냅샷은 미회수.
- 정식 경로: Studio → `nvidia_controller.py` → `nvidia_backend.py` → `nvidia_worker.py` → `lease_supervisor.py` → `backend/capture_nvidia.mjs`. 모든 controller/backend 파일은 `recovery/codex-to-gcube-handoff-v1/` 아래다.
- 입력: bundled `AVIATION_EUROPE_NL.json`과 원본 receipt의 canonical 입력 해시 일치. 원본 HTTP body는 미보존. 입력 hash `05f50ae38c9d45e93ee14c6873f40a37398f27995de3468739ed44d5b8b379d9`.
- 출력: private `capture/VIDEO.mp4` → export `public/WORLD_ENGINE_STUDIO_VIDEO.mp4`. 공개 보관 디렉터리의 studio ID가 capture job ID와 다른 것은 기존 export 기록에 명시돼 있으며, 임의로 같은 ID로 바꾸지 않았다.

## 더 최근의 6초 성공도 함께 보존

`production/reference-6s-20261112/CHECKPOINT.json`의 previousSuccessfulRelease는 required-fixes 이미지다. `quality-v1/GPU_SUCCESS_RECEIPT.json`은 사용자 제공 실제 GPU MP4 180프레임과 companion hash 일치를 보존한다. 영상 SHA는 `e804f277bc4664a2e8e090aa13a690fb5f718610b65ab8bdb7eaa1e69c51d9e7`, 기존 fullDecode PASS는 `quality-v1/USER_QUALITY_SUMMARY.json`에 있다. 단, 그 receipt 자체에는 job와 digest를 결합한 attestation이 없다.

| 후보 | 소스 커밋 | digest | GPU 성공 연결 강도 |
|---|---|---|---|
| required-fixes | f0f44d269b9a | `sha256:8f7a91201840b84769523ec4cd2430df54470403883d57c40e26d3d1e36ce329` | CHECKPOINT의 이전 성공 release + 실제 MP4 증거 |
| quality-boundary-camera | 044bde9e8bc3 | `sha256:cf52ba25cb46b16b6bee0ba3149d1e8048a3d6a5abf05f1cfda932f7094665a8` | 설정 readback와 후속 실제 MP4 비교 증거; job/digest attestation 없음 |
| quality-v2 | 2c26a3bfa6e3 | `sha256:ed2ff287e7617b201876059210603e4f507632ca7143ae1768414364faf848ce` | 사용자 품질 승인 기록은 있으나 후보의 actualNvidiaRenderVerified는 false; 독립적 GPU 성공 이미지로 승격하지 않음 |

모든 정확한 이미지 주소는 `SUCCESS_IMAGE_COMPATIBILITY.json`에 기록했다. 최근 0/600 WebGL 실패는 위 기존 성공 PASS를 무효화하지 않는다. 반대로 과거 성공이 현재 GPU 노드의 WebGL 성공을 보장하지 않는다.

## 이번에 확인한 별도 차단

네 후보의 고정 소스 `controller/common.py::validate_plan()`은 HISTORICAL 6초·180프레임을 `HANDOFF_EXACT_NONHISTORICAL_SIX_SECOND_PLAN_REQUIRED`로 거부한다. Controller와 backend profile도 비역사 범위를 제한한다. 실제 순수 admission 함수를 추출하여 새 HISTORICAL/180 조합만 검사했다. 정상 6초·10초 기존 PASS, GPU, renderer는 재실행하지 않았다.

현재 몽골 `history_authored_v1.mjs`와 기존 106개 연속 도형 runtime은 네 이미지의 빌드 커밋에 없다. 최신 history20 helper도 20초·600프레임 고정 계약이다. **길이만 6초로 바꾸거나 HISTORICAL을 GENERAL로 바꾸는 것은 유효한 해결이 아니다.** 이 결론은 GPU 장애 원인 판정이 아니라 신규 입력의 호환성 판정이다.
