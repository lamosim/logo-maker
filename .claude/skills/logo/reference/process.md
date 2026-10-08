# Process

Read this when: starting or resuming a brand, before every `brand advance`, and before showing the owner anything.

Agencies run one stable sequence: "research before decisions, strategy before design, design before rollout"; "skipping straight to visuals is the most common cause of rebrand failure" [01 §1.1]. This workflow runs seven working phases and a closing state. Each phase ends at a gate the owner passes and the CLI checks [spec §3.2] [code].

## Phases and gates

| Phase | Claude does | CLI | Artifacts | Gate |
|---|---|---|---|---|
| `intake` | Asks the core questions one per message, infers archetype, personality, industry and surfaces, writes back | `brand new "<Name>"` (`--unnamed` for a working title), `brand decide` | `brief.md`, `brief.json` | Owner confirms the brief |
| `naming`, only for a brand made with `--unnamed` | 15 to 25 candidates across descriptive, evocative and invented; analysis, availability and a web knock-out of the shortlist | `names analyze`, `names check`, `brand rename --name` | `naming.md` | Owner picks a name |
| `strategy` | Positioning, archetype, personality, the one idea, ladder, category audit, feature targets, logo type, constraints | `brand set --industry --surface` | `strategy.md`, `strategy.json` | Owner approves |
| `territories` | Two or three visual territories | `fonts fetch`, `sheet territories`, `brand set --territory --font` | `territories/territories.json`, `board.html`, `board.png` | Owner picks one |
| `concepts` | 12 to 20 ideas tagged by route; the obviousness probe per direction; 5 to 8 directions as black-only concept modules; critique, score, revise or kill; 3 to 5 survivors; the blind critic's two passes, reconciled | `concept run <slug> <NN-slug>`, `concept knockout`, `sheet critic --concepts`, `concept critic --sheet`, `sheet concepts --concepts`, `brand set --concept` | `concepts/ideas.md`, `concepts/NN-slug/` with `knockout.json`, `sheets/concepts.html` | Owner picks one; no blending |
| `refinement` | Optical corrections, small tiers, wordmark quirk, lockups, colour, reverse, unintended readings, knock-out, the critic's last pass | `concept run <slug> final`, `concept knockout`, `sheet critic --final`, `concept critic --sheet`, `color ramp`, `color check`, `brand set --primary-lockup`, `sheet refine` | `final/` with its module, `params.json`, `tokens.json`, `knockout.md`, `knockout.json`; `sheets/refine-N.html` | Owner approves after one to three rounds |
| `package` | Writes `final/rationale.md`, builds, verifies, reads the brand sheet | `package build` (Bash timeout 300000), `package verify` | `package/` with `manifest.json`, `verify.json`, `BRAND.md`, `brand-sheet.pdf`, `README.md` | Owner has the folder and the sheet |
| `done` | Summarises what was delivered and where | `brand advance <slug> --to done` | the registry entry at `done` | none: the brand is finished |

Moving between phases [code]:

- `uv run logomaker brand advance <slug> --to <phase>` accepts only the next phase. `intake` leads to `naming` when the brand needs a name, otherwise to `strategy`.
- It re-checks every earlier phase's artifacts too. A refusal exits 2 and lists the reasons under `missing`, most ending with the command that clears them.
- `uv run logomaker brand status <slug>` shows the phase, `next` and the same `missing` list without moving anything. Run it first when resuming.
- `uv run logomaker brand decide <slug> --phase <phase> --by user --note "..."` logs each owner decision in brand.json, for the rationale and resuming.

## Artifacts each phase must contain

What `brand advance` checks, phase by phase, as `registry.PHASE_CHECKS` implements it [code]. Every JSON shape has one source: `src/logomaker/schemas.py` holds `Brief`, `Strategy`, `TerritoriesSpec` and `Scorecard`, and `src/logomaker/color.py` holds `Tokens`. Read the model before writing a file a gate validates.

