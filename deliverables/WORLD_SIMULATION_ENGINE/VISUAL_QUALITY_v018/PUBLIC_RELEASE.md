# v018 공개 이미지 검증

Container Image: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v018-visual-quality`

Digest: `sha256:7145a2bae3a75478aa68fe3255ff5faf5abfca8aff9aa9e8c34dc9b052a5fa57`

OCI source revision: `ee84e5402719a5971ca7f1f3d2e56b0a392fa473`

[최종 Docker 빌드·검사·익명 pull 실행](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/37859545451)

- 최종 컨테이너: core 671, proxy/GPU 206, 독립 v007 진단 31개. 전체 908 PASS / FAIL 0 / SKIP 0.
- 필수 기존 자산 75개와 추가 지역 PNG 4개 검사 PASS. 지역 PNG의 해시·decode·native resolution·HTTP serving PASS.
- 720개 camera position/quaternion/FOV/state와 기존 사건/텍스트/오디오 계획 UNCHANGED.
- 이미지 안의 libegl1/libvulkan1/libx11-6/libxext6, Chromium, Node, FFmpeg, UID1000 쓰기 경로 PASS.
- 실제 production entrypoint에서 물리 NVIDIA 부재는 GPU_HARDWARE_UNAVAILABLE로 차단하며 서버는 61초 이상 유지. GPU 성공 또는 CPU renderer fallback을 주장하지 않음.
- 익명 public pull, OCI revision 대조, owner login, health, 61초 유지 PASS.

`local-validation.json`의 PENDING_CI는 이미지 소스 커밋 당시 기록이다. 최종 컨테이너·공개 결과는 `public-release-evidence.json`을 기준으로 한다.

실제 RTX4080S AFTER 프레임·NVIDIA 새 material compile/draw·peak VRAM·render time은 NOT_RUN이다. gcube Workload를 시작하거나 변경하지 않았다. 기존 8K night-map의 사각 texel footprint와 2K 높이 자료 한계는 남는다. 도시광 증폭 제한을 원본 해상도 개선으로 보고하지 않는다.

다음 실제 비교는 새 24초 HIGH 계획을 만들어 동일한 카메라의 F000/F240/F435/F630을 MP4와 Diagnostic ZIP에서 대조한다. 과거 승인 계획은 v018로 자동 변경하지 않는다.
