# AI & Programmatic Logo Generation — State of the Art (Oct 2026)

Research memo for the Claude Code–driven logo generator. Date: 2026-10-02. ~30 searches/scrapes; package versions pulled live from the npm/PyPI registries today. Where a claim comes from a vendor or an affiliate blog, it is flagged as such.

---

## 1. LLM-authored SVG: what frontier models can and cannot draw

### 1.1 Benchmarks and evidence

**The pelican series (Simon Willison, 2024–2026).** 146 posts tagged `pelican-riding-a-bicycle` (https://simonwillison.net/tags/pelican-riding-a-bicycle/). Observations relevant to logos:

- Every frontier release through Sep 2026 (GPT-6 Luna/Terra/Sol/Astra, Claude Sonnet 5.5, Claude Fable 5.1, Gemini 3.8 Flash) is tested; the comparison grid for the GPT-6 family was "surprisingly useful" (https://simonwillison.net/2026/Sep/4/astra-pelicans/).
- Willison's own verdict (May 2026 newsletter): "the pelican on the bicycle has firmly exceeded its limits as a useful benchmark" — a 20 GB local Qwen3.6-35B-A3B "drew a better pelican than Claude Opus 4.7, which messed up the bicycle frame" (https://simonw.substack.com/p/the-last-six-months-in-llms-in-five). Translation for logos: raw drawing skill no longer separates models; geometry errors (a frame that doesn't close) still happen at the top tier.
- Gemini 3.1 Pro "thought for 323.9 seconds" to produce one pelican (https://simonwillison.net/2026/Feb/19/gemini-31-pro/) — reasoning effort materially changes output quality, and he reports "very different looking" results across low/medium/high effort.
- A supposed "invalid SVG" from Gemini 3.7 Flash turned out to be a renderer discrepancy, not the model (update 14 Aug 2026) — a reminder that *your rasterizer is part of the benchmark*.
- Tom Gally's extension: 30 prompts of the form "Generate an SVG of [A] [doing] [B]" × 9 frontier models (https://gally.net/temp/20251107pelican-alternatives/index.html, via https://simonwillison.net/2025/Nov/25/llm-svg-generation-benchmark/).
- Dylan Castillo, "Are AI labs pelicanmaxxing?": 1,008 SVGs across GPT-5.6 Terra, Claude Sonnet 5, Gemini 3.5 Flash, Grok 4.5, Qwen3.7-Max, GLM-5.2, DeepSeek V4 Pro, LLM-judged on accuracy/visual quality/composition. Conclusion: no model draws pelican+bicycle better than its other animal/vehicle pairs, so the skill is general, not memorised (https://dylancastillo.co/posts/pelicanmaxxing.html).

**SVGBench** (johnbean393, VLM-judged render accuracy; https://github.com/johnbean393/SVGBench): GLM-5 70.3 %, GLM-4.7 62.4 %, Qwen3-30B-A3B 40.9 %. Note the leaderboard only lists Zhipu/Qwen models — treat as partial. A separate "SVG-Bench" on llm-stats.com (MiniMax M3, 63.7 %) is **vendor self-reported**. A blind arena exists at https://svgbench.ai/.

**SVGenius** (ACM MM 2025; 2,377 queries, 24 domains, 22 models; https://arxiv.org/html/2506.03139v1). The most rigorous evidence, though it predates the current model generation (tested GPT-4o, Gemini 2.0 Flash, Claude 3.7 Sonnet). Findings that still hold:
1. Proprietary > open-source, and the gap widens with complexity.
2. **All** models degrade systematically as SVG complexity (paths/control points) rises — GPT-4o fell from 82.7 % to 42.2 % on perceptual QA from easy to hard.
3. "Top models achieve 70–80 % semantic understanding but struggle with structural synthesis (PSS scores rarely exceed 20), indicating a comprehension–creation gap."
4. Reasoning-enhanced training beats scaling for generation; style transfer is the hardest task.
5. Claude 3.7 Sonnet led editing/bug-fixing (76 % accuracy) — LLMs are better at *repairing and editing* SVG than at synthesising it from nothing.

**Research models.** StarVector (CVPR 2025, image→SVG, 1B/8B; https://github.com/joanrod/star-vector), OmniSVG (NeurIPS 2025; 3B weights Apache-2.0, 17 GB GPU, 4–83 s per SVG; https://huggingface.co/OmniSVG/OmniSVG), LLM4SVG (CVPR 2025; 2,048-token cap), Chat2SVG (LLM builds a template from geometric primitives, then diffusion refines; https://chat2svg.github.io/), Reason-SVG (CVPR 2026; "Drawing-with-Thought" — the model emits a design rationale before the SVG, trained with hybrid-reward RL; https://arxiv.org/abs/2505.24499), Rendering-Aware RL (NeurIPS 2025), DuetSVG (Dec 2025), CTRL-S (Mar 2026). None of these produce logo-grade output better than a frontier LLM plus tooling; OmniSVG's own table shows GPT-4o generating "icon-level" SVG in 0.6k tokens where OmniSVG spends 4–35k tokens, and the specialised models "fail completely" outside their niche (SVGenius on IconShop/StarVector). **Verdict: do not self-host a research text-to-SVG model for logos.**

**The render→inspect→revise loop is now peer-reviewed.** "Seeing is Improving: Visual Feedback for Iterative Text Layout Refinement" (CVPR 2026; https://arxiv.org/html/2603.22187v1) shows code-only SVG generation yields syntactically valid files "that still suffer from overlapping elements, poor contrast, or misaligned components," and that a generation → render → reflect → refine cycle fixes them. Two practical findings: a tool call `svg_to_image_tool` was enough for the loop, and **an outcome-only reward beat process rewards** — judge the final render, not the intermediate steps.

### 1.2 How practitioners get logo-grade output from Claude

The three open-source Claude Code logo skills (section 7) converge on the same recipe:

- **Construction, not freehand.** A `viewBox` of 512×512 or a 24/32-unit grid; shapes built from primitives (`circle`, `rect`, `path` arcs) with integer or quarter-unit coordinates; strokes ≥ 6 units at 512 so they survive 16 px (neonwatty SKILL.md). A Towards AI piece puts the failure crisply: an LLM typing `x="147"` "has no grid, no ruler, no alignment guide — every coordinate is a token prediction" (https://pub.towardsai.net/stop-fixing-your-ai-svgs-715df70ccca0). The fix is to give it one: a constrained DSL or JSON spec (grid cells, named anchors, boolean ops) that *code* turns into path data.
- **Real glyph outlines, never hand-drawn letters.** LogoLoom's `text_to_path` (opentype.js) and b1rdmania's "mandatory font exploration before wordmark creation" exist because hand-drawn letterforms are the single most reliable tell of LLM output. Set type with a real font, convert to outlines, then let the model make *parametric* modifications (ligature, cut, notch, custom terminal) rather than drawing the alphabet.
- **Render and look.** kaankiziltug's skill "works best with a model that can view images, because it renders its own drafts to PNG and checks them before showing you anything." Claude Code's `Read` on a PNG gives you this for free.
- **Automated audits before the human sees anything.** kaankiziltug's `svg_audit.py` scores anchor count against a library median (75, p75 155), flags straight edges 0.3–3° off a clean angle, sub-shapes smaller than 1/48 of the canvas, off-centre bounds, and colour count; `preview_sheet.py` renders 96/32/16 px, one-colour, reversed, mirrored, and a competitor "shelf test" (https://github.com/kaankiziltug/logo-design-skill).
- **Diverge, kill, don't blend.** b1rdmania's "convergence problem" write-up is the most honest account of LLM design limits: "every token I generate is a vote for the average… I can generate divergence but I can't evaluate it." Their workflow forces 3–5 structurally different directions, a human kill step, and forbids averaging survivors (https://github.com/b1rdmania/claude-brand-skills).
- **Category-cliché exclusion lists.** kaankiziltug's later batches explicitly ban "chat bubbles, charts or padlocks" for SaaS, "coins, piggy banks or bank blue" for finance, "crosses, pills or heartbeat lines" for health — and use the 1,400-logo reference library to detect look-alikes.
- **Multiple concepts in parallel subagents**, each with a *different* creative direction and the full brief inlined (agents share no context) — neonwatty.

### 1.3 Known failure modes and mitigations

| Failure | Evidence | Mitigation |
|---|---|---|
| Geometry that almost closes / near-miss angles / wobbly curves | Opus 4.7 bicycle frame; `svg_audit` near-miss-angle warnings | Grid DSL; snap to angles; booleans via paper.js; audit script rejects |
| Clip-art / "polished illustration" look, over-detail | Designlab 2026 tests; Uncommon Blue "mush at favicon size" | Idea-first brief; 16 px test gate; anchor-count ceiling; one-colour first |
| Convergence to the mean (same swoosh, same gradient) | b1rdmania; SVGenius style-transfer weakness | Diverge/kill; reference-library look-alike check; banned-motif lists; constrained randomness in construction params |
| Hand-drawn letters, bad kerning | all three skills special-case it | Font outlines via opentype.js/fontTools; kerning from GPOS |
| `<text>` depends on fonts at render time | neonwatty allows system fonts (fragile) | Always outline text in deliverables; keep an editable `.source.svg` with `<text>` |
| Complexity collapse beyond ~a few hundred points | SVGenius finding 2 | Keep marks < 150 anchors; compose from parts |
| Renderer disagreement | Willison Aug 2026 correction | Render with resvg *and* a browser for final QA; avoid filters/masks/`textPath` |
| Reasoning-effort sensitivity | Gemini 3.1/3.7 Flash results | Pin effort per phase (high for concepting, low for mechanical edits) |

---

## 2. Image models for logos (Oct 2026 pricing)

All prices are vendor list prices for 1024² unless noted; third-party resellers quote conflicting numbers and are ignored.

| Model | Vector? | Text rendering | Price / image | API | Notes |
|---|---|---|---|---|---|
| **OpenAI gpt-image-2** (Apr 21 2026) | No | Good for short marks | $8/$30 per M image tokens → ~$0.006 (low) – $0.211 (high) | Yes | gpt-image-2.5 "sunburst"/"flare" now on the pricing page at the same token rates (https://developers.openai.com/api/docs/pricing). gpt-image-1.5 (Dec 2025) $0.009/$0.034/$0.133; gpt-image-1 deprecated Oct 23 2026; gpt-image-1-mini $0.005/$0.011/$0.036. Designlab: weakest first pass, "added extra text we hadn't requested… more like a polished illustration than a logo"; autoregressive → slow. |
| **Google Nano Banana Pro** (Gemini 3 Pro Image, Nov 20 2025) | No | Best-in-class, multilingual (vendor claim; 94 % in one third-party test) | $0.134 (1K/2K), $0.24 (4K); Batch −50 % | Yes | Google's own showcase prompt: "make 8 minimalistic logos… flat vector rendering" — still raster. SynthID watermark on every output. (https://ai.google.dev/gemini-api/docs/pricing) |
| Nano Banana 2 / 2 Lite (Gemini 3.1 Flash Image) | No | Good | $0.045 (0.5K), $0.067 (1K), $0.101 (2K); Lite $0.0336 | Yes | Cheapest capable Google tier. |
| Nano Banana (Gemini 2.5 Flash Image) | No | OK | $0.039 | Yes | |
| Imagen 4 Fast / Ultra | No | Strong | $0.02 / $0.06 | Yes (Vertex/Gemini API) | |
| **Recraft V4 SVG / V4 Pro SVG** | **Yes, native** | Very good for short type | $0.08 / $0.30 (Replicate); V4.1 Vector 80 units ≈ $0.088, V4.1 Pro Vector ≈ $0.33, V4 Styles Vector ≈ $0.055, V4.1 Flash raster $0.0077 | Yes (https://www.recraft.ai/pricing?tab=api) | The only mainstream model emitting real SVG. Caveats: reviewers report "excessive anchor points and redundant" paths (svggenie); "works best for simpler graphic compositions" (MindStudio); **Free plan images are owned by Recraft and not licensed for commercial use.** Vectorize endpoint $0.011. |
| **FLUX.2** pro / flex / max / klein (BFL) | No | flex is "the family's best" for typography; reviews still call text a weakness | $0.03/MP, $0.05–0.06/MP, $0.07/MP, $0.014–0.015/img; Kontext pro $0.04, max $0.08 | Yes | Hex-colour control and JSON prompting are useful for brand colour adherence; only klein-4B is Apache-2.0, dev-32B needs a paid licence to deploy (https://invideo.io/blog/flux-ai-image-generator/). |
| **Ideogram 3.0** (Turbo/Default/Quality); 4.0 appearing on Together | No | Best for typography-led marks; has a dedicated "Logo" mode | $0.03 / $0.06 / $0.10 | Yes | Designlab: handled iteration "extremely well". Raster only. |
| Adobe Firefly Image 5 / Text-to-Vector | Web app only | Good | Subscription | **API is raster-only** — community feature request for SVG parity still open (https://community.adobe.com/feature-requests-405/feature-request-firefly-api-parity-for-text-to-vector-svg-output-1479544) | Text-to-vector exports SVG (beta) in the browser; not automatable. |
| Midjourney V7 / V8.x | No | Lags Ideogram/GPT | Subscription (~$0.30–0.60/img effective) | **No official API** (only Discord wrappers) | Best for mood/illustration, not marks. |
| Stable Diffusion 3.5 | No | Weak (~65 % in third-party tests) | ~$0.03 (Replicate) or self-host | Yes | |
| Qwen-Image (20B, Apache-2.0) / Qwen-Image 2.0 | No | Best *open* text-in-image (esp. CJK) | self-host; 2.0 is closed/API-only | Partial | https://huggingface.co/Qwen/Qwen-Image |

**The structural problem.** Designlab's May 2026 re-test (https://designlab.com/blog/top-best-ai-logo-generators-a-review) is blunt: with the partial exception of Recraft, image models "don't produce logos. They produce pictures of logos." A real logo must be scalable, come in variants, be editable, and be reproducible — so the raster path always adds: vectorize → clean anchor points → rebuild lockups → export. Their recommendation ladder: Recraft first, Ideogram for typography, GPT Image/Nano Banana for conversational ideation, then "take it into Recraft to generate a clean vector version, or bring in a designer."

**What the "AI logo" cliché looks like** (synthesised from Uncommon Blue, Jul 2026, https://uncommonblue.co.uk/blog/5-signs-your-branding-looks-ai-generated-and-why-customers-notice; Designlab; b1rdmania): a mark that is either "so over-detailed it turns to mush the moment it's shrunk to a favicon" or "a bland, perfectly symmetrical swoosh that could belong to literally any company"; glossy, gradient-heavy illustration style; 3D bevels and rendered highlights; near-perfect symmetry; stray generated text; the same trendy geometric sans, soft purple–blue gradient, and "safe minimalism" across unrelated brands ("Inter, Roboto, purple gradients on white"); nothing in the system quite matching anything else. The common thread: "decoration where there should be an idea."

---

## 3. Vectorization (raster → vector)

| Tool | Type | Cost | Quality notes | Logo suitability |
|---|---|---|---|---|
| **potrace 1.16** (`brew install potrace`; not installed locally) | B/W bitmap tracer; optimal-polygon search | Free | Smoothest curves for monochrome shapes; one colour per pass | Excellent for one-colour marks and letterforms; run per colour layer |
| **vtracer 0.6.15** (PyPI, Mar 2026, arm64 wheels; Rust; https://github.com/visioncortex/vtracer) | Colour tracer, stacking strategy, no holes | Free | More compact than Illustrator Image Trace; Python API with `palette`, `mode="polygon"`, watershed, adaptive threshold | Good for flat colour marks; still produces more nodes than hand-drawn |
| AutoTrace | Legacy colour tracer | Free | StarVector's table: AutoTrace 0.942, Potrace 0.898, VTracer 0.954 image-similarity on SVG-Stack (fidelity, not editability) | Superseded by vtracer |
| **vectorizer.ai API** | Deep-learning tracer, "Vector Graph" corner optimisation | 50 credits $9.99/mo ($0.20 each) sliding to $0.05 at 100k; watermarked previews 0.2 credit; SVG/PDF/EPS/DXF (https://vectorizer.ai/pricing) | Best automatic results on logos per most roundups; configurable curve types for software compatibility | Strong, but output still needs node review; subscription model |
| **Recraft vectorize** | API endpoint | $0.011 (10 units) | Marketing calls it SOTA; same anchor-bloat complaints as its SVG generator | Cheapest decent option; good for sketches → clean-up pass |
| Adobe Illustrator Image Trace | Desktop | CC subscription | Designlab: "auto-vectorization is never perfect… nudge anchor points, smooth a few curves" | Not scriptable from Node without Illustrator |
| PerfectVector / Trazor / "node-soup" start-ups | Web | Credits / free | PerfectVector shows 522 vs 59 nodes for the same art; claims are vendor's own (https://perfectvector.com/blog/best-ai-vectorizers-2026) | Unproven at scale |

Practical rule from every source: **vectorization is only acceptable for flat, illustrative art, and never for type** — text in a traced image must be discarded and re-set from the real font. A Reddit builder summed up the field: "every tracer gave me node soup." Plan a post-trace simplification pass (paper.js `simplify`, svgo `convertPathData` with limited precision, or the audit's anchor ceiling) and expect human cleanup for anything client-facing.

---

## 4. Toolchain for Node 25 / Python on macOS Apple Silicon

Versions and publish dates verified against the registries on 2026-10-02 (`node --version` → v25.9.0; Homebrew 6.0.3).

### Rendering SVG → PNG
- **`@resvg/resvg-js` 2.6.2** (Jan 2026; prebuilt `@resvg/resvg-js-darwin-arm64`, no native build). Primary rasteriser. Options: `font.fontFiles: [...]`, `font.fontDirs`, `font.loadSystemFonts: false` (faster, deterministic), `font.defaultFontFamily`, `fitTo`. resvg historically passes more of the W3C SVG suite than librsvg/Inkscape. Gotchas: font **weight** matching can be wrong when several faces share a family name (issue #289 — load exactly the faces you reference); `loadSystemFonts: true` makes output machine-dependent; no CSS `@font-face` from URLs; filters/`textPath` support is partial. `@resvg/resvg-wasm` 2.6.2 is a drop-in without native code.
- **`sharp` 0.35.5** (Sep 2026; prebuilt darwin-arm64 with libvips 1.3.4). Use for resizing, WebP, compositing social cards, and ICO prep — not as the SVG renderer: libvips renders SVG via librsvg and resolves fonts through fontconfig, so text depends on installed system fonts (`FONTCONFIG_FILE`/`FONTCONFIG_PATH` env or `fc-cache`), and one write-up documents sharp failing in production when the libvips SVG loader was unavailable, fixed by switching to resvg (https://sahansera.dev/replacing-sharp-with-wasm-hidden-svg-dependency/). Render with resvg at 2–4× then downsample in sharp for crisp small sizes.
- **`playwright` 1.63.0 / `puppeteer` 25.12.0** — browser-parity rendering for the final QA pass and for the preview/compare sheets (`@font-face` from local files works; `page.screenshot`). Slower and heavier; use once per concept, not per iteration.
- Python: **`cairosvg` 2.9.1** (needs `brew install cairo`; on arm64 set `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` if cairocffi cannot find `libcairo`), **`resvg-py` 0.5.0** (Aug 2026, arm64 wheels), `skia-python` 144. `rsvg-convert` via `brew install librsvg` is what b1rdmania's skill uses.

### Text → outlines
- **`opentype.js` 2.0.0** (May 2026 — the long-awaited 2.0 with variable-font and colour-font support). `font.getPath(text, x, y, size, {kerning: true, features})` → `toPathData(2)`. Parses TTF/OTF/WOFF; **not WOFF2** (so prefer TTF downloads, see fonts below). Kerning via GPOS/kern; full OpenType shaping (contextual ligatures, Arabic) is limited.
- **`fontkit` 2.0.4** (Sep 2026): better shaping (`font.layout(text)` applies GSUB/GPOS), reads WOFF2, variable instances via `font.getVariation({wght: 600})`; glyph `path.toSVG()`. Used by pdfkit. Use fontkit when you need ligatures/variable axes; opentype.js when you want simplicity.
- Python **`fonttools` 4.66.1** (Sep 2026): `fontTools.pens.svgPathPen.SVGPathPen`, `varLib.instancer` to pin a variable font, `subset` to ship a tiny font with the editable source. `text-to-svg` (npm) is from 2022 — skip.
- `satori` 0.35.0 (Vercel; Oct 2026) turns JSX/CSS into SVG with text already outlined — a pragmatic layout engine for wordmark + tagline lockups and social cards.

### Optimise, favicons, PDF
- **`svgo` 4.1.0** (Aug 2026; ESM). Keep `removeViewBox: false`, `cleanupIds: false` for the editable source (preserve `#icon`, `#wordmark` groups); run a stricter profile for distributed SVGs (`convertPathData` with `floatPrecision: 2`, `mergePaths`, `convertShapeToPath` off if you want editable primitives).
- **`png-to-ico` 3.0.2** (Jul 2026) builds multi-size ICO from PNGs (16/32/48). `to-ico` and `sharp-ico` are unmaintained (2022). Modern favicon set: `favicon.svg` + `favicon.ico` (16/32/48) + `apple-touch-icon.png` 180 + manifest 192/512 (+ maskable).
- PDF: **`svg2pdf.js` 2.8.1** (Aug 2026) is browser-oriented (jsPDF) and needs jsdom in Node; `pdfkit` 0.20.2 + `svg-to-pdfkit` 0.1.8 (2022) is dated. The cleanest vector-preserving routes are `cairosvg --format pdf` or `rsvg-convert -f pdf`; Inkscape CLI adds EPS. Outline text before export regardless of route.

### Fonts programmatically
- **Google Fonts Developer API** `https://www.googleapis.com/webfonts/v1/webfonts?key=…&family=Inter` returns direct TTF URLs per variant (official; needs a free API key).
- **google/fonts GitHub** raw files: `https://raw.githubusercontent.com/google/fonts/main/ofl/<family>/<Family>[wght].ttf` plus `OFL.txt` — ship the licence with the deliverable.
- **google-webfonts-helper** (https://gwfh.mranftl.com/, OSS: https://github.com/majodev/google-webfonts-helper): `GET /api/fonts/<id>?download=zip&subsets=latin&formats=ttf` — convenient but a community service.
- **`@fontsource/<family>` 5.3.0 / `@fontsource-variable/<family>` 5.3.0** (Jul 2026): npm-installable, but ships **woff2/woff only** — fine for previews in a browser, not for opentype.js (use fontkit, or the TTF routes above).

### Colour
- **`culori` 4.0.2** (Apr 2026): OKLCH palettes, gamut mapping, `wcagContrast`, deltaE — the workhorse.
- **`colorjs.io` 0.7.1** (Jul 2026; still 0.x API): CSS Color 4 parity, has APCA and WCAG contrast built in.
- **`apca-w3` 0.1.9** (2022, reference implementation of APCA; stable but unmaintained). Use WCAG 2.x for compliance claims, APCA for small-type legibility judgement.

### Geometry
- **`paper` 0.12.18** (Jul 2024; `paper-jsdom` for Node): curve-aware booleans (`unite/subtract/intersect/exclude`), `simplify`, `flatten`, offsets via community plugins. Last release two years ago but stable — the only JS library that does booleans on Béziers, not polygons.
- **`polygon-clipping` 0.15.7** (Dec 2023) and **`martinez-polygon-clipping` 0.9.0** (Sep 2026): robust polygon booleans; require flattening curves first, then re-fitting (`fitCurve`/paper `simplify`). Keep as fallback.
- **`svgpath` 2.6.0** (2022, stable): parse/transform/absolutise/`unshort` path data. **`svg-path-properties` 2.1.0** (Aug 2026): length, point-at-length, tangents. `bezier-js` 6.1.4 for arc/offset maths. `@svgdotjs/svg.js` 3.2.8 needs a DOM (`svgdom`) — optional.
- Canvas for raster measurements: **`@napi-rs/canvas` 1.0.10** (Oct 2026; Skia, prebuilt arm64) over `canvas` 3.2.3 (cairo build).

### Image comparison
- **`pixelmatch` 7.2.0** (Apr 2026) + `pngjs`: diff two renders (regression tests between iterations; "did the change touch anything else?"). Use SSIM (`ssim.js`) if you need perceptual scores for the LLM judge.

### Local environment notes
`potrace`, `vtracer`, `inkscape`, `rsvg-convert`, and `magick` are **not** installed on this machine; `brew install potrace librsvg` and `pip install vtracer` (wheel) or `cargo install vtracer` cover the optional tracing path. `pypotrace` has no arm64 wheel; use the potrace CLI.

---

## 5. Generative and dynamic identities

- **MIT Media Lab (2011, TheGreenEyl + E Roon Kang)** — a Processing program places three "spotlight" shapes on a 4×4 grid, yielding 40,000 logo permutations × 12 colourways (~480k); each person at the Lab claimed one for cards and web (https://www.creativeapplications.net/project/mit-media-lab-identity-processing/, https://eroonkang.com/feature/mit-media-lab-identity). In 2014 Pentagram (Bierut) replaced it with a fixed glyph system "to ensure unity across diverse groups" — the canonical lesson that algorithmic identities need governance and tend to be simplified later (https://www.media.mit.edu/posts/MLBrandPortal/).
- **OCAD University (Bruce Mau Design, 2011)** — black-and-white modular "windows" from Will Alsop's Sharp Centre; each year graduating medal winners design logos inside the frame, building "a living library of identities" (https://www.brucemaudesign.com/work/ocadu).
- **Visit Nordkyn (Neue Design Studio, 2010)** — a snowflake-derived mark whose geometry and colour are driven by live wind direction and temperature from the Norwegian Meteorological Institute; a public logo generator still runs (https://visitnordkyn.com/vngenerator/; D&AD archive https://www.dandad.org/work/d-ad-awards-archive/where-nature-rules).
- **Casa da Música (Sagmeister, 2007)** — the Koolhaas building's 17 faces become a wireframe mark; a "logo generator" samples colours from any image (a performer's photo, a poster) and recolours the facets — MoMA holds the generator in its collection (https://sagmeister.com/work/casa-da-musica/, https://www.moma.org/collection/works/145254).
- **AOL (Wolff Olins, 2009)** — the wordmark is a fixed, reversed-out element over ever-changing artwork; the identity "as a platform for content" rather than a logo.
- **Brasília** appears in dynamic-identity roundups, but I could not locate a primary source in this pass; treat as unverified.

**Does an algorithmic approach suit a code-driven generator?** Yes for *construction*, rarely for *delivery*. Every case above is a small rule system (a grid, a frame, a shape family, a colour sampler) plus a data or human input — exactly what code does well, and a generator that defines marks as parameters on a grid can trivially emit families (icon, lockups, patterns, motion). But the MIT/Pentagram arc shows most organisations ultimately need one fixed, governable mark; dynamic systems succeed for institutions with the design capacity to run them. Recommendation: use generative/parametric construction internally to explore and to derive the asset system, and offer "dynamic identity" only as an explicit, opt-in output.

---

## 6. Existing AI logo makers

| Product | How it actually works | Price points | Criticism |
|---|---|---|---|
| **Looka** | Template layouts + font pairings + symbol library, colour rules; "AI" is largely combinatorial ranking | downloads from ~$20; brand kit $80+ (Designlab); Looka quotes $65–96 (LogoLoom) | "Heavily templated… noticeable ceiling on originality"; "prioritizes safe branding choices… formula-driven" (Designlab May 2026; Medium hands-on Jun 2026) |
| **Brandmark** | "Hand-crafted fonts & templates" plus a generative-AI icon option (its own site) | $25 one-off to $175 | Narrow preset "colour profiles" (organic → mostly brown); flat editing controls |
| **Tailor Brands** | Template wizard inside an LLC/branding bundle | ~$10/mo | "A suggested design looked nearly identical to what the platform generated two years ago" |
| **Logo.com** | Template-driven, icon library | free first download; files from ~$8 | Strongest of the old guard in Designlab's re-test, still template-bound |
| **Design.com** | "World's largest logo library" + AI ranking, IP/originality checks (vendor claims) | subscription | Marketing-heavy; still library recombination |
| **Canva / Wix / Hatchful / Namecheap** | Template + font + icon combinatorics; Canva now adds image-model generation | free to ~$15/mo | Designlab: Canva is now "genuinely competent" because it is where non-designers already work |
| **Logo Diffusion** | Stable-Diffusion-based generation (sketch/ControlNet-style conditioning, 3D styles) + vectorization jobs | credits | Trustpilot 3.9/5 on 11 reviews — thin signal |
| **Krea** | Real-time general image generation; not logo-specific | subscription | n/a |

Designlab's overall verdict: the dedicated tools "haven't gotten worse — the category they belonged to stopped being the right category"; Recraft V4 is "currently the closest thing to a full replacement," and the honest workflow is image model → vector tool → designer finish.

---

## 7. Open-source agentic logo/brand repos (2024–2026)

- **kaankiziltug/logo-design-skill** (https://github.com/kaankiziltug/logo-design-skill; 89 forks, 23 commits, last commit 30 Sep 2026; trending "The New 100 #14"; Claude Code plugin + Agent Skills format for Gemini CLI/Codex/Cursor). The most complete: brief → library research → 8–12 one-liners → 3 SVG builds → audit/16 px/one-colour/shelf test → **hard checkpoint** → full kit (colour, lockups, presentation board with industry mockups, favicon/app-icon/web-manifest, guidelines). Dependency-free Python tools; 1,400+ classified SVG logos (median 2 colours; 75 % ≤ 3; gradients in 19 %; 141 "exemplary"). Got right: principles-first references (optical corrections, mark-type decision guide), measurable audits, the checkpoint discipline, 28 end-to-end examples. Weaknesses: Python stdlib tools render through "whatever is available" (cairosvg/rsvg/Inkscape/Chrome/Quick Look) so output is environment-dependent; no explicit text-to-outline pipeline visible in the README; large library makes the skill heavy to install.
- **neonwatty/logo-designer-skill** (https://github.com/neonwatty/logo-designer-skill; 125★, v1.0.0 May 2026, MIT). Interview → 3–5 parallel subagent concepts → preview.html with light/dark + favicon strip → refine → export PNGs 16–2048 via `export.sh`. Got right: structured SVG conventions (viewBox-only, named groups, flat fills, ≥6-unit strokes), parallel divergence, an optional canvas hand-off (lineagehq/lineage-logo) for human nudging. Got wrong: allows `<text>` with system fonts (non-portable), no audit, export depends on an external renderer, no vector deliverables beyond the raw SVG, 37 iterations for the author's first logo (https://neonwatty.com/posts/logo-designer-skill-claude-code/).
- **mcpware/logoloom** (https://github.com/mcpware/logoloom; 45★, v1.0.0 Mar 2026, 9 commits, inactive since). MCP server with four tools — `text_to_path` (opentype.js), `optimize_svg` (SVGO), `export_brand_kit` (sharp: 31 files incl. ICO, WebP, OG/GitHub/Twitter images, BRAND.md), `image_to_svg` (vtracer/potrace). Got right: the *post-processing* half (outline text, optimise, export matrix) packaged as tools the model can call. Got wrong: almost no design guidance; dormant.
- **b1rdmania/claude-brand-skills** (https://github.com/b1rdmania/claude-brand-skills; 23★, v2.0 Feb 2026). 8-phase brand system (emotive narrative → discovery → visual direction via image models → mark via bitmap tracing *or* hand-coded SVG → wordmark with mandatory font exploration → design system → evolutionary composition → DESIGN.md → packaging). Got right: naming the convergence problem and designing around it (diverge/kill/mutate, human filter, bitmap tracing "lets me work with images I can evaluate instead of SVG code I can't see"); multi-model image CLI (nano-banana-pro, Flux, Replicate, OpenAI). Costly in practice: Compost.fi took "~2,600 API calls… 26 logo iterations."
- Also: `Anil-matcha/Open-AI-Design-Agent` (image-model brand-kit agent, Lovart alternative), `longcipher/brand-kit`, `lineagehq/lineage-logo` (shared canvas for agent + human fine-tuning), SVGMaker MCP (cloud credits). Anthropic's own **Claude Design** (Apr 17 2026, Anthropic Labs, Opus 4.7; design-system ingestion, exports to Canva/PDF/PPTX/HTML; https://www.anthropic.com/news/claude-design-anthropic-labs) is a prototype/slides tool, not a vector logo tool, but confirms the "agentic loop with visual review" direction.

---

## 8. Recommended architecture options

### (a) Claude-authored SVG with a render → critique → revise loop
- **Logo quality:** strong for the mark types that dominate real identities — abstract/geometric symbols, letterforms, monograms, wordmarks (kaankiziltug's library: abstract 24 %, combination 21 %, letterform 15 %, wordmark 10 %). Weak for pictorial/mascot/organic marks where freehand curves matter.
- **Editability:** best possible — clean primitives, named groups, parametric construction, text kept as `<text>` in the source and outlined only on export.
- **Cost (Claude pricing, Oct 2026):** Opus 5.5 $4/$20 per MTok, Sonnet 5.5 $2/$10, Haiku 4.5 $1/$5 (https://docs.claude.com). A 1024² render is ~1.4k input tokens; a logo SVG is 1–3k tokens. Ten concept→render→critique rounds ≈ 60–120k tokens ≈ **$0.60–$2.00 per concept on Opus 5.5**, half on Sonnet 5.5. Negligible tooling cost.
- **Reliability:** deterministic pipeline, fully local except the model; risks are convergence/cliché, geometric near-misses, and complexity collapse — all of which the audits, grid DSL, and font outlines mitigate. Legally clean (no third-party model licences on the asset).

### (b) Image-model generation + vectorization
- **Logo quality:** highest first-impression quality for illustrative/pictorial marks; Nano Banana Pro/Ideogram/GPT Image render legible type, but it is *rendered*, not set — every source agrees the text must be discarded and re-set.
- **Editability:** poor. Traced output is node soup; lockup variants must be rebuilt by hand; reproducibility across months is weak. Recraft V4 SVG is the exception, with anchor-bloat and "simpler compositions" caveats, and its free tier forbids commercial use.
- **Cost:** cheap per image ($0.03–$0.30) plus $0.011 (Recraft) to $0.05–0.20 (vectorizer.ai) per trace — but b1rdmania's 2,600 calls per brand shows exploration volume dominates.
- **Reliability:** non-deterministic; SynthID/C2PA watermarks; prompt adherence drifts; no official Midjourney API; Firefly vector not in the API.

### (c) Hybrid (recommended)
Use (a) as the spine and treat image models as optional *instruments*:
1. **Brief → direction** (Claude; constrained by cliché exclusion lists and a reference library look-alike check).
2. **Mood/reference** (optional): Nano Banana 2 or FLUX.2 klein for cheap mood boards; never shipped.
3. **Pictorial candidates** (optional): Recraft V4 SVG or Ideogram → potrace/vtracer → paper.js `simplify` → Claude *rebuilds* the silhouette as constructed geometry on the grid. The image is a sketch, not the asset.
4. **Mark construction**: Claude writes a small JSON/DSL (grid, primitives, booleans, optical corrections) that code compiles to SVG; type set from real Google Fonts via opentype.js/fontkit with kerning; parametric letter modifications only.
5. **Loop**: resvg render at 512/64/32/16, one-colour and reversed → `svg_audit`-style checks (anchor count, near-miss angles, tiny details, centring, contrast via culori/APCA) → Claude critiques the PNGs → revise. Outcome-only judging (VFLM finding); cap iterations; Haiku 4.5 as a cheap parallel judge, Opus 5.5 for construction.
6. **Checkpoint**: 3–5 structurally different concepts on one sheet; human picks; no blending.
7. **Kit**: svgo'd distributable SVGs (outlined text), editable source SVG + subset font, PNG matrix (sharp), ICO (png-to-ico), favicon set, PDF (cairosvg/rsvg-convert), social cards (satori or sharp composite), BRAND.md with OKLCH palette and contrast tables, optional parametric "dynamic" variants.

**Trade-off summary:** (a) wins on editability, cost predictability, and avoiding the AI look; (b) wins only when the brief genuinely needs an illustrative mark; (c) gets both at the cost of two extra integrations and a licensing review per image model. Reliability ranking: (a) > (c) > (b).

### Concrete toolchain (pin these)
**Node 25.9 (primary):** `@resvg/resvg-js@2.6.2`, `sharp@0.35.5`, `opentype.js@2.0.0` (+ `fontkit@2.0.4` for WOFF2/variable/shaping), `svgo@4.1.0`, `png-to-ico@3.0.2`, `svgpath@2.6.0`, `svg-path-properties@2.1.0`, `paper@0.12.18` + `paper-jsdom@0.12.18`, `polygon-clipping@0.15.7` (fallback), `culori@4.0.2`, `apca-w3@0.1.9` (or `colorjs.io@0.7.1`), `pixelmatch@7.2.0` + `pngjs`, `playwright@1.63.0` (final QA + preview sheets), `satori@0.35.0` (lockups/social cards, optional), `@napi-rs/canvas@1.0.10` (optional raster maths). Fonts from the Google Fonts Developer API or google/fonts raw TTFs, cached under `./fonts/<family>/` with the OFL file.

**Python 3 (optional sidecar):** `cairosvg==2.9.1` (PDF/EPS; `brew install cairo`), `fonttools==4.66.1` (subset/instance variable fonts), `vtracer==0.6.15`, `resvg-py==0.5.0`; `brew install potrace librsvg` for `potrace` 1.16 and `rsvg-convert`.

**External APIs (optional, feature-flagged):** Recraft API (V4 SVG $0.08; vectorize $0.011), Gemini API (Nano Banana 2 $0.067 / Pro $0.134), Ideogram 3.0 ($0.03–0.10). Keep all image-model outputs out of the deliverable path unless rebuilt as constructed vectors.
