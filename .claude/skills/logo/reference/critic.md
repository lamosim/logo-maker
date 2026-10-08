# Critic

Read this when: dispatching the blind critic after scoring the survivors (phase 4), reconciling its card with yours, and running its last pass on `final/` before `package build` (phase 5).

The critic is a second designer who sees the work for the first time. LLM judges prefer what they wrote and what comes first on the page [spec 2026-10-08 §2], so the critic sees neither your scores nor your reasons, and the sheet it reads is lettered in a shuffled order, twice [spec 2026-10-08 §3.1].

## What the critic sees

- `sheets/critic-N.png` from `uv run logomaker sheet critic <slug> --concepts <a,b,c>`: each survivor's lockups, ladder, mirrored and rotated panels, one-colour panels and mockups under a letter, "Concept A", "Concept B" and so on. No slug, no idea, no score [code].
- `brief.md`, `strategy.md`, `reference/scorecard.md`, `reference/evidence-rules.md` and `reference/trends.md`.
- Nothing else: not `ideas.md`, not a `concept.py`, not `critique.md`, not `scorecard.json`, not the key. It never searches the web and never lists or reads the brand folder.

How the sheet is made [code]:

- Each call takes the next round number N and writes `sheets/critic-N.html`, `sheets/critic-N.png` and `sheets/critic-N.key.json`. It never opens the sheet in the browser.
- The order of the letters is a shuffle seeded with `--seed` (default: N). Two calls over the same concepts give two sheets, N and N+1, each with its own key and a different lettering: with the default seed, when a shuffle would letter two or more concepts exactly as the latest sheet of the same concepts did, the seed steps up by one until it does not, and the key and the JSON result record the seed used. An explicit `--seed` is used as given, to reproduce a sheet; leave it out for a critic pass.
- The key holds the round, the seed, the letter-to-concept map and each concept's fingerprint at that moment. Only you read it, and only to check; the merge reads it for you.
- `sheet critic` refuses a survivor that is not vetted: it needs a fresh, rendered, passing audit and a gate-passing `scorecard.json`, the same rule as `sheet concepts`, checked before Chrome starts. It letters at most eight concepts (`critic.LETTERS`, A to H).
- `uv run logomaker sheet critic <slug> --final` letters `final/` alone as Concept A. It needs a fresh, rendered, passing final audit, and takes no `--concepts`.

## What the critic returns

`sheets/critic-N.pass-K.json`, validating as `critic.CriticPass` [code]: one file per critic run, N the sheet it read, K the pass number on that sheet (1 when one critic reads the sheet). The two parts:

- `cards`: one entry per letter on the sheet, no more and no fewer. Each has `scores`, all ten criteria of scorecard.md as whole numbers from 1 to 5, and `evidence`, one line per criterion in the rubric's terms (a criterion may go without a line, but the brief asks for all ten).
- `pairs`: for every two letters, which concept the critic would show the owner first, judged twice, once with each letter named first. Each entry has `first`, `second`, `prefer` (the letter of `first`, of `second`, or `"tie"`) and `why`. A pair given in one order only is refused; a pair left out counts as a tie. With one letter, as on the final sheet, `pairs` is empty.

The critic never searches the web, so it scores `clear` from the marks it already knows in the category rather than by a search, and its evidence line for `clear` says so, beginning "unsearched:" (the dispatch prompt asks for it). The search by description stays your job.

An example for a two-letter sheet, shortened to two evidence lines:

```json
{
  "cards": {
    "A": {"scores": {"appropriate": 4, "distinctive": 3, "simple": 5, "legible": 4, "adaptable": 4,
                     "timeless": 4, "universal": 4, "clear": 3, "congruent": 4, "system": 3},
          "evidence": {"distinctive": "an arch over a letter; two of the brief's competitors use arches",
                       "simple": "one arch and one stem; drawable from memory"}},
    "B": {"scores": {"appropriate": 3, "distinctive": 4, "simple": 3, "legible": 3, "adaptable": 3,
                     "timeless": 4, "universal": 4, "clear": 4, "congruent": 3, "system": 4},
          "evidence": {"legible": "the inner cut closes at the 24 px rung",
                       "distinctive": "no stock shape; the jaw reads as this brand's own"}}
  },
  "pairs": [
    {"first": "A", "second": "B", "prefer": "A", "why": "A survives the ladder; B closes at 24 px"},
    {"first": "B", "second": "A", "prefer": "A", "why": "A holds at the favicon size"}
  ]
}
```

`uv run logomaker concept critic <slug> --sheet N --sheet M` merges the passes of both sheets into `critic.json` in each concept's folder (`final/critic.json` for a final sheet), validating as `schemas.CriticCard` [code] [spec 2026-10-08 §3.2]:

- Each pass is checked against its own sheet's key, then translated from letters to concepts. The sheets must letter the same concepts, with the same fingerprints; a concept that changed between the two sheets is refused ("run sheet critic again"), and so is a sheet with no pass file.
- `scores`: the mean of every pass per criterion, rounded half up (3.5 is 4).
- `evidence`: every pass's line per criterion, as a list.
- `preferred_over`: the concepts this one beat in every verdict of every pass and both orders, every pass having judged the pair; `tied_with`: the rest, including a concept that beat it.
- `sheet`: the highest round merged; `passes`: the number of pass files merged; `fingerprint`: the concept's fingerprint when the sheets were made, so any later change to `concept.py`, `params.json`, `tokens.json`, the industry, the minimum sizes or the cliché data makes the card stale.
- Nothing is written until every pass validates. One `--sheet` alone also works: one sheet, one or more passes.

