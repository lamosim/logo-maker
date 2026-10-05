# Logo Maker: design spec

Date: 2026-10-05. Status: approved in conversation, pending written review.

## 1. Purpose

A Claude Code workflow that lives in this folder. The owner opens a terminal here, runs `claude`, and is guided from "I have a venture" to a production-ready logo package for it. The result must be thought out (derived from an explicit strategy), relevant (every visual choice traces to that strategy and to the evidence in `docs/research/`), and ready to go (every file a small company needs, with usage rules).

Success looks like this:

- A new brand goes from first question to a verified package in one or more sessions, resumable at any phase.
- Every mark is a parametric vector built from real geometry and real font outlines, never a traced picture.
- Nothing reaches the owner that failed an automated audit or a scorecard gate; nothing is shown on a blank page.
- The package verifies against a manifest: every expected file exists, has the right dimensions, and is listed in `README.md`.

## 2. Decisions already made

| Decision | Choice | Why |
|---|---|---|
| Rendering approach | Constructed vector: Claude writes construction code; a CLI compiles, renders, audits, exports | Research 04: image models make "pictures of logos"; LLM SVG is strong for geometric, letterform and wordmark marks when given a grid, real fonts and a render-critique loop |
| Brands in scope | New ventures, some unnamed | Owner's answer. No rebrand or equity-audit flow in this version |
| Stack | Python 3.12 managed by uv; CLI for deterministic steps; a Claude Code skill for judgment | Matches the owner's tote-label project conventions |
| Renderer | Installed Google Chrome via Playwright, `channel="chrome"`, never `playwright install` | Same convention; every SVG is paths-only so rendering is deterministic |
| Geometry engine | skia-python for booleans, stroking and path maths | Verified on this Mac: `skia.Op`, `Paint.getFillPath` |
| Type | fontTools for outlines and variable-font instancing, uharfbuzz for shaping and kerning | Verified; hand-drawn letters are the most reliable tell of LLM output |
| Colour | coloraide for OKLCH, WCAG contrast, colour-vision-deficiency simulation; APCA computed in-house | Verified |
| Print | reportlab vector PDF in RGB and CMYK, plus legacy EPS | Chrome PDFs are RGB only |
| Image-model APIs | None in this version | Owner's choice; an `inspiration/` folder lets Claude view any reference images the owner drops in |

## 3. Experience

### 3.1 Session flow

1. Owner runs `claude` in this folder. `CLAUDE.md` routes any logo, brand or naming request to the `logo` skill.
2. The skill runs `logomaker brand list` and greets with existing brands and their phase, offering "new brand" or "continue <brand>".
3. Phases run in order with a gate at the end of each. Claude asks one question at a time, writes back its understanding before designing, and records every decision in the brand's state file.
4. Anything visual is rendered by the CLI and opened in the browser with `open`. Claude reads every render itself before showing it.
5. The owner may stop at any time. The next session resumes at the recorded phase.
6. "Done" is `brands/<slug>/package/` verified against its manifest, plus `BRAND.md`, `brand-sheet.pdf` and `rationale.md`.

### 3.2 Phases, artifacts and gates

| # | Phase | Claude does | CLI does | Artifact | Gate |
|---|---|---|---|---|---|
| 0 | Intake | Adaptive interview (section 4.1); infers archetype and personality; writes back the brief | `brand new` | `brief.md`, `brief.json` | Owner confirms the brief |
| 1 | Naming (only if unnamed) | Generates 15 to 25 candidates across descriptive, evocative and invented types with sound-symbolism and letterform notes; runs a web trademark knock-out, flagged as not legal clearance | `names analyze`, `names check` (domains, GitHub handle) | `naming.md` | Owner picks a name |
| 2 | Strategy | Writes positioning, archetype, personality scores, the one idea, the adjective ladder, category audit, feature targets, logo-type decision, constraints | none | `strategy.md`, `strategy.json` | Owner approves |
| 3 | Territories | Defines 2 or 3 visual territories as JSON | `fonts fetch`, `sheet territories` | `territories/territories.json`, `territories/board.html`, `board.png` | Owner picks one |
| 4 | Concepts | Lists 12 to 20 one-line ideas; strikes clichés; builds 5 to 8 structurally different directions as concept modules, black only; revises within caps; kills failures; scores survivors; presents 3 to 5 | `concept run`, `sheet concepts` | `concepts/NN-slug/` (module, SVGs, audits, critique sheets, `critique.md`), `sheets/concepts.html` | Owner picks one; no blending |
| 5 | Refinement | Optical corrections; small tiers redrawn; wordmark set with one owned quirk; lockups; then colour; reversed variants designed; unintended-readings pass; look-alike and trademark knock-out | `concept run`, `color check`, `sheet refine` | `final/` (module, params, `tokens.json`, `knockout.md`), `sheets/refine-N.html` | Owner approves after 1 to 3 rounds |
| 6 | Package | Writes `rationale.md`; runs the package test | `package build`, `package verify`, `brand advance --to done` | `package/`, `BRAND.md`, `brand-sheet.pdf` | Owner opens the folder; registry updated |

### 3.3 Conversation rules the skill enforces

- Strategy before any drawing. Silhouette in black before any colour. Knock-out search before presenting.
- One question per message. Multiple-choice where it helps. Write back understanding at the end of intake and wait.
- Never present a concept that failed a hard audit or scored below 4 on the three gating criteria (appropriate, legible, simple).
- Never show a mark alone on a blank page; always through a sheet with mockups.
- Before the first concept presentation, use the Collins rule 95 preface: new ideas are fragile; before saying what you dislike, find something you like in each.
- Never blend concepts. Pick one; a detail from another may be noted as a steal and recorded as a decision.
- Caps: 4 revise rounds per concept in phase 4; 3 refinement rounds in phase 5. If stuck, say so and offer to return to concepts.
- Distinguish unfamiliarity from a real flaw: on a negative first reaction, ask one probing question (what reads wrong, at what size, in which mockup) before changing anything.
- Rationale is one paragraph, written for the owner, without the word "represents", without construction diagrams, ratios or the golden ratio.
- When `brands/<slug>/inspiration/` contains images, view them during strategy and territories and say what was taken from them.
- Trademark and look-alike checks are web searches by Claude and are always labelled "knock-out only, not legal clearance".

## 4. Workflow detail

### 4.1 Intake

Core questions (always asked, in this order, one per message; skip any already answered):

