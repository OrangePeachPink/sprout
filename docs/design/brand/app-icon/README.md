# The desktop app icon (#1359)

Master: `../app-icon.svg`. Rendered sizes live here; **DX owns the `.ico` packaging.**

## Why this exists

The previous desktop icon was the thin stroked mark on pure transparency. Her words:
*"it feels like I only have a small click target to aim for… I'd like a more substantial
feeling icon so it doesn't feel like I have to carefully line up my double click."*

The whole square was always clickable — but the icon *read* as a small thing, and how it
reads is the actual complaint. A filled tile gives it mass.

## The design

- **Tile** `#18231F`, corner radius 18.75% of the edge — the same ground the favicon
  family uses. Dark reads as a solid object on light *and* dark wallpapers; a leaf-green
  tile would have been louder and would vanish against green wallpaper.
- **Mark** the two-leaf sprout: stem `#5FA23C`, left leaf `#34A853`, right leaf `#8BD24F`,
  soil line `#2C3A24`.
- **Mark scale** is ~14% larger than the favicon proportion. A/B'd at 48 px and 96 px —
  the family proportion left enough dark margin that it still read as a small thing
  inside a big square, which is the complaint this icon answers.

## Two deliberate choices worth knowing

1. **Two leaves, not three.** The old desktop icon used the three-leaf "thriving" mark;
   the favicon *and* the apple-touch-icon both use two. This joins the family — the old
   icon was the outlier, and it was the only asset that had forked.
2. **16 px and 32 px come from their hand-tuned siblings** (`favicon-16x16.svg`,
   `favicon-32.svg`, #1124), not from downscaling the master. Below ~24 px the curves
   mush; those two are drawn on the pixel grid on purpose. Everything 24 px and up
   renders from the master.

## Sizes provided

`16 · 24 · 32 · 48 · 64 · 128 · 256` — the set Windows wants in a multi-resolution `.ico`.

## Regenerating

```sh
magick -background none docs/design/brand/app-icon.svg -resize NxN app-icon-N.png
# 16 and 32 only:
magick -background none docs/design/brand/favicon-16x16.svg -resize 16x16 app-icon-16.png
magick -background none docs/design/brand/favicon-32.svg   -resize 32x32 app-icon-32.png
```

## For DX

Pack these into `tools/launch/sprout.ico` (all seven frames) and re-point the shortcut.
`Install-SproutShortcut.ps1` already sets `IconLocation` from that path, so replacing the
file plus a shortcut refresh should be the whole job — no reinstall ceremony, per the issue.

Worth a live check: Windows caches icons aggressively, so a stale desktop may keep showing
the old one after the file changes. If the tile doesn't appear, that's the icon cache, not
the asset.
