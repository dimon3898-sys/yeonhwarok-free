# gcube deployment research

Checked 2026-10-06 19:00:27 KST from current Data-Alliance official docs/examples and official released gcube-cli0.4.2 (2026-09-01). No login, payment, token, workload action, render or application edit.

The official [docs README](https://github.com/Data-Alliance/gai-platform-docs/blob/master/README.md) links `https://console.gcube.ai/` and [gcube Docs](https://data-alliance.github.io/gai-platform-docs/). Official serving guides also link `https://gcube.ai/ko/demand/workload/list`. Native console and price-page requests were denied by inherited proxy CONNECT403; the documented UI was verified from source, not observed inside the account.

## Documented workload setup

[Register Workload](https://github.com/Data-Alliance/gai-platform-docs/blob/master/docs/user-guide/workload/register-workload.ko.md) gives:

1. Workload Mode → 새 워크로드 등록; enter description.
2. Select registry and supply image (`ghcr.io/owner/repository:tag` for GitHub); image verification auto-detects Docker `EXPOSE` port. CLI documentation permits explicit port override. An official serving example uses8000.
3. Set optional startup command, env, Personal Storage and max concurrent HTTP connections. Blank command uses image startup; precise ENTRYPOINT override precedence is undocumented.
4. Select live GPU model/VRAM, hourly-price range and available-only filter. Review CPU/RAM/disk as well as GPU.
5. Options include Istio proxy/consistent hash/minCUDA/shared memory; review expected total and immediate deployment before registration.
6. [Deploy](https://github.com/Data-Alliance/gai-platform-docs/blob/master/docs/user-guide/workload/deploy-workload.ko.md) activates Service URL after several minutes. [Official Ollama guide](https://github.com/Data-Alliance/gai-platform-docs/blob/master/docs/user-guide/platform-guide/ollama-api.ko.md#L235) states the URL appears in workload details → 개요 as `https://xxxxxxxx.gcube.ai`. No actual WorldEngine hostname is known.

No source establishes forwarded-header values or a provider-injected public-origin env. Use the actual issued URL for optional app configuration; do not guess a hostname or env variable. Minimum CUDA selection does not prove Chromium graphics/EGL/NVENC capabilities.

## Billing and stopping

Official serving guide says billing runs from deploy until stop, including when unused. [Stop Workload](https://github.com/Data-Alliance/gai-platform-docs/blob/master/docs/user-guide/workload/stop-workload.ko.md) says stopping halts point deduction. Released CLI skeleton explicitly warns that without a STOP schedule the workload will not auto-stop and billing continues. Scheduled START/STOP exists; automatic request-triggered wake is not documented.

Current RTX5070/5070Ti availability and final price remain unknown. Provider-set node prices vary; actual selected node determines charge. Official demo rates.py has no5070 entry and is not a live price guarantee. The official CLI skill says1P=1KRW; traffic can incur separate Network Points. User-reported minimum20000P/VAT-inclusive22000KRW and account existence were not independently verified.

## Persistence: critical distinction

Official stop documentation warns that **without backup storage, all working container data and environment are deleted when stopped**. [Storage Management](https://github.com/Data-Alliance/gai-platform-docs/blob/master/docs/user-guide/sign-up/storage-management.ko.md) describes Dropbox OAuth or S3 credentials/region, a container mount path, and selecting that storage in the workload. It does not define sync/restore or POSIX guarantees.

Released official CLI supports two mount forms: external StorageSER→path and native literal`gcube`→path. It only lists PV/PVC Bound storage. The official [gcube-file-api](https://github.com/Data-Alliance/gcube-file-api) design mounts a user JuiceFS PVC in an internal on-demand Pod. Native storage therefore has implementation evidence beyond older Dropbox/S3 docs, but actual account entitlement, price/capacity and workload semantics remain unverified.

A separately published chaeyoon-08 RAG example warns that Dropbox/S3 FUSE SQLite locks fail and uses local working DB plus periodic backup/startup restore. Its author is not independently verified as official; use this as a compatibility warning, not a blanket claim about native JuiceFS. Before putting live engine state or owner-auth files on any mount, verify `fcntl`, atomic rename and0600 behavior on the actual mount. Otherwise use an explicit backup/export/restore design.

## API evidence, not execution

Official CLI defaults to`https://api.gcube.ai`. Its released source implements start`GET /api/workloads/gai/{SER}/state/deploy`, stop`GET .../state/finish`, and schedule GET/PUT/DELETE`.../{SER}/schedule`. PUT replaces all schedules. None of those endpoints was contacted. A user's provider token is required for authorized actions.

`REPORT.json` preserves 15 primary sources, exact quote ranges, URLs, UTC/KST timestamps, byte SHA256 and CLI wheel/member hashes. Current actual UI, paid rates/account balance, backup guarantees, origin headers and GPU graphics exposure remain unverified.