## Reconciliation

You score first, before the critic sheet exists; the critic never sees your card. After the merge, compare the two cards criterion by criterion [spec 2026-10-08 §3.3]:

- Where your score and the critic's differ by `critic.DISAGREEMENT` (2) or more, add a `reconciled` entry to your `scorecard.json`: `{"<criterion>": "<one line: whose score stands and why>"}`. A difference of one needs nothing.
- A `clear` gap of two is expected, since your score rests on the web search by description (the knock-out, scorecard.md) and the critic's on memory alone: reconcile it by citing that search, what you searched for and what it found.
- You may change your own score after reading the critic's evidence; then say so in the entry. You never edit `critic.json`: the merge writes it, and the gates read it as the critic left it.
- The gate criteria stay yours. The critic informs the gate; it does not own it. A critic's 2 on `legible` against your 4 is a reason to look again at the ladder, then to lower your score or say in one line why 4 stands.
- `uv run logomaker sheet concepts <slug> --concepts <a,b,c>` refuses a survivor whose `critic.json` is missing, invalid or stale, or whose scorecard leaves a disagreement of two or more without a `reconciled` entry; each refusal names the command that clears it. `brand advance --to refinement` applies the same rule to the chosen concept [code].
- The concept sheet shows two totals per survivor, "designer 43 / critic 38 (2 passes)", and under the preface the critic's order: concepts grouped by how many they beat, best first, `>` between groups and `=` within. It prints the order only when every survivor's card comes from one merge; otherwise it prints "critic's order: not comparable; the cards come from different critic sheets (one order: logomaker sheet critic <slug> --concepts <a,b,c>)" [code].
- After a concept module changes, its card is stale. Refresh it with the other survivors, so the order stays comparable: `sheet critic` twice again over all the survivors, one critic per sheet, then `concept critic` with both sheets. A stale card's refusal names this command, with every concept its last critic sheet lettered; when that sheet's key is gone, it names a one-concept `sheet critic`, which clears the gate too but leaves the order not comparable.

The final pass [spec 2026-10-08 §3.3]:

- After the last refinement round, re-score `final/` into `final/scorecard.json`, then run `uv run logomaker sheet critic <slug> --final`, one critic, one pass, and `uv run logomaker concept critic <slug> --sheet N`, which writes `final/critic.json`.
- Reconcile into `final/scorecard.json` by the same rule. `brand advance --to package` and `package build` refuse without a fresh `final/critic.json` and a `final/scorecard.json` with every disagreement reconciled (`registry.require_final_critic`) [code].

## Dispatch

1. Run `uv run logomaker sheet critic <slug> --concepts <a,b,c>` twice; the second sheet gets a different shuffle by itself. Read `round` from each JSON result: these are N and M. Never pass a key to a critic.
2. Dispatch two critics in one message: two Agent calls, each with `model: "opus"` set explicitly, never inherited from the session. Each gets its own sheet. For the final pass, one call with the `--final` sheet.
3. Give each subagent this prompt verbatim, with the paths filled in:

> You are the second designer in the studio, seeing this brand's logo work for the first time. Read `brands/<slug>/brief.md`, `brands/<slug>/strategy.md`, `.claude/skills/logo/reference/scorecard.md`, `.claude/skills/logo/reference/evidence-rules.md` and `.claude/skills/logo/reference/trends.md`, then look at `brands/<slug>/sheets/critic-N.png` with the Read tool. The letters on the sheet are in an arbitrary order; do not let position decide anything. Score every lettered concept on the ten criteria of scorecard.md, 1 to 5 by its rubric, with one line of evidence each that names what you see on the sheet. Score `clear` from the marks you already know in the category, and begin its evidence line with "unsearched:". Then, for every two letters, say which you would show the owner first and why, judging each pair twice, once with each letter named first. Write one JSON object to `brands/<slug>/sheets/critic-N.pass-1.json` with `cards` (letter to `scores` and `evidence`) and `pairs` (`first`, `second`, `prefer` as a letter or "tie", `why`). Read no other file, do not list or open the brand folder, and do not search the web. Reply with the file path only.

4. When both have written, run `uv run logomaker concept critic <slug> --sheet N --sheet M`. On exit 2, read `errors`: a pass that scores the wrong letters or judges a pair one way only goes back to that critic with the message, never edited by hand.
5. Read both cards against yours and reconcile, then run `sheet concepts`.

## Sources

spec 2026-10-08 §2, §3.1 to §3.4; code: `critic.py` (`CriticPass`, `PassCard`, `Pair`, `Key`, `LETTERS`, `DISAGREEMENT`, `merge`, `write_cards`, `preference_line`), `sheets.critic_sheet`, `registry.vetted_scorecard`, `registry.require_final_critic`.