- `intake`: `brief.md` exists; `brief.json` validates as `Brief` (at least three adjective pairs, at least one surface; the field list is in questionnaire.md).
- `naming`: checked only when leaving `naming`, and only that `naming.md` exists. Advancing to `strategy` while the brand still needs a name is refused until `brand rename <slug> --name "<Name>"`.
- `strategy`: `strategy.md` exists; `strategy.json` validates as `Strategy` (at least three ladder rungs, a full set of feature targets, `logo_type` one of the seven values in logo-types.md).
- `territories`: `territories/territories.json` validates as `TerritoriesSpec` (two or three territories with unique, slug-shaped slugs; one to three fonts and two to six colours each) and contains the territory chosen with `brand set --territory`.
- `concepts`: a concept chosen with `brand set --concept <NN-slug>`; its `concept.py`; its `scorecard.json`, valid, with route and probe, and passing the gate in scorecard.md; its `audit.json`. When leaving `concepts`, that audit must be fresh (its fingerprint matches the files now), rendered (not `--no-render`) and ok, and its `critic.json` fresh, with every disagreement reconciled (critic.md), and its `knockout.json` fresh, the image search done or skipped by the owner's decision (naming.md). Later phases need only the audit present and valid JSON and the scorecard passing: `final/` is what ships.
- `refinement`: `final/concept.py`; `final/params.json` (`{}` is enough); `final/tokens.json`, valid as `Tokens`; `final/audit.json`, fresh, rendered and ok; `final/scorecard.json` with route and probe; `final/critic.json`, fresh, and the scorecard reconciled; then `final/knockout.json`, fresh, with the image and WIPO searches each done or skipped by the owner's decision.
- `package`, checked by `--to done`: `package/verify.json` reports ok against the current inputs fingerprint.

Freshness [code]:

- An audit's fingerprint covers `concept.py`, `params.json`, `tokens.json`, the brand's industry (brand.json's and brief.json's), its minimum sizes and `assets/cliches.json`. After any change, re-run `uv run logomaker concept run <slug> <NN-slug or final>` without `--no-render` before `sheet concepts`, `sheet refine`, `brand advance` or `package build`.
- `concept knockout` stamps that fingerprint into `knockout.json`; after a change, re-running it resets the searches.
- The package's fingerprint covers `final/concept.py`, `params.json`, `tokens.json` and `rationale.md`, `final/knockout.json` when present, `strategy.json`, and brand.json's name, primary lockup, minimum sizes and fonts. Any change after a build means `package build`, then `package verify`, again.
- `package build` also refuses without `final/rationale.md`, without a fresh, rendered, passing final audit, or without a fresh `final/critic.json` and a `final/scorecard.json` reconciled with it (critic.md).

What no gate reads, and Claude still owes:

- `strategy.md` with all nine sections of spec §4.3: (1) positioning, the "only" statement and a Moore-format statement; (2) archetype, primary and secondary, each with its row from strategy-frameworks.md; (3) personality, the five Aaker scores with one sentence each; (4) the one idea in one sentence; (5) the adjective ladder; (6) the category audit: the uniform's type classes, colours and motifs from cliches.md and a web look at the five nearest competitors, what to avoid and what is free to own; (7) feature targets from evidence-rules.md; (8) the logo-type decision; (9) constraints: minimum sizes, one-colour use, surfaces, scripts [spec §4.3].
- Congruence. No CLI check reads `strategy.json`'s `targets`; scorecard criterion 9 is Claude's judgment of shape, weight, colour, type and name sound against them, written into the evidence [code].
- `critique.md` per concept: notes longer than the line of evidence per criterion in `scorecard.json`, and every audit warning either fixed or justified [spec §8.1].
- `final/knockout.md`: the look-alike and trademark queries and findings, with the caveat from naming.md [spec §4.6].

## Agency rules

