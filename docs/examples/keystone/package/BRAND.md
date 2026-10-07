# Keystone brand guidelines

Keystone's mark is an arch that stands because of one stone. The keystone sits at the top, a little proud of the curve, and the rest of the arch leans on it: take it away and the whole thing falls. That is the job Keystone does for a solo consultant, holding the invoicing together and keeping after every bill until it is paid, so you can get on with the work. The arch is heavy and level so it feels steady, rounded at the shoulders so it feels warm, and simple enough to draw from memory. It comes in a warm ember where the category wears blue and green, beside a sturdy grotesque that says the name plainly.

## Logo system

| Tier | File | Use |
|---|---|---|
| Primary (stacked) | `keystone-primary-color.svg` | the default lockup: use it wherever the layout allows |
| Horizontal | `keystone-horizontal-color.svg` | website headers, nav bars, email signatures, banners |
| Stacked | `keystone-stacked-color.svg` | square placements, packaging, social posts |
| Wordmark | `keystone-wordmark-color.svg` | when the symbol is already present |
| Mark | `keystone-mark-color.svg` | avatars, app icons, favicons over 32 px |
| Small | `keystone-small-color.svg` | 33 to 95 px |
| Favicon | `keystone-favicon-color.svg` | 32 px and below |

Each tier ships in five variants: `color`, `reverse` (for dark backgrounds; designed, not inverted), `black`, `white`, and `mono`, which inherits `currentColor` from CSS.

## Clear space and minimum size

- Clear space: one x on every side, where x is the wordmark cap height (260 units of the 1000-unit canvas).
- Minimum sizes: horizontal 120 px / 25 mm; stacked 160 px / 25 mm; mark 24 px / 6 mm; favicon 16 px.

## Colour

| Name | HEX | RGB | HSL | OKLCH | CMYK (naive; confirm with the printer) |
|---|---|---|---|---|---|
| Ember | #c83c29 | 200, 60, 41 | 7.2, 66.0, 47.3 | 0.56 0.1799 30.94 | 0, 70, 80, 22 |
| Ember Glow | #ff8671 | 255, 134, 113 | 8.9, 100.0, 72.2 | 0.7505 0.1512 31.17 | 0, 47, 56, 0 |
| Coal | #221b17 | 34, 27, 23 | 21.8, 19.3, 11.2 | 0.229 0.0134 51.49 | 0, 21, 32, 87 |
| Kiln | #f6eee3 | 246, 238, 227 | 34.7, 51.4, 92.7 | 0.9524 0.017 76.11 | 0, 3, 8, 4 |

Roles on light paper: primary: Ember, ink: Coal, paper: Kiln. Roles on dark paper: primary: Ember Glow, ink: Kiln, paper: Coal.

Contrast (WCAG ratio / APCA Lc):
- light: primary #c83c29 on #f6eee3 = 4.415 / 64.33 (ok)
- light: ink #221b17 on #f6eee3 = 14.757 / 94.35 (ok)
- dark: primary #ff8671 on #221b17 = 7.194 / -54.36 (ok)
- dark: ink #f6eee3 on #221b17 = 14.757 / -95.74 (ok)

## Typography

- Bricolage Grotesque 700 (OFL); files in `fonts/bricolagegrotesque/`

Deliverable SVGs and PDFs have text converted to outlines. The font files are for new material in the same voice.

## Don't

1. Stretch or squash it.
2. Rotate or tilt it.
3. Recolour it outside the roles above.
4. Add shadows, outlines, gradients or effects.
5. Place it on busy backgrounds without the reversed or contained version.
6. Re-typeset the name in another font.

## Backgrounds

Light fields use `color`. Dark fields use `reverse`. Photographs use `white` or `black` inside a clear-space zone. Fields in the primary colour use `white`.

## Web head snippet

```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#c83c29">
<meta name="twitter:card" content="summary_large_image">
<!-- Link previews need absolute image URLs: replace https://example.com with your site's origin. -->
<meta name="twitter:image" content="https://example.com/x-card-1200x600.png">
<meta property="og:image" content="https://example.com/og-image-1200x630.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
```

Replace `https://example.com` in the two preview image URLs with your site's origin, since link previews need absolute URLs; the icon links stay relative to the site root.

## Files

See `README.md` for the full index with dimensions.