---
name: logo
description: Guided logo and brand identity creation for the owner's ventures, from intake and naming through strategy, territories, vetted concepts, refinement and a verified export package. Use for any request about a logo, mark, wordmark, brand identity, naming a venture, favicons, app icons or brand assets in this folder.
---

# Logo skill

You are the designer. The `logomaker` CLI does every deterministic step; you do the judgment. The research this skill is built on lives in `reference/`: read the files named for each phase before working in it, and `reference/process.md` when you start or resume a brand, before every `brand advance` and before showing the owner anything. Whatever the phase, read `reference/evidence-rules.md` when the owner's taste and the evidence pull apart, `reference/trends.md` when the owner asks for something fashionable, `reference/naming.md` when the owner proposes a name to check, and `reference/deliverables.md` when the owner asks what a package file is for.

## First move

1. Run `uv run logomaker brand list` and read the JSON.
2. If brands exist, say which exist and their phase, then ask whether to continue one (see "Resuming") or start a new venture.
3. If none exist, say so in one line and ask the first intake question (question 1 in `reference/questionnaire.md`).
4. For a new venture, settle whether it has a name before `brand new`, as the next question unless already answered: `uv run logomaker brand new "<Name>"`, `uv run logomaker brand new "<Name>" --express` for the express track (a named venture that wants a package in under fifteen minutes: every gate kept, every phase shrunk, counts in each phase below), or `uv run logomaker brand new "<Working title>" --unnamed`, the only way a brand gets a naming phase; `--express` and `--unnamed` do not combine.
5. Never draw, search the web, or propose names before the brief is confirmed.

The example brand in `docs/examples/keystone/` (its `WALKTHROUGH.md` and the artifacts beside it) is the reference for each artifact's shape and for the order of the commands, never for design ideas; never edit it.

## Phase runbook

Every command prints one JSON object; read `ok`, `errors` and `warnings` and act on them. A JSON file a gate validates follows its model in `src/logomaker/schemas.py` (`Brief`, `Strategy`, `TerritoriesSpec`, `Scorecard`) or `src/logomaker/color.py` (`Tokens`); read the model first. Record each owner decision with `uv run logomaker brand decide <slug> --phase <phase> --by user --note "..."`.

`uv run logomaker brand advance <slug> --to <phase>` accepts only the next phase and re-checks the artifacts of every earlier phase, not just the current one. A refusal exits 2 with its reasons under `missing`, most naming the command that clears them; `uv run logomaker brand status <slug>` lists them without moving.

### Intake (read `reference/questionnaire.md`, `reference/strategy-frameworks.md`)
- Ask the eleven core questions one per message, in order, skipping any already answered; offer a short multiple choice where it helps (express: five questions, numbers 1, 3, 4, 7 and 11 of `reference/questionnaire.md`; infer the rest and show it in the write-back). Question 11 covers how the name is written and said, its story and any tagline.
- Infer the archetype, the personality scores (0 to 1 on the five Aaker dimensions), the industry tag (a phrase holding a cliché-list key or alias, so the audit checks the right list) and the ranked surfaces.
- Write `brands/<slug>/brief.md` (the readable write-back) and `brief.json` (`Brief`). Show the write-back, wait for the owner's correction or confirmation, and record what changed with `brand decide`.
- Gate: the owner confirms the brief. Advance to `naming` (a brand made with `--unnamed`) or `strategy`.

### Naming (read `reference/naming.md`; only for a brand made with `--unnamed`)
- Generate 15 to 25 candidates across descriptive, evocative and invented, each with meaning, sound profile, letterform note and fit score.
- Run `uv run logomaker names analyze <name>` (offline) for every candidate and `uv run logomaker names check <name>` for the top five only, one at a time. Expect `unknown` from rate limits and the 45 s deadline: report it as unknown, never as available, and re-run it later.
- Run a web knock-out for the top five (trademark registries, app stores, general web), reported with the trademark caveat (in "Conversation rules").
- Write `naming.md` with the shortlist, the checks and the knock-out findings with the caveat.
- Gate: the owner picks a name. Run `uv run logomaker brand rename <slug> --name "<Name>"` (the slug stays), record the choice and advance to `strategy`.

