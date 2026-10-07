# Scorecard

Read this when: scoring a concept after reading its critique sheet (phase 4), before running `sheet concepts`, and when re-scoring `final/` after the last refinement round, before `package build`.

The ten criteria merge the judging lists the research found: Haviv's three (appropriate, distinctive and memorable, simple), Rand's seven questions, Bierut's written rationale, Romaniuk's distinctiveness and the composite scorecard derived from them [01 §4] [05 §5.1] [spec §8.2]. Score only after reading the critique PNG with the Read tool; write the numbers in scorecard.json, each with one line of evidence, and longer notes in critique.md.

## Ten criteria

| # | Key | Question | Evidence that counts |
|---|---|---|---|
| 1 | `appropriate` | Does it carry the one idea and fit the archetype, without over-explaining? Haviv: "Logos are identification, not communication" [05 §5.1] | the idea is visible without a story; the archetype row matches; nothing needs a caption |
| 2 | `distinctive` | Does it stand apart from the category uniform and the five nearest competitors? | none of the five could own it; no blacklisted motif, or one twisted and justified; it survives the phone mockup's shelf test |
| 3 | `simple` | Can it be drawn from memory, with one dominant silhouette? "Understandable in just a few seconds" [01 §4] | it can be described in one sentence; few parts; anchors well under 100 |
| 4 | `legible` | Does the name read at a glance, and does the mark hold at 16 px and 6 mm? | the 16 to 32 px ladder; the audit's `text_legibility`, `min_feature` and `one_colour_merge` lines; the Kia test |
| 5 | `adaptable` | Does it work in one colour, reversed, as an app icon, and ready to move? | the white-on-black and one-colour panels; the phone and avatar mockups; `small` and `favicon` tiers drawn |
| 6 | `timeless` | Is it free of trend shapes from trends.md, or are they justified? | no "avoid" item; any "use carefully" item has a reason in strategy.md |
| 7 | `universal` | Are the mirrored and rotated panels free of unintended readings, and the brief's cultural notes respected? | both panels read clean; nothing in `cultural` is touched |
| 8 | `clear` | Has the knock-out found no look-alike or conflicting mark? | a web search by description before presenting (CGH knock-out every option first) [01 §1.1]; `final/knockout.md` in refinement |
| 9 | `congruent` | Do shape, weight, colour and type match `strategy.json`'s targets and the name's sound? | each target compared in a line; no CLI check reads the targets, so this is Claude's judgment [code] |
| 10 | `system` | Do lockups, tiers and variants derive cleanly, and does a one-paragraph rationale exist? | horizontal, stacked, symbol, small and favicon outputs all built without tier warnings; a rationale draft in critique.md |

## Scoring rubric

Whole numbers 1 to 5; 2 and 4 sit between the anchors below [synthesis from 01 §4 and spec §8.2].

| Criterion | 1 | 3 | 5 |
|---|---|---|---|
| appropriate | contradicts the idea or the archetype, or needs a paragraph to explain | fits the archetype; the idea needs a sentence | the idea reads at once; the mark feels inevitable (Collins rule 34) |
| distinctive | a category cue or a near copy of a competitor | different in detail, generic in silhouette | an ownable silhouette no competitor could claim |
| simple | many parts; cannot be redrawn from memory | redrawable with effort; two competing shapes | one dominant shape, drawable in seconds |
| legible | the name misreads, or the mark is mush at 32 px | reads at 32 px, strains at 16 px | reads at a glance at 16 px and in the 6 mm print size |
| adaptable | fails in one colour or reversed | works in one colour; the icon needs a redraw | works in one colour, reversed, as an icon, with a clear motion logic |
| timeless | built on an "avoid" trend | carries a "use carefully" trend with a reason | no trend shape; would have read the same ten years ago |
| universal | an unintended reading in a panel, or a cultural conflict | a faint secondary reading | nothing reads but the mark in any panel |
| clear | a close look-alike or registered conflict found | similar marks in other categories | nothing similar found by description |
| congruent | contradicts three or more targets or the name's sound | matches most targets | matches every target and the name's sound |
| system | tiers or lockups missing or broken | tiers built, lockups uneven | every lockup, tier and variant derives cleanly, rationale written |

## Gate

- Gate criteria: `appropriate`, `simple` and `legible` must each be 4 or more, and `kill` must be false (`schemas.GATE`, `GATE_MIN = 4`) [code] [spec §8.2].
- No hard audit failures: the concept's `audit.json` must be fresh, rendered (not `--no-render`) and ok [code].
- `uv run logomaker sheet concepts <slug> --concepts <a,b,c>` refuses any concept that misses either condition and names the command that clears it; `brand advance --to refinement` checks the chosen concept the same way [code].
- Fix it or kill it: at most four revise rounds per concept [spec §3.3]. A killed card sets `kill` to true, gives a `reason`, and still carries all ten scores, because the model requires them [code].
- The other seven criteria do not block the sheet. A score of 1 or 2 on any of them goes into critique.md with its reason, and into what you tell the owner [synthesis].
- The total out of 50 is shown beside each survivor on the concept sheet; it ranks survivors and never overrides a failed gate [code].
- The audit's warnings are not scores: each is fixed or justified in critique.md [spec §8.1].

## scorecard.json format

`<concept>/scorecard.json` validates as `schemas.Scorecard` in `src/logomaker/schemas.py` [code]: `scores` holds all ten keys as whole numbers from 1 to 5, `evidence` maps criteria to a line each, `kill` is true or false, `reason` is text. A passing card:

```json
{
  "scores": {"appropriate": 4, "distinctive": 4, "simple": 5, "legible": 4, "adaptable": 4,
             "timeless": 4, "universal": 5, "clear": 3, "congruent": 4, "system": 4},
  "evidence": {
    "appropriate": "the O reads as a socket at once; Ostrom makes tools",
    "distinctive": "no competitor among the five uses a letter as the tool end",
    "simple": "one oval, one square hole; drawable in two strokes",
    "legible": "the square stays open at 16 px; Ostrom reads at 120 px wide",
    "clear": "description search found no socket-O mark yet; full knock-out in refinement"
  },
  "kill": false,
  "reason": ""
}
```

`final/scorecard.json`, the re-score of the final mark after the last refinement round and before `package build`, takes the same format; no gate reads it [code].

A killed card keeps every score:

```json
{
  "scores": {"appropriate": 3, "distinctive": 2, "simple": 4, "legible": 2, "adaptable": 3,
             "timeless": 3, "universal": 4, "clear": 3, "congruent": 3, "system": 3},
  "evidence": {"legible": "the counters close at 24 px after four rounds"},
  "kill": true,
  "reason": "cannot pass legible within four rounds"
}
```

## Sources

01 §4 (Haviv's three criteria, Rand's seven questions, Bierut, Collins rule 34, Romaniuk's grid, Interbrand, the composite scorecard), §1.1 (CGH's knock-out before presenting); 05 §5.1 (the masters' tests); spec §3.3, §8.1, §8.2; code: `schemas.Scorecard`, `schemas.CRITERIA`, `schemas.GATE`, `schemas.GATE_MIN`, `registry.passing_scorecard`, `sheets.concepts_sheet`.
