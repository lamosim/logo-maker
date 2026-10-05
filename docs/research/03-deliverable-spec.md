# Production-ready logo package: deliverable specification (2026)

Research date: 2026-10-02. Purpose: define exactly what an AI-driven logo workflow must auto-generate for a package to be "ready to go", with exact pixel/mm numbers and primary-source citations. Numbers marked **[secondary]** come from aggregator guides rather than platform documentation; everything else is from the platform or standards body itself. Source URLs are listed inline and collected in Section 8.

---

## 1. The logo system

### 1.1 Components a complete system contains

A professional handoff is a *system*, not one file. DesignAuditly's pre-delivery checklist (updated Sept 2026) lists the minimum variant set: primary lockup, an alternate layout where the primary is wide (stacked/compact), a standalone symbol/icon for avatar/favicon/app use, and deliberately prepared monochrome and reverse variants, plus SVG vectors, transparent PNGs, and predictable file names such as `Brand_Primary_RGB.svg` / `Brand_Icon_White.png` (https://designauditly.com/logo-design-checklist.html).

| Tier | What it is | Typical use |
|---|---|---|
| Primary lockup | Symbol + wordmark in the approved arrangement | Website header, documents, print |
| Horizontal lockup | Symbol beside wordmark | Nav bars, email signatures, banners |
| Stacked lockup | Symbol above wordmark | Square/narrow placements, packaging, social posts |
| Wordmark | Name only, custom-spaced type (outlined) | When the symbol is already present nearby |
| Symbol / mark | Standalone graphic | Avatars, app icons, favicons >32 px |
| Monogram / favicon tier | Simplified mark or single letter re-drawn for a 16–32 px grid | Browser tabs, 16 px favicon, tiny embroidery |

### 1.2 Responsive logo scaling tiers

Joe Harrison's *Responsive Logos* experiment (https://responsivelogos.co.uk/) demonstrated the idea of a logo that drops detail as it shrinks. Fast Company's write-up describes the Walt Disney Pictures mark "first loses its Sleeping Beauty castle, then becomes Disney, before finally shrinking down into a whimsical cursive 'D'", and Coca-Cola "ultimately shrinks down to 'Coke'"; other examples were Nike, Levi's, Bang & Olufsen and Chanel (https://www.fastcompany.com/3033446/what-corporate-logos-would-look-like-if-you-shrank-them).

Real brands codify the same idea with hard breakpoints:

