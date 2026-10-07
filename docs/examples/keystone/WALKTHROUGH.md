# Keystone: walkthrough

This folder is a complete brand made with the logo skill: the runbook in `.claude/skills/logo/SKILL.md` followed by hand, phase by phase, with the `logomaker` CLI doing every deterministic step and the designer (Claude) making every judgment. The owner's side of the conversation was scripted (below). Where the runbook asks something the script does not answer, the most conservative option was taken, and each such answer is listed. The run took place on 7 October 2026, headless: no board or sheet was opened in a browser (every sheet command ran with `--no-open`), and every territories board, critique sheet, concept sheet, refine sheet and the brand sheet PDF was read with the Read tool instead.

The folder is `brands/keystone/` as the skill left it at `done`, copied whole apart from the CLI's `build/` folders (see "What was left out of the copy").

## The owner's answers

The script, verbatim:

1. Business: Keystone sends invoices that get paid faster, for solo consultants, solving late payments.
2. One idea: the piece that holds everything together.
3. Onliness: the only invoicing tool that nags clients so you don't have to.
4. Adjectives: steady but not boring; direct but not rude; warm but not cute.
5. Persona: a calm site foreman who is good at follow-up.
6. Admired: Stripe (restraint), Patagonia (conviction). Disliked: generic fintech blue.
7. Surfaces: app icon, website header, social avatar.
8. Harshest: 16 px favicon and one-colour embroidery.
9. Colours: wants ember orange; forbids fintech blue; category has claimed blue and green.
10. Off limits: upward arrows, shields. No cultural constraints; English only.
11. Name: Keystone, written "Keystone", no tagline; story: the stone that locks an arch.
12. Territory choice: the warmer, denser of the boards. Concept choice: the direction whose symbol derives from the K or the arch. First reaction to the concept sheet: "the ring one looks like a loading spinner"; expect the probing question and answer "at the avatar size".
13. Refinement approval after the colour round. Any extra question: answer with the most conservative option.

Questions the script does not answer, and the conservative answer taken (answer 13):

- Named or unnamed, settled before `brand new` (first move, step 4): named, from answer 11, so `brand new "Keystone"` and no naming phase.
- The intake write-back: confirmed as written, no corrections.
- Optional intake questions: none asked; the core answers left no gap that the strategy research could not fill.
- The strategy: approved as written.
- The name conflict the look-alike search found (an app called Keystone; see Concepts): keep the name and have a trademark attorney clear it before filing or spending.
- "What do you like in each?": no specific likes named, so no steal and nothing to carry into refinement.
- Which of the K or the arch: both 01-k-jaw (from the K) and 02-arch (from the arch) were on the sheet; the higher-scoring one, 02-arch (43 of 50 against 37), was taken.
- The primary lockup: questionnaire.md's rule, the top surface picks it; the app icon is a square placement, so stacked. That reading set aside strategy.md's own constraint that "the horizontal lockup is the header" (section 9), and an app icon draws the mark, never a lockup, so the rule now reads the mockups that show one (the website headers, the card, the sign), by which Keystone's primary would be horizontal; the package here keeps the stacked primary this run chose.
- The package handover: recorded with `brand decide`; opening the brand sheet is left to the owner at plan closure.

## Time per phase

The clock was noted at each `brand advance` (times are EDT, 7 October 2026). These are wall-clock times of one agent session, including reading every sheet and the web research; the CLI itself never took more than 18 s for one command (`package build`), and a rendered `concept run` took 1 to 3 s.

| Phase | Started | Took | What took the time |
|---|---|---|---|
| Intake | 16:07:45 | 2 min 5 s | first move, `brand new`, the brief write-back |
| Strategy | 16:09:50 | 4 min 19 s | the web look at five competitors, strategy.md and strategy.json |
| Territories | 16:14:09 | 1 min 19 s | four font fetches, the board |
| Concepts | 16:15:28 | 19 min 39 s | prototyping, five modules in nine rounds, nine critique sheets, scoring, look-alike searches, the concept sheet |
| Refinement | 16:35:07 | 6 min 33 s | six final rounds, colour, the knock-out, the refine sheet |
| Package | 16:41:40 | 1 min 15 s | the rationale, `package build` (18 s), `package verify`, reading the brand sheet |
| Done | 16:42:55 | | |

From the first `brand list` to `done`: 35 minutes 10 seconds. Writing this walkthrough, the copy and the tests came after.

## Where things are

