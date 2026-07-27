# Signing-key ceremony — Sprout release signing (#302 / ADR-0026)

The one-time ceremony that lets CI sign release firmware, so a future pull-OTA (#302, 0.8.0) and the
web-flasher (#271) can verify **authenticity**. **Scheme: ed25519** — Firmware's recommendation per
ADR-0026 Decision 2 (small, software-verifiable on the ESP32, **no eFuse** per the maker-first ruling). If
the maintainer rules a different scheme, swap the keygen (step 2) + the workflow's sign step; the shape is
identical, so this stays a same-day land.

## The fence (ADR-0026)

- The **private key never touches the maintainer's persistent machine** — it is generated in an ephemeral
  environment, pasted into a GitHub Actions secret, then the environment is destroyed. CI is the only place
  that holds it (a repo secret) and the only place that signs. Nothing is ever hosted or signed from a
  personal machine.
- The **public key is committed** (`firmware/keys/`), so the firmware + flasher verify against a key that
  ships in the repo, not one fetched at runtime.

## Steps (maintainer, ~5 min)

1. **Open a throwaway environment** — a GitHub Codespace on this repo (Code → Codespaces → New), or any
   container you will discard. **Not** your daily machine.

2. **Generate the ed25519 keypair:**

   ```bash
   openssl genpkey -algorithm ed25519 -out signing.key
   openssl pkey -in signing.key -pubout -out sprout-signing-ed25519.pub.pem
   ```

3. **Add the PRIVATE key as an Actions secret:** copy the full contents of `signing.key` (the
   `-----BEGIN PRIVATE KEY-----…` block) into a new repo secret named **`SPROUT_SIGNING_KEY`**
   (repo Settings → Secrets and variables → Actions → New repository secret).

4. **Commit the PUBLIC key:** place `sprout-signing-ed25519.pub.pem` at
   `firmware/keys/sprout-signing-ed25519.pub.pem` and commit it (or paste it to Firmware and we commit it).
   It is public — safe to commit.

5. **Destroy the environment** — delete the Codespace/container. `signing.key` (the private key) must not
   survive anywhere but the Actions secret.

## After the ceremony

- Merge the signing PR (#302). The next **published** release runs `sign-release.yml`: it builds the
  board-aware factory bins (classic + C5), signs each with the secret, verifies against the committed public
  key, and attaches `<bin>` + `<bin>.sig` to the release. **What is signed is domain-separated** (#1282): the
  message is the 10-byte tag `sprout-fw\0` followed by the image bytes, never the bare image — so a firmware
  signature can never be replayed as a signature over a different artifact class. The device-side verify
  prepends the same tag; signer and verifier must agree or every release is rejected on-device. The `.sig`
  stays **detached** (a sibling artifact, never a trailer inside the image), so one signed image serves both
  the OTA and web-flasher paths. A future pull-OTA (#302) checks the `.sig` before
  applying.
- **Before the ceremony** the workflow **skips signing with a warning** — it does not fail, so releases
  still cut unsigned in the interim.
- **Rotation:** re-run steps 1–5 with a fresh keypair; keep the old public key until every deployed board
  has been OTA'd past the rotation (a signed image chains trust).