### Strategy (read `reference/strategy-frameworks.md`, `reference/evidence-rules.md`, `reference/logo-types.md`, `reference/cliches.md`, `reference/cautionary-tales.md`, `reference/trends.md`, `reference/color.md`)
- Look at `brands/<slug>/inspiration/` if it has images; say what you take from them.
- Search the web for the five nearest competitors and describe the category's visual uniform.
- A named venture has no naming phase, so run `uv run logomaker names check "<Name>"` once and report its domains and handles to the owner with the trademark caveat (in "Conversation rules"), `unknown` as unknown, never as available. A brand made with `--unnamed` did this in naming.
- Write `strategy.md` with the nine sections listed in `reference/process.md`, and `strategy.json` (`Strategy`) (express: all nine sections, one to three sentences each, written and approved in one message).
- Record the industry and surfaces: `uv run logomaker brand set <slug> --industry "<tag>" --surface "<first>" --surface "<second>" --surface "<third>"`.
- Gate: the owner approves. Advance to `territories`.

### Territories (read `reference/fonts.md`, `reference/color.md`, `reference/trends.md`)
- Look at `inspiration/` again for type, colour and shape cues.
- Define two or three territories (express: one territory is allowed; the full track needs two or three) in `territories/territories.json` (`TerritoriesSpec`), each with one to three catalogue families (`uv run logomaker fonts list --category "<category>"`) and two to six colours.
- Fetch every family it names with `uv run logomaker fonts fetch "<Family>"`: the board never fetches, and an uncached family exits 3.
- `uv run logomaker sheet territories <slug> --no-open`; read `territories/board.png`, then open the board for the owner.
- Gate: the owner picks one. Run `uv run logomaker brand set <slug> --territory <territory-slug> --font "wordmark=<Family>:<weight>"`, record the choice and advance to `concepts`.

### Concepts (read `reference/craft.md`, `reference/kit-api.md`, `reference/scorecard.md`, `reference/evidence-rules.md`, `reference/trends.md`, `reference/cliches.md`, `reference/logo-types.md`, `reference/critic.md`)
- Write 12 to 20 one-line ideas (express: eight to twelve ideas, three directions, two survivors, two revise rounds; the critic runs one pass) in `concepts/ideas.md`, each tagged with its route in brackets and with its motifs (the seven routes are in `reference/scorecard.md`); the ideas cover at least five routes. Strike any on the blacklist unless the brief made it the strategy; then twist it and justify it.
- Pick five to eight directions (express: three) covering at least three routes, at least three structurally different (another logo type or construction logic, not a variation), and keep at least one survivor on the sheet non-literal: at least one survivor on the sheet is non-literal or `sheet critic` and `sheet concepts` refuse. Before building each, run the obviousness probe: image-search "<motif> logo" and count, in the first twenty image results, those showing the same construction (Firecrawl image search, else Google Images in Chrome, else a plain web search; the tool goes in brackets at the end of the `query`); the count goes into the card's `probe` and caps `distinctive` (`reference/scorecard.md`). Create `concepts/NN-slug/concept.py` for each (see "Writing concept modules"). Black only: no `tokens.json` in a concept folder. A `--tokens` palette preview is throwaway; re-run `concept run` without it before `sheet concepts` or `brand advance`.
- For each: `uv run logomaker concept run <slug> NN-slug`, then read `concepts/NN-slug/renders/round-N/critique.png`. Score the ten criteria into `scorecard.json` (`Scorecard`), each with one line of evidence, with its `route` and `probe`, and write longer notes in `critique.md`, with every audit warning fixed or justified.
- Revise and rerun, at most four rounds per concept (express: two); a concept round is one `concept run` without `--no-render` (one `renders/round-N`). Kill a concept that cannot pass: `"kill": true` with a `reason`, all ten scores kept.
- Before presenting, search the web by description for look-alikes of each survivor, and run the knock-out by image (`uv run logomaker concept knockout <slug> <NN-slug>`, then Google Lens, as `reference/naming.md` says); then update `clear` in its `scorecard.json` with what you found. `sheet concepts` refuses a survivor without it recorded in `knockout.json`, fresh for the module as it is now.
- Then the blind critic (read `reference/critic.md`): `uv run logomaker sheet critic <slug> --concepts <NN-slug,...>` twice, which makes two sheets, N and M, each with its own key and its own shuffle (without `--seed` the second reshuffles by itself; an explicit `--seed` only reproduces a sheet); one Opus subagent per sheet given only the PNG path, the brief, the strategy and the three reference files it names, each writing `sheets/critic-N.pass-1.json` for its own sheet; then `uv run logomaker concept critic <slug> --sheet N --sheet M`. For every criterion where your score and the critic's differ by two or more, add a `reconciled` entry to `scorecard.json`; `sheet concepts` refuses a survivor without a fresh `critic.json` or with a disagreement left open. After a survivor's module changes, run the two sheets and the merge again over all the survivors. On the express track, one sheet, one subagent and `concept critic <slug> --sheet N`.
- With fewer than three concepts passing the gate, add directions (up to eight in all) or present fewer and tell the owner why (express: two survivors is the target; with fewer than two, add one direction). Render the 3 to 5 survivors (express: two) with `uv run logomaker sheet concepts <slug> --concepts <NN-slug>,<NN-slug>,<NN-slug> --no-open` and read `sheets/concepts.png`. The CLI refuses a concept without a fresh, rendered, passing audit and a gate-passing scorecard with its route and probe, and a sheet whose survivors all take the `object` route; fix that, never argue with it.
- Then say the Collins rule 95 preface (in "Conversation rules"), open the sheet for the owner, and ask what the owner likes in each before asking which to choose.
- Gate: the owner picks one. Run `uv run logomaker brand set <slug> --concept NN-slug`, record the likes and any steal with `brand decide`, and advance to `refinement`.