| File | What it is |
|---|---|
| `brief.md`, `brief.json` | the intake write-back and the validated brief |
| `strategy.md`, `strategy.json` | the nine sections, with the competitor audit and its sources |
| `territories/territories.json`, `board.html`, `board.png` | the two territories and the board the owner chose from |
| `concepts/ideas.md` | twenty ideas, five struck, five taken forward |
| `concepts/NN-slug/` | each direction: `concept.py`, `audit.json`, `scorecard.json`, `critique.md`, `renders/round-N/critique.{html,png}` |
| `sheets/concepts.{html,png}` | the concept sheet the owner saw (three survivors) |
| `sheets/refine-1.{html,png}` | the refine sheet, the colour round the owner approved |
| `final/` | the refined module, `params.json`, `tokens.json`, `audit.json`, `knockout.md`, `rationale.md`, `scorecard.json` (a re-score of the final mark), `renders/round-1` to `round-6` |
| `package/` | the deliverables: 186 files, `manifest.json`, `verify.json`, `BRAND.md`, `brand-sheet.pdf`, `README.md` |
| `brand.json` | the brand's state at `done`, with the ten decisions below |

## Phase by phase

### Intake

Read first: process.md, questionnaire.md, strategy-frameworks.md. `brand list` showed no brands, so the first message said so and asked question 1; the next settled that the venture is named, and `brand new "Keystone"` made the brand. Questions 2 to 11 followed one per message (the answers above).

Inferences, shown in the write-back for correction:

