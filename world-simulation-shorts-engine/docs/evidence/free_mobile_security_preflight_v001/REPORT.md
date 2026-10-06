# 무료 모바일 배포 보안·보존 사전 검수

기준 `8d7c60446476ce2358cd92300ddecbf44fe9f8de`. 읽기 전용 검사.

**원본 local/LAN 서버의 직접 인터넷 공개는 아직 안전하지 않다.** 외부 래퍼에 인증·미디어·작업 비용·영속성 경계를 추가해야 한다.

보존 lock: **95개 / 1,427,401,815바이트**, 기존 기준 일치: **True**. 승인28소스·25그래픽·28기존 MASTER/75초 영상 포함. 기존1012개 전체 검수는 이전 evidence에 유지.

## S01 · BLOCKER · 원본 서버 인증·소유권 부재

GET 프로젝트/계획/상태/다운로드와 POST 기획/승인/렌더/수정/업로드에 인증이 없다. Origin 검사는 optional이며 Origin 없는 직접 요청을 허용한다.

근거: `server.py:109-151; server.py:226-229`.

HTTPS 소유자 로그인/session을 모든 API·미디어·다운로드에 적용. Secure/HttpOnly/SameSite cookie, 만료·CSRF·Origin·로그인 rate limit. 프로젝트ID를 권한으로 간주하지 않음.

## S02 · HIGH · 요청·렌더·디스크 비용 DoS 경계 없음

ThreadingHTTPServer와 queued job마다 thread 생성이 무제한이다. render_lock은 동시에1개만 렌더하지만 queue/thread 수는 제한하지 않는다. 기획20~3600초; JSON>2MB만 거절해 음수 Content-Length read(-1) 차단이 없다. 업로드256MiB이며 집계 quota/socket deadline/media 길이 한도가 없다. 나레이션은 전체 decode 뒤 길이를 검사한다.

근거: `server.py:34-46,74,96-99,173-195; engine/planner.py:94-112; engine/audio.py:123-128`.

single active + single queued job, 연결/요청 rate 제한, read/write timeout, 단일 decimal Content-Length와 크기 하한/상한, Transfer-Encoding 거절. JSON64KiB/주제·수정 길이 제한, 배포별 영상·Scene·quality·디스크 quota, 오디오 사전 길이 제한. 품질을 몰래 낮추지 않음.

## S03 · HIGH · 미디어 자동 감지에 외부 참조·무기한 subprocess 가능

ffprobe/ffmpeg argv에 shell injection은 없지만 default protocol/autodetect와 timeout 부재가 있다. MP4로 이름만 바꾼 playlist/HLS/참조 미디어는 검증 이전에 네트워크/다른 로컬 파일 참조를 시도할 수 있다. 공격은 실행하지 않았다.

근거: `server.py:189; engine/audio.py:38-46; engine/rendering.py:163,200-205; engine/qc.py:16-18`.

upload ingestion override에서 첫 probe 전에 format/protocol whitelist/정확한 허용 container 지정, timeout10초와 CPU/RAM/pids/filesize 제한. container/codec/stream 수/해상도/길이 검증 및 단일 로컬 파일 정규화. playlist/외부참조 거절. worker 외부망 차단과 credential mount 금지; loopback 내부 renderer만 허용.

## S04 · HIGH · Chromium OS sandbox 비활성

--no-sandbox 및 unsafe SwiftShader로 승인된 로컬 그래픽을 렌더한다. 브라우저/미디어 취약점 발생 시 worker 파일권한이 경계다.

근거: `tools/render_rhythm_scene.mjs:46; tools/render_production_scene.mjs:44`.

비루트 컨테이너, read-only 승인 code/assets, 별도 writable runtime/tmp/cache, Docker socket/클라우드 credential mount 없음, capabilities 제거/no-new-privileges와 CPU/RAM/pids 제한. 사용자 URL을 브라우징하지 않음.

## S05 · HIGH · 시작 recovery가 기존 tree 수정·복수 worker lock 없음

Application 초기화에서 queued/rendering 상태를 interrupted로 바꾼다. Store/render lock은 process-local; 여러 replica가 공유 status/cache를 동시에 쓰면 race. 완료 Scene/checksum cache와 승인/plan hash gate는 유지되어 있다. durable worker lease/자동 job supervisor는 없다.

근거: `server.py:14-15; engine/storage.py:90-122; engine/rendering.py:134-151,437-460,526-532`.

새 배포 전용 project root와 단일 worker/replica, 기존 Masters/projects/배포본 read-only mount. 새 runtime에서 checkpoint 복구, 외부 lease/supervisor와 시간 예산. old status를 startup에서 수정하지 않음.

## S06 · MEDIUM · 경로 guard는 있으나 자산 허용 root가 넓음

PID/version/asset/revision regex와 resolve containment, static hidden segment 거절이 있다. upload filename 정규화/서버 ID 생성. 다만 asset resolver는 APP/V3 전체를 허용하고 ProjectStore directory symlink를 거절하지 않는다. 확인한 web/asset/library 경로에는 symlink가 없었다.

근거: `server.py:148-151,196-198; engine/storage.py:41-51; engine/assets.py:86-93; engine/revisions.py:286-295; web/app.js:409-411`.

narration_asset_id 소유권과 실제 등록 경로 일치 확인, private upload runtime으로 한정, runtime symlink path component 거절, 다운로드는 실제 approved output allowlist만 허용. raw Scene JSON/경로/플러그인/명령 입력 endpoint를 만들지 않음.

