# 현재 60분 정책 원인과 240분 변경안

상태: **240분 변경안 준비, 5,200원 비용 증액은 사용자 승인 대기**. 실제 운영 정책·환경변수·워크로드·이미지·기존 작업을 변경하지 않았으며 영상 렌더링은 시작하지 않았다.

## 실제 읽기 전용 관측

무료 표준 Actions [39230383629](https://github.com/dimon3898-sys/yeonhwarok-free/actions/runs/39230383629), evidence commit `c64d9ab`. 공식 gcube-cli0.4.2의 기존 API wrapper로 workload describe와 현재 요금표를 각각 한 번 읽었다. Secret·전체 환경변수·원문 응답·관리자 코드는 출력하지 않았다.

**2026-10-19 18:29:07 KST**의 #5373 상태는 `finish`였다. 이는 앞선 사용자의 9개 사전검사 PASS 시점 이후 관측이다. 재시작·배포·종료·렌더링 호출은 하지 않았다. 이미지 digest 환경변수는 기존8ef393과 일치했다. `WORLD_ENGINE_STUDIO_STATE_ROOT`는 미설정이라 기존 기본 private 경로를 사용하도록 구성돼 있었다.

실제 `WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON`:

| 필드 | 현재 환경변수 값 |
| --- | --- |
| `maxWallSeconds` | 3600 |
| `maxRetries` | 0 |
| `gpuHourlyRate` | 360 |
| `currency` | KRW |
| `maxCostAmount` | 1000 |
| `validUntil` | 2026-10-19T23:59:00+09:00 |

이 환경변수는 60분·최대1,000원이라는 사용자 화면과 일치한다. private `operator_policy.json` 파일 자체나 브라우저 세션을 읽은 것은 아니므로 그 파일의 전체 byte 동일성은 별도 미검증이다.

## 60분이 적용된 이유

240분은 기존 코드가 지원하는 범위이고 자동 기본값이 아니다. 현재 설정에 이전의 시간당360원·3,600초 정책이 남아 있다. GPU 선택이나 사전검사 PASS는 이 수치를 자동으로 갱신하지 않는다. 원본 `studio_controller._policy()`는 private `production/operator_policy.json`을 읽고, 부트스트랩은 해당 파일을 위 환경변수에서 생성하거나 기존 파일을 검증해 사용한다.

현재 이미지는 다른 기존 정책을 덮어쓰지 않는다. 같은 private root에 다른 JSON을 주면 `STUDIO_EXISTING_PRIVATE_CONFIGURATION_PRESERVED`로 차단할 수 있다. 로그아웃/로그인/새로고침은 정책 변경 방법이 아니다. 3,600초인 오디오 재합성 fallback은 신규 승인 GPU 작업의 이번 원인이 아니다.

## 현재 GPU 요금과 승인 금액

공식 `match_gpu_pricing`으로 현재 workload의 GPU SKU를 요금표에 정합했다. VRAM32GB·tier2, catalogue910KRW와 usagePrice390KRW, 합계 상한1,300KRW/시간, 가용true로 응답했다. 배포 GPU spec에는 `price:975`, `maxPrice:1300`이 들어 있었다.

`price:975`를 실제 청구된 고정 시간당 요금으로 단정하지 않는다. 실제 청구 원장/선택 노드의 최종 고정 과금은 조회하지 않았다. 보고서의 `specModelIsRtx5090:false`와 product:null은 이 수집기의 엄격한 내부 문자열 비교가 일치하지 않았다는 뜻이며, 실제 GPU 장치/렌더러가 다르다는 판정이 아니다. 하드웨어 사전검사9PASS는 사용자가 확인한 결과를 그대로 재사용하며 새 GPU probe를 실행하지 않았다.

안전한 새 작업 산정은 확인된 시간당 상한1,300원으로 한다. 4시간 계산은 **5,200원**이다. 이는 기존1,000원 승인을 자동 증액한 것이 아니라 사용자가 별도로 승인할 **변경안**이다. catalogue 하한으로 산정하면3,640원이지만, 그 값만 승인해서 최대1,300원 요금을 덮을 수 있다고 가정하지 않는다. 준비·대기·이미 사용한 시간·저장소 등 제공자 추가 비용은 별도다.

## 기존 만료시각

현재 승인은 **2026-10-19 23:59:00 KST** 만료다. 새 작업 기한은 `min(작업 생성시각 + 14400초, validUntil)`이므로, 이 만료시각을 유지하면서 4시간을 온전히 확보하려면 **오늘19:59:00 KST까지 작업이 생성**되어야 한다. 그보다 늦게 시작하려면 사용자가 새 만료시각을 별도로 승인해야 한다. 이 작업에서 만료시각을 임의 연장하지 않았다.

## 같은 이미지를 유지하는 지원 경로

현재8ef393 이미지에는 운영 정책 갱신 UI/API나 환경변수 hot reload가 없다. 이전 GitHub의 `studio-80s-recovery-v1/policy.py`는 10,800초와 기존 비용/요금 유지만 허용하고 해당 이미지에 포함되지 않아 이 요청의14,400초·비용 증액 수단으로 사용할 수 없다. 파일을 삭제/직접 덮어쓰거나 공개 API를 추가하지 않는다.

따라서 기존 이미지는 그대로 두고, 사용자가 비용 증액을 승인한 후 **다음 필요한 설정 반영 시** 두 환경변수를 함께 설정한다. 현재 관측은 finish였으므로 Codex가 워크로드를 다시 실행할 이유가 없다. 상태가 다시 바뀌었거나 작업이 실행 중이라면 설정 적용 전에 해당 작업부터 확인해야 한다.

```text
WORLD_ENGINE_STUDIO_STATE_ROOT=/var/lib/world-engine-private/engine/studio-240m-20261019-v1
```

```text
WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON={"maxWallSeconds":14400,"maxRetries":0,"gpuHourlyRate":1300,"currency":"KRW","maxCostAmount":5200,"validUntil":"2026-10-19T23:59:00+09:00"}
```

위 JSON은 `PROPOSED_OPERATOR_POLICY_NOT_APPROVED.json`과 같은 값이다. 사용자가 **5,200원 승인과 위 만료시각**을 확인한 경우에만 적용한다. 운영 환경에 이미 적용됐거나 유료 제작을 승인받은 것으로 표시하지 않는다.

새 private 상태는 원본0700/0600·UID1000 생성 검사를 사용하며 기존 정책·작업·claim을 코드로 삭제하거나 초기화하지 않는다. 지정한 leaf가 이미 사용되어 다른 정책이 있으면 차단하고 덮어쓰지 않는다. `/world-storage`를 private 상태로 지정하지 않는다. gCube가 컨테이너를 교체하면 임시 writable layer 보존은 보장되지 않으며, 이번 실행의 자동 백업 보류 위험은 그대로다. GitHub 원본과 기존 FINAL은 영향받지 않는다.

환경변수는 실행 중인 Python 프로세스에 즉시 적용되지 않는다. 같은 이미지를 이용한 필요한 설정 적용/재시작은 구분해야 한다. 이미지 재빌드·새 이미지 등록·재렌더링은 필요 없다. 이 작업에서는 gCube 설정 적용이나 유료 재배포를 수행하지 않았다.

기존 owner code·Secret·image/digest·포트8080·Command비움·공유 메모리2GB·NVIDIA 설정·`/world-storage`는 유지한다. 새 private 상태에서는 실제 HTTPS 주소로 로그인/필요시 `/setup` 등록을 다시 하되, 주소가 바뀌었으면 과거 주소를 강제하지 않는다. 동일80초 프리셋을 다시 불러 **사전검사만** 수행하고, 표시된 시간14,400초·비용5,200KRW·재시도0을 확인한다. 별도 제작 승인 전 **제작 시작/재개**는 누르지 않는다.

240분은 애플리케이션 작업 상한이다. 이 정책은 gCube 과금을 자동 종료하거나 계정의 실제 총 지출을5,200원으로 강제하는 기능이 아니다.

## 검증 및 보호

- 새 수집기 집중 CPU4/4 PASS, 공식 무료 Actions에서도 동일 검사 PASS.
- 원본 보호 코드의14,400초 허용/부족한 예산·만료 거부 결과는 기존 `studio-no-backup-preflight-v1/FOCUSED_CHECKS.json`을 재사용했다. 불필요한 전체 테스트·GPU 검사는 반복하지 않았다.
- Secret Scan 발견0.
- 기존 FINAL·Scene·Asset·렌더러·Camera·전선·이미지·완료 영상·claim·Secret 변경0. Git diff는 새 namespace와 새 읽기 전용 workflow만 포함한다.
- 작업 브랜치 `development/studio-policy-240m-review-20261019`, 필수 temp-only파일0. 최종 커밋은 Git 이력으로 확인한다.