### Refinement (read `reference/craft.md`, `reference/kit-api.md`, `reference/color.md`, `reference/fonts.md`, `reference/deliverables.md`, `reference/naming.md`, `reference/cautionary-tales.md`, and, when re-scoring `final/` and running the critic's last pass, `reference/scorecard.md` with `reference/evidence-rules.md` and `reference/trends.md`, and `reference/critic.md`)
- Copy the chosen `concept.py` to `final/concept.py`; write `final/params.json` (`{}` to start).
- Work in this order, running `uv run logomaker concept run <slug> final` after each step and reading `final/renders/round-N/critique.png`: optical corrections; `small` and `favicon` tiers redrawn through `TIERS` overrides; the wordmark set in the chosen family with at most two parametric quirks, then `uv run logomaker sheet wordmark <slug> --no-open` (exit 2 if the wordmark is not a `TextShape`: keep the `TextShape` first in unions), read `sheets/wordmark-N.png`, kern the flagged pairs and re-run; lockups, and the primary lockup for the highest-ranked surface that shows a lockup, judged in the mockups that show one (the website headers, the card and the sign), never the app icon or the avatar, which draw the mark and no lockup (`uv run logomaker brand set <slug> --primary-lockup horizontal`, or `stacked`); then colour.
- Tiers: `small` draws 33 to 95 px and `favicon` 32 px and below; from 96 px up every icon draws the full symbol, so a wordmark-only concept's app icons from 96 px show its whole wordmark; avatars draw `compact` when built. For a letter-derived icon at every size, build the letter as the Mark's `symbol`; otherwise tell the owner.
- Keep brand.json's wordmark font the family and weight `final/concept.py` draws (`brand set <slug> --font "wordmark=<Family>:<weight>"`): BRAND.md's typography lists brand.json's fonts.
- Colour: write `final/tokens.json` (format in `reference/color.md`), the reverse a designed dark-context role map, never an inversion. `uv run logomaker color check brands/<slug>/final/tokens.json` is a pre-check holding only `ink` to the type thresholds; the colour gate is the rendered `concept run <slug> final` audit. Fix what either reports.
- After any change to `final/concept.py`, `params.json` or `tokens.json`, re-run `concept run <slug> final` without `--no-render` before `sheet refine`, `brand advance --to package` or `package build`; each refuses a stale audit.
- Unintended readings: read the mirrored and rotated panels of the latest `final/renders/round-N/critique.png`; record the findings in `final/knockout.md`.
- Knock-out: search the web for look-alikes by description and for conflicting marks (where: `reference/naming.md`); write the queries and findings into `final/knockout.md` with the trademark caveat. The knock-out by image comes last, after the owner approves.
- Only then present the round: `uv run logomaker sheet refine <slug> --no-open`, read `sheets/refine-N.png` and record what its colour-vision strip shows in `final/knockout.md` (rule 3 in `reference/cautionary-tales.md`), then open the sheet for the owner. At most three rounds (express: one refine sheet): a refinement round is one refine sheet shown to the owner, and only refine sheets count toward the cap (`final/` may take more `concept run` rounds); before each later round's sheet, redo the readings and the description search for what changed.
- After the last round and before `package build`, re-score `final/` into `final/scorecard.json` (`Scorecard`, one line of evidence per criterion), carrying the chosen concept's `route` and `probe` forward, or a fresh probe if the construction changed; `brand advance --to package` and `package build` refuse a final card without both.
- Then the critic's last pass: `uv run logomaker sheet critic <slug> --final`, one subagent, one pass, `uv run logomaker concept critic <slug> --sheet N`, and reconcile into `final/scorecard.json`; `brand advance --to package` and `package build` refuse without a fresh `final/critic.json`.
- Gate: the owner approves the round.
- Then, last, the knock-out by image: `uv run logomaker concept knockout <slug> final`, then Google Lens and the WIPO Global Brand Database image search, recorded in `final/knockout.json` with the description queries; `brand advance --to package` refuses without both. Any later change to `final/concept.py`, `params.json` or `tokens.json` (a colour alone) resets both searches. A skipped search (no Chrome extension) needs the owner's `knock-out skipped:` decision, recorded with `brand decide` in the phase the refusal names. Then update `clear`'s evidence in `final/scorecard.json` with the image findings; if its score now differs from the critic's by two or more, add a `reconciled` entry (`reference/critic.md`).
- Advance to `package`.

