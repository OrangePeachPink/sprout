# Run sheet — Sprout search deployment (both engines) · #1232

**Owner of the manual steps:** maintainer (account-gated — Google + Bing logins).
**Prepared by:** DX. **Milestone:** v0.8.1 pre-release close.

Context: `vkhogue.com` is already fully live in both Google Search Console and Bing Webmaster
Tools (verified + sitemap fed 2026-07-14, indexed, HTTP 200). Nothing to redo on the portfolio
side. This sheet is the Sprout half — the two account actions only you can take — plus the one
shared structured-data string, which the Sprout side already ships (see §C).

The Sprout front-door and its sitemap:

- Front door: `https://orangepeachpink.github.io/sprout/`
- Sitemap: `https://orangepeachpink.github.io/sprout/sitemap.xml` (source: `docs/sitemap.xml`)

## A. Google Search Console — add the Sprout Pages property

1. Use the **same Google account** as `vkhogue.com` (one login = coherent reporting). GSC has no
   cross-property rollup — the two stay separate property reports, there is no merged dashboard.
2. **Add property → URL-prefix**, scoped to `https://orangepeachpink.github.io/sprout/`. Not a
   domain property — GitHub owns the domain, so domain verification is impossible (this is why the
   old `github.com` GSC entries were dead). URL-prefix is the only path.
3. **Verify via the HTML-tag method** — you control the front-door `<head>`, so it is the easy one.
   Add Google's real verification `<meta>` tag to `docs/index.html` (the FD-3 TODO at the top of
   that file marks the spot; no placeholder token is committed until you generate the real one).
4. **Sitemaps → submit** `sitemap.xml`.
5. **URL Inspection → front-door URL → Request Indexing.** This also flushes the stale cached
   title (see §D). Allow a few days for the recrawl.

## B. Bing Webmaster Tools — add Sprout (parity with `vkhogue.com`)

1. **Same account.** Easiest path: **Import from GSC** (one click, carries verification +
   sitemap). Otherwise add `https://orangepeachpink.github.io/sprout/` manually.
2. **Sitemaps → submit** the Sprout `sitemap.xml`.
3. **URL Submission → front-door URL.**

Bing also powers DuckDuckGo + Ecosia — three engines for one action.

## C. Structured data — mirror the Person `@id` (the one real optimization) — DONE (Sprout side)

- Authoritative value, minted and owned by the portfolio side: `https://vkhogue.com/#person`.
- The front-door JSON-LD `author` Person node now carries `"@id": "https://vkhogue.com/#person"`,
  byte-for-byte exact. A mismatch would be worse than nothing, so it is a literal copy.
- `vkhogue.com`'s own Person node carries the identical `@id` (confirmed live 2026-07-22, serving
  the exact string). Matching `@id`s tell Google the two Person nodes are **one entity**.
- Do **not** add Sprout as a `sameAs` on `vkhogue.com` — a project is not an alternate identity of
  the person. The correct `project → author` link already exists.

Nothing for you to do in §C — it ships with the PR that carries this run sheet. Listed here so the
picture is complete.

## D. The stale "Honest" cached title — mostly not a live string (flag, not a bug)

- Live surfaces are already clean (description = "plants with a pulse", front-door title clean,
  README H1 clean). The "Honest, local-first ESP32 plant care" that Google shows is its
  pre-voice-clean **cache**; step A5 flushes it (allow a few days).
- Optional voice-audit — your doctrine call, not an SEO one: two residual descriptive uses survive,
  in `docs/process/ADOPTION.md` and `README.md` (the "a percentage is ... never VWC" line). These
  read as in-voice description, not the retired hook, so DX left them. To rule on them yourself:
  `git grep -niE 'honest|refuses to lie|never a fake'` surfaces the class. <!-- voice-guard: allow -->
  (That grep pattern names the retired hooks on purpose — it is the search, not the voice.)

## Log

Record the outcome on #1232 (property added, sitemap accepted, indexing requested — both engines).
When both engines are serving the Sprout property, #1232 closes.
