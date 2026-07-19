# Front-door alt-text register

**Status:** Canonical · **Surface:** [`docs/index.html`](../../index.html) · **Owner:** DX lane

This register covers every image exposed by the public front door, including the metadata-only social
preview. Browser chrome icons are excluded because they are not page content and have no HTML alternative
text. Update this register whenever front-door imagery or its accessible text changes.

| Surface | Asset path | Accessible text in `docs/index.html` | Decision |
| --- | --- | --- | --- |
| Navigation brandmark | `docs/design/brand/sprout-avatar.svg` | `alt=""` | Decorative. The same link already contains the visible text “Sprout”; repeating it would duplicate the link's accessible name. |
| Hero mark | `docs/design/brand/sprout-hero-mark.svg` (inlined) | `role="img"` and `aria-label="Sprout — a three-leaf seedling, gently swaying"` | Informative. The inline SVG keeps one concise accessible name and needs no duplicate hidden text. |
| Social preview | `docs/design/brand/social-preview.png` | `og:image:alt="Sprout — the plant that talks back: local-first plant care on an ESP32, four plants each with their own mood."` | Metadata-only image. Its description travels with the share card. |

## Audit result

The front-door DOM contains one `<img>` and one meaningful inline `<svg>`. The navigation image's empty
alternative is intentional because adjacent text supplies the link name. The hero SVG already has the
required `role="img"` and descriptive `aria-label`; neither markup item needs changing.

— DX
