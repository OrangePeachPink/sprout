# Vendored: Monocypher 4.0.3 (ed25519 for the ADR-0026 signing fence)

**VENDORED CODE — never edit, never reformat.** (The pre-commit clang-format hook excludes this
directory; upstream bytes must stay byte-identical for provenance.)

| | |
| --- | --- |
| Upstream | <https://github.com/LoupVaillant/Monocypher> |
| Release | **4.0.3** (published 2026-06-15) |
| Tarball | `monocypher-4.0.3.tar.gz` — sha256 `8cc9bc341a66249016db9bd70e9142d8d0aef9945973744b1ac05dbc55d8ee66` |
| License | Dual **CC0-1.0 / BSD-2-Clause** (see `LICENCE.md`, shipped intact) |
| Ruling | Maintainer, 2026-07-19 (#1282): Monocypher over wolfSSL — permissive license for Sprout's distributed signed binaries + a small auditable surface |

Per-file sha256 (vs the extracted release):

```text
57eb914fc88136119bd41655cccb8c250048bf54d470540625186f8ab16f64be  monocypher.c
c494da712122da7ff679fdcf318a5317e84972b6c950fe9d896212947797facd  monocypher.h
60fce3578fb00b00da96490653d993c4cb427b1e1be38183285c66e04d22cc18  monocypher-ed25519.c
abc4fad381879f5c29176ebe014b9189956b3dfe0a3e36459b6990bc57212380  monocypher-ed25519.h
```

Scope: `monocypher.{c,h}` (core) + the optional `monocypher-ed25519.{c,h}` module (Ed25519 +
SHA-512) — the implementation behind the S1 verify seam (Trellis's #1282 binding ruling:
Firmware's `lib/` interface + KAT vectors sit on top; this dir is only the vetted primitive).
Upgrades: replace wholesale from a pinned upstream release + update this README — never patch.
