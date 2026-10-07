# Deliverables

Read this when: choosing lockups and the primary lockup in refinement, running the package phase, and answering what a package file is for.

A professional handoff is a system, not one file: lockups, a standalone symbol, monochrome and designed reverse variants, vectors and transparent rasters, with predictable names [03 §1.1]. `package build` makes all of it from `final/` [code].

## Package manifest

- `uv run logomaker package build <slug>` (set the Bash timeout to 300000; a simple mark takes about 15 s) reads `final/` and the brand, never `source/`. It writes into `package.tmp/` beside the package and swaps it in only when every group has succeeded, so a failed build keeps the previous package [code].
- It refuses with exit 2, before Chrome starts, unless `final/` has `concept.py`, `params.json`, `tokens.json` and `rationale.md` and a fresh, rendered, passing `final/audit.json`. A raster that comes out blank (art the colour of its background) stops it with exit 4: change the mark or the tokens, never rebuild verbatim [code].
- `uv run logomaker package verify <slug>` writes `package/verify.json`: every manifest file present, not empty, unchanged since the build (sha256), each raster at its declared size, each listed in README.md, and the build's inputs fingerprint still current. Problems exit 4 [code].

The groups, in `PackageBuilder.GROUPS` order, with counts for a symbol plus a wordmark set in one single-file font family [code]:

| Group | Writes | Files |
|---|---|---|
| `masters` | SVG of 7 variants (primary, horizontal, stacked, wordmark, mark, small, favicon) in 5 colours (color, reverse, black, white, mono), named `<name>-<variant>-<colour>.svg`; mono uses `currentColor` | 35 |
| `pngs` | transparent PNG of primary, horizontal, stacked, wordmark and mark in color, reverse, black and white, long edge 256, 512, 1024 and 2048 | 80 |
| `flattened` | primary on white as a 2048 JPG; primary as a transparent 2048 WebP | 2 |
| `favicons` | `favicon.ico`, `icon.svg`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, `icon-mask-512.png`, `manifest.webmanifest`, `favicon-head.html` | 8 |
| `apple` | `ios-app-icon-1024.png`; `app-icon-layers/background.svg` and `foreground.svg` for Icon Composer | 3 |
| `android` | adaptive `ic_launcher_foreground.svg`, `_background.svg`, `_monochrome.svg`; five `mipmap-*/ic_launcher.png`; `play-store-icon-512.png` | 9 |
| `social` | `avatar-320`, `-400`, `-512`, `-720`, `-800` PNGs | 5 |
| `banners` | X, LinkedIn personal, LinkedIn page, YouTube, Facebook and Bluesky banners | 6 |
| `previews` | `og-image-1200x630.png`, `x-card-1200x600.png` | 2 |
| `commerce` | `stripe-icon-512.png`, `gbp-logo-720.png`, `email-signature-logo@2x.png`, `shopify-header-logo@2x.png`, `stripe-logo.png` | 5 |
| `print_files` | RGB, CMYK and black vector PDFs of primary, horizontal, stacked, wordmark and mark, plus CMYK EPS of primary and mark, drawn by reportlab from the kit's paths, never through Chrome | 17 |
| `tokens_file` | `tokens.json`: every colour in HEX, RGB, HSL, OKLCH and CMYK, role maps, contrast and colour-vision results | 1 |
| `fonts` | each family's TTF files and licence in `fonts/<slug>/`, and `fonts/FONT-NOTICE.md` | 3 |
| `docs` | `BRAND.md`, `rationale.md`, `source/` (concept.py, params.json, tokens.json, rationale.md, brand.json, strategy.json) and `brand-sheet.pdf` | 9 |
| `readme` | `README.md`, the index of every file with purpose and size | 1 |

That is 186 manifest entries, plus `manifest.json` and, after verifying, `verify.json`. A concept without a wordmark makes fewer files; a variant the concept cannot draw falls back to the next larger output, with a warning [code].