1. What does the business do, for whom, and what problem does it solve?
2. If there were one idea the logo could carry, what would it be? (Haviv's forcing question)
3. Finish truthfully: "We are the only ___ that ___ for ___ who ___."
4. Three to five adjectives, each with its unwanted neighbour ("premium but not aloof").
5. If the brand were a person at a dinner party, who are they and how do they talk?
6. Three brands you admire visually and precisely why; any you dislike and why.
7. Where will the mark live most? Rank the top three of: app icon, website header, social avatar, packaging, signage, merch, pitch decks, print.
8. The smallest size and harshest environment it must survive.
9. Colours you want, colours you forbid, colours your category has already claimed.
10. Symbols, metaphors or tropes that are off limits. Any cultural or language constraints.
11. The name: how it is written, pronounced, its story, any tagline. Or: it needs a name.

Optional questions, asked only when the answers above leave a gap: twelve-month goals, nearest competitors by behaviour, sub-brands or product lines expected, markets and scripts, who else decides.

Claude infers and writes back: primary and secondary archetype, Aaker personality scores (sincerity, excitement, competence, sophistication, ruggedness, each 0 to 1), industry tag for the cliché blacklist, and the three ranked surfaces. `brief.json` holds the structured answers; `brief.md` is the readable write-back.

### 4.2 Naming

Only when `brief.json.needs_name` is true.

- Claude generates candidates using `reference/naming.md`: at least five each of descriptive, evocative and invented; each with a one-line meaning, a sound profile (front or back vowels, stops or fricatives), a letterform note (length, initial letter class, double letters, ligature chances, L-flourish warning), and a fit score against the personality profile.
- `logomaker names analyze <name>` returns deterministic linguistic features for each candidate.
- `logomaker names check <name>` returns domain status for `.com .co .io .ai .app .dev` over RDAP with `whois` fallback, and GitHub user and organisation availability. Statuses are `available`, `registered`, `unknown`.
- Claude runs a web knock-out (USPTO search, EUIPO or WIPO where reachable, general web and app stores) for the top five and records results in `naming.md` with the caveat.
- The owner picks. Claude runs `logomaker brand rename <slug> --name <Name>`; the slug is kept.

### 4.3 Strategy

`strategy.md` sections, all required:

1. Positioning: the "only" statement and a Moore-format positioning statement.
2. Archetype: primary and secondary with the visual cheat-sheet row for each.
3. Personality: Aaker scores with one sentence each.
4. The one idea: one sentence.
5. Adjective ladder: adjective, visual principle, test. Example: "approachable" to "rounded terminals, open counters" to "no corner radius under 2 px at 32 px".
6. Category audit: the category's visual uniform (type class, colours, motifs) from `reference/cliches.md` and a web look at the five nearest competitors; what to avoid and what is free to own.
7. Feature targets from `reference/evidence-rules.md`: shape (round to angular, 0 to 1), symmetry dose (0 to 1, tied to excitement), complexity (low, moderate, high, tied to exposure), stroke weight (light to heavy), hue family and saturation and lightness targets, typeface class, frame (open, framed, badge), dynamism (static to implied motion), name-sound congruence note, descriptive cue (yes or no, with the negative-category exception).
8. Logo-type decision via `reference/logo-types.md`: wordmark-led combination by default; justify any other.
9. Constraints: minimum sizes per tier, one-colour requirement, surfaces, scripts.

`strategy.json` carries the numeric targets so audits and the kit can use them.

### 4.4 Territories

`territories.json` holds 2 or 3 entries:

```json
{"slug": "forge", "name": "Forge",
 "embraces": ["dense", "industrial", "warm"], "rejects": ["pastel", "thin lines"],
 "fonts": [{"family": "Sora", "weight": 700}, {"family": "Archivo", "weight": 600}, {"family": "Bricolage Grotesque", "weight": 700}],
 "palette": [{"hex": "#1f1b18", "name": "Coal"}, {"hex": "#e8572a", "name": "Ember"}],
 "shapes": {"corner": 0.15, "stroke": 0.12, "angularity": 0.8, "symmetry": 0.7}}
```

`logomaker sheet territories <slug>` fetches any missing fonts, renders the name in each font at three sizes, palette chips with hex and OKLCH, six abstract shape specimens driven by `shapes` (ring, chevron, rounded square, monoline loop, stacked bars, the name's initial as a glyph), and the embraces and rejects lists, then writes `board.html` and `board.png` and opens the HTML.

### 4.5 Concepts

1. Claude writes 12 to 20 one-line ideas in `concepts/ideas.md`, each tagged with motifs. Any motif on the industry blacklist is struck unless the brief made it the strategy, and then it must be twisted and justified.
2. Claude selects 5 to 8 structurally different directions (different logo type or construction logic, not variations) and creates `concepts/NN-slug/concept.py` for each. For 4 or more directions Claude may dispatch parallel subagents, each given `brief.md`, `strategy.md`, the chosen territory, and `reference/kit-api.md`, returning only a concept module.
3. `logomaker concept run <slug> <NN-slug> --round 1` builds all tiers, audits, renders the critique sheet.
4. Claude reads `renders/round-1/critique.png`, writes a scorecard entry in `critique.md`, and either revises the module (next round) or kills the concept with a reason. Hard audit failures must be fixed or the concept killed.
5. Survivors with gating scores of 4 or more are listed in `logomaker sheet concepts <slug> --concepts a,b,c`, which writes `sheets/concepts.html` and `.png` and opens it.
6. The owner picks one. The choice and the "what I liked in each" notes are recorded with `brand decide`.

Concepts are black-only in this phase. Colour roles may be declared in the module but the critique sheet renders black on white and white on black until phase 5.

### 4.6 Refinement

Order of work, each step a module edit followed by `concept run` on `final/`:

1. Optical corrections: overshoot on round and pointed forms, stroke compensation, optical centring, as `reference/craft.md` describes.
2. Small tiers: `small` (24 to 64 px) and `favicon` (16 to 32 px) redrawn through parameter overrides: thicker strokes, opened counters, dropped detail.
3. Wordmark: family and weight chosen from the territory; shaped with kerning; tracking set; at most one owned quirk (a ligature, a cut, a notch, a terminal) applied parametrically; never a hand-drawn letter. Letter identity must survive the quirk (the Kia rule).
4. Lockups: horizontal and stacked with a declared gap in `x` units; the primary lockup chosen from the top surface in the brief.
5. Colour: palette built in OKLCH from the feature targets; at most two colours plus ink by default; `tokens.json` written; `logomaker color check` must pass; reversed variants designed as explicit dark-context role mappings, never auto-inverted.
6. Unintended-readings pass: Claude reads the mirrored and rotated panels of the critique sheet and the refine sheet; records findings.
7. Knock-out: Claude searches the web for look-alikes by description and for conflicting marks; `final/knockout.md` records queries and findings with the caveat.
8. `logomaker sheet refine <slug>` renders tiers, lockups, colour variants, the clear-space diagram, the minimum-size ladder and the colour-vision strip; opened for the owner.

### 4.7 Package

- `logomaker package build <slug>` writes everything in section 9 into `package/`, plus `manifest.json`.
- `logomaker package verify <slug>` checks every manifest entry exists with the declared dimensions and non-empty content, and that `README.md` lists every file. Exit 4 on any mismatch.
- Claude writes `rationale.md`, opens `package/` in Finder and `brand-sheet.pdf` in the browser, and runs `brand advance --to done`.

## 5. Architecture

### 5.1 Parts

- **`logomaker` CLI** (`src/logomaker/`): every deterministic step. One JSON object on stdout per command; logs on stderr; exit codes in section 10.
- **`logo` skill** (`.claude/skills/logo/SKILL.md` + `reference/`): the conversation and all judgment: briefs, strategies, territories, concept modules, critiques, rationale.
- **Knowledge base** (`.claude/skills/logo/reference/*.md`): the research distilled into operational documents (section 11). Full reports with sources stay in `docs/research/`.

### 5.2 Folder layout

```
logo-maker/
  CLAUDE.md  README.md  pyproject.toml  uv.lock  .python-version  .gitignore
  .claude/settings.json              # deny reading .env; allow uv run logomaker
  .claude/skills/logo/SKILL.md
  .claude/skills/logo/reference/     # knowledge base, section 11
  src/logomaker/
    cli.py                           # click entry points
    kit/                             # geometry kit: primitives, ops, text, mark, svg, optical
    render.py                        # Chrome via Playwright
    audit.py                         # deterministic checks
    color.py                         # conversions, contrast, CVD, ramps, tokens validation
    sheets.py                        # critique, territories, concepts, refine, brand sheet
    export.py                        # package builder and manifest
    names.py                         # analyze, RDAP, whois, GitHub
    fonts.py                         # catalog, fetch, instancing, cache
    registry.py                      # brand.json state machine, registry index
    schemas.py                       # pydantic models for brief, strategy, territories, tokens, audit, manifest
  templates/
    sheets/                          # critique.html, territories.html, concepts.html, refine.html
    mockups/                         # phone-home, browser-tab, site-header-light, site-header-dark, avatar, card, sign-one-colour
    brand-sheet.html
    readme.md.j2  brand.md.j2  favicon-head.html.j2  manifest.webmanifest.j2
  assets/fonts/
    catalog.json                     # ~60 logo-grade open families with tags
    <family>/                        # fetched TTFs, licence, manifest.json, instances/
  docs/research/                     # five reports
  docs/superpowers/specs/            # this document
  docs/examples/<slug>/              # one completed example brand for the skill to learn from
  brands/<slug>/
    brand.json  brief.md  brief.json  naming.md  strategy.md  strategy.json
    inspiration/                     # owner-supplied reference images, optional
    territories/  concepts/  sheets/  final/  package/
  registry/brands.json  registry/INDEX.md
  tests/
```

### 5.3 State

`brand.json`:

```json
{"slug": "keystone", "name": "Keystone", "needs_name": false,
 "created": "2026-10-05T14:00:00-05:00", "updated": "...",
 "phase": "concepts",
 "industry": "fintech",
 "surfaces": ["app icon", "website header", "social avatar"],
 "primary_lockup": "horizontal",
 "min_sizes": {"horizontal_px": 120, "stacked_px": 160, "mark_px": 24, "favicon_px": 16, "horizontal_mm": 25, "stacked_mm": 25, "mark_mm": 6},
 "territory": "forge", "concept": "03-keystone",
 "fonts": {"wordmark": {"family": "Sora", "weight": 650}},
 "decisions": [{"at": "...", "phase": "concepts", "by": "user", "note": "Picked 03-keystone; liked the counter in 05"}]}
```

Phases: `intake`, `naming`, `strategy`, `territories`, `concepts`, `refinement`, `package`, `done`. `brand advance --to <phase>` checks prerequisites (the artifacts of every earlier phase exist and validate) and refuses with exit 2 otherwise. `registry/brands.json` lists `{slug, name, phase, updated}`; `registry/INDEX.md` is regenerated on every change.

## 6. Mark construction kit

### 6.1 Canvas and units

- Symbol canvas is 1000 by 1000 units, origin at the centre, y up in the kit and flipped on output.
- `snap(v)` rounds to 0.25 units; `snap_angle(a)` rounds to 15 degrees. Primitives snap by default; `free=True` opts out and the audit reports the segment.
- Wordmarks are set in font units and scaled to a cap height given in canvas units.

### 6.2 API (module `logomaker.kit`, re-exported with `from logomaker.kit import *`)

Primitives, all returning `Shape` (a wrapper over `skia.Path`):

- `circle(cx, cy, r)`, `ring(cx, cy, r, width, start=None, end=None)` (degrees, counter-clockwise), `rect(x, y, w, h)`, `rrect(x, y, w, h, radius)`, `polygon(points)`, `regular_polygon(cx, cy, r, n, rotation=0)`, `arc(cx, cy, r, start, end, width, cap="butt"|"round"|"square")`, `line(x1, y1, x2, y2, width, cap)`, `polyline(points, width, cap, join)`, `bezier(points, width=None, closed=False)`, `wedge(cx, cy, r, start, end)`.
- `text(string, family, weight=400, cap_height=200, tracking=0, kern=None, features=("kern","liga"), italic=False)`: shapes with uharfbuzz, outlines with fontTools, returns a `TextShape` (a `Shape` with the attributes `advance`, `cap_height`, `x_height` and `glyph_bounds`). `glyph(char, ...)` returns one letter as a `TextShape`.

Operations:

- `union(*shapes)`, `subtract(a, b)`, `intersect(a, b)`, `xor(a, b)` via `skia.Op`.
- `stroke(shape, width, cap="butt", join="miter", miter_limit=4)` converts an outline or open path to a filled shape via `Paint.getFillPath`.
- `offset(shape, distance)` grows or shrinks via stroke and boolean.
- `translate`, `rotate(shape, degrees, cx=0, cy=0)`, `scale`, `mirror_x`, `mirror_y`, `align(shape, to, edge|center)`, `center(shape)`, `fit(shape, w, h)`.
- Optical helpers: `overshoot(shape, amount=0.015)` scales round and pointed extremes beyond flat extremes; `compensate_stroke(horizontal, vertical)` returns adjusted widths (horizontals thinner, curves thicker, per `reference/craft.md`); `optical_center(shape)` returns the area centroid so parts can be centred by mass rather than bounds.
- Queries: `bounds`, `area`, `centroid`, `anchor_count`, `segments` (for audits).

Mark assembly:

- `Mark(symbol, wordmark=None, tagline=None, lockup="horizontal"|"stacked"|"symbol"|"wordmark", gap=None, align="center"|"baseline", roles=None)`.
- `symbol` is a `Shape` or a `Composite([(shape, role), ...])`. Roles are `primary`, `secondary`, `accent`, `ink`, `paper`. Default: symbol to `primary`, wordmark to `ink`.
- `gap` defaults to one `x` unit, where `x` is the wordmark cap height for lockups and one fifth of the symbol height for symbol-only marks. The same `x` is the clear-space unit in the package.

Output:

- `Mark.to_svg(variant="color"|"reverse"|"black"|"white"|"mono", tokens=None, padding=0)` returns paths-only SVG: artwork-fitted `viewBox`, no `width` or `height`, groups `#symbol`, `#wordmark`, `#tagline`, cubic Béziers and lines only (conics converted), two-decimal precision, `fill-rule="nonzero"`. `mono` uses `fill="currentColor"`.
- `Mark.geometry()` returns the JSON geometry report used by audits (per-part bounds, anchors, segments with angles, areas).

### 6.3 Concept module contract

```python
# brands/<slug>/concepts/03-keystone/concept.py
from logomaker.kit import *

META = Meta(slug="keystone", idea="A keystone cut from the K's counter",
            logo_type="combination", motifs=["keystone", "letter K"], territory="forge")

PARAMS = Params(stroke=90, gap=40, radius=120, weight=650)

TIERS = {
    "full": {},
    "compact": {},
    "small": {"stroke": 120, "gap": 60},
    "favicon": {"stroke": 160, "gap": 80, "wordmark": False},
}

def build(p: Params) -> Mark:
    k = glyph("K", family="Sora", weight=p.weight, cap_height=600)
    arch = ring(0, 40, 400, p.stroke, start=200, end=340)
    symbol = union(k, arch)
    word = text("Keystone", family="Sora", weight=600, cap_height=180, tracking=-10)
    return Mark(symbol=symbol, wordmark=word, lockup="horizontal", gap=p.gap)
```

- `META`, `PARAMS`, `TIERS` and `build` are required. `TIERS` values are parameter overrides; `wordmark: False` drops the wordmark for that tier.
- The CLI imports the module in-process and calls `build` once per tier. Builds must be deterministic: same parameters, same SVG bytes (golden tests enforce this).
- `final/concept.py` and `final/params.json` are the refined copies; `params.json` overrides `PARAMS` so tuning does not require editing code.

### 6.4 Tiers and lockups

| Build | Purpose | Export names |
|---|---|---|
| `full` | primary lockup at full detail | `primary`, `horizontal`, `stacked`, `wordmark`, `mark` (derived by changing `lockup`) |
| `compact` | symbol plus short word, or symbol only, for 48 to 120 px | used by `sheet` mockups and avatar exports |
| `small` | symbol redrawn for 24 to 64 px | icons from 33 to 95 px |
| `favicon` | mark or monogram for 16 to 32 px | `favicon.ico`, `icon.svg`, 16 to 32 px uses |

Exports choose the build by target size: 96 px and above uses `full` symbol; 33 to 95 px uses `small`; 32 px and below uses `favicon`. A missing `small` or `favicon` tier falls back to the next larger build and the audit records a warning.

### 6.5 Fonts

- `assets/fonts/catalog.json`: about 60 families from `docs/research/03-deliverable-spec.md` section 4.4, each `{family, category, license, personality[], google_dir, variable, weights[]}`. Categories: geometric sans, grotesk, humanist sans, transitional serif, old-style serif, didone display, slab, display, mono, rounded.
- `logomaker fonts fetch <Family>`: downloads the family's TTF files and licence from `https://raw.githubusercontent.com/google/fonts/main/<google_dir>/`, verifies each file parses with fontTools, writes `assets/fonts/<family>/manifest.json` with URLs and sha256. Families not in the catalogue are fetched by reading the repository's `METADATA.pb`.
- Variable fonts are instanced to the requested weight with `fontTools.varLib.instancer` and cached under `instances/`.
- The kit refuses an uncached family with exit 3 and the message "run logomaker fonts fetch <Family>".
- Packages copy the used family's TTFs and licence file into `package/fonts/` with a `FONT-NOTICE.md` naming the licence.

## 7. Rendering and sheets

### 7.1 Renderer

- `render.py` launches the installed Chrome once per CLI invocation (`channel="chrome"`, headless), renders SVG strings inside a minimal HTML wrapper at the exact target pixel size, and screenshots. PNGs are written with Pillow.
- Sheets are HTML templates (Jinja2) with SVGs inlined; `page.screenshot(full_page=True)` makes the PNG twin.
- `brand-sheet.pdf` is `page.pdf(format="Letter", print_background=True)`; `--paper a4` switches format.
- Missing Chrome exits 3 with the install path checked.

### 7.2 Critique sheet (for Claude)

One PNG per concept per round, 2000 by 1400 px:

- Row 1: 512 px black on white; 512 px white on black; in phase 5 also colour on light and reverse on dark.
- Row 2: size ladder 256, 128, 64, 48, 32, 24, 16 px using the tier rules; mirrored at 256; rotated 90 degrees at 256.
- Row 3: one-colour test at 64 and 32 px; the audit summary as text (anchors, minimum feature widths, warnings, failures).

### 7.3 Territory board, concept sheet, refine sheet (for the owner)

- Territory board: section 4.4.
- Concept sheet: each survivor gets its row-1 and row-2 strip plus seven mockups: phone home screen (our icon among eleven generated generic neighbours in common colours, the "shelf test"), browser tab with 16 px favicon and title, site header on light, site header on dark (horizontal lockup at 32 px tall), round avatar at 80 px on a social-post card, business card at 85 by 55 mm scaled, and a one-colour fascia sign. Mockup neighbours are generated by the kit, never third-party logos.
- Refine sheet: tiers, lockups, five colour variants, clear-space diagram with the `x` unit drawn, minimum-size ladder with the px and mm rules, colour-vision strip (protan, deutan, tritan, achromatopsia), and the contrast table.
- Every sheet is opened with `open <file>` by the CLI unless `--no-open` is passed.

## 8. Audits and scorecard

### 8.1 Automated audit (`logomaker concept audit`)

Writes `audit.json` with `{ok, failures[], warnings[], info{}}`. Checks and thresholds:

| Check | Rule | Severity |
|---|---|---|
| anchors | symbol anchor count over 100 | warn |
| anchors | symbol anchor count over 150, unless `META.allow_complex` with a reason | fail |
| near_miss_angles | straight segment angle 0.3 to 3 degrees off a multiple of 15 | warn, lists segments |
| free_segments | segments created with `free=True` | info |
| tiny_parts | subpath whose largest dimension is under 1/48 of the canvas | warn; fail in `small` and `favicon` tiers |
| min_feature | raster erosion on a 512 px render until any component vanishes; width scaled to the tier's target size; `favicon` at 16 px under 1.0 px, `small` at 32 px under 1.5 px, `full` symbol at 64 px under 1.5 px | fail |
| one_colour_merge | connected components at 512 px versus at 32 px (and 16 px for `favicon`); any merge or loss | warn; fail for `small` and `favicon` |
| bounds | symbol aspect ratio, bounds centre versus area centroid offset | info |
| generic_profile | symbol height/width between 0.72 and 0.82 and symmetric and abstract (the false-recognition profile) | info |
| colour_count | more than 3 roles used | warn |
| grayscale | luminance difference under 0.15 between any two used role colours | warn |
| contrast | WCAG ratio and APCA Lc for every role versus light paper and dark paper; wordmark under 4.5 or under Lc 60; symbol roles under 3.0 or under Lc 45 | fail (colour variants only) |
| cvd | protan, deutan, tritan, achromatopsia simulations; any role pair whose simulated contrast falls under 1.5 | warn |
| text_legibility | wordmark x-height in px at the brand's minimum lockup width under 7 px | fail |
| cliche | `META.motifs` matched against the industry blacklist | warn, names the term |
| determinism | rebuild produces identical SVG bytes | fail |

Hard failures block presentation; warnings must be addressed in `critique.md` (fixed or justified).

### 8.2 Scorecard (in `critique.md`, by Claude)

Ten criteria, each 1 to 5 with one line of evidence:

1. Appropriate to the one idea and archetype, without over-explaining.
2. Distinctive against the category uniform and the five nearest competitors.
3. Simple: drawable from memory; one dominant silhouette.
4. Legible: name reads at a glance; mark holds at 16 px and 6 mm.
5. Adaptable: one colour, reversed, app icon, motion-ready.
6. Timeless: no trend shape from `reference/trends.md` unless justified.
7. Universal: no unintended readings in the mirrored and rotated panels; no cultural conflicts noted in the brief.
8. Clear: no look-alike or conflicting mark found in the knock-out.
9. Congruent: shape, weight, colour and typeface match the feature targets and the name's sound.
10. System: lockups, tiers and variants derive cleanly; a one-paragraph rationale exists.

Gate: criteria 1, 3 and 4 at 4 or above, no hard audit failures. The sheet shows the scores beside each survivor.

## 9. Package manifest

Naming: `{brand}-{variant}-{colour}[-{size}].{ext}`, lowercase, hyphenated. Variants: `primary`, `horizontal`, `stacked`, `wordmark`, `mark`, `small`, `favicon`. Colours: `color`, `reverse`, `black`, `white`, `mono`.

| Group | Files | Spec |
|---|---|---|
| SVG masters | 7 variants by 5 colours = 35 | paths only, artwork-fitted viewBox, no dimensions; `mono` uses currentColor. The favicon set's `icon.svg` is the `favicon-color` master plus a `prefers-color-scheme: dark` style block that switches to the reverse role map |
| PNG | `primary`, `horizontal`, `stacked`, `wordmark`, `mark` by `color`, `reverse`, `black`, `white` by long edge 256, 512, 1024, 2048 = 80 | transparent; `reverse` and `white` are rendered on transparent and previewed on dark in the README |
| Flattened | `{brand}-primary-color-white-bg-2048.jpg`, `{brand}-primary-color-2048.webp` | |
| Favicon set | `favicon.ico` (16, 32, 48), `icon.svg`, `apple-touch-icon.png` 180 (opaque paper background, art about 140 px), `icon-192.png`, `icon-512.png`, `icon-mask-512.png` (art inside a 409 px circle on a solid background), `manifest.webmanifest`, `favicon-head.html` | per `docs/research/03` section 2.4 |
| Apple | `ios-app-icon-1024.png` (opaque, full-bleed background, mark at about 60% width), `app-icon-layers/background.svg`, `app-icon-layers/foreground.svg` | Icon Composer-ready, unmasked square layers |
| Android | `android/ic_launcher_foreground.svg`, `ic_launcher_background.svg`, `ic_launcher_monochrome.svg` on a 1080-unit canvas with art inside the central 660 units; `android/mipmap-{m,h,x,xx,xxx}hdpi/ic_launcher.png` at 48, 72, 96, 144, 192; `play-store-icon-512.png` (no corners, no shadow) | |
| Social avatars | `avatar-320.png`, `avatar-400.png`, `avatar-512.png`, `avatar-720.png`, `avatar-800.png` | solid background, art inside an 80% circle |
| Banners | `banner-x-1500x500.png`, `banner-linkedin-personal-1584x396.png`, `banner-linkedin-page-1512x256.png`, `banner-youtube-2560x1440.png` (logo inside the central 1235 by 338), `banner-facebook-851x315.png`, `banner-bluesky-1500x500.png` | brand background, horizontal lockup, safe areas respected |
| Link previews | `og-image-1200x630.png`, `x-card-1200x600.png` | |
| Commerce and email | `email-signature-logo@2x.png` 400 by 100, `shopify-header-logo@2x.png` 800 by 200, `stripe-icon-512.png`, `stripe-logo.png` (horizontal, 1024 wide), `gbp-logo-720.png` | |
| Print | `{brand}-{variant}-rgb.pdf`, `-cmyk.pdf`, `-black.pdf` for `primary`, `horizontal`, `stacked`, `wordmark`, `mark` = 15; `{brand}-primary-cmyk.eps`, `{brand}-mark-cmyk.eps` | reportlab vector; CMYK is a naive conversion and the README says to confirm with the printer |
| Tokens | `tokens.json` | every colour as hex, rgb, hsl, oklch, cmyk, name; role maps for light and dark; contrast and CVD results |
| Fonts | `fonts/<family>/*.ttf`, licence file, `FONT-NOTICE.md` | |
| Docs | `BRAND.md`, `brand-sheet.pdf`, `README.md` (generated file index with purpose and dimensions), `rationale.md` | |
| Source | `source/concept.py`, `source/params.json`, `source/brand.json`, `source/strategy.json` | the package is regenerable from these |
| Manifest | `manifest.json` | every file with purpose, dimensions, sha256 |

`BRAND.md` and the brand sheet contain: the tiers; the clear-space rule with the `x` unit; minimum sizes in px and mm per tier; colour chips with all values and the approved pairings with contrast results; typefaces with weights and licence; six "don't" items (stretch, rotate, recolour, effects, busy backgrounds, re-typeset); background rules for light, dark, photographic and brand-colour fields; the HTML head snippet for favicons and Open Graph; the rationale paragraph.

## 10. CLI reference

All commands print one JSON object with at least `{"ok": bool, "errors": [], "warnings": []}`. Exit codes: 0 ok; 2 input or rule violation; 3 external failure (Chrome, network, missing font); 4 render or export verification failure.

| Command | Purpose |
|---|---|
| `logomaker setup [--check]` | verify Chrome, dependencies, folders; fetch nothing by default |
| `logomaker brand new <name> [--slug s] [--unnamed]` | create the brand folder and state; with `--unnamed`, `<name>` is a working title and `needs_name` is true |
| `logomaker brand rename <slug> --name <Name>` | set the chosen name after the naming phase; the slug never changes |
| `logomaker brand list` / `brand status <slug>` | registry and state |
| `logomaker brand advance <slug> --to <phase>` | gated phase transition |
| `logomaker brand decide <slug> --phase p --by user|claude --note "..."` | append a decision |
| `logomaker names analyze <name>` | linguistic features |
| `logomaker names check <name> [--tlds com,co,io,ai,app,dev] [--handles github]` | availability |
| `logomaker fonts list [--category c] [--personality p]` / `fonts fetch <Family>` | catalogue and cache |
| `logomaker color info <hex>` / `color ramp <hex> [--steps 9]` / `color check <tokens.json>` | conversions, OKLCH ramps, contrast and CVD validation |
| `logomaker concept build|audit|render|run <slug> <concept-dir> [--round n]` | build tiers, audit, critique sheet; `run` does all three |
| `logomaker sheet territories|concepts|refine <slug> [...] [--no-open]` | owner-facing sheets |
| `logomaker package build <slug> [--paper letter|a4]` / `package verify <slug>` | export and verify |

Timeouts: every command finishes within 60 seconds except `package build` (set the Bash timeout to 300000) and `fonts fetch` (network).

## 11. Knowledge base (`.claude/skills/logo/reference/`)

Each file is operational: rules, tables and checklists with the source report named, not essays.

| File | Contents | Source |
|---|---|---|
| `process.md` | phases, gates, artifact contents, agency rules (strategy first, silhouette first, knock-out, in-context, Collins 95, do not over-explain, test recognition not likability) | 01 |
| `evidence-rules.md` | the 20 evidence-based rules with confidence tags and boundary conditions; the feature-to-personality table | 02 |
| `strategy-frameworks.md` | onliness, positioning template, archetype cheat sheet, Aaker, distinctive assets, adjective ladder, naming-to-letterform implications | 05 |
| `questionnaire.md` | section 4.1 questions with inference guidance | 05, 01 |
| `logo-types.md` | taxonomy with fit, misfit and app-icon behaviour; decision guide; "symbol-only is never a launch state" | 05 |
| `cliches.md` | industry blacklist, AI cliché, LogoLounge saturation list, how to twist a justified motif | 05, 04 |
| `craft.md` | optical corrections with amounts, small-size redraw rules, wordmark tracking, quirk rules, construction checklist, common kit recipes | 05, 04 |
| `scorecard.md` | the ten criteria, rubric, gate | 01 |
| `trends.md` | use, use carefully, avoid; dated 2026 | 05 |
| `cautionary-tales.md` | the cases and their rules | 05, 01 |
| `naming.md` | name types, sound symbolism, letterform scoring, checks, the trademark caveat | 05, 02, 03 |
| `fonts.md` | catalogue by category with personality notes, pairing guidance, licensing | 03 |
| `color.md` | hue, saturation and lightness to personality, cross-culture notes, thresholds, OKLCH palette construction, designing reverse variants | 02, 03 |
| `deliverables.md` | package manifest, platform specs with sources, clear space and minimum size conventions, BRAND.md template | 03 |
| `kit-api.md` | section 6 as a reference, with worked examples for a monogram, a pictorial mark, an abstract mark, a wordmark quirk | this spec |

`SKILL.md` itself holds the routing, the phase runbook, the conversation rules (section 3.3), the subagent recipe for parallel concepts, and the list of reference files to read per phase.

## 12. CLAUDE.md

Contents: what the folder is; routing (always use the `logo` skill for anything about logos, brands, names or packages); rules (never hand-write SVG, PNG or PDF deliverables, write concept modules and use the CLI; never edit `registry/` or `brand.json` directly, use `brand` commands; never read `.env`; read the JSON on stdout; Bash timeout for `package build`; never run `playwright install`); where things live; test commands.

## 13. Error handling

- Input and rule violations exit 2 with `errors[]` naming the field or rule: bad slug, unknown phase, missing prerequisite artifact, concept module import error (with traceback text), hard audit failure on `package build`.
- External failures exit 3: Chrome not found at `/Applications/Google Chrome.app`; network failure fetching fonts (cached fonts still work); RDAP and whois failures degrade to `unknown` with a warning rather than exit 3.
- Verification failures exit 4: a render produced an empty or fully transparent PNG; a manifest file missing or with wrong dimensions; `README.md` missing a file.
- The skill reads `ok` and `errors` and never retries a verbatim failing command; it fixes the module or asks.

## 14. Testing

- Fast suite (`uv run pytest -m "not render and not live"`), no Chrome, no network: kit primitives and snapping; booleans and stroking against known areas and bounds; text shaping and outlining with a vendored OFL test font (one small family committed under `tests/fixtures/fonts/`); SVG serialization golden files; determinism; audits on fixture modules that deliberately contain a near-miss angle, a tiny part, a too-thin stroke, low contrast and a blacklisted motif; colour conversions, contrast, CVD, ramps; names analysis; registry state transitions and gating; export naming and manifest construction (dry run without rendering).
- Render suite (`-m render`): Chrome screenshot of a fixture mark at 16 and 512 px; critique and concept sheets produce non-empty PNGs; favicon ICO reads back with sizes 16, 32, 48; reportlab PDFs parse (pypdf) and contain vector operators; `package build` then `package verify` passes on `docs/examples/<slug>`.
- Live suite (`-m live`): `fonts fetch` for one family; `names check` for a known-registered and a nonsense domain.
- Skill check: a walkthrough document in `docs/examples/<slug>/WALKTHROUGH.md` records a complete run so the skill has an exemplar and so regressions in the conversation can be reviewed by reading.

## 15. Dependencies and setup

- `pyproject.toml` with `requires-python = ">=3.12,<3.13"`, `.python-version` pinned to 3.12; `uv run logomaker ...` and `uv run pytest`.
- Runtime: skia-python, fonttools, uharfbuzz, coloraide, reportlab, playwright, pillow, numpy, scipy, click, pydantic, jinja2, pypdf (verification only).
- Dev: pytest, ruff.
- `logomaker setup --check` reports Chrome, Python and dependency status as JSON.
- `.claude/settings.json` denies `Read(.env)` and `Read(.env.*)`.

## 16. Out of scope for this version

Image-model integrations (only the `inspiration/` folder and a `FEATURE_IMAGE_MODELS = False` constant that gates nothing yet), animated logos, legal trademark clearance, PDF/X output intents and Pantone matching, the rebrand and equity-audit flow, and generative or dynamic identity systems beyond parametric tiers.
