# gCube Secret delivery review — no credential transfer performed

Parent candidate `646a79a2ae98ebb4b785f3371946ddb1ff0d591f` is unchanged.
This is read-only capability research plus an additive report. No renderer,
FINAL, Candidate, GitHub Secret, encryption key, backup or gCube setting was
changed. No GPU was started, redeployed, stopped or charged by this task.

## Confirmed support and limits

Official docs HEAD was checked again using GitHub:
`Data-Alliance/gai-platform-docs@6338ac39d1b964226b1d7b378c0fa8e4af6cb201`.
The repository last-pushed metadata is `2026-08-25T07:35:28Z`.

- [Workload registration](https://github.com/Data-Alliance/gai-platform-docs/blob/6338ac39d1b964226b1d7b378c0fa8e4af6cb201/docs/user-guide/workload/register-workload.ko.md)
  documents generic container environment Key/Value and personal Storage.
- [Storage management](https://github.com/Data-Alliance/gai-platform-docs/blob/6338ac39d1b964226b1d7b378c0fa8e4af6cb201/docs/user-guide/sign-up/storage-management.ko.md)
  describes registry credentials and Dropbox/S3 mounts. Those are not evidence
  of workload Secret injection and do not expose the WORLD ENGINE app's token.
- [Official CLI](https://github.com/Data-Alliance/gai-platform-docs/blob/6338ac39d1b964226b1d7b378c0fa8e4af6cb201/docs/user-guide/gcube-cli/cli-workload.ko.md)
  and previously verified CLI 0.4.2 source provide stopped-workload `update`.
  This sends generic `containerEnvs` through authenticated HTTPS, not SecretRef.
- The CLI includes `containerEnvs` in authenticated describe output and exports
  their values to update-skeleton YAML. This is **not** a claim that an
  unauthenticated public endpoint exposes credentials. It does mean that a
  non-displayable Secret contract cannot be assumed from the Key/Value field.
- Dedicated workload SecretRef, file injection, masking, at-rest encryption and
  read-access separation were not established by those public contracts. This
  does not prove the provider offers no such account-specific feature.

No real Secret or account environment was retrieved to test visibility. Public
issue searches for `secret` and `환경변수` returned zero matches; this alone is
not evidence of absence.

## Automatic transfer, without phone token copying

| Path | What is established | Current decision |
| --- | --- | --- |
| GitHub Actions -> official workload Secret API/file mount | Native target contract not verified | Wait for provider's documented mechanism; no credential sent |
| GitHub Actions -> stopped workload update | Official API supports configuration update without deployment; existing Repo Secrets are usable inside approved Actions | Technically possible, but ordinary readable env configuration is not verified as a Secret destination; do not auto-send |
| GitHub Actions -> SSH private files | Official SSH requires Running pod; strict existing `_FILE` inputs available | Not verified predeployment; requires approved GPU window, reachable authenticated SSH and trusted host identity; no SSH attempt here |
| GitHub Actions -> Studio credential enrollment | Existing Studio has no such endpoint or UI button | New authenticated delivery feature would be a separate implementation, not a completed capability |

GitHub's Secret REST read endpoints return metadata, never stored plaintext.
The existing four Secrets can be bound directly to a trusted Actions job, as
the successful real backup/recovery checks already demonstrated. No re-login,
token reissue, key rotation, user download/export of Secrets or repeated OAuth
is needed. Once an approved destination is confirmed, Actions can deliver them
without passing the plaintext through the user's phone.

The current mobile connect page stores encrypted values into GitHub; it does
not export stored values to gCube. The production workflow only binds those
values to the free CPU recovery test. `/setup` registers HTTPS Origin; it is not
a Dropbox credential handoff endpoint. No nonexistent connect button is offered.

Stopped-workload update must preserve all existing configuration, including
the user's five normal environment fields, team, image and storage. An eventual
adapter must not submit an incomplete replacement manifest or silently deploy.
No such update was executed in this review.

## Existing runtime file-input contract

If gCube confirms private file injection, existing inputs can be reused:

```text
WORLD_ENGINE_STUDIO_BACKUP_KEY_FILE
WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_KEY_FILE
WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_APP_SECRET_FILE
WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_REFRESH_TOKEN_FILE
```

They reference actual private absolute file paths, not Secret values or invented
example paths. Runtime files are UID/GID1000, mode0600, single-link regular files
in private directories, outside `/world-storage`. Existing bootstrap can
materialize approved inputs privately; no permission checks are removed.
Approved raw Secret input also exists, but a safe provider delivery mechanism
has to be established before using it automatically.

## Minimal owner action

Keep the five already entered non-secret settings. Do not paste Dropbox tokens
or the backup encryption key into the ordinary Key/Value fields, reauthorize
Dropbox, change Secrets, or press GPU deploy for this check.

Official docs link to Contact. The current Korean public page was fetched with
HTTP 200: https://gcube.ai/ko/contact . Its HTML contains fields `제목`, `내용`
and the submit button **문의하기**. No form was submitted by Codex.

1. Open that link; fill your own contact details required by the page.
2. In **제목**, enter `워크로드 Secret 자동 주입 지원 방식 문의`.
3. In **내용**, paste:

> WORLD ENGINE에 사용할 Dropbox Refresh Token과 백업 암호화 키는 이미
> GitHub Actions Repository Secrets에 보관되어 있습니다. 사용자가 값을
> 다시 복사하지 않고 전달하려고 합니다. gCube 워크로드에 Secret 참조 또는
> 비공개 파일(UID1000/0600)을 주입하는 공식 기능/API가 있나요? 일반
> containerEnvs만 지원한다면 저장 암호화, 조회 권한, UI/CLI/YAML 출력의
> 마스킹 정책을 알려주세요. GPU를 시작하지 않고 중지된 워크로드에 연결할
> 수 있는 공식 절차도 부탁드립니다. 토큰이나 키 원문은 보내지 않겠습니다.

4. Press **문의하기**. Share only the provider's procedure/documentation reply,
   not credentials, so the supported Actions delivery can be prepared.

The UI may request personal contact details; no fake values or automatic contact
submission were used. The exact Secret-specific button cannot be supplied until
the provider confirms one. User contact is necessary to resolve this currently
undocumented account-specific support boundary; no additional credential entry
is required now.

Decision: official private Secret destination **UNVERIFIED**; automatic transfer
**NOT ENABLED**. Existing GPU candidate and successful Dropbox recovery proof
remain valid evidence in their original scope. No tests or image builds were
repeated for this documentation-only review.
