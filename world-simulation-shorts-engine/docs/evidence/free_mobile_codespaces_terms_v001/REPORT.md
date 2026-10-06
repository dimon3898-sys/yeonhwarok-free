# 개인 GitHub Codespaces 무료 조건 확인 — 2026-10-06 03:14 UTC / 2026-10-06 12:14 KST

**개인 GitHub Free 계정의 Codespaces를 필요할 때만 켜는 방식은 기존 Python·FFmpeg·Chromium 앱을 모바일에서 사용하는 현실적인 무료 후보다.** 공식 문서에서 2코어·8GB RAM·32GB 디스크 구성, 개인 계정 월 120 core-hours·15GB-month, 비공개 포트의 HTTPS 접속을 확인했다. 실제 사용자의 로그인·남은 무료 한도·과금 차단 설정·원격 앱 실행은 이번 문서 조사에서 확인하지 않았다.

## 무료 한도와 정지 중 저장 사용량

| 항목 | 현재 공식 조건 | 이 앱에서 필요한 해석 |
|---|---|---|
| 개인 GitHub Free compute | 월 120 core-hours | 2코어는 시간당 2 core-hours이므로 전량 남아 있을 때 최대 월 60시간 활성 상태. 생성·시작·작업·다른 Codespace 사용도 함께 차감 |
| 개인 GitHub Free storage | 월 15GB-month | 15GB 고정 디스크 용량이나 무기한 무료 보관이 아니라 시간에 따라 누적되는 사용량. 파일·자산·캐시·영상도 계산 |
| 가장 작은 문서상 머신 | 2코어·8GB RAM·32GB 디스크 | 실제 계정·저장소·지역에서 선택 가능 여부는 생성 화면에서 확인. 32GB 디스크와 15GB-month 무료 allowance는 다른 수치 |
| 기본 devcontainer image | base container 저장량 무료·quota에서 제외 | default 이미지에 Features를 추가해도 base image 자체는 제외된다고 명시 |
| custom Docker/devcontainer image | 이미지·저장소·추가 파일 모두 storage 계산 | 현재 앱의 커스텀 이미지와 렌더 scratch/cache가 무료 storage를 소진할 수 있어 실제 용량 확인 필요 |
| Stop | compute 사용 중단, 저장 파일 유지 | **정지 중에도 storage 누적은 계속됨** |
| Delete | 이후 해당 Codespace storage 누적 중단 | 이번 달 이미 누적된 사용량은 환급·차감되지 않음. 먼저 영상·checkpoint를 내보내고 확인 |

조직·기업 계정에는 위 개인 무료 quota가 포함되지 않는다. 각 무료 quota는 월 billing cycle 기준이며, 이미 다른 Codespace에서 사용한 양을 여기서 알 수 없다. provider의 실제 storage 사용량이나 이번 달 비용을 측정한 결과가 아니다.

## 0원 사용을 위한 과금 차단 조건

공식 문서는 **“If your account does not have a valid payment method on file, usage is blocked once you use up your quota.”**라고 명시한다. 유효한 결제 수단이 없는 개인 계정은 무료 quota가 소진되면 사용이 차단되며, quota가 갱신될 때까지 새 Codespace 생성·기존 Codespace 열기가 제한된다. 이번 조사에서 카드 추가나 유료 활성화는 수행하지 않았다.