- Archetype: Everyman first (the persona is a plain-spoken, sturdy site foreman), Caregiver second (good at follow-up is looking after someone else's money).
- Aaker scores, by strategy-frameworks.md's steps: warm and direct lift sincerity to 0.9; steady and the persona lift competence to 0.8 and Stripe's restraint nudges it to 0.9; the calm persona keeps excitement under neutral and "not boring" floors it at 0.4; sophistication 0.4; Patagonia nudges ruggedness to 0.6 and "not rude" caps it there. Two dimensions above 0.7, the most the rules allow.
- Industry tag: "invoicing for solo consultants", which resolves to the fintech cliché list only (checked against `assets/cliches.json` before writing; "consultants" does not select the consulting list, and the tag names what Keystone sells).
- Surfaces in the owner's order: app icon, website header, social avatar.

`brief.md` (the readable write-back) and `brief.json` (validated as `Brief`) were written, the write-back shown, and the brief confirmed.

| # | Time | Command | Exit | Outcome |
|---|---|---|---|---|
| 1 | 16:07:45 | `uv run logomaker setup --check` | 0 | Chrome 154 found, every module present |
| 2 | 16:07:45 | `uv run logomaker brand list` | 0 | no brands |
| 3 | 16:08:40 | `uv run logomaker brand new "Keystone"` | 0 | brand keystone, phase intake, needs_name false |
| 4 | 16:09:40 | `uv run logomaker brand decide keystone --phase intake --by user --note "..."` | 0 | decision appended (text in the decisions table below) |
| 5 | 16:09:40 | `uv run logomaker brand status keystone` | 0 | next strategy, nothing missing |

### Strategy

Read first: strategy-frameworks.md, evidence-rules.md, logo-types.md, cliches.md, cautionary-tales.md, trends.md, color.md. `inspiration/` was empty, so there were no reference images.

The web look (Firecrawl search and scrape): the five nearest competitors, judged by what a solo consultant would buy instead, were FreshBooks, Wave, Bonsai, HoneyBook and Chaser. Each site's colours and fonts were read with Firecrawl's branding extraction, and each logo was downloaded and viewed. The uniform: blue everywhere (FreshBooks #0075dd, Wave #0040ff, Zoom blue on Bonsai), green second, lowercase geometric or heavy caps type, a letter in a rounded tile (FreshBooks, Bonsai) and Wave's slanted growth strokes. The finding that shaped the colour: Chaser, the payment chaser and the closest competitor to Keystone's promise, owns a burnt orange (#d75e36, OKLCH hue 38), so Keystone's ember had to be redder and darker. Free to own: masonry and the arch (none of the five uses a building or stone), a heavy grounded symmetric silhouette, and a title-case wordmark with weight.

`strategy.md` holds the nine sections of process.md with the sources; `strategy.json` validates as `Strategy`. Two decisions worth noting: `descriptive_cue` is false, a deliberate override of evidence rule 3 written into strategy.md (no tagline, and every visual cue for invoicing is a fintech cliché or a literal document), and `frame` is "framed" (rule 8, finance is a risky category; shields are off limits, so the frame is the mark's own enclosure). The logo type is a wordmark-led combination mark: at eight letters the name is one too long to carry an app icon alone, and the app icon is the first surface.

| # | Time | Command | Exit | Outcome |
|---|---|---|---|---|
| 6 | 16:09:50 | `uv run logomaker brand advance keystone --to strategy` | 0 | phase strategy |
| 7 | 16:09:50 | `uv run logomaker names analyze Keystone` | 0 | 8 letters, 2 syllables, front ratio 0.67, diagonal initial, pronounceable |
| 8 | 16:14:09 | `uv run logomaker brand set keystone --industry "invoicing for solo consultants" --surface "app icon" --surface "website header" --surface "social avatar"` | 0 | industry and three ranked surfaces recorded |
| 9 | 16:14:09 | `uv run logomaker brand decide keystone --phase strategy --by user --note "..."` | 0 | decision appended (text in the decisions table below) |
| 10 | 16:14:09 | `uv run logomaker brand advance keystone --to territories` | 0 | phase territories |

### Territories

Read first: fonts.md, color.md, trends.md. Two territories, both naming what they reject:

- Site Ledger: Sora 600 with Archivo 400; Chalk, Graphite, Steel, Concrete and an Ember Spark accent; thin strokes, sharp corners. Airy and cool.
- Hearth Stone: Bricolage Grotesque 700 with Fraunces 600; Ember #c83c29 (OKLCH 0.56 0.18 31, redder and darker than Chaser's), Coal, Kiln, Brick and Ash; heavy strokes, softened corners. Warm and dense.

All four families were fetched before the board (the board never fetches). Reading `board.png` showed Bricolage Grotesque drawn at its display optical size (its variable font's default), dense and characterful, and Fraunces warm without tipping into cute. The owner took "the warmer, denser of the boards": Hearth Stone, with Bricolage Grotesque 700 recorded as the wordmark font.

| # | Time | Command | Exit | Outcome |
|---|---|---|---|---|
| 11 | 16:14:14 | `uv run logomaker fonts list --category grotesk` | 0 | 11 families, none cached |
| 12 | 16:14:14 | `uv run logomaker fonts list --category "geometric sans"` | 0 | 10 families, none cached |
| 13 | 16:14:14 | `uv run logomaker fonts list --category "didone display"` | 0 | 8 families, none cached |
| 14 | 16:14:21 | `uv run logomaker fonts fetch Sora` | 0 | Sora[wght].ttf and OFL.txt |
| 15 | 16:14:22 | `uv run logomaker fonts fetch Archivo` | 0 | Archivo roman and italic variable files, OFL.txt |
| 16 | 16:14:23 | `uv run logomaker fonts fetch "Bricolage Grotesque"` | 0 | BricolageGrotesque[opsz,wdth,wght].ttf, OFL.txt |
| 17 | 16:14:23 | `uv run logomaker fonts fetch Fraunces` | 0 | Fraunces roman and italic variable files, OFL.txt |
| 18 | 16:15:08 | `uv run logomaker sheet territories keystone --no-open` | 0 | territories/board.png and board.html |
| 19 | 16:15:24 | `uv run logomaker brand set keystone --territory hearth-stone --font "wordmark=Bricolage Grotesque:700"` | 0 | territory hearth-stone; font wordmark Bricolage Grotesque 700 |
| 20 | 16:15:24 | `uv run logomaker brand decide keystone --phase territories --by user --note "..."` | 0 | decision appended (text in the decisions table below) |
| 21 | 16:15:24 | `uv run logomaker brand status keystone` | 0 | next concepts, nothing missing |
| 22 | 16:15:28 | `uv run logomaker brand advance keystone --to concepts` | 0 | phase concepts |

### Concepts

Read first: craft.md, kit-api.md, scorecard.md, evidence-rules.md, trends.md, cliches.md, logo-types.md.

`concepts/ideas.md` lists twenty ideas tagged with motifs; five are struck for the owner's off-limits list or the fintech blacklist (an upward arrow of stones, a shield, a coin, an arch on columns, hands).

Before each module the shapes were sketched with the kit in a throwaway script in the session's scratch folder, outside the brand, and looked at as PNGs: ways to put a keystone into the K (filling its counters, a stone in its jaw, joints at its junction, a stone in its top counter, a tapered stem), arch and ring proportions, six stacked-block constructions (a bond, a pinned stack, a pyramid, a slab with a raised key, a cairn, a dovetail) and three wordmark quirks. The runbook has since ruled this out: exploration goes through concept modules and `concept run` only (SKILL.md, "Writing concept modules"), because a scratch script bypasses the audit. These sketches are exploration, not deliverables: every SVG, PNG, PDF and ICO in this folder was rendered by the CLI, and the files written by hand are the ones the runbook asks the designer to write (the brief, the strategy, the territories, the ideas, the concept modules, scorecards and critiques, the tokens, the knock-out and the rationale).

Five directions, five modules written directly (the runbook's optional subagent recipe was not used), at least three structurally different (a glyph-built lettermark, a pictorial from primitives, an abstract tile and joint, a wordmark, a ring):

| Concept | Construction | Rounds | Gate (appropriate, simple, legible) | Total | Outcome |
|---|---|---|---|---|---|
| 01-k-jaw | Bricolage Grotesque K 800, the stone first in its jaw, then (round 3) at its junction | 3 | 4, 4, 4 | 37 | survivor |
| 02-arch | a ring sector on straight feet, a keystone wedge rising above the crown, two joints | 1 | 5, 5, 4 | 43 | survivor, chosen |
| 03-dovetail | a block cut by one dovetail joint whose tail is keystone-shaped | 2 | 3, 4, 4 | 32 | killed |
| 04-wordmark | "Keystone" with the o's counter cut as an arch; the o alone in the small tiers | 1 | 3, 5, 5 | 36 | killed |
| 05-ring-gap | a ring with a gap at the top, closed by a keystone sector between two joints | 2 | 4, 5, 4 | 34 | survivor, kept on the sheet for the owner's scripted reaction |

Each concept's `critique.md` gives its round-by-round notes and every audit warning fixed or justified, and for the survivors a rationale draft; each `scorecard.json` holds the ten scores with evidence. The kills keep all ten scores and a reason.

Before presenting, look-alikes were searched by description for each survivor, and each `clear` score was updated: stock libraries sell "Keystone" arch logos (Dreamstime 336333639, Adobe Stock 2199319247), so 02-arch's `clear` stayed at 3; segmented rings are everywhere; nothing like the K with a keystone at its junction turned up. The same search found an app already called Keystone, selling invoicing to solo service operators (decision 6 below).

The presentation, in the runbook's order: `sheet concepts` for the three survivors, `sheets/concepts.png` read; then the Collins rule 95 preface, word for word: "New ideas can be fragile because they are unfamiliar. You may not like something you see here, but you are not allowed to say that for now... find something, anything, you like in every idea." The sheet would then be opened for the owner (not in this headless run); the mockups were walked through before the strips; the look-alike and name findings were given with the caveat: "These checks are a knock-out only, not legal clearance: they can surface an obvious conflict but cannot prove there is none, so have a trademark attorney run a clearance search before you file the name or spend money on it." Then "What do you like in each?" before "Which one?".

The owner's first reaction was negative: "the ring one looks like a loading spinner". Before changing anything came the one probing question (what reads wrong, at what size, in which mockup?), and the answer was "at the avatar size". By process.md's sort that is a flaw, not unfamiliarity: an unintended reading at a named size, the University of California's 2012 "loading icon" case. It is also the reading critique.md had already flagged for 05-ring-gap (universal 2): on the concept sheet as it was then drawn, the avatar mockup showed the small tier, a ring with one separated segment (the sheet now draws a concept's `compact` tier there, as the avatar exports do; 05-ring-gap's is the same ring with its keystone between two joints). So the ring was not carried forward. The owner then chose the direction whose symbol derives from the arch, 02-arch, with no steal and no blend.

| # | Time | Command | Exit | Outcome |
|---|---|---|---|---|
| 23 | 16:25:50 | `uv run logomaker concept run keystone 02-arch` | 0 | 02-arch round 1: audit ok, no warnings |
| 24 | 16:26:22 | `uv run logomaker concept run keystone 05-ring-gap` | 0 | 05-ring-gap round 1: audit ok, no warnings |
| 25 | 16:26:53 | `uv run logomaker concept run keystone 01-k-jaw` | 0 | 01-k-jaw round 1: audit ok; 3 near_miss_angles warnings (2 segments each) |
| 26 | 16:27:19 | `uv run logomaker concept run keystone 03-dovetail` | 0 | 03-dovetail round 1: audit ok, no warnings |
| 27 | 16:27:43 | `uv run logomaker concept run keystone 04-wordmark` | 0 | 04-wordmark round 1: audit ok, no warnings |
| 28 | 16:29:11 | `uv run logomaker concept run keystone 01-k-jaw` | 0 | 01-k-jaw round 2: audit ok; near_miss_angles 3, 3, 2 segments |
| 29 | 16:29:13 | `uv run logomaker concept run keystone 03-dovetail` | 0 | 03-dovetail round 2: audit ok, no warnings |
| 30 | 16:29:15 | `uv run logomaker concept run keystone 05-ring-gap` | 0 | 05-ring-gap round 2: audit ok, no warnings |
| 31 | 16:30:41 | `uv run logomaker concept run keystone 01-k-jaw` | 0 | 01-k-jaw round 3: audit ok; near_miss_angles 2, 2, 2 segments (the font's K leg) |
| 32 | 16:34:30 | `uv run logomaker sheet concepts keystone --concepts 01-k-jaw,02-arch,05-ring-gap --no-open` | 0 | sheets/concepts.png and concepts.html |
| 33 | 16:35:02 | `uv run logomaker brand decide keystone --phase concepts --by claude --note "..."` | 0 | decision appended (text in the decisions table below) |
| 34 | 16:35:02 | `uv run logomaker brand decide keystone --phase concepts --by claude --note "..."` | 0 | decision appended (text in the decisions table below) |
| 35 | 16:35:02 | `uv run logomaker brand decide keystone --phase concepts --by user --note "..."` | 0 | decision appended (text in the decisions table below) |
| 36 | 16:35:02 | `uv run logomaker brand decide keystone --phase concepts --by user --note "..."` | 0 | decision appended (text in the decisions table below) |
| 37 | 16:35:02 | `uv run logomaker brand decide keystone --phase concepts --by user --note "..."` | 0 | decision appended (text in the decisions table below) |
| 38 | 16:35:02 | `uv run logomaker brand set keystone --concept 02-arch` | 0 | concept 02-arch |
| 39 | 16:35:03 | `uv run logomaker brand status keystone` | 0 | next refinement, nothing missing |
| 40 | 16:35:07 | `uv run logomaker brand advance keystone --to refinement` | 0 | phase refinement |

### Refinement

Read first: craft.md, kit-api.md, color.md, fonts.md, deliverables.md, naming.md, cautionary-tales.md, and for the re-score scorecard.md, evidence-rules.md and trends.md.

`final/concept.py` started as a copy of 02-arch with `params.json` set to `{}`, and `concept run keystone final` ran after each step, each critique sheet read before the next:

1. Round 1: the module as chosen, the baseline.
2. Round 2, optical corrections: curves look thinner than straight strokes, so the intrados' centre drops 9 units below the springing line, which thickens the crown by about 5 percent over the feet with no step at the joint. Nothing else needed correcting: the mark is symmetric, its centroid sits within 6 units of its box centre, and no round part meets a flat line it must overshoot.
3. Round 3, the small tiers redrawn through `TIERS`: the favicon fitted to a 16 px grid at 50 units a pixel (band 4 px, opening 8 px, feet 3 px, the keystone 2 px proud, no joints); the small tier's joints narrowed from 72 to 60 units, which still stay open at 32 px.
4. Round 4, the wordmark: Bricolage Grotesque 700 as the territory set it, cap height 260 so the arch leads, tracked open by 10/1000 em because the display cut sets tight in a 32 px header, and no quirk (the symbol carries the idea; the plain type suits the Everyman). Kia test: no letter of "Keystone" reads as another at the 120 px minimum.
5. Round 5, the lockups: the gap between symbol and wordmark tightened to 170 units (about two thirds of x) so the stacked lockup reads as one unit; the primary lockup set to stacked with `brand set`, since the top surface, the app icon, is a square placement; the module's own lockup made stacked so the critique and the clear-space diagram show the primary.
6. Round 6, colour: `final/tokens.json` with Ember (#c83c29) and Coal on Kiln, and for dark paper a designed reverse rather than an inversion: a lighter step of Ember's own ramp, with Kiln for the type. `color check` failed the first choice, ramp step 4 (#e85a45): WCAG 4.83:1 but APCA Lc 38.2 on Coal, under the 45 a non-type role needs. Step 3 (#ff8671, "Ember Glow") passed at WCAG 7.19:1 and Lc 54.4, still 0.20 of lightness from Kiln. A more orange glow at hue 42 was considered and rejected: color.md asks for a lighter step of the primary's own ramp, and hue 42 drifts toward Chaser's orange. The rendered audit, the colour gate, then passed with every colour-vision pair at 1.87:1 or more.

Then the unintended-readings pass (the mirrored, rotated and ladder panels of round 6, the 180-degree turn, the squint at 16 and 24 px, the motion, and the refine sheet's colour-vision strip) and the knock-out searches, both written into `final/knockout.md` with the caveat. `final/scorecard.json` re-scores the final mark: 46 of 50.

Only then did the owner see the round: `sheet refine` (round 1, the colour round), `sheets/refine-1.png` read (tiers including compact, the four lockups, the five colour variants, clear space of one x = 260 units, the minimum-size ladder, the colour-vision strip, the contrast table), and the owner approved after the colour round.

| # | Time | Command | Exit | Outcome |
|---|---|---|---|---|
| 41 | 16:36:16 | `uv run logomaker concept run keystone final` | 0 | final round 1 (02-arch as chosen): audit ok |
| 42 | 16:37:07 | `uv run logomaker concept run keystone final` | 0 | final round 2 (crown compensation): audit ok |
| 43 | 16:37:29 | `uv run logomaker concept run keystone final` | 0 | final round 3 (small and favicon tiers): audit ok |
| 44 | 16:37:45 | `uv run logomaker concept run keystone final` | 0 | final round 4 (wordmark: cap 260, tracking 10): audit ok |
| 45 | 16:38:04 | `uv run logomaker brand set keystone --primary-lockup stacked` | 0 | primary lockup stacked |
| 46 | 16:38:06 | `uv run logomaker concept run keystone final` | 0 | final round 5 (gap 170, stacked lockup): audit ok |
| 47 | 16:38:19 | `uv run logomaker color ramp "#c83c29" --steps 9` | 0 | nine steps from #ffe9e4 to #1e0100 at the ember's hue |
| 48 | 16:38:35 | `uv run logomaker color check brands/keystone/final/tokens.json` | 2 | exit 2: dark primary #e85a45 on #221b17 is APCA -38.24 (needs 45) |
| 49 | 16:39:13 | `uv run logomaker color check brands/keystone/final/tokens.json` | 0 | dark primary #ff8671: WCAG 7.194, APCA -54.36; every pair passes |
| 50 | 16:39:23 | `uv run logomaker concept run keystone final --variants black,white,mono,color,reverse` | 0 | final round 6 (colour): audit ok, no warnings, colour checks pass |
| 51 | 16:40:57 | `uv run logomaker brand status keystone` | 0 | next package, nothing missing |
| 52 | 16:40:59 | `uv run logomaker sheet refine keystone --no-open` | 0 | sheets/refine-1.png and refine-1.html |
| 53 | 16:41:39 | `uv run logomaker brand decide keystone --phase refinement --by user --note "..."` | 0 | decision appended (text in the decisions table below) |
| 54 | 16:41:39 | `uv run logomaker brand status keystone` | 0 | next package, nothing missing |
| 55 | 16:41:40 | `uv run logomaker brand advance keystone --to package` | 0 | phase package |

### Package

Read first: deliverables.md, cautionary-tales.md. `final/rationale.md` is one paragraph of 118 words for the owner, checked before the build for "represent", the golden ratio, ratios and construction talk (none). `package build` wrote 186 files in 18 s with no warnings and no skipped group; `package verify` reported ok. The brand sheet PDF was read: one page, with the rationale, the logo system, clear space, the four colours in every notation, contrast, typography, backgrounds and the head snippet. The iOS app icon, whose Kiln-on-Ember pair no check measures, was looked at too: a Kiln arch on an Ember tile, clear and warm. In a live session the runbook now runs `open` on the package folder and `open -a "Google Chrome"` on the brand sheet; this headless run recorded the handover instead and advanced to `done`.

| # | Time | Command | Exit | Outcome |
|---|---|---|---|---|
| 56 | 16:42:18 | `uv run logomaker package build keystone` | 0 | 186 files; absolute package, manifest and brand_sheet paths |
| 57 | 16:42:23 | `uv run logomaker package verify keystone` | 0 | ok, no problems, 186 files |
| 58 | 16:42:55 | `uv run logomaker brand decide keystone --phase package --by user --note "..."` | 0 | decision appended (text in the decisions table below) |
| 59 | 16:42:55 | `uv run logomaker brand advance keystone --to done` | 0 | phase done |
| 60 | 16:42:55 | `uv run logomaker brand status keystone` | 0 | phase done, next none, nothing missing |

## Decisions recorded with `brand decide`

All ten, as brand.json holds them (`--by user` for the owner's decisions, `--by claude` for the designer's kills):

| # | At | Phase | By | Note |
|---|---|---|---|---|
| 1 | 16:09:40 | intake | user | Brief confirmed as written, no corrections (the owner's reply to the write-back was not scripted; the most conservative option was taken, per answer 13): Everyman with Caregiver; sincerity 0.9, excitement 0.4, competence 0.9, sophistication 0.4, ruggedness 0.6; industry tag 'invoicing for solo consultants' (fintech list). |
| 2 | 16:14:09 | strategy | user | Strategy approved as written (the owner's reply was not scripted; the most conservative option, per answer 13): one idea 'the piece that holds everything together'; combination mark, wordmark-led; avoid blue, green, slants, a bare letter in a tile, columns; own masonry, a grounded symmetric silhouette and an ember redder and darker than Chaser's orange. |
| 3 | 16:15:24 | territories | user | Chose Hearth Stone, the warmer and denser board: Bricolage Grotesque 700 for the wordmark with Fraunces 600 beside it; Ember #c83c29 on Coal #221b17 and Kiln #f6eee3, Brick and Ash as support; heavy strokes, softened corners. Site Ledger (Sora, Archivo, greys with an ember spark) set aside. |
| 4 | 16:35:02 | concepts | claude | Killed 03-dovetail after round 2: in a tile it is a figure in the category's container and reads as a bucket or keyhole at 32 px; out of the tile the joint draws a shirt collar; appropriate stays 3. |
| 5 | 16:35:02 | concepts | claude | Killed 04-wordmark after round 1: the arched o carries the arch, not the piece that holds it, and a wordmark-only mark shows the whole word on every app icon from 96 px up, against the first surface; appropriate 3. |
| 6 | 16:35:02 | concepts | user | Name knock-out shown with the trademark caveat: an app named 'Keystone: Run Your Business' (VinTEK Solutions; vinteksolutions.com/keystone, App Store id6768339087) sells invoicing to solo service operators. Most conservative option (answer 13): keep the name as given and have a trademark attorney clear it before filing or spending. |
| 7 | 16:35:02 | concepts | user | First reaction to the concept sheet: 'the ring one looks like a loading spinner'. Probing question: what reads wrong, at what size, in which mockup? Answer: 'at the avatar size'. Sorted as a flaw (an unintended reading at a named size, the University of California 2012 loading-icon case), not unfamiliarity: 05-ring-gap is not carried forward. |
| 8 | 16:35:02 | concepts | user | Chose 02-arch, the direction whose symbol derives from the arch (answer 12 allows the K or the arch; 02-arch is the higher-scoring of the two, 43 against 37, the most conservative pick). Likes: none named beyond the choice (not scripted; most conservative answer). No steal from 01-k-jaw or 05-ring-gap; no blend. |
| 9 | 16:41:39 | refinement | user | Approved after the colour round (refine sheet round 1): 02-arch refined with a 5% heavier crown, a favicon redrawn on a 16 px grid, Bricolage Grotesque 700 tracked +10 with no quirk, stacked primary lockup with a 170-unit gap, Ember #c83c29 and Coal on Kiln, Ember Glow #ff8671 and Kiln on Coal. Knock-out in final/knockout.md shown with the caveat. |
| 10 | 16:42:55 | package | user | Package handed over: brands/keystone/package (186 files, verify ok) and package/brand-sheet.pdf, read and found to print on one page. Headless run: the folder and sheet were not opened in Finder or Chrome; the owner opens brand-sheet.pdf once at plan closure. |

## What the critique sheets caught

Every critique sheet (nine concept rounds, six final rounds) and every owner sheet was read with the Read tool before scoring or deciding. What they caught, by concept and round:

1. 01-k-jaw, rounds 1 to 3, an audit warning fixed. Round 1 warned `near_miss_angles` on two segments in each of full-symbol, small and favicon; round 2's bigger stone raised full-symbol and small to three. The two common ones are the straight edges of Bricolage Grotesque's own K leg (104.5 and 107.9 degrees), the type designer's angles, justified in critique.md. The third was the stone's: cut back from the letter by `offset`, it picked up a short straight edge parallel to the leg, at 107.9 degrees. Round 3 draws the stone with its own sides at exactly 15 degrees, and the count fell back to the font's two.
2. 01-k-jaw, rounds 1 and 2: the stone in the K's jaw read as an arrowhead, a loudspeaker or a rewind sign rather than a keystone, and in round 1 it thinned to 1.09 px at 16 px, just over the audit's 1.0 px floor. Round 3 moved the stone to the junction, where an arch lying on its side keeps its keystone; the rotated panel then showed the construction plainly (turned 90 degrees, the K is an arch with the stone at its crown), and the favicon's thinnest feature rose to 4.47 px.
3. 05-ring-gap, round 1: the open favicon (the keystone dropped, the gap left) read as a power button at 16 to 32 px, and the small tier at 48 to 64 px as a loading spinner or a donut chart. Round 2 closed the favicon into a whole ring, which removed the power-button reading; the spinner reading in the small tier is inherent to a ring with one separated segment, so it was flagged (universal 2) and said to the owner, who confirmed it at the avatar size.
4. 03-dovetail, rounds 1 and 2: round 1's tile, which the audit passed cleanly, is the category's own container (FreshBooks' F tile, Bonsai's b tile), and its tail on a neck read as a bucket, a goblet or a keyhole at 32 px; round 2, without the tile, drew a shirt collar over a box. Killed with that reason.
5. 04-wordmark, round 1: the arched counter was visible at 256 px and gone at 128 px, and the o icon was a plain ring at 16 px. With no symbol, every app icon from 96 px up would show the whole word. Killed.
6. The concept sheet: on the phone shelf, the ring sat beside generated neighbour icons that are rings themselves, and the avatar mockup showed the spinner reading the owner then named.
7. Final, round 6 (by `color check` before the audit): the first dark-context primary, #e85a45, failed APCA on Coal (Lc 38.2, needs 45) though it passed WCAG; the next lighter ramp step, #ff8671, passes at Lc 54.4.

## What was left out of the copy

- The six `build/` folders (`concepts/*/build/` and `final/build/`): the CLI's build output (an SVG per output and variant, `geometry.json`, `build.json`). The repository's `.gitignore` ignores every `build/` folder, so they could not be committed anyway; `concept run` writes them again.
- Nothing else. The package is copied whole, all 186 manifest files plus `manifest.json` and `verify.json`, and every critique round is kept. The plan suggested dropping the package's 1024 and 2048 px PNGs and the earlier critique rounds to stay under 10 MB; neither was needed (the copy, this walkthrough included, is under 6 MB), and dropping package files would break `package verify`.
- Outside this folder: the fetched font caches (`assets/fonts/sora`, `archivo`, `bricolagegrotesque`, `fraunces`) are git-ignored and stay out of the repository; the package carries its own copy of the one family it uses, in `package/fonts/bricolagegrotesque/`. After the copy, `brands/keystone/` and `registry/` were removed from the checkout, so a fresh session in this repository lists no brands.

## Verifying and reusing this example

- `uv run pytest tests/test_example.py -q` checks the folder is complete, that the rationale follows the rule, and that the package still matches its manifest and the brand's inputs (it runs `export_docs.verify` on a copy in a temporary project, so the committed `verify.json` is not taken on trust). Its render-marked test copies the folder into a temporary project, installs `package/fonts/` into that project's `assets/fonts/`, builds the package again through Chrome, and verifies it.
- To continue Keystone as a live brand, copy this folder to `brands/keystone/` and run `uv run logomaker brand list`. It rebuilds the registry index from the brand folders only when `registry/brands.json` is missing; with an index already there, it warns that keystone is left out, and deleting `registry/brands.json` (after telling the owner) lets the next `brand list` rebuild it with keystone. Fetch the wordmark family with `uv run logomaker fonts fetch "Bricolage Grotesque"` (or copy `package/fonts/bricolagegrotesque/` into `assets/fonts/`). The final audit's fingerprint covers `assets/cliches.json`, so if the cliché list has changed since 7 October 2026, run `uv run logomaker concept run keystone final` before `package build`.
- What this run did not do: `names check` (the runbook now runs it once in strategy for a named venture; this run followed the runbook before that step was added), the trademark registry searches (USPTO design codes, EUIPO, WIPO image similarity) and a reverse image search, all left for the attorney, as `final/knockout.md` says. These checks are a knock-out only, not legal clearance: they can surface an obvious conflict but cannot prove there is none, so have a trademark attorney run a clearance search before you file the name or spend money on it.

## Refreshing this example

The example must stay valid against the current code and rules, and `tests/test_example.py`'s render test is what breaks when they move: a change to `assets/cliches.json` makes `final/audit.json` stale (its fingerprint covers the list), and a change to the package's file set no longer matches the committed manifest. Refresh it with the CLI, never by hand, from the checkout root with `LOGOMAKER_ROOT` unset:

1. Copy this folder to `brands/keystone/` without its `build/` folders (`rsync -a --exclude build/ docs/examples/keystone/ brands/keystone/`). The wordmark family must be cached: `uv run logomaker fonts fetch "Bricolage Grotesque"`, or copy `package/fonts/bricolagegrotesque/` into `assets/fonts/`.
2. When the audit is stale: `uv run logomaker concept audit keystone final`. When the package or its file set changed (the export code, a template): `uv run logomaker package build keystone` (Bash timeout 300000), then `uv run logomaker package verify keystone`, which must report ok. When both, the audit comes first: the build refuses a stale one.
3. Copy back what the commands rewrote, never a `build/` folder: `final/audit.json` after an audit, `package/` whole after a build (`rsync -a --delete brands/keystone/package/ docs/examples/keystone/package/`). The sheets, the concepts and the files the designer wrote stay as they are.
4. Remove `brands/keystone/`, and `registry/` if anything made it: none of these commands touches the registry, but `brand list` writes `registry/brands.json` when it is missing (it rebuilds the index only then).
5. Run `uv run pytest tests/test_example.py -q`, render test included.
