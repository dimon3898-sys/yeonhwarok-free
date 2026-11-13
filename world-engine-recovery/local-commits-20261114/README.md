# WORLD ENGINE local Git history recovery

Original commits are now on `fix/reference-6s-formal-admission-20261113`, with exact original SHAs retained. The bundle is a second recovery copy, not a replacement for those commits.

Required base: `4f1ccf960bd3ca102f7de543c229299744673839`

Original tip: `2836408ae2a8cb7cd4734e5d51da224f44f9c2cb`

Reassemble the parts in filename order from this directory, check SHA-256, then import into a repository containing the required base. These commands do not change an existing branch:

```sh
cat original-local-commits.bundle.part-* > /tmp/world-engine-original.bundle
printf '%s  %s\n' 'fd2a4edf62de74cc4016946978e694dd0da7edba198093be5072a2c481dd4db5' /tmp/world-engine-original.bundle | sha256sum -c -
git bundle verify /tmp/world-engine-original.bundle
git fetch /tmp/world-engine-original.bundle HEAD:refs/heads/recovered-world-engine-original
```

The remote parts were downloaded again and matched the complete 12724874-byte original bundle. GitHub runner 43525902555 also restored and checked all three original commits and the exact tip tree. Its final push was refused by runner workflows permission. The authorized branch update was then completed through the connected GitHub API with an expected-head check and no force.