- **Slack** draws its octothorpe on a 19×19 grid, but ships a separate "Small Octothorpe" built on a 15×15 grid with more open internal spacing, and mandates it "at a size smaller than 30px" (Slack Brand Guidelines PDF, https://a.slack-edge.com/0f43e/marketing/img/media-kit/Slack-Brand-Guidelines.pdf).
- **Spotify**: "The Spotify logo should never be smaller than 70px in digital or 20mm in print. The Spotify icon should never be smaller than 21px in digital or 6mm in print" (https://developer.spotify.com/documentation/design).
- **Johns Hopkins Medicine**: horizontal logo never below 1.5 in (38 mm), vertical never below 1.25 in (32 mm); below that, set the name in the brand typeface instead of using the logo (https://brand.hopkinsmedicine.org/brand/branding-guidelines/logo-guidelines/clear-space-and-minimum-size).

**Recommended tier model for generation** (derived from the above): Tier A full lockup (≥ ~120 px wide / ≥ 20–25 mm); Tier B symbol + abbreviated word or symbol only (≥ ~48 px); Tier C simplified mark on a 15–19 unit grid (24–32 px); Tier D monogram for 16 px. Each tier is a separately drawn file, not an automatic downscale.

### 1.3 Clear space and minimum size conventions

Clear space is defined as a ratio to an element inside the logo so it scales: Google uses the height of the "G", PayPal the "P", McDonald's uses 2× the width of one leg of the arches, Reddit uses 120% of its mark; x-height or full logotype height are the other common units (https://kokolv.medium.com/how-to-design-clear-space-for-a-logo-291359020819). Primary-source examples: Johns Hopkins Medicine uses the cap-height of the "H" and requires the zone be "clear of typography, photography, patterns, folds and surface edges"; Slack requires clear space "greater than or equal to the length of one pill shape in the octothorpe" for both horizontal and stacked logos (https://slack.com/terms-of-service/slack-brand); Spotify's hardware-partner guide uses 1/5 of the logo height with 30 mm / 130 px minimums (https://developer.spotify.com/legal/hardware-partners/spotify-connect-logo-guidelines.pdf).

Typical minimum-size numbers published in guidelines (ranges, **[secondary]**): primary horizontal 18–25 mm print / 120–160 px screen; stacked 25 mm / 200 px; simplified mark 10 mm / 80 px; embroidery 40 mm full lockup, 20 mm emblem (https://www.quora.com/How-do-you-define-the-minimum-and-maximum-size-for-the-logo-when-you-write-brand-guidelines-Is-the-size-standard-or-depending-on-factors-1). The generator should emit: clear-space unit `x` (e.g., cap-height of first letter or mark height), and minimum sizes in both px and mm for each tier.

### 1.4 Color variants, backgrounds, placement

Every lockup and the mark should exist in: full color (positive), full color reversed (for dark backgrounds, with a deliberately re-coloured version, not an auto-invert), one-color black, one-color white, and optionally one-color brand color. DesignAuditly: "Confirm that the intended reversed version is designed, not merely auto-inverted" and the mark must "retain hierarchy in solid black or solid white when gradients and color contrast disappear" (https://designauditly.com/logo-design-checklist.html). LinkedIn explicitly notes Page logos are "displayed on both light and dark backgrounds" (https://www.linkedin.com/help/linkedin/answer/a563309), and Apple now requires light, dark, clear and tinted icon appearances (Section 2.5), so background rules must state which variant goes on light, dark, photographic and brand-color fields.

### 1.5 What "misuse" sections forbid

Slack's brand terms are a representative primary list: do not crop, outline the logotype, rotate, distort, add drop shadows or special effects/animation, re-create in another typeface, change transparency, shuffle or change colors, change the size or orientation of symbol vs. logotype, overprint/obstruct, or use old versions (https://slack.com/terms-of-service/slack-brand). Add to this: no stretching, no placing on busy backgrounds without the reversed/contained version, no gradients on the one-color version.

---

## 2. File formats and export specs

### 2.1 SVG (the master format)

Rules for a logo SVG that behaves everywhere:

1. **Square or artwork-fitted `viewBox`, no fixed `width`/`height`** so it scales ("Fit to artwork bounds" so the viewBox has no dead space; https://css-irl.info/optimising-svgs-for-the-web/). For icons/favicons the SVG must be square (https://evilmartians.com/chronicles/how-to-favicon-in-2021-six-files-that-fit-most-needs).
2. **Text converted to outlines, strokes expanded to fills, groups collapsed, paths merged**; no `<text>`, no linked/embedded fonts, no raster `<image>` (https://css-irl.info/optimising-svgs-for-the-web/). Apple's HIG says the same for icon layers: "Outline artwork and convert text to outline in your design" (https://developer.apple.com/design/human-interface-guidelines/app-icons).
3. **Optimize with SVGO** (`npx svgo --multipass icon.svg`). `preset-default` runs removeDoctype, removeComments, removeMetadata, removeEditorsNSData, inlineStyles, cleanupIds, convertShapeToPath, collapseGroups, convertPathData, mergePaths, etc. (https://svgo.dev/docs/preset-default/). Note `removeDimensions` is *not* in the default preset; enable it (or strip `width`/`height` yourself) if you want pure viewBox scaling.
4. **Mono variant uses `currentColor`**: remove hard-coded `fill` so `svg { fill: currentColor }` inherits the surrounding text colour (https://css-irl.info/optimising-svgs-for-the-web/).
5. **Dark-mode favicon**: embed `<style>@media (prefers-color-scheme: dark){.a{fill:#f0f0f0}}</style>` and class the dark paths (https://evilmartians.com/chronicles/how-to-favicon-in-2021-six-files-that-fit-most-needs).
6. **Wide gamut (optional)**: keep the sRGB hex as the attribute and override inside `@media (color-gamut: p3) { ... fill: oklch(55% 0.23 146) }` or `color(display-p3 r g b)` (https://evilmartians.com/chronicles/how-to-use-p3-colors-in-svg).
7. **BIMI/VMC email logo variant**: SVG Tiny 1.2 with `baseProfile="tiny-ps"`, a `<title>` containing the company name, square artboard, draw data only (no embedded bitmaps), and no `x=`, `y=`, `overflow` attributes (https://knowledge.digicert.com/solution/how-to-convert-your-logo-to-svg-format).

### 2.2 Raster exports (PNG / JPG / WebP)

- Apple defines scale factors @1x, @2x, @3x (iOS needs @2x and @3x; macOS @1x and @2x); de-interlaced PNG for bitmap work, 8-bit palette when full colour is unnecessary, and "Include a color profile with each image" (https://developer.apple.com/design/human-interface-guidelines/images).
- Package convention: transparent PNG of every variant at 256, 512, 1024 and 2048 px on the long edge, plus @2x/@3x pairs for the sizes used in UI. 1080 px wide is "the most common standard" for social post images (https://blog.hootsuite.com/social-media-image-sizes-guide/) **[secondary]**.
- JPG only for flattened versions on a white or brand-colour background (no alpha). Optimize PNGs with OxiPNG/palette reduction (Squoosh) as Evil Martians recommends.

### 2.3 Print: PDF, EPS, CMYK

- PDF is the print vector deliverable. Adobe's community guidance: "The EPS format is outdated; one of the format's most serious limitations is no support for transparent fills… PDF must be considered a must for print" (https://community.adobe.com/questions-652/best-vector-format-for-logos-808528). Ship EPS only as a legacy courtesy (flattened, outlined).
- Use a PDF/X standard; Acrobat notes an output-intent device "is required for PDF/X-1a, PDF/X-3, and PDF/X-4 compliance" (https://helpx.adobe.com/acrobat/using/pdf-x-pdf-a-pdf.html). PDF/X-4 keeps live transparency; PDF/X-1a flattens to CMYK + spot only.
- Provide a CMYK build and, where the brand has one, a Pantone spot build (Section 3).

### 2.4 Favicon and web-app icon set

The modern minimal set (Evil Martians, updated Jan 2026; https://evilmartians.com/chronicles/how-to-favicon-in-2021-six-files-that-fit-most-needs):

| File | Spec | Notes |
|---|---|---|
| `/favicon.ico` | 32×32 (add a hand-tuned 16×16 layer if the 32 downscales badly) | Must live at site root; link with `sizes="32x32"` to stop Chrome preferring ICO over SVG. Shopify also lists 16/32/48 px as favicon sizes (https://www.shopify.com/blog/logo-size); 48 is the Windows size. |
| `/icon.svg` | square viewBox, `prefers-color-scheme` style | `type="image/svg+xml"` |
| `/apple-touch-icon.png` | 180×180, opaque background, ~20 px padding (artwork ≈140 px) | iOS crops its own corners |
| `/icon-192.png`, `/icon-512.png` | 192×192, 512×512 | Manifest `any` icons; 512 doubles as PWA splash |
| `/icon-mask.png` | 512×512, `purpose: "maskable"`, artwork inside a 409×409 central circle | W3C: safe zone is a centred circle of radius 2/5 (40%) of the icon's smaller dimension; "most icons will have around 10% padding"; UA composites transparent pixels onto a solid fill, so avoid transparency (https://w3c.github.io/manifest/#icon-masks) |
| `/manifest.webmanifest` | JSON listing the three PNGs | `<link rel="manifest">` |

Head snippet: `<link rel="icon" href="/favicon.ico" sizes="32x32">`, `<link rel="icon" href="/icon.svg" type="image/svg+xml">`, `<link rel="apple-touch-icon" href="/apple-touch-icon.png">`. Deprecated: Windows tile meta, Safari `mask-icon`, `rel="shortcut icon"`.

### 2.5 Apple app icons (iOS 26 / macOS Tahoe era, "Liquid Glass")

From the HIG (change log "June 8, 2026: Refined guidance for Liquid Glass"; https://developer.apple.com/design/human-interface-guidelines/app-icons):

- Layout size **1024×1024 px** for iOS, iPadOS and macOS (square layers, rounded-rect mask applied by the system); **1088×1088** watchOS and **1024×1024** visionOS (circular mask); tvOS 800×480.
- Provide **unmasked square layers**; "Providing layers with pre-defined masking negatively impacts specular highlight effects and makes edges look jagged." Apple does not publish a fixed corner radius; use the grid in the App Icon Template from Apple Design Resources (https://developer.apple.com/design/resources/). WWDC25 says the new grid "features a rounder corner radius… Still using our 1024 pixel canvas" (https://developer.apple.com/videos/play/wwdc2025/220/).
- Build with **Icon Composer** (ships with Xcode 26; https://developer.apple.com/icon-composer/): import vector layers (SVG/PDF preferred, PNG for raster/mesh), define a solid/gradient background, set specular/refraction/translucency, and annotate **default, dark, clear (light/dark) and tinted (light/dark)** appearances; the system generates variants you omit.
- No baked-in shadows, bevels, blurs or glows; avoid thin lines; text only when essential; colour spaces sRGB, Gray Gamma 2.2 or Display P3. One opaque, full-bleed background layer.

### 2.6 Android

- **Adaptive icon**: foreground + background (+ optional monochrome) layers each **108×108 dp**; the inner **66×66 dp** is the safe zone never clipped by OEM masks; outer 18 dp per side is reserved for masking/parallax; logo artwork at least 48×48 dp and at most 66×66 dp; vectors preferred; clean edges, no baked masks/shadows; from Android 16 QPR2 the OS auto-themes icons that lack a monochrome layer (https://developer.android.com/develop/ui/views/launch/icon_design_adaptive). At xxxhdpi (4×) 108 dp = 432 px, 66 dp = 264 px.
- **Legacy launcher PNGs** for API ≤25 are generated per density by Android Studio's Image Asset Studio into `res/mipmap-<density>/`, and it also emits the 512 px Play icon (https://developer.android.com/studio/write/create-app-icons); the standard 48 dp base yields 48/72/96/144/192 px at mdpi/hdpi/xhdpi/xxhdpi/xxxhdpi (https://developer.android.com/training/multiscreen/screendensities).
- **Google Play listing icon**: **512×512, 32-bit PNG, sRGB, ≤1024 KB, full square, no shadow, no rounded corners** (Play applies a radius equal to 30% of icon size and the shadow dynamically); avoid transparency; legacy assets are scaled to a 384 px keyline (https://developer.android.com/distribute/google-play/resources/icon-design-specifications).

### 2.7 Social profile images and banners

Avatars on X, LinkedIn, Instagram, Facebook, YouTube, TikTok, Threads, Bluesky and Discord render as circles; GitHub and Slack use rounded squares. Design every avatar as a full-bleed square with the mark inside a centred circle of 80% of the width (the W3C maskable rule: radius 40%), e.g., a 320 px circle on a 400 px canvas or 409 px on 512 px.

| Platform | Profile/logo | Banner/cover | Source |
|---|---|---|---|
| X | 400×400, JPEG/GIF/PNG, ≤2 MB | 1500×500; 60 px top/bottom may be cropped | https://help.x.com/en/managing-your-account/common-issues-when-uploading-profile-photo |
| LinkedIn Page (company) | Logo rec. 400×400 (min 268×268), PNG/JPEG ≤3 MB, shown on light and dark | Cover 1512×256; custom post image 1200×627 (1.91:1) | https://www.linkedin.com/help/linkedin/answer/a563309 |
| LinkedIn personal | 400×400 (up to 7680×4320, 8 MB) | 1584×396 (4:1) | https://blog.hootsuite.com/social-media-image-sizes-guide/ **[secondary]** |
| Instagram | upload 320×320; displays 110×110 | — | https://www.ziflow.com/blog/social-media-image-sizes **[secondary]** |
| Facebook Page | displays 176×176 desktop, 196×196 phone, 36×36 feature phone (upload ≥320×320) | 851×315 **[secondary]** | https://m.facebook.com/help/125379114252045 ; https://buffer.com/resources/social-media-image-sizes/ |
| YouTube | renders at 98×98; JPG/GIF/BMP/PNG, ≤15 MB (upload 800×800 **[secondary]**) | min 2048×1152 (16:9), safe area for text/logos 1235×338, recommended 2560×1440, ≤6 MB; watermark ≥150×150 | https://support.google.com/youtube/answer/10456525 |
| TikTok | 200×200 rec., 20×20 min | — | https://sproutsocial.com/insights/social-media-image-sizes-guide/ **[secondary]** |
| Threads | 320×320 | link image 1200×600 | https://buffer.com/resources/social-media-image-sizes/ **[secondary]** |
| Bluesky | 400×400 (1:1, circular) | 1500×500 (3:1); link preview 1200×627 | https://buffer.com/resources/social-media-image-sizes/ **[secondary]** |
| GitHub | square, cropped on upload; docs give no px (≈500×500, ≤1 MB is the upload-dialog guidance) | — | https://docs.github.com/en/account-and-profile/tutorials/personalize-your-profile |
| Slack | square crop; GIF/PNG/JPG/JPEG/HEIC/HEIF; 512×512 target **[secondary]** | — | https://slack.com/help/articles/204379773-Upload-a-Slack-icon ; https://postiz.com/tools/slack-photo-resizer |
| Discord | 512×512 recommended, 1:1, circular | profile banner 600×240; server banner 1920×1080 **[secondary]** | https://support.discord.com/hc/en-us/community/posts/1500000526561 |

### 2.8 Link previews, email, commerce platforms

- **Open Graph `og:image`**: at least **1200×630**, 1.91:1, minimum 600×315 for the large layout, absolute minimum 200×200, ≤8 MB; add `og:image:width/height` so the first share renders (https://developers.facebook.com/docs/sharing/webmasters/images/).
- **X summary_large_image**: 2:1, min 300×157, max 4096×4096, <5 MB, JPG/PNG/WEBP/GIF, SVG not supported (https://devcommunity.x.com/t/twitter-card-summary-large-image/144086/2). Export a 1200×600 version alongside the 1200×630.
- **Email signature**: signature block 300–400 px wide and 150–200 px tall; logos display at 100–200 px wide, exported at 2× for Retina and set to display width in HTML (https://www.wisestamp.com/guides/what-are-correct-email-signature-dimensions/); logo 100–300 × 30–100 px (https://www.emailsignaturerescue.com/blog/what-size-should-the-images-be-in-my-email-signature); Shopify suggests 320×100 PNG (https://www.shopify.com/blog/logo-size).
- **Shopify**: the theme editor has a dedicated logo upload with a desktop logo-width slider; recommended header PNGs 250×150 / 350×75 / 400×100 (horizontal) or 160×160 (vertical), keep under 200 KB (https://www.shopify.com/blog/logo-size). Export 2× versions (e.g., 800×200).
- **Stripe**: icon (square) and logo (non-square) must be JPG or PNG, <512 KB and ≥128×128 px; the icon is used in emails, Checkout, Payment Links, customer portal and invoices (https://docs.stripe.com/get-started/account/branding).
- **Google Business Profile**: JPG or PNG, 10 KB–5 MB, recommended 720×720, minimum 250×250 (https://support.google.com/business/answer/6103862).

---

## 3. Colour specification

**Document every brand colour in HEX, RGB, HSL, CMYK and (if used) Pantone, plus an optional OKLCH/P3 value.** Pantone's own guidance is the key caveat: "neither RGB, nor CMYK values may be used to define a color. Rather, we need to think of RGB and CMYK as recipes"; both are device-dependent, whereas CIELAB is device-independent; "In a typical print environment, you can achieve about 55% of the Pantone Matching System (PMS) Spot Colors… using only CMYK", rising to ~90% with seven-colour CMYKOGV; spot colours are "well-suited for applications like corporate logos and identity programs"; the Pantone Color Bridge prints the spot colour beside its closest CMYK simulation with sRGB/HTML values (https://www.pantone.com/na/en-us/articles/color-fundamentals/understanding-different-color-spaces). About 20% of Pantone colours cannot be shown correctly on sRGB monitors (https://graphicdesign.stackexchange.com/questions/159715/should-pantone-colors-outside-the-rgb-gamut-be-avoided) **[secondary]**.

Practical rules for the generator:

- Pick colours inside sRGB first (hex/rgb/hsl can only encode sRGB; https://evilmartians.com/chronicles/how-to-use-p3-colors-in-svg). Offer a Display P3 enhancement only as a media-query override with an sRGB fallback; Apple icons accept sRGB, Gray Gamma 2.2 or Display P3 (https://developer.apple.com/design/human-interface-guidelines/app-icons).
- Convert RGB→CMYK with a named ICC profile (e.g., GRACoL/FOGRA) and warn when the colour is out of gamut; saturated blues/oranges/greens shift most. Never "define" the brand by the CMYK recipe; define it by the swatch (Pantone/LAB) and publish recipes per medium.
- **WCAG 2.2**: text in a logo or brand name "has no contrast requirement", but if the logo acts as a link/control the guidance is to choose a variant with ≥4.5:1 (3:1 for large text ≥24 px / ≥18.5 px bold), and an author-chosen low-contrast presentation of logos is *not* exempt; non-text UI graphics need 3:1 under 1.4.11 (https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html). Contrast = (L1+0.05)/(L2+0.05) using sRGB relative luminance.
- **APCA** (candidate WCAG 3 method; https://github.com/Myndex/SAPC-APCA): Bronze Simple Mode thresholds are Lc 75 body text (Lc 90 preferred), Lc 60 other content text, Lc 45 for text >36 px; logos/branding are a separate use-case not covered at Bronze (https://readtech.org/ARC/tests/bronze-simple-mode/?tn=criterion). Report both WCAG ratio and Lc for wordmark-on-background pairs.
- **Colour-blind checks**: run every colour variant through a CVD simulator for protanopia, deuteranopia, tritanopia and achromatopsia: Coblis (https://www.color-blindness.com/coblis-color-blindness-simulator/), Adobe Color's conflict checker (https://color.adobe.com/create/color-accessibility), Myndex CVD (https://www.myndex.com/CVD/), Sim Daltonism on macOS. Pass criterion: hierarchy survives in the grayscale and deuteranopia views.
- **Documentation format**: a `colors.json`/tokens file with `{name, role, hex, rgb, hsl, cmyk, pantone, oklch, p3}` per swatch, plus allowed pairings and the WCAG/APCA results.

---

## 4. Typography and font licensing

### 4.1 What open licences allow

- **SIL OFL 1.1** (most Google Fonts): FAQ 1.1: using OFL fonts "to create logos or other graphics" is explicitly allowed with "no additional license or permission"; 1.1.1: the resulting artwork is yours and not restricted; 1.1.2: no acknowledgement required; 1.13: creating a graphic does not make the artwork subject to the OFL; 1.26: AI-based design tools may use OFL fonts "as long as the resulting work is not intended to be a font" (https://openfontlicense.org/ofl-faq/).
- **Reserved Font Names** matter only if you *modify or re-format the font itself*: a format change "normally is considered modification, and Reserved Font Names cannot be used" (FAQ 2.2); derivative fonts must drop every reserved word (5.1–5.4). Outlined glyphs in a logo are artwork, not a font, so RFNs do not apply to the logo. Note also 5.5: font names already linked to trademarks you don't own must be avoided.
- The Google Fonts repository README confirms the licence mix: "Most of the fonts in the collection use the SIL Open Font License, v1.1. Some fonts use the Apache 2 license. The Ubuntu fonts use the Ubuntu Font License v1.0", and every family directory carries its licence file (https://raw.githubusercontent.com/google/fonts/main/README.md). Apache 2.0 and UFL likewise permit logo use; Apache requires the licence/notice to travel with redistributed font files, UFL requires renaming of modified fonts.
- **Trademark note**: the OFL grants a copyright licence to the font software; it does not stop you registering your outlined wordmark as a trademark, but your trademark covers the logo, not the typeface.

### 4.2 Why convert to outlines

Outlining removes the runtime font dependency (no `<text>`, no embedded font in SVG/PDF), freezes kerning and custom letter modifications, avoids WOFF/subsetting RFN questions, and is what Apple requires for icon layers. Keep an editable master (with the live font) alongside the outlined deliverable, and respect licensing for any font files you package (https://designauditly.com/logo-design-checklist.html).

### 4.3 Programmatic font sourcing

- **GitHub `google/fonts`**: top-level `ofl/`, `apache/`, `ufl/` directories; each family folder holds the served `.ttf` files, `METADATA.pb` and the licence file; raw-file URL pattern `https://raw.githubusercontent.com/google/fonts/main/ofl/<family>/<File>.ttf`; full snapshot zip >1 GB (https://github.com/google/fonts).
- **google-webfonts-helper** (https://gwfh.mranftl.com/, source https://github.com/majodev/google-webfonts-helper): REST API returning eot/ttf/svg/woff/woff2 plus `@font-face` CSS for self-hosting.
- **Fontsource**: `npm install @fontsource-variable/<family>` (variable, full weight range) or `@fontsource/<family>` then `import "@fontsource/<family>/700.css"`; version-locked, offline, `unicode-range` subsetting (https://fontsource.org/docs/getting-started/install).
- **Variable fonts**: one file with continuous axes (wght, wdth, opsz, ital, slnt, custom); named instances still appear in menus; let the logo generator pick any weight value (e.g., 742) for optical tuning before outlining (https://fonts.google.com/knowledge/introducing_type/introducing_variable_fonts).

### 4.4 Logo-grade open-source families (all on Google Fonts, OFL unless noted)

Selection cross-checked against Typewolf's curated top 40 (https://www.typewolf.com/google-fonts) and Figma's logo-font guide (https://www.figma.com/resource-library/best-fonts-for-logos/).

| Category | Families | Personality |
|---|---|---|
| Geometric sans | Montserrat, Poppins, Outfit, Jost, Plus Jakarta Sans, Sora, DM Sans, Manrope, Urbanist, Figtree | Modern, tech, confident, startup; circular "o"s read well at small sizes |
| Grotesk / neo-grotesque | Inter, Space Grotesk, Work Sans, Archivo, Familjen Grotesk, Bricolage Grotesque, Instrument Sans, Public Sans, IBM Plex Sans, Roboto (Apache), Geist | Neutral, Swiss, editorial, "serious software"; quirks (Bricolage, Space Grotesk) add character |
| Humanist sans | Open Sans, Source Sans 3, Lato, Fira Sans, Nunito Sans, Alegreya Sans, PT Sans, Cabin, Inclusive Sans, Atkinson Hyperlegible | Warm, approachable, trustworthy; healthcare, education, civic |
| Transitional serif | Libre Baskerville, Source Serif 4, Merriweather, Lora, Newsreader, Literata, Spectral, Crimson Pro, Libre Caslon Text | Established, credible, publishing, finance, law |
| Old-style serif | EB Garamond, Cormorant (Garamond), Cardo, Alegreya, Crimson Text | Heritage, literary, artisanal, hospitality |
| Didone / high-contrast display | Playfair Display, Bodoni Moda, DM Serif Display, Abril Fatface, Instrument Serif, Gilda Display, Prata, Fraunces (soft/"wonky" variable) | Luxury, fashion, beauty, editorial |
| Slab | Roboto Slab (Apache), Zilla Slab, Arvo, Bitter, Aleo, Josefin Slab, Alfa Slab One (display) | Sturdy, craft, industrial, Americana, outdoors |
| Display | Syne, Unbounded, Bebas Neue, Anton, Oswald, Archivo Black, Righteous, Climate Crisis, Rozha One, Ultra | Loud, distinctive, entertainment, sports, streetwear; use for wordmarks, not body |
| Mono | Space Mono, JetBrains Mono, IBM Plex Mono, Azeret Mono, DM Mono, Roboto Mono, Fira Code, Geist Mono, Martian Mono | Technical, developer, data, retro-futurist |
| Rounded | Nunito, Quicksand, Varela Round, Comfortaa, Fredoka, Baloo 2, M PLUS Rounded 1c | Friendly, playful, kids, food, wellness, consumer apps |

---

## 5. Trademark and originality

- **Distinctiveness spectrum** (USPTO): fanciful (invented words: Exxon, Pepsi) > arbitrary (real word unrelated to goods: Apple for computers) > suggestive (Coppertone) are strong and registrable; descriptive ("Creamy" for yogurt) is weak and only registrable after acquired distinctiveness; generic ("Bicycle" for bicycles) can never be a trademark (https://www.uspto.gov/trademarks/basics/strong-trademarks). A logo generator should flag descriptive or generic names and category clichés (cross/leaf/shield/swoosh) as weak.
- **Likelihood of confusion** is the most common refusal; marks need not be identical, only similar in "sound, appearance, or meaning", or creating "a similar commercial impression" (e.g., the same dominant design element with or without words), *and* the goods/services must be related (https://www.uspto.gov/trademarks/search/likelihood-confusion).
- **Basic clearance workflow** (USPTO's comprehensive-search list; https://www.uspto.gov/trademarks/search/comprehensive-clearance-search-similar-trademarks): (1) USPTO Trademark Search system (https://tmsearch.uspto.gov/) for word and design marks, using design search codes for logo shapes (https://tmdesigncodes.uspto.gov/); (2) Trademark Official Gazette; (3) state registries; (4) ICANN domain registries; (5) WIPO Madrid Monitor and **Global Brand Database**, which supports "image similarity" search (https://www.wipo.int/en/web/global-brand-database); (6) **EUIPO eSearch plus** (drag one image to search trade marks; https://euipo.europa.eu/eSearch/) and TMview (https://www.tmdn.org/tmview/); (7) web search for common-law use. Add reverse image search (Google Lens, TinEye) on the rendered mark.
- **Famous marks**: avoid any resemblance to well-known logos even in unrelated categories; owners police this explicitly, e.g., Slack: "Do not apply for a trademark that includes the word 'slack,' our logo, or any other words or marks similar to our own" (https://slack.com/terms-of-service/slack-brand).
- **Indie originality checks**: silhouette comparison against category clichés, reverse image search of the mark and of each letterform treatment, search of logo galleries, and a design-code search in USPTO/WIPO/EUIPO before committing (https://designauditly.com/logo-design-checklist.html). None of this replaces an attorney's clearance opinion.

---

## 6. Quality checklist and the one-page brand sheet

### 6.1 Tests professionals run

| Test | Pass criterion | Source |
|---|---|---|
| 16 px favicon test | Render at 16×16; if blurry, draw a dedicated tiny version | https://evilmartians.com/chronicles/how-to-favicon-in-2021-six-files-that-fit-most-needs |
| Scale test | Check favicon/avatar scale for "counters closing, lines merging, and tiny gaps turning into noise"; check nav-size lockup | https://designauditly.com/logo-design-checklist.html |
| Squint / blur test | Blur the logo; a clear, confident silhouette should persist | https://lumance.ai/blog/logo-scalability-test-how-to-check-if-your-logo-works-at-any-size |
| Grayscale test | Hierarchy survives with colour removed | https://designauditly.com/logo-design-checklist.html |
| One-colour / photocopy / fax / embroidery test | Solid black and solid white versions keep hierarchy with no gradients; works in one thread colour | https://designauditly.com/logo-design-checklist.html ; https://www.vistaprint.com/hub/logo-checklist |
| Inversion (reverse) test | Reversed version is designed, not auto-inverted | https://designauditly.com/logo-design-checklist.html |
| "1 cm on a pen" test | Icon legible at 6 mm print / 21 px digital; full logo at 20 mm / 70 px (Spotify precedent) | https://developer.spotify.com/documentation/design |
| Silhouette and cliché test | Flat-shape recognition; distinguishing decision vs. category clichés | https://designauditly.com/logo-design-checklist.html |
| Flip / mirror test | Flip horizontally to expose balance errors | https://www.youtube.com/watch?v=j299fIs_fMI |
| Contrast and CVD test | WCAG ratio + APCA Lc; deuteranopia/protanopia/tritanopia simulation | Section 3 |
| Package test | Open the delivery folder as the client would; check transparency, crops, names | https://designauditly.com/logo-design-checklist.html |

### 6.2 One-page brand sheet contents

Typical one-page guides contain: logo variations, colour palette (chips with values), typography hierarchy, a mood/imagery section and brand asset placeholders (https://www.behance.net/gallery/234930875/Free-1-Page-Brand-Guideline-Template-Logos); logo, colour chips, type stack and visual direction with mini usage notes (https://fliphtml5.com/blog/10-one-page-brand-guidelines-templates-examples-and-design-ideas/). Recommended generator output: (1) primary, horizontal, stacked, mark and monogram tiers; (2) clear-space diagram with the `x` unit and minimum sizes in px and mm; (3) colour swatches with HEX/RGB/HSL/CMYK/Pantone and approved pairings with contrast results; (4) primary and secondary typefaces with weights and licence names; (5) a six-item "don't" row; (6) background rules (light/dark/photo); (7) file index.

---

## 7. Export manifest

Naming pattern: `{brand}-{variant}-{color}-{size}.{ext}` (lowercase, hyphenated). "Each variant" = primary, horizontal, stacked, wordmark, mark, monogram.

| File | Format | Dimensions / spec | Purpose |
|---|---|---|---|
| `{brand}-{variant}-color.svg` | SVG (outlined, svgo, viewBox) | artwork-fitted viewBox | Master full-colour vector |
| `{brand}-{variant}-reverse.svg` | SVG | same | Full colour for dark backgrounds |
| `{brand}-{variant}-black.svg`, `-white.svg` | SVG | same | One-colour positive/negative |
| `{brand}-{variant}-mono.svg` | SVG, `fill="currentColor"` | same | Inherits CSS colour; icon systems |
| `{brand}-{variant}-color-p3.svg` | SVG with `color-gamut: p3` override | same | Optional wide-gamut web |
| `{brand}-{variant}-cmyk.pdf` | PDF/X-4 (and PDF/X-1a) | vector, outlined, CMYK + spot | Print master |
| `{brand}-{variant}-black.pdf`, `-white.pdf` | PDF/X-4 | vector | One-colour print |
| `{brand}-{variant}-cmyk.eps` | EPS (legacy, flattened) | vector | Old print/sign vendors only |
| `{brand}-{variant}-color-{256,512,1024,2048}.png` | PNG-24 transparent | long edge 256/512/1024/2048 | General digital use |
| `{brand}-{variant}-{black,white}-{512,1024,2048}.png` | PNG transparent | as named | One-colour digital |
| `{brand}-{variant}-color@2x.png`, `@3x.png` | PNG | 2×/3× of the @1x UI size | Apple/UI scale factors |
| `{brand}-{variant}-color-white-bg-2048.jpg` | JPG | 2048 long edge, no alpha | Flattened, email/office |
| `{brand}-{variant}-color-2048.webp` | WebP | 2048 | Web performance |
| `favicon.ico` | ICO (16, 32, 48 layers) | 16×16, 32×32, 48×48 | Legacy browsers, Windows |
| `icon.svg` | SVG + `prefers-color-scheme` | square viewBox | Modern favicon |
| `apple-touch-icon.png` | PNG, opaque | 180×180 (art ≈140) | iOS home screen bookmark |
| `icon-192.png`, `icon-512.png` | PNG | 192×192, 512×512 | PWA / Android home screen |
| `icon-mask-512.png` | PNG, opaque | 512×512, art within 409 px circle | Maskable PWA icon |
| `manifest.webmanifest`, `favicon-head.html` | JSON, HTML | — | Manifest + `<link>` snippet |
| `bimi-logo.svg` | SVG Tiny 1.2 `tiny-ps` | square, `<title>` = company | BIMI/VMC email sender logo |
| `ios-app-icon-1024.png` | PNG, opaque, sRGB or P3 | 1024×1024, square, unmasked | iOS/iPadOS/macOS flat fallback |
| `app-icon.icon` (Icon Composer project) + layer SVGs | Icon Composer | 1024 canvas; 1088 watchOS | Liquid Glass layered icon, all appearances |
| `android/ic_launcher_foreground.svg`, `_background.svg`, `_monochrome.svg` | SVG (VectorDrawable-ready) | 108×108 dp, art in 66 dp safe zone | Adaptive icon layers |
| `android/mipmap-{m,h,x,xx,xxx}hdpi/ic_launcher.png` | PNG | 48/72/96/144/192 px | Legacy launcher icons |
| `play-store-icon-512.png` | 32-bit PNG, sRGB, ≤1024 KB | 512×512, no corners/shadow | Google Play listing |
| `avatar-400.png` | PNG | 400×400, art in 320 px circle | X, LinkedIn, Bluesky |
| `avatar-320.png` | PNG/JPG | 320×320 | Instagram, Facebook, Threads |
| `avatar-512.png` | PNG | 512×512 | Discord, Slack, GitHub |
| `avatar-800.png`, `avatar-720.png` | PNG/JPG | 800×800; 720×720 | YouTube; Google Business Profile |
| `banner-x-1500x500.png` | PNG/JPG | 1500×500, keep 60 px top/bottom clear | X header |
| `banner-linkedin-personal-1584x396.png` | PNG/JPG | 1584×396 | LinkedIn profile |
| `banner-linkedin-page-1512x256.png` | PNG/JPG ≤3 MB | 1512×256 | LinkedIn Page cover |
| `banner-youtube-2560x1440.png` | PNG/JPG ≤6 MB | 2560×1440, logo inside central 1235×338 | YouTube channel art |
| `banner-facebook-851x315.png`, `banner-bluesky-1500x500.png` | PNG/JPG | as named | Facebook Page, Bluesky |
| `og-image-1200x630.png` | PNG/JPG ≤8 MB | 1200×630 (1.91:1) | Open Graph / Facebook / LinkedIn |
| `x-card-1200x600.png` | PNG/JPG <5 MB | 1200×600 (2:1) | X summary_large_image |
| `email-signature-logo@2x.png` | PNG | 400×100 displayed at 200×50 | Email signatures (Retina) |
| `shopify-header-logo@2x.png` | PNG <200 KB | 800×200 (shown 400×100) | Shopify theme header |
| `stripe-icon-512.png`, `stripe-logo.png` | PNG/JPG <512 KB | 512×512; non-square ≥128 px tall | Stripe branding |
| `gbp-logo-720.png` | PNG/JPG 10 KB–5 MB | 720×720 | Google Business Profile |
| `brand-sheet.pdf` | PDF, 1 page | A4/Letter | One-page guidelines |
| `colors.json` / `tokens.json` | JSON | HEX/RGB/HSL/CMYK/Pantone/OKLCH + contrast results | Design tokens |
| `fonts/` + `OFL.txt` (or Apache/UFL licence) | TTF/WOFF2 + licence text | — | Redistributed fonts with their licences |
| `README.md` | Markdown | — | Variant map, clear space, min sizes, misuse, file index |

---

## 8. Sources

1. https://responsivelogos.co.uk/
2. https://www.fastcompany.com/3033446/what-corporate-logos-would-look-like-if-you-shrank-them
3. https://a.slack-edge.com/0f43e/marketing/img/media-kit/Slack-Brand-Guidelines.pdf
4. https://slack.com/terms-of-service/slack-brand
5. https://developer.spotify.com/documentation/design
6. https://developer.spotify.com/legal/hardware-partners/spotify-connect-logo-guidelines.pdf
7. https://brand.hopkinsmedicine.org/brand/branding-guidelines/logo-guidelines/clear-space-and-minimum-size
8. https://kokolv.medium.com/how-to-design-clear-space-for-a-logo-291359020819
9. https://designauditly.com/logo-design-checklist.html
10. https://evilmartians.com/chronicles/how-to-favicon-in-2021-six-files-that-fit-most-needs
11. https://evilmartians.com/chronicles/how-to-use-p3-colors-in-svg
12. https://w3c.github.io/manifest/#icon-masks
13. https://css-irl.info/optimising-svgs-for-the-web/
14. https://svgo.dev/docs/preset-default/
15. https://knowledge.digicert.com/solution/how-to-convert-your-logo-to-svg-format
16. https://developer.apple.com/design/human-interface-guidelines/app-icons
17. https://developer.apple.com/design/human-interface-guidelines/images
18. https://developer.apple.com/icon-composer/
19. https://developer.apple.com/videos/play/wwdc2025/220/
20. https://developer.android.com/develop/ui/views/launch/icon_design_adaptive
21. https://developer.android.com/distribute/google-play/resources/icon-design-specifications
22. https://developer.android.com/studio/write/create-app-icons
23. https://community.adobe.com/questions-652/best-vector-format-for-logos-808528
24. https://helpx.adobe.com/acrobat/using/pdf-x-pdf-a-pdf.html
25. https://help.x.com/en/managing-your-account/common-issues-when-uploading-profile-photo
26. https://www.linkedin.com/help/linkedin/answer/a563309
27. https://m.facebook.com/help/125379114252045
28. https://support.google.com/youtube/answer/10456525
29. https://docs.github.com/en/account-and-profile/tutorials/personalize-your-profile
30. https://slack.com/help/articles/204379773-Upload-a-Slack-icon
31. https://support.discord.com/hc/en-us/community/posts/1500000526561
32. https://developers.facebook.com/docs/sharing/webmasters/images/
33. https://devcommunity.x.com/t/twitter-card-summary-large-image/144086/2
34. https://docs.stripe.com/get-started/account/branding
35. https://www.shopify.com/blog/logo-size
36. https://support.google.com/business/answer/6103862
37. https://www.wisestamp.com/guides/what-are-correct-email-signature-dimensions/
38. https://www.emailsignaturerescue.com/blog/what-size-should-the-images-be-in-my-email-signature
39. https://blog.hootsuite.com/social-media-image-sizes-guide/ ; https://buffer.com/resources/social-media-image-sizes/ ; https://sproutsocial.com/insights/social-media-image-sizes-guide/ ; https://www.ziflow.com/blog/social-media-image-sizes ; https://postiz.com/tools/slack-photo-resizer
40. https://www.pantone.com/na/en-us/articles/color-fundamentals/understanding-different-color-spaces
41. https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
42. https://github.com/Myndex/SAPC-APCA ; https://readtech.org/ARC/tests/bronze-simple-mode/?tn=criterion
43. https://www.color-blindness.com/coblis-color-blindness-simulator/ ; https://color.adobe.com/create/color-accessibility
44. https://openfontlicense.org/ofl-faq/
45. https://github.com/google/fonts ; https://raw.githubusercontent.com/google/fonts/main/README.md
46. https://gwfh.mranftl.com/ ; https://github.com/majodev/google-webfonts-helper
47. https://fontsource.org/docs/getting-started/install
48. https://fonts.google.com/knowledge/introducing_type/introducing_variable_fonts
49. https://www.typewolf.com/google-fonts ; https://www.figma.com/resource-library/best-fonts-for-logos/
50. https://www.uspto.gov/trademarks/basics/strong-trademarks
51. https://www.uspto.gov/trademarks/search/likelihood-confusion
52. https://www.uspto.gov/trademarks/search/comprehensive-clearance-search-similar-trademarks
53. https://www.wipo.int/en/web/global-brand-database ; https://euipo.europa.eu/eSearch/
54. https://lumance.ai/blog/logo-scalability-test-how-to-check-if-your-logo-works-at-any-size
55. https://www.behance.net/gallery/234930875/Free-1-Page-Brand-Guideline-Template-Logos ; https://fliphtml5.com/blog/10-one-page-brand-guidelines-templates-examples-and-design-ideas/
