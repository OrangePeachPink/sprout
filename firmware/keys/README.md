# Release signing keys

The **public** ed25519 key for verifying signed release firmware (#302 / ADR-0026) lives here, committed
once by the key ceremony ([`docs/process/signing-key-ceremony.md`](../../docs/process/signing-key-ceremony.md)):

```text
firmware/keys/sprout-signing-ed25519.pub.pem
```

It is **public** — safe to commit. The **private** key is never stored here; it lives only in the
`SPROUT_SIGNING_KEY` GitHub Actions secret, and CI (`.github/workflows/sign-release.yml`) is the only signer.
Until the ceremony runs, this dir holds only this README and releases cut unsigned (the workflow warns, does
not fail).
