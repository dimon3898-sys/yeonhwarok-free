# Split private workspace and shared export contract

The actual reported STORAGE stage failed; exact Dropbox stat and metadata semantics are unknown. This change does not claim Dropbox supports private POSIX directories. Original bootstrap and GPU admission APIs already accept explicit storage paths; their bytes and checks remain protected.

A root-owned 0755 container-local parent `/var/lib/world-engine-private` contains the UID 1000, 0700 base `/var/lib/world-engine-private/engine` and fresh private run directories. Original bootstrap receives the selected private path. Original LauncherConfig receives the same path. Runtime, private admission, capture frames/rows, locks and raw reports remain local. Local storage must support the original private semantics, fsync, rename and flock.

`/world-storage` is an untrusted shared export destination. It is never admitted as private storage and receives no existing-file chmod/chown/delete. A new random export namespace is tested as UID 1000 with exclusive no-follow file creation, actual byte write/readback SHA, and deletion of only the newly created probe. Symlinks and path substitution are rejected. Export failure blocks GPU admission and does not suppress console diagnostics.

Only allowlisted MP4, checkpoint PNG, SHA256SUMS and strict sanitized startup diagnostics may cross to the shared destination. Original private admission, source, internal manifests, raw report/log archives and full frame sets are excluded. Copies use new names, no overwrite, destination readback verification and a last completion record. Failed exports preserve local output and remain failed.

Mounted-view readback is not proof of remote Dropbox upload, durable storage, external download or survival after termination. These states must remain separate. A local private workspace is ephemeral; external retrieval with SHA equality is required before an intentional stop. No existing approved public-review directory is modified.

No GPU checks are bypassed. GPU presence, EGL/Vulkan, physical WebGL2 draw/readPixels, VRAM/shared memory and gCube health/restart behavior remain actual-hardware gates. No paid workload is launched by this task.