## S07 · MEDIUM · 공개 HTTP 헤더·오류 노출 경계 없음

nosniff/Range206/인코딩된 Content-Disposition은 있다. CSP/frame-ancestors/referrer/HTTPS/HSTS/auth cookie 경계는 없다. plan/status/error에 absolute path/log가 노출될 수 있다. UI 사용자 문구는 textContent로 표시하여 직접 stored-XSS 경로는 관찰하지 않았다.

근거: `server.py:94-108,202-215,226-229; web/app.js:13,35`.

고정 allowed Host/Origin, trusted proxy에서만 forwarded header 신뢰, HTTPS·private cache policy·CSP/frame-ancestors none/Referrer-Policy, 오류 정제. native render HTML은 inline code 때문에 private 전용 CSP 필요. 모바일 Range/다운로드 유지.

## S08 · BLOCKER · reverse proxy 뒤 loopback 인증 우회 금지

native Chromium은 local HTML/assets/plan API를 읽어야 한다. 원본 전체 핸들러 인증은 native callback을 깨뜨릴 수 있다. public reverse proxy는 모든 외부 요청을127.0.0.1 client로 전달할 수 있다.

근거: `engine/rendering.py:482-501; server.py:147-169`.

공개 인증 listener와 unexposed127.0.0.1 read-only renderer listener를 분리. 공개 ingress가 닿는 port에서 loopback IP라는 이유로 인증 우회 금지. 사용자 base_url/URL 입력 금지.

## S09 · MEDIUM · 승인28 소스 변경 시 FAST_PLUS promotion 무효

promotion은 28 실제 source hashes/final movie/evidence hash를 확인한다. 기존 server/UI/engine을 수정하면 승인 기준이 깨진다.

근거: `engine/rhythm_promotion.py:19-31; docs/evidence/rhythm_source_lock_final_v001/SOURCE_LOCK.json`.

deployment/mobile_server.py subclass/adapter와 deployment 문서를 별도 추가. original28, approved shader/material/GIS/font 및 oldMaster lock 유지. wrapper의 새 보안 검증은 독립적으로 기록.

## 유지할 보호 장치

- 감사한 HTTP/media/render 경로는 subprocess argument vector이며 shell=True/os.system 또는 사용자 arbitrary command 실행을 발견하지 않았다.
- 렌더 전에 schema/semantic gate, hash-bound user approval, 저장된 Scene plan을 재검수한다.
- 완료 Scene/cache/final SHA/QC 검사와 불량 결과 보존 및 부분 재개 구조가 있다.
- GPUCloud는 adapter 부재 fail-closed, 승인/비용 cap/finally stop_worker 구조다. 실제 HTTP renderer는 CPU_LOCAL만 선택해 유료 GPU를 암묵 provisioning하지 않는다.
- UI는 textContent, static/download containment, ID regex와 일부 요청·업로드 상한이 있다.
- Python requirements와 Three/Playwright 버전·package lock이 고정돼 있다. 취약점 advisory/network 검사는 하지 않았다.

## 실제 자원과 배포 요구

현재 cgroup **4vCPU / 32GiB**. disk 가용 20,236,611,584바이트. 이전12초 HIGH 실제996.575788119초; 5cache 오디오 교체13.830002466초. RAM peak는 측정하지 않았다.

- Pinned Python requirements; sibling cinematic-world-map with Three/Playwright; ffmpeg/ffprobe, Chromium/SwiftShader, offline eSpeak or supplied narration. Root separately audits exact Python/Node/FFmpeg/Docker availability.
- 단일 worker 시작 예산4vCPU/8GiB 후 실제 peak RSS 측정. 이것은 설계 권고이며 실측 최소가 아니다. 현재 성공한 environment는4vCPU/32GiB quota. 작은 free/serverless instance의 native4K 처리능력을 인증하지 않음.
- durable project/cache/upload/final volume과 read-only old outputs 필요. 현재 directory 실측 포함. native terrain crop을 재사용하므로699969932-byte NaturalEarth 원본을 작업마다 다시 받거나 계산할 필요 없음. 소스/라이선스 archive 별도 유지. 전체 workspace 약11.8GB 사용; 보존 범위·프로젝트 수에 따라 용량 달라짐. 남은 공간 reserve 검사; old approved outputs 자동삭제 금지.
- 1renderer replica, durable lease/supervisor/checkpoint, 벽시계/CPU/RAM/pids quota. 중단 시 자기 worker process group만 종료하고 완료 Scene 보존.
- authenticated owner-only HTTPS. multi-tenant로 간주하려면 project와asset 소유권 추가. 내부 loopback read-only renderer port를 공개 forwarding하지 않음.
- JSON64KiB·주제/수정2k문자, 업로드256MiB보다 낮은 배포 정책, probe10s, media 길이/stream/해상도/codec 사전 제한, singleactive/singlequeued, 명시적 영상 duration/scene 상한. Local core 기능은 변경하지 않음.

## 검수 한계

- 새 wrapper 코드/보안 테스트는 아직 검수하지 않았다. 이 보고서는 원본 local/LAN 서버 대상.
- 악성 미디어·network exfiltration exploit을 실행하지 않았다.
- dependency advisory/network scan/설치/새 렌더/peakRSS benchmark/hosting 속도/실제폰 테스트 없음.
- 비밀 값 조회, 서버 process 제어, Git write 없음. 호스팅 영속성은 아직 증명되지 않음.

해시·receipt·자원 수집 실측 3.809초. 상세 해시 [REPORT.json](REPORT.json).
