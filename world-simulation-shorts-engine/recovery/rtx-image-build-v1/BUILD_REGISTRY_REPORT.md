**GPU_IMAGE_READY_FOR_DEPLOYMENT**

기존 RTX 패키지를 그대로 사용하여 실제 Docker build, GHCR push, 별도 새
runner의 digest pull 및 소스 무결성 검증을 완료했습니다. GPU 배포,
실제 NVIDIA/WebGL2 검사와 5초 장면 렌더링은 실행하지 않았습니다.

| 확인 항목 | 실제 결과 |
|---|---|
| 무료 빌드 환경 | 공개 저장소의 GitHub 표준 `ubuntu-24.04`, overlay2, 빌드 직전 여유 약 85GiB; 20GiB gate 통과 |
| 기존 Codex 빌더 | vfs, 약 1.87GiB; 빌드하지 않음. 기존 이미지·캐시·볼륨 삭제 없음 |
| GHCR 인증·쓰기 | 저장소 Actions의 생성된 `GITHUB_TOKEN` 사용. 실제 push 성공과 원격 manifest/config 검증으로 확인 |
| Docker build | PASS, `linux/amd64`, 1,570,248,543 bytes |
| GHCR 등록 | PASS, 신규 고유 태그; 기존 태그 overwrite/delete 없음 |
| 독립 pull | PASS, 새 runner가 immutable digest로 pull; config SHA와 160개 staged 파일/6개 검증된 파생 캐시의 증거 일치 |
| 보호 | 기존 FINAL·ASTRA CPU·렌더러·카메라·전선·기존 RTX 패키지 변경 0건 |
| Secret Scan | 실제 이미지 application tree 및 알려진 credential path/environment 검사 PASS, credential findings 0 |
| 필수 temp-only | 0; 소스·workflow·테스트·증거·재현 지침 Git 저장 |
| 빌드·등록 차단 문제 | 없음 |

신규 태그는 `rtx4080s-2f9158b-38663698599-1`입니다. gCube 이미지 입력에는
다음 immutable reference를 사용합니다.

```text
ghcr.io/dimon3898-sys/world-simulation-shorts-engine@sha256:82a4d9086edc2345cd3f00430ff4c354ee3fbaedcef5f0b927a0d5f9c5e16a37
```

Registry manifest digest는 위 SHA입니다. 검증된 local/remote/pulled config
digest는 `sha256:1e784975dd022458c06f95fcd8804f1c6adc0ed0640db106e6e588f1049adb4a`
입니다. Config digest와 registry manifest digest를 구분하여 기록했습니다.

| 포함된 소스 | 기준 |
|---|---|
| 기존 RTX 패키지 / image revision label | `2f9158ba2df2a9f58362fb0b17118b8dc19f705a` |
| ASTRA CPU 공급자·캐시·Scene JSON·중립 데이터 | `a002d89492734bfa9d17b98145ee6cb9a3b366a2` |
| 65422 전선 발광 및 기존 런타임 | `45af879d7417abba58e9ebd59d8e6630a785ac28` |
| 새 CI wrapper | `d1515d02cf4e7823382789772c5aea36d7b26206` |
| Source contract SHA-256 | `5938d0f33168daae415d9573701cafe290bcdd9850a14f4cb61c966560640180` |

Source contract가 지정한 원본 140개 파일을 Git blob까지 검증했고,
기존 package overlay 20개를 포함해 전체 160개를 이미지에서 다시 검사했습니다.
기존 renderer API와 SwiftShader launcher를 수정하지 않았습니다.

| 이미지 내부 CPU 의존성 | 실제 검증 버전 |
|---|---|
| Python / NumPy / Pillow | 3.12.3 / 1.26.4 / 10.2.0 |
| GDAL / libnetcdf | 3.10.3 / 4.9.2 |
| Node / Playwright | 24.19.0 / 1.62.1 |
| Chromium | 155.0.8059.79 |
| FFmpeg / FFprobe | 6.1.1 / 6.1.1, libx264 |

GDAL/netCDF 필수 native API와 terrain, classic NetCDF, NetCDF4, surface,
neutral 5개 소형 CPU parser probe가 통과했습니다. UID 1000과 network-none
조건에서 Playwright module을 로드하고 16×16 검정 2프레임 codec probe를
확인했습니다. Chromium page, GPU draw/readPixels와 실제 장면은 실행하지
않았으므로 GPU나 영상 품질 PASS로 해석하지 않습니다.