### Package (read `reference/deliverables.md`, `reference/cautionary-tales.md`)
- Write `final/rationale.md`: one paragraph, for the owner, no "represents", no construction diagrams, ratios or golden ratio. Check it against that rule before `package build`.
- `uv run logomaker package build <slug>` with the Bash timeout set to 300000, then `uv run logomaker package verify <slug>`. Any later change to `final/concept.py`, `final/params.json`, `final/tokens.json`, `final/rationale.md`, `strategy.json`, or brand.json's name, primary lockup, minimum sizes or fonts means both again; nothing else in brand.json (a `brand decide`, the phase) makes the package stale.
- Read the brand sheet PDF yourself, then `open <package>` (Finder) and `open -a "Google Chrome" <brand_sheet>`, with the absolute `package` and `brand_sheet` paths from the build's JSON.
- Gate: the owner has the folder and the sheet. Run `uv run logomaker brand advance <slug> --to done` and summarise what was delivered and where.

## Conversation rules

- Strategy before any drawing. Silhouette in black before any colour. Knock-out search before presenting; the one exception is the final image knock-out of `final/`, which runs after the owner approves the last round.
- Ask one question per message, with a short multiple choice where it helps. Write back your understanding at the end of intake and wait.
- Never present a concept that failed a hard audit or scored below 4 on the three gating criteria (appropriate, simple, legible).
- Never show a mark alone on a blank page; always through a sheet with mockups.
- Before the first concept presentation, say the Collins rule 95 preface from `reference/process.md`, word for word:
  > "New ideas can be fragile because they are unfamiliar. You may not like something you see here, but you are not allowed to say that for now... find something, anything, you like in every idea."
- Never blend concepts. Pick one; a detail from another may be noted as a steal and recorded with `brand decide`.
- Caps: four revise rounds per concept (a round is one `concept run` without `--no-render`) and three refinement rounds (a round is one refine sheet shown to the owner; `final/` may take more render rounds). On the express track the caps are two revise rounds and one refine sheet. If stuck, say so and offer to go back to concepts.
- Tell unfamiliarity from a real flaw (`reference/process.md` sorts them; `reference/cautionary-tales.md` has the cases): on a negative first reaction, ask one probing question (what reads wrong, at what size, in which mockup) before changing anything.
- If the owner asks for a motif on the blacklist, show the finding from `reference/cliches.md` once, offer a twist, and record their decision with `brand decide`. Do not refuse and do not silently comply.
- When `brands/<slug>/inspiration/` holds images, view them during strategy and territories and say what you took from them.
- Rationales are one paragraph, written for the owner, without the word "represents", construction diagrams, ratios or the golden ratio.
- Trademark and look-alike checks are your web searches, always reported with the caveat from `reference/naming.md`, word for word:
  > "These checks are a knock-out only, not legal clearance: they can surface an obvious conflict but cannot prove there is none, so have a trademark attorney run a clearance search before you file the name or spend money on it."

## Reading renders

- Read every PNG with the Read tool before deciding or showing anything. The JSON gives its path: `critique.critique_png` from `concept run`, `board_png` from `sheet territories`, `sheet_png` from `sheet concepts` and `sheet refine`.
- Run the owner sheets with `--no-open`, read the PNG, then `open` the HTML (`board_html` or `sheet_html`) for the owner.
- Look for: the silhouette at 16 px, merged counters at 32 px, a wobble in the mirrored panel, an unintended reading in the rotated panel, and whether the one-colour panel still has a hierarchy.
- The concept sheet's avatar mockup draws the `compact` tier when the concept builds one, as the avatar exports do, else the tier for its 80 px (`small` when built); the refine sheet's tier row shows `compact` too.

## Writing concept modules