A wordmark-only concept (no symbol) shows its full lockup, the wordmark, wherever the package draws the mark at 96 px and above: the `mark` masters, PNGs and PDFs, `ios-app-icon-1024.png` and the Icon Composer foreground, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, `icon-mask-512.png`, the Android adaptive layers and the xhdpi to xxxhdpi launchers, the Play icon, and the Stripe and Google Business tiles. Its `small` tier draws the mdpi and hdpi launchers and the 48 px favicon frame, its `favicon` tier the 32 and 16 px frames and `icon.svg`, and its `compact` tier, when built, the avatars. Tell the owner, or give the concept a symbol (logo-types.md) [code].

README.md lists the files under these sections, in this order: SVG masters, PNG exports, Flattened, Favicons and web app icons, Apple app icon, Android, Social, Email and commerce, Print, Documents and tokens, Fonts, Source; then a "Package files" table for README.md and manifest.json [code]. The research's naming pattern `{brand}-{variant}-{color}-{size}.{ext}` is followed, with the brand name slugified [03 §7].

## Platform specs

Every number is the code's [code]; the platform's own rule is in the last column [03 §2.4 to §2.8].

| File | What the package does | Platform rule |
|---|---|---|
| `favicon.ico` | frames of 48, 32 and 16 px, each drawn by the tier for its size, art at 90% of the square | 32 px, with a hand-tuned 16; 48 for Windows [03 §2.4] |
| `icon.svg` | the favicon tier in a square viewBox, art at 90%, with a `prefers-color-scheme: dark` style switching to the dark roles | square, dark-mode style [03 §2.1, §2.4] |
| `apple-touch-icon.png` | 180 px on the light paper, opaque, art 140 px | 180 x 180, opaque, art about 140 [03 §2.4] |
| `icon-192.png`, `icon-512.png` | transparent, art at 80% | manifest "any" icons [03 §2.4] |
| `icon-mask-512.png` | 512 px on the light paper; the art's box is fitted into a 289 px square, whose corners stay inside the 409.6 px safe circle (radius 40%, 204.8 px) | maskable safe zone: a centred circle of radius 2/5 [03 §2.4] |
| `ios-app-icon-1024.png` | 1024 px, opaque with no alpha channel (App Store Connect refuses one), primary tile, art in the light paper colour at 60% | 1024 x 1024 unmasked square; no baked shadows [03 §2.5] |
| `app-icon-layers/` | background: a 1024 square of the primary; foreground: the mark at 60% of the canvas | Icon Composer layers [03 §2.5] |
| Android adaptive layers | foreground and monochrome on a 1080-unit square (108 dp); each layer's art box is fitted by its own half-diagonal inside the 66 dp safe circle, radius 330 of the 1080 units; background: a primary square | 108 x 108 dp layers; inner 66 x 66 dp safe zone [03 §2.6] |
| `mipmap-*/ic_launcher.png` | 48, 72, 96, 144 and 192 px (mdpi to xxxhdpi), art at 60% on the primary | 48 dp base [03 §2.6] |
| `play-store-icon-512.png` | 512 px full square, art at 60% on the primary | 512 x 512, no corners, no shadow [03 §2.6] |
| `avatar-*.png` | 320, 400, 512, 720 and 800 px on the light paper, art at 56%, inside the circle crops; drawn by the `compact` tier when the concept has one | design inside a centred circle of 80% of the width [03 §2.7] |
| banners | the horizontal lockup at 60% of its safe box on the light paper; X 1500 x 500 keeps the top and bottom 60 px clear; YouTube 2560 x 1440 keeps the logo inside the central 1235 x 338 | X crops 60 px top and bottom; YouTube's safe area [03 §2.7] |
| `og-image-1200x630.png`, `x-card-1200x600.png` | the horizontal lockup at 60% on the light paper | Open Graph 1200 x 630; X card 2:1 [03 §2.8] |
| `stripe-icon-512.png`, `gbp-logo-720.png` | the mark at 62% on the light paper | Stripe at least 128 px; Google Business 720 [03 §2.8] |
| email and Shopify logos | 400 x 100 and 800 x 200, transparent, the lockup as large as fits | shown at 200 x 50 and 400 x 100 [03 §2.8] |
| `stripe-logo.png` | the horizontal lockup 1024 px wide | non-square, at least 128 px [03 §2.8] |
| print PDFs and EPS | vector, outlined; CMYK by naive conversion | confirm with the printer; no PDF/X intent in this version [03 §2.3] [spec §16] |