1. Strategy before style. Write the one idea before drawing; every direction traces back to it. Koto built Bolt on "Shockingly Simple", from a 50-millisecond checkout; Mozilla's identity carried "Reclaim the Internet" [01 §1.1, §3 rule 1]. Here: no concept module before `strategy.json` validates.
2. Silhouette before colour. CGH: "We don't even touch colour until we've found a distinctive own-able silhouette that also feels appropriate" [01 §1.1, §3 rule 5]. Here: concepts are black only; `tokens.json` arrives in refinement.
3. Knock-out before presenting. CGH runs a trademark knock-out on every option before the meeting, otherwise "this whole exercise is meaningless"; when Meta launched its infinity M, LogoLounge counted 1,200+ infinity logos and a near-identical 2015 mark surfaced within days [01 §1.1, §2, §3 rule 8]. Here: a web knock-out in naming and refinement, and one by image of every survivor and of `final/`, always with the caveat.
4. Never a blank page. The Armani Exchange mark was rejected when shown "between meetings in a rush on a white piece of paper" and approved when re-shown in ads, storefronts and billboards [01 §1.1, §3 rule 11]. Here: the owner sees marks only through `sheet concepts` and `sheet refine`.
5. Test recognition, not likability. Mastercard dropped its name once 81% recognised the symbol without it; Max chose blue as "the most liked color, universally" and reverted within two years [01 §1.1, §2, §3 rule 13] [05 §2]. Here: ask what reads, and at what size, not what pleases.
6. Do not over-explain. Verizon's "Veritas and Horizon", Kenvue's rectangle for "scientific precision", Kia's "rhythmical, unbroken line" and Pepsi's 27-page "Breathtaking" document did not survive the public; "the less they say, the better" [01 §2, §3 rule 9] [05 §2]. Here: a one-paragraph rationale, no "represents", no construction diagrams.
7. Explore wide, then converge hard. CGH: "Oftentimes there are thousands of sketches leading to a single design"; Collins rule 71: "Never create and edit at the same time... Quantity is more important than quality at the start" [01 §1.1, §3 rule 15]. Here: 12 to 20 ideas, 5 to 8 directions, 3 to 5 survivors.
8. Design the system, not the logo. Smith & Diction: "A brand move is literally everything except your logo"; Mozilla's system flexes "Grassroots to Government" [01 §1.1, §3 rule 14]. Here: tiers, lockups, colour roles and the reverse count in every score (criterion 10).
9. Change the logo last. Haviv: "change everything you need to change before you change the logo"; Coca-Cola's 2026 system kept its logo [01 §1.1, §3 rule 16]. For a new venture: settle the name and the strategy before the mark.
10. Never launch into a vacuum. Jaguar revealed its identity a year before any product and the internet filled the gap [01 §2, §3 rule 17] [05 §2]. Here: advise launching the mark with the product, and planning the introduction, as the University of New Hampshire did at a hockey game [01 §1.1].

## Presentation protocol

1. Before the first concept sheet, say the Collins rule 95 preface, word for word (canonical wording; SKILL.md quotes this):

   > "New ideas can be fragile because they are unfamiliar. You may not like something you see here, but you are not allowed to say that for now... find something, anything, you like in every idea."

   Collins pairs it with banning devil's advocates from the first presentation [01 §1.1, §4].
2. Show only fully vetted options, each in context, so that the owner "can literally pick any of the options" (CGH) [01 §1.1]. `sheet concepts` refuses a concept without a fresh, rendered, passing audit, a gate-passing scorecard and a fresh critic card the scorecard is reconciled with [code].
3. Remember Armani Exchange: rejected on a white page, approved in ads and storefronts. Walk the owner through the mockups before the strips [01 §1.1].
4. Ask "what do you like in each?" before "which one?". Record the likes with `brand decide`; they become refinement notes or steals, never a blend [spec §3.3].
5. On a negative first reaction, ask one probing question before changing anything: what reads wrong, at what size, in which mockup [spec §3.3].
6. Sort the answer:
   - Unfamiliarity: "it feels strange", "not what I pictured", with no size or mockup named. Hold the design. Airbnb's Bélo and Instagram's glyph were mocked at launch and then accepted; "the test is month twelve, provided the mark is sound" [05 §2] [01 §3 rule 12].
   - Flaw: a misread name (26% read Kia as "KN"), an unintended reading (the University of California monogram), a failure at a named size, or a lost asset (Cracker Barrel's Uncle Herschel). Fix it, or go back to concepts [01 §2] [05 §2].
7. Judge "what works", not "what one likes or dislikes" (Haviv), and give every option a written rationale, as every Pentagram presentation Bierut has given does [01 §4].

## Sources

01 §1.1 (the phase sequence, presenting, CGH, Collins, Haviv), §2 (Jaguar, Kia, Meta, Max, Mastercard, Verizon, Kenvue, Cracker Barrel), §3 rules 1, 5, 8, 9, 11 to 17, §4 (judging criteria, Collins rules 71 and 95); 05 §2 (cautionary tales); spec §3.1 to §3.3, §4.3, §4.6, §8.1; code: `registry.PHASE_CHECKS`, `registry.prerequisites`, `registry.audit_problems`, `schemas.py`, `audit.concept_fingerprint`, `export_docs.inputs_fingerprint`.