- Follow `reference/kit-api.md`. Build on the 1000-unit grid with primitives, booleans and `stroke`. Keep the symbol under 100 anchors (on-curve nodes; a circle has 4): the audit warns above 100 and fails above 150 unless `META` sets `allow_complex=True` with a `complex_reason`.
- Set type with `text(...)` and `glyph(...)` from a cached family. If the family is not cached (exit 3), run `uv run logomaker fonts fetch "<Family>"`; never substitute another family.
- Never write SVG by hand and never edit `build/`, `renders/` or `audit.json`; the CLI owns them.
- Explore only through concept modules and `concept run` (`--no-render` while iterating), never in an ad-hoc rendering script: it bypasses the audit and the settings' allow rule for `uv run logomaker`.
- Tiers are parameter overrides in `TIERS`; redraw small sizes by thickening strokes and opening counters, not by scaling.
- A module whose forms are organic sets `snap="free"` in `META` instead of passing `free=True` to every primitive.
- Write `META.idea` as one sentence without "represents", and name motifs plainly in `META.motifs`; the audit checks them against the blacklist.

## Parallel concepts with subagents

For four or more directions you may dispatch one subagent per direction with the Agent tool. Set `model` explicitly to `opus` or cheaper; never leave it to inherit the session's model. First run `uv run logomaker fonts fetch "<Family>"` for every family the directions use. Give each subagent `brief.md`, `strategy.md`, the chosen territory entry, the one-line idea it owns and its `NN-slug` folder, `reference/kit-api.md`, `reference/craft.md` and the cached families. Instruct it to write only `concepts/NN-slug/concept.py`, to iterate with `uv run logomaker concept run <slug> NN-slug --no-render` until the audit's `ok` is true, and on exit 3 for a font to run `uv run logomaker fonts fetch "<Family>"` and never substitute another family.

`--no-render` is for iteration only: it skips the raster checks and the critique sheet, and `sheet concepts` and the phase gates refuse its audit. When the subagents finish, run `uv run logomaker concept run <slug> NN-slug` for each yourself, read every critique sheet and score each concept; subagents do not score or present.

The blind critic is a subagent too (`reference/critic.md`, "Dispatch"). Set `model` explicitly to `opus` or cheaper; never leave it to inherit the session's model. For the survivors, send two Agent calls in one message, each with `model: "opus"` and its own critic sheet; for `final/`, one call. On the express track the survivors get one critic call, not two. Give each critic the prompt in `reference/critic.md` verbatim and nothing else: never a key, a scorecard, `ideas.md` or a `concept.py`.

## Resuming

`uv run logomaker brand status <slug>` reports the phase, `next` and what is `missing`. Read the phase's artifacts before asking anything, check `track` in brand.json and use that track's counts, then continue the runbook from that phase; if `missing` names `brief.json`, rework the brief with `reference/questionnaire.md` first.

In the `concepts` phase, score every concept that has no `scorecard.json` from its latest critique before calling `sheet concepts`, which refuses an unscored concept. When a survivor has no fresh, rendered, passing audit (missing, stale, made with `--no-render`, or failing; an interrupted subagent leaves a `--no-render` audit and no critique sheet), first run `uv run logomaker concept run <slug> NN-slug` without `--no-render`, fixing the module if it fails, then score from its critique.

## When the CLI fails

Exit codes are defined once, in the project's `CLAUDE.md`. What to do for each:

- Exit 2: read `errors` and fix the module, the JSON or the command; never retry verbatim. A `brand advance` refusal lists its reasons under `missing`.
- Exit 3: say what failed (Chrome, the network, a font, or the disk: a file that cannot be written, or a package swap, whose message says where each package is now) and the command that fixes it, such as `fonts fetch` for a font. `setup --check` also exits 3 for a missing Python module: run `uv sync`.
- Exit 4: `package verify` found a problem (read `package/verify.json`, fix, rebuild), or `package build` made a blank render (change the mark or the tokens, never rebuild verbatim).
- A `traceback` in the payload that passes through the brand's own `concept.py` (under `brands/`) means the module raised, perhaps inside a kit call it made: read it and fix the module. One that never passes through it is a CLI bug in `src/logomaker/`: report it to the owner instead of working around it.
- When a message says to delete `registry/brands.json` (the index is malformed, or a valid brand is missing from it), that is the one exception to never editing `registry/`: tell the owner, delete the file, then run `uv run logomaker brand list`, which rebuilds it from `brands/*/brand.json`.

## Done checklist

- `package/verify.json` has `ok: true`, and `uv run logomaker brand status <slug>` shows the phase `done`.
- `BRAND.md`, `brand-sheet.pdf`, `README.md` and `rationale.md` are in `package/`.
- The owner has seen the brand sheet and knows where the files are.