확인된 문제는 기존 코드를 변경하지 않고 새 검증 경로에서 해결했습니다.
기존 Dockerfile이 생성한 Python cache 6개는 원본 소스 SHA, interpreter
magic, timestamp/size와 재컴파일 body가 모두 일치해야 인정합니다.
캐시를 실행하거나 unmarshalling하지 않으며 다른 추가 파일은 계속 거부합니다.

Gitleaks는 기존 `assets/flat/SOURCES.json`의 `cache_key`를 한 번 API 키로
오탐했습니다. 생성 코드와 저장된 레시피를 확인하여 공개된 콘텐츠 주소
SHA-256임을 입증하고 [근거](NON_CREDENTIAL_EVIDENCE.json)를 영구 저장했습니다.
정확한 원본 파일 SHA·경로·필드·해시값만 `generic-api-key` rule의 legacy
allowlist로 제한했습니다. 전체 파일이나 vendor 경로를 제외하지 않았고,
entropy threshold를 낮추지 않았습니다. 실제 스캐너 시험에서 같은 파일의
추가 테스트 키, 다른 필드와 다른 파일은 계속 탐지됐습니다. 최종 스캔은
exit 0/findings 0이며 검토된 비인증 공개 checksum 예외 1건을 별도 기록합니다.
Gitleaks 8.24.3의 전역 allowlist가 AND를 무시하는 문제도 실제 시험으로
확인하여 전역 방식은 사용하지 않았습니다.

기존 104개 완료 테스트와 기존 감사 결과를 재사용했습니다. 새 경로의
초기 95개 집중 mock 검사, 캐시 변경 영향 범위 30개, 단계별 증거 5개,
실제 스캐너 정책 5개를 검사했습니다. 정책 연동 변경 후 해당 증거 5개만
재검증했으며 기존 104개 전체는 재실행하지 않았습니다. 실제 빌드·이미지
검사·push·pull 증거를 mock 결과와 구분하여 저장했습니다.

성공 실행은 [Actions 38663698599](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/38663698599)
이며 전체 workflow 결과 SUCCESS, 소요 2m 30s입니다.
[build evidence](runs/38663698599-1/build.json)는 commit
`a209f7d50328cca5514f56f981481d848e74e73a`,
[pull evidence](runs/38663698599-1/pull.json)는 commit
`9534c397adccb3e3e28c927b05861380b3022ce1`에 원격 저장됐습니다.
pull 보고서의 `imageBuilt=false`는 새 pull runner에서 build하지 않았다는
뜻입니다. Registry read-only helper의 `writeVerified=false`도 해당 GET
검사가 write 시험을 수행하지 않았다는 뜻이며, 별도의 실제 push 성공이
패키지 쓰기 권한을 입증합니다. 합산 결과는 [RESULT.json](RESULT.json)에 있습니다.

실패한 세 실행의 보고서와 중간 구현 commit도 보존했습니다. 각 확인된
원인·수정·집중 재검증을 저장한 뒤 진행했고 근거 없는 동일 빌드를
반복하지 않았습니다. 소스 checksum 목록은 [SHA256SUMS](SHA256SUMS)입니다.

이미지 build/등록을 위해 사용자가 추가로 제공해야 할 인증정보나 유료
빌더 설정은 없습니다. 실제 gCube pull, NVIDIA 드라이버 전달, GPU 모델,
Chromium WebGL2 draw/readPixels와 렌더링은 미검증입니다. 배포를 별도로
승인한 뒤 기존 `rtx-gpu-package-v1/GCUBE_SETTINGS.md`, `GCUBE_EXECUTION.md`,
`GPU_HARDWARE_VALIDATION_TODO.md`의 설정과 하드웨어 검증 순서를 적용해야 합니다.
ASTRA CPU 계층의 포함을 실제 GPU material 연결/영상 품질 검증으로 보고하지 않습니다.

Codex의 직접 `api.github.com` 경로는 여전히 403이었습니다. 이 제한은
Actions 인증·Git/공개 저장 증거 경로로 우회하지 않고 독립적으로 작업을
완료했으므로 image blocker가 아닙니다. 직접 API 모니터링이 필요하면
기존 164개 host/credentials를 보존한 추가 허용 draft를 환경 설정에서
게시해야 합니다. 토큰 값, 비밀번호, SSH 키는 코드·이미지·보고서에 넣지 않았습니다.

이번 작업은 여기서 종료합니다. **USER_REVIEW_REQUIRED** — GPU 배포,
유료 작업, 5초 렌더링, 다음 개발 단계와 FINAL 승격은 자동 실행하지 않습니다.
