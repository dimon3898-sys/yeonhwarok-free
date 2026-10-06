# gcube 휴대폰 운영 안내

배포 예정 이미지: `ghcr.io/dimon3898-sys/world-simulation-shorts-engine:gcube-v001`.
**현재 이 문서는 이미지 게시·gcube 실제 배포·GPU 실측 완료를 의미하지 않습니다.** 이미지 게시와 아래 실제 환경 검수가 끝난 뒤 운영합니다. gcube는 유료 서비스이며 사용하지 않는 배포 시간도 과금됩니다.

## 휴대폰에서 설정하는 5단계

1. [gcube 콘솔](https://console.gcube.ai/)에 로그인합니다. 게시된 이미지가 준비되었는지 확인하고, 저장소 관리에서 **gcube 자체 Personal Storage**를 준비합니다. 실제 계정에서 제공하는 용량·요금을 확인합니다. 컨테이너 연결 경로는 `/world-storage`입니다. GHCR 패키지가 비공개라면 GitHub 소유자가 해당 패키지의 **Package settings → Change visibility → Public**으로 공개해야 인증 없이 가져올 수 있습니다. 아직 게시되지 않은 이미지로 워크로드를 배포하지 않습니다.
2. **Workload Mode → 새 워크로드 등록(Create Workload)**에서 저장소 유형 **GitHub**, 위 이미지 주소, 컨테이너 포트 **8000**을 지정합니다. **컨테이너 명령은 비워** 이미지 시작 설정을 사용합니다. Personal Storage에서 준비한 자체 저장소를 선택하고 `/world-storage`에 연결합니다. 환경변수에 `WORLD_ENGINE_OWNER_CODE`로 직접 정한 **16자 이상 512자 이하의 비밀 로그인 코드**를 넣습니다. 앞뒤 공백·제어 문자를 피하고 공개 문서나 이미지에 넣지 않습니다. 필수 환경변수는 `WORLD_ENGINE_OWNER_CODE` 하나입니다. 포트 8000, `gpu-required`, 필수 저장소 `/world-storage`는 이미지·프로그램 기본값을 사용합니다.
3. **현재 사용 가능한 GPU**에서 CPU·RAM·디스크와 실제 시간당 요금을 함께 비교해 필요한 조건을 충족하는 가장 저렴한 노드를 고릅니다. RTX5070은 실제 제공·가격·GPU 검수 조건이 맞을 때 선택하며, 더 비싼 GPU의 속도 우위를 미리 가정하지 않습니다. 이미지 포트 검증과 총 예상 금액을 확인한 뒤 배포합니다. 최소 CUDA 버전 입력이 필요하면 실제 드라이버 조건을 확인합니다. 이 엔진은 CUDA Toolkit을 사용하지 않으므로 임의 CUDA 버전을 요구하지 않습니다.
4. 상태가 **배포**가 되면 워크로드 상세 **개요 → 서비스 URL**을 엽니다. 공식 주소 형식은 `https://xxxxxxxx.gcube.ai`이며 실제 발급 주소를 사용합니다. 소유자 코드로 WorldEngine에 로그인하고 아래 GPU·저장소 검수를 확인합니다. 필요할 때만 실제 주소의 origin(경로 없이 `https://발급호스트`)을 `WORLD_ENGINE_PUBLIC_ORIGIN`으로 명시합니다. 주제 입력 → 계획 확인 → 승인 → 렌더 → 재생·MP4 다운로드 순서로 사용합니다. 별도 75초 샘플 렌더는 실행하지 않습니다.
5. MP4 다운로드와 필요한 상태 보존을 확인한 뒤 gcube 워크로드 목록에서 **배포중지 → 확인**을 누르고 **종료** 상태를 확인합니다. **브라우저 닫기, 앱 로그아웃, 서버 종료·오류는 gcube 워크로드 중지나 과금 중지를 뜻하지 않습니다.** 재배포 후 같은 코드와 저장소로 로그인해 이전 파일·상태가 남았는지 확인합니다. 자동 깨우기와 서비스 주소 유지 여부는 아직 검증되지 않았습니다.

## 실제 환경에서 확인할 조건

이미지의 기본 드라이버 설정은 `NVIDIA_DRIVER_CAPABILITIES=graphics,utility`입니다. 이미지는 시작할 때 NVIDIA 장치와 같은 서버 계정의 Chromium WebGL2 그리기·GPU renderer를 확인합니다. `gpu-required`에서 하드웨어 GPU를 확인하지 못하면 시작을 중단합니다. GPU 장치가 보이는 것만으로 성공으로 처리하지 않습니다. 원래 FFmpeg 인코더는 **CPU `libx264`**이며 CUDA Toolkit·NVENC를 사용하지 않습니다. GPU 가속 대상은 브라우저 그리기이고, 속도 향상은 실제 렌더 측정 전까지 미확인입니다. 배포 예정 이미지의 영상 길이 상한은 180초이고 작업 마감은 기본 3,600초입니다. 고급 설정 `WORLD_ENGINE_MAX_JOB_SECONDS`로 최대 14,400초까지 조정할 수 있으나 실제 시간·비용을 확인한 경우에만 사용합니다. 작업 마감은 provider 과금 중지가 아닙니다. 짧은 10~15초 QA와 80초 운영 비용 검증은 각각 확인해야 합니다.

운영은 `/world-storage`의 실제 마운트를 요구합니다. 시작 시 독립 프로세스 파일 잠금, `0600` 권한, atomic rename, 디렉터리 동기화를 검사합니다. 검수 통과도 클라우드 장애·재배포 시 영속성을 보증하지 않으므로 실제 중지·재배포 보존 확인이 추가로 필요합니다. 기존 소유자 코드가 있으면 같은 값을 사용해야 하며 자동으로 교체하지 않습니다. Dropbox/S3 백업 마운트의 POSIX 동작은 가정하지 않습니다.

공식 문서는 **백업 저장소 없이 중지하면 컨테이너 데이터·환경이 삭제**된다고 명시합니다. 저장소 선택 누락이나 검수 실패를 영속성 성공으로 처리하지 않습니다. 저장소 없이 제한된 벤치마크를 별도로 승인한 경우에만 `WORLD_ENGINE_STORAGE_MODE=ephemeral`, `WORLD_ENGINE_STORAGE_PATH=/data`를 사용합니다. 이 모드는 운영용이 아니며 **중지하면 결과·캐시·로그인 상태를 잃을 수 있습니다**. 필요한 파일을 먼저 다운로드합니다. `WORLD_ENGINE_RENDER_MODE=cpu`도 별도 비교 측정용이며 GPU 검증 성공으로 표시되지 않습니다.

## 비용과 확인 범위

**목표는 80초 영상 1편, 월 30편입니다.** 영상 재생 길이 80초는 실제 렌더 가동 시간이 아닙니다. 80초 1편 예상 비용은 해당 계획의 장면 수·복잡도·캐시 조건을 검증한 실측 가동 시간(시간 단위)에 실제 선택 노드의 시간당 요금을 적용하고, 부팅·대기·재시도와 네트워크·저장소·세금 등 실제 청구 항목을 더해 계산합니다. 월 30편은 각 편의 검증된 가동 시간·요금을 합산해야 합니다. 짧은 장면 벤치마크나 캐시가 재사용된 결과를 영상 길이 비율로 늘려 80초 비용을 추정하지 않습니다. 현재 GPU 클라우드의 80초 1편 렌더 시간·RTX5070 단가·월 30편 비용은 실측하지 않았으며 처리량이나 금액을 보장하지 않습니다. 사용자 확인 최소 충전 `20,000P`, 부가세 포함 `22,000원`은 이 문서에서 별도로 검증한 가격이 아닙니다.

공식 CLI에는 예약 START/STOP 기능이 있지만 이 구성은 provider API 중지나 유휴 자동 중지를 설정하지 않습니다. 명시적으로 중지하지 않으면 과금이 계속됩니다. 실제 계정의 잔액·소진 차단·노드 가격·자체 저장소 요금, HTTPS 전달 헤더와 Android 로그인·다운로드는 배포 후 확인할 항목입니다.

출처 검증일: 2026-10-06 KST. [공식 등록 안내](https://github.com/Data-Alliance/gai-platform-docs/blob/master/docs/user-guide/workload/register-workload.ko.md) · [종료 안내](https://github.com/Data-Alliance/gai-platform-docs/blob/master/docs/user-guide/workload/stop-workload.ko.md) · [저장소 안내](https://github.com/Data-Alliance/gai-platform-docs/blob/master/docs/user-guide/sign-up/storage-management.ko.md) · [원문·HTTP 시각·SHA256 증거](../../docs/evidence/gcube_official_sources_v001/REPORT.md).
