# gcube-cli-examples

gcube 워크로드를 Claude Code 와 함께 배포하는 두 가지 방식의 예시 자료입니다.

- **examples/usage1-pytorch-jupyterlab** — Claude Code + SPEC.md 로 PyTorch + JupyterLab 환경 배포
- **examples/usage2-comfyui-z-image-turbo** — Claude Code 스킬로 ComfyUI + Z-Image-Turbo 환경 배포

스킬 (`skills/gcube-workload-create.zip`) 은 활용 2 에서 사용됩니다.

> 본 자료는 작성 시점(2026-05)의 gcube CLI 기준입니다.
> 최신 gcube CLI 와 명령·옵션이 다를 수 있으며, 추후 업데이트 예정입니다.


## 구조

| 폴더 | 내용 |
|---|---|
| `skills/gcube-workload-create.zip` | gcube 워크로드 배포 Claude Code 스킬 |
| `examples/usage1-pytorch-jupyterlab/` | PyTorch + JupyterLab 배포 예시 |
| `examples/usage2-comfyui-z-image-turbo/` | ComfyUI + Z-Image-Turbo 배포 예시 |


## 사전 준비

- gcube-cli (설치 + 토큰 등록 완료)
- GitHub Personal Access Token (repo · ghcr push 권한)
- Claude Code 또는 Claude Desktop


## examples/usage1 — PyTorch + JupyterLab

Claude Code 에 `SPEC.md` 를 작성해두면, 명세 따라 결과물을 작성합니다.

### 사용법

1. `CLAUDE.md` · `SPEC.md` 의 사용자 정보(GitHub username 등)를 본인 값으로 정정
2. Claude Code 실행 → `SPEC.md 따라 작업 진행해줘`
3. 생성된 `Dockerfile` · `build.yml` · `workload.yaml` 확인 후 GitHub push
4. GitHub Actions 탭 → "Run workflow" 수동 트리거로 이미지 빌드
5. `gcube workload register -f workload.yaml` 로 배포

자세한 내용은 `examples/usage1-pytorch-jupyterlab/README.md` 참고.


## examples/usage2 — ComfyUI + Z-Image-Turbo

Claude Code 스킬을 사용해 워크로드 배포를 단계별로 진행합니다.

### 사용법

1. `skills/gcube-workload-create.zip` 다운로드 후 스킬 등록 (아래)
2. Claude Code 실행 → `gcube 에 ComfyUI 워크로드 띄워줘` 등 자연어 요청
3. 스킬이 4단계 (정보 수집 → 설계 → 이미지 제작 → 배포) 로 함께 진행
4. `examples/usage2-comfyui-z-image-turbo/` 의 결과물 파일을 참고 자료로 활용 가능

자세한 내용은 `examples/usage2-comfyui-z-image-turbo/README.md` 참고.


## 스킬 설치

### Claude Desktop

Settings → Customize → Skills → Upload 로 zip 업로드

### Claude Code

zip 압축 해제 후 폴더를 `~/.claude/skills/` 에 복사

OS별 경로:

| 환경 | 경로 |
|---|---|
| macOS | `/Users/<user>/.claude/skills/` |
| Linux | `/home/<user>/.claude/skills/` |
| Windows 네이티브 | `C:\Users\<user>\.claude\skills\` |
| Windows + WSL | WSL 내부 `~/.claude/skills/` (별도 파일시스템) |


## GitHub Actions 트리거

각 예시 폴더의 `.github/workflows/build.yml` 은 수동 트리거(`workflow_dispatch`)로 설정되어 있습니다.

GitHub repo 의 Actions 탭에서 "Run workflow" 버튼으로 빌드를 실행할 수 있습니다.
push 마다 자동 빌드되도록 하려면 `on:` 부분을 다음과 같이 정정합니다:

```yaml
on:
  push:
    branches: [main]
```