Two deviations from the spec, where the code is what ships [spec §9] [code]: the spec gives the maskable icon "a 409 px circle", and the code fits the art's square box (289 px) inside that 409.6 px circle; the spec puts Android art "inside the central 660 units", and the code fits each layer's box by its half-diagonal inside the 66 dp circle (radius 330 units), so a wide mark grows as far as the circle allows.

## Clear space and minimum sizes

- The x unit is the wordmark's cap height when the wordmark is set with `text()`; otherwise one fifth of the symbol's height; otherwise the wordmark's height. The same x is the default lockup gap and the clear space on every side, drawn on the refine sheet and stated in BRAND.md [spec §6.2] [code].
- The research's convention: define clear space by an element inside the logo, so it scales (Google's G, PayPal's P, Slack's pill, Spotify's fifth of the logo height) [03 §1.3].
- Minimum sizes are brand.json's `min_sizes`, the `schemas.MinSizes` defaults: horizontal 120 px or 25 mm, stacked 160 px or 25 mm, mark 24 px or 6 mm, favicon 16 px. In this version they are fixed at these defaults: `brand set` has no option for them and brand.json is never edited by hand [code].
- The research ranges they sit in: primary horizontal 18 to 25 mm or 120 to 160 px; Spotify's logo at least 70 px or 20 mm and its icon at least 21 px or 6 mm [03 §1.3, §6.1].
- They drive the audit's `text_legibility` (x-height at least 7 px at the 120 px horizontal and 160 px stacked widths), the refine sheet's minimum-size ladder, BRAND.md and the brand sheet. A failing `text_legibility` is fixed by shortening the lockup or thickening and enlarging the type, since the minimums cannot be raised in this version [code].

## BRAND.md template

What `templates/brand.md.j2` renders, in order [code]:

1. "<Brand> brand guidelines", then the rationale paragraph from `final/rationale.md`.
2. Logo system: a table of Primary (with its lockup), Horizontal, Stacked, Wordmark (when the concept has one), Mark, Small and Favicon, each with its file and use; the five variants named.
3. Clear space and minimum size: one x on every side, what x is and its size in canvas units; the four minimum sizes.
4. Colour: name, HEX, RGB, HSL, OKLCH and naive CMYK per colour; the role maps on light and dark paper; every contrast row as WCAG and APCA.
5. Typography: each family with its weights, licence and where its files are.
6. Don't: stretch or squash it; rotate or tilt it; recolour it outside the roles; add shadows, outlines, gradients or effects; place it on busy backgrounds without the reversed or contained version; re-typeset the name in another font.
7. Backgrounds: `color` on light fields, `reverse` on dark, `white` or `black` on photographs inside a clear-space zone, `white` on primary-colour fields.
8. Web head snippet, when the package has `favicon-head.html`, with the note to replace `https://example.com` in the two preview image URLs.
9. Files: see README.md.

`brand-sheet.pdf` repeats this on one page (Letter, or `--paper a4`): the logo system, the clear-space diagram, the minimum sizes, the colours with contrast, the typefaces, the backgrounds and the head snippet. A sheet that runs past one page warns: shorten the rationale or the palette [code]. Its contents follow the research's one-page sheet [03 §6.2], and the don'ts follow Slack's misuse list [03 §1.5]. The rationale is one paragraph for the owner, without "represents", construction diagrams, ratios or the golden ratio [spec §3.3].

## Sources

03 §1.1 (system components), §1.3 (clear space and minimum sizes), §1.5 (misuse), §2.1 to §2.8 (SVG, favicons, Apple, Android, social, previews, commerce, print), §6.1 (tests), §6.2 (the one-page sheet), §7 (export manifest); spec §3.3, §6.2, §9, §16; code: `export.PackageBuilder` (`GROUPS`, `MASK_SAFE`, `ADAPTIVE_RADIUS`, `circle_viewbox`, the group methods), `export_docs` (`DocumentGroups`, `verify`, the README sections), `schemas.MinSizes`, `kit.mark.Mark.x_unit`, `templates/brand.md.j2`, `templates/brand-sheet.html`.