계정에 이미 유효한 결제 수단이 있으면 기본적으로 0원 한도가 걸려 있다고 가정하면 안 된다. 생성 전에 [개인 billing](https://github.com/settings/billing) → **Budgets and alerts**에서 **Codespaces product-level / 전체 개인 계정** 예산을 확인한다. 0원 목적이면 $0 예산과 **Stop usage when budget limit is reached**가 함께 적용되는지 로그인한 사용자 화면에서 확인해야 한다. 공식 how-to에서 금액 필드와 stop option은 확인했지만, $0 값의 실제 허용 여부와 해당 계정 적용 상태는 여기서 검증하지 못했다. 확실한 무료 차단 조건을 확인하지 못하면 Codespace를 생성·재개하지 않는다.

**알림만 설정하면 사용이 멈추지 않는다.** included usage의 90%·100% 알림과 달러 budget의 75%·90%·100% 알림은 별도다. 예산은 생성 시점 이후의 metered 사용에만 적용되므로, 이미 발생한 사용량을 없애지 않는다. 실제 사용자 청구 0원이나 계정에 적용된 hard stop을 검증했다고 주장하지 않는다.

## 모바일 접속과 수명

공식 repository-specific 진입 방식은 `https://codespaces.new/OWNER/REPO-NAME`이고, `?quickstart=1`은 조건이 맞는 기존 Codespace가 있으면 재개하는 방식이다. 이 저장소의 진입 링크는 다음과 같다.

**[이 저장소의 Codespace 생성·재개](https://codespaces.new/dimon3898-sys/yeonhwarok-free?quickstart=1)**

이 URL은 공식 문서의 URL 규칙을 저장소명에 적용한 사용자 진입 링크다. 실제 로그인·생성·재개 성공을 자동 검증한 서비스 URL이 아니다. 무분별하게 새 Codespace를 반복 생성하지 말고 같은 인스턴스를 재개한다. 머신 지정용 URL query를 임의로 넣지 않는다. 저장소에 설정이 준비되어 있어도 생성과 계정 과금 확인은 사용자가 직접 한다.

앱 포트는 **Private**로 유지한다. 공식 forwarded app 주소는 `https://CODESPACENAME-PORT.app.github.dev`이며 private 포트는 Codespace 소유자의 인증이 필요하다. 같은 GitHub 계정으로 모바일 브라우저에서 로그인한 뒤 해당 앱 주소를 연다. Python 내부 HTTP 서버를 실행해도 외부 forwarded 주소는 HTTPS다. 기존 Python 서버가 평문 HTTP를 제공한다는 실제 코드 조건과 포트 protocol 문서를 함께 적용해, 내부 포트 protocol은 HTTP로 둔다. 이는 외부 HTTPS 주소와 구분한 호환성 권고다.

기본 유휴 종료는 30분이고 사용자가 5~240분으로 설정할 수 있다. 실제 파일 변경·terminal output은 활동으로 계산된다. 절전 회피용 가짜 트래픽을 만들지 않는다. **현재 공식 lifecycle에는 적극 사용 중이어도 연속 최대 12시간 후 저장·자동 정지**한다고 명시한다. 다시 사용하려면 재개가 필요하다. 기본 정지 보관 기간은 30일이며, 보관 기간이 지나 자동 삭제되면 내보내지 않은 파일을 잃을 수 있다. 지속 무료 상시 호스팅으로 간주하지 않는다.

## 사용자에게 필요한 최소 단계

1. GitHub 개인 계정에 로그인하고 [billing](https://github.com/settings/billing)에서 남은 Codespaces compute/storage와 위 과금 차단 조건을 먼저 확인한다.
2. 위 생성·재개 링크로 한 개의 Codespace를 열고, 가능한 경우 2코어 구성을 선택한다. 앱 포트의 Private 상태와 앱 startup 결과를 확인한다.
3. 같은 계정으로 로그인한 모바일 브라우저에서 앱의 실제 `*.app.github.dev` HTTPS 주소를 연다. 생성·재생·다운로드는 실제 provider에서 별도 확인한다.
4. 영상과 필요한 프로젝트/checkpoint를 내려받고 확인한 뒤 작업을 마치면 Stop한다. 필요 없는 Codespace는 백업 확인 후 Delete하여 이후 storage 누적을 멈춘다.

이 보고서는 공식 문서 조사다. 로컬 2CPU·8GB 제한 Docker 검증은 실제 Codespaces 성능·저장량·무료 비용·물리 휴대폰 end-to-end 성공을 증명하지 않는다. provider 생성, GitHub 로그인/OAuth, 카드 등록, 계정 설정 변경, 외부 배포, 새 영상 렌더는 이 조사에서 수행하지 않았다. 상속 proxy와 TLS 검증을 유지했고 차단된 API나 목적지를 우회하지 않았다.

## 공식 출처

- [Codespaces billing](https://raw.githubusercontent.com/github/docs/main/content/billing/concepts/product-billing/github-codespaces.md): 개인 무료 quota·core multiplier·storage·custom/default 이미지·결제 수단 없는 quota 초과 차단.
- [Included usage](https://raw.githubusercontent.com/github/docs/main/content/codespaces/troubleshooting/troubleshooting-included-usage.md): core-hours 산정·정지/삭제·누적 storage·default image 제외.
- [Default over-quota behavior](https://raw.githubusercontent.com/github/docs/main/data/reusables/billing/default-over-quota-behavior.md): 유효한 결제 수단 없는 quota 초과 차단, 카드 있는 계정 budget 확인.
- [Budgets and alerts](https://raw.githubusercontent.com/github/docs/main/content/billing/concepts/budgets-and-alerts.md), [Set up budgets](https://raw.githubusercontent.com/github/docs/main/content/billing/how-tos/set-up-budgets.md): hard stop 선택·알림과 차단 차이·예산 생성 전 사용량 제외.
- [What are Codespaces](https://raw.githubusercontent.com/github/docs/main/content/codespaces/about-codespaces/what-are-codespaces.md): 2코어·8GB·32GB부터 제공되는 머신.
- [Lifecycle](https://raw.githubusercontent.com/github/docs/main/content/codespaces/about-codespaces/understanding-the-codespace-lifecycle.md), [Timeout](https://raw.githubusercontent.com/github/docs/main/content/codespaces/setting-your-user-preferences/setting-your-timeout-period-for-github-codespaces.md), [Deep dive](https://raw.githubusercontent.com/github/docs/main/content/codespaces/about-codespaces/deep-dive.md): default idle·설정 범위·활동·현재 연속 12시간 제한·정지 중 storage·자동 삭제.
- [Quick creation and resumption](https://raw.githubusercontent.com/github/docs/main/content/codespaces/setting-up-your-project-for-codespaces/setting-up-your-repository/facilitating-quick-creation-and-resumption-of-codespaces.md): 공식 repository-specific codespaces.new 형식·quickstart=1.
- [Port visibility](https://raw.githubusercontent.com/github/docs/main/data/reusables/codespaces/port-visibility-settings.md), [Tools accessing ports](https://raw.githubusercontent.com/github/docs/main/data/reusables/codespaces/using-tools-to-access-ports-1.md): private 기본값·앱 외부 HTTPS 주소·private authentication.

각 원문의 HTTP status·UTC 조회 시각·바이트·내용 SHA256·정확한 인용은 [REPORT.json](REPORT.json)에 기록했다. SHA256은 조회한 문서 바이트의 fingerprint이며 Git commit SHA가 아니다.
