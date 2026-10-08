# Questionnaire

Read this when: running intake (phase 0), and resuming a brand whose brief.json is missing or fails validation.

Ask one question per message, in this order, skipping any the owner has already answered; offer a short multiple choice where it helps [spec §3.3, §4.1]. Open questions beat "what colour do you want" (Logo Geek: "Is there a unique story behind your business or name?", "What 5 words best describe your company?") [01 §1.1].

## Core questions

| # | Question | Why | A good answer |
|---|---|---|---|
| 1 | What does the business do, for whom, and what problem does it solve? | `business`, `audience`, `problem`; the industry tag | one sentence each, with a concrete customer |
| 2 | If there were one idea the logo could carry, what would it be? | Haviv's forcing question; `one_idea` [01 §1.1] | one sentence, an idea not a picture: "cover for the day it pours", not "an umbrella" |
| 3 | Finish truthfully: "We are the only ___ that ___ for ___ who ___." | `onliness`; the difference the mark must own [05 §3.1] | true and checkable; a blank slot means the brief is premature |
| 4 | Three to five adjectives, each with its unwanted neighbour ("premium but not aloof"). | `adjectives`; personality scores; the ladder [05 §3.5] | at least three pairs; the "not" is as specific as the adjective |
| 5 | If the brand were a person at a dinner party, who are they and how do they talk? | `persona`; the archetype [05 §3.7] | a person with a job and a manner, not a list of virtues |
| 6 | Three brands you admire visually, and precisely why; any you dislike, and why. And anything the venture already uses that should carry over: a colour, a holding page, a shipped icon? | `admired`, `disliked`; territory cues; existing assets to score in strategy (cautionary-tales.md rule 1) | a named brand plus the detail ("Stripe's restraint"), not "it's clean"; each existing asset named, or "none" |
| 7 | Where will the mark live most? Rank the top three of: app icon, website header, social avatar, packaging, signage, merch, pitch decks, print. | `surfaces`; the primary lockup; which tiers matter | a ranked three, with the first one certain |
| 8 | The smallest size and the harshest environment it must survive. | `harshest`; small-size tiers, one-colour needs | "16 px favicon and one-colour embroidery", not "anywhere" |
| 9 | Colours you want, colours you forbid, colours your category has already claimed. | `colours_wanted`, `colours_forbidden`, `colours_category` | named colours with reasons; "fintech blue" counts |
| 10 | Symbols, metaphors or tropes that are off limits; any cultural or language constraints. | `off_limits`, `cultural`; the cliché check | concrete ("no shields, no upward arrows"; "must read in Arabic") |
| 11 | The name: how it is written, how it is said, its story, any tagline. Or: it needs a name. | `name`, `name_written`, `name_story`, `tagline`, `needs_name` | the exact spelling and case; the story in one line |

Whether the venture has a name decides how the brand is created, so settle that before `brand new`: a venture without one is created with `uv run logomaker brand new "<Working title>" --unnamed`, which puts the naming phase after intake. Nothing can set `needs_name` later; `brand rename` only clears it [code].

## Express intake

On the express track ask questions 1, 3, 4, 7 and 11 only, in that order; infer `one_idea` from 3, `persona` and the archetype from 4, `harshest` from 7's first surface (an app icon or favicon means the 16 px tier), `colours_*` and `off_limits` from the category's uniform in cliches.md, and show every inference in the write-back for correction [spec 2026-10-08 §8]. The brand was made with `uv run logomaker brand new "<Name>" --express`, so question 11 confirms the name rather than opening a naming phase [code].

## Optional questions

Ask only when the answers above leave a gap [spec §4.1] [05 §3.7]:

- What are the twelve-month goals the identity must support: launch, fundraise, a new market?
- Who are the nearest competitors, judged by what customers buy instead?
- Will sub-brands, features or product lines hang off this mark?
- Which markets, languages and scripts must it work in?
- Who else decides, who else will comment, and which three objections do you expect from them?
- Will the mark need to move (video, loading states) or come in variations (events, campaigns)?
- Any typographic preferences or aversions, or fonts you already licence?
- Anything a stranger would need to know to design this that we have not asked?

## Inference guidance

Infer these, then show them in the write-back for correction [spec §4.1]:

- Archetype: read the persona first (a calm site foreman who follows up suggests Everyman, then Caregiver), then the admired brands, then the adjectives. Name a primary and a secondary, with the row from strategy-frameworks.md [05 §3.2].
- Personality: score the five Aaker dimensions from the adjectives, the persona and the admired brands, as strategy-frameworks.md sets out [02 §L].
- Industry tag: a short phrase from question 1 that contains an industry key or alias from `assets/cliches.json` as whole words, so the audit checks the right cliché list ("invoicing for consultants" resolves to fintech; "cloud backup app" to saas) [code]. Every industry the tag names is checked, and the ai list's aliases are broad: "ai", "ml", "machine learning", "artificial intelligence", "tech", "software", "llm" and "agent" all resolve to ai, so "invoicing software" runs the ai list beside fintech's; leave those words out unless the venture is about AI [code]. The keys are ai, saas, crypto, fintech, real-estate, healthcare, dental, legal, consulting, education, nonprofit, food, coffee, fitness, beauty, sustainability, logistics, travel, creative, pets, photography, trades, cannabis and faith; cliches.md lists every alias. After the first audit, read its `industry` info line: "resolves to ..." confirms the match; "none matched" means only the Any category list ran, so rewrite the tag. In strategy, `uv run logomaker brand set <slug> --industry "<tag>"` records it in brand.json, which then takes precedence over brief.json [code].
- Surfaces: keep the owner's ranking. In strategy, record it with one `--surface` per surface in rank order (`brand set <slug> --surface "app icon" --surface "website header"`). In refinement the highest-ranked surface that shows a lockup picks the primary lockup: a wide header suggests horizontal, a square placement (packaging, a social post) suggests stacked. The app icon and the social avatar draw the mark, never a lockup, so they never pick it; judge it in the concept sheet's mockups that show lockups, the website headers, the card and the sign [spec §4.6] [code].
- Harshest environment: a 16 px favicon means drawing the `favicon` tier; embroidery or engraving means one colour, no hairlines, no gradients [03 §6.1].

## Write-back template

Write `brands/<slug>/brief.md` for the owner and `brands/<slug>/brief.json` for the gate, show brief.md, and wait for a correction or a confirmation. Record what the owner changed with `uv run logomaker brand decide <slug> --phase intake --by user --note "..."` [spec §3.3, §4.1].

```markdown
# <Name or working title>: brief

## The business
<what it does>, for <whom>, solving <problem>.

## The one idea
<one sentence>

## Only statement
We are the only <category> that <difference> for <customer> who <need>.

## Personality
Adjectives: <adjective> (not <neighbour>), ...
Persona: <the dinner-party person>
Archetype, inferred: <primary>, with <secondary>
Aaker scores, inferred: sincerity <0-1>, excitement <0-1>, competence <0-1>, sophistication <0-1>, ruggedness <0-1>

## References
Admired: <brand: why>; disliked: <brand: why>
Existing assets to carry over: <asset, or none>

## Where it lives
Surfaces, ranked: 1. <surface> 2. <surface> 3. <surface>
Harshest: <size and environment>

## Colour and limits
Wanted: ...; forbidden: ...; claimed by the category: ...
Off limits: ...; cultural: ...

## The name
Written: <exact case>; said: <pronunciation>; story: <one line>; tagline: <or none>

## Industry tag
<tag>, which selects the <key> cliché list

## What I assumed
<each inference the owner should check>
```

`brief.json` validates as `schemas.Brief` in `src/logomaker/schemas.py`; the intake gate refuses anything else [code]:

| Field | Type | From |
|---|---|---|
| `business`, `audience`, `problem` | text | question 1 |
| `one_idea` | text | question 2 |
| `onliness` | text | question 3 |
| `adjectives` | list of `{"adjective": ..., "not": ...}`, at least three | question 4 |
| `persona` | text | question 5 |
| `admired`, `disliked` | lists of text | question 6 |
| `surfaces` | ranked list of text, at least one | question 7 |
| `harshest` | text | question 8 |
| `colours_wanted`, `colours_forbidden`, `colours_category` | lists of text | question 9 |
| `off_limits` | list of text | question 10 |
| `cultural` | text, may be empty | question 10 |
| `needs_name` | true or false | question 11 |
| `name`, `name_written`, `tagline` | text or null | question 11 |
| `name_story` | text, may be empty | question 11 |
| `archetype` | `{"primary": ..., "secondary": ...}` | inferred |
| `personality` | `sincerity`, `excitement`, `competence`, `sophistication`, `ruggedness`, each 0 to 1 | inferred |
| `industry` | text with a cliché key or alias | inferred |

A minimal valid file (note the key `not`):

```json
{"business": "Cloud backup for small offices", "audience": "office managers at 5 to 50 person firms", "problem": "a lost day after a crash",
 "one_idea": "cover for the day it pours", "onliness": "the only backup that restores a whole office in one click",
 "adjectives": [{"adjective": "calm", "not": "sleepy"}, {"adjective": "sure", "not": "smug"}, {"adjective": "kind", "not": "cute"}],
 "persona": "the colleague who already has a spare umbrella", "surfaces": ["app icon", "website header", "social avatar"],
 "harshest": "16 px favicon", "needs_name": false, "name": "Brolly", "name_written": "brolly",
 "archetype": {"primary": "Caregiver", "secondary": "Everyman"},
 "personality": {"sincerity": 0.8, "excitement": 0.3, "competence": 0.7, "sophistication": 0.3, "ruggedness": 0.4},
 "industry": "cloud backup app"}
```

## Sources

spec §3.3 and §4.1 (questions, optional questions, inference, write-back); spec 2026-10-08 §8 (the express intake); 05 §3.1, §3.2, §3.5, §3.7 (the synthesised 22-question discovery brief); 01 §1.1 (Haviv's forcing question, Logo Geek's open questions); 02 §L; 03 §6.1; code: `schemas.Brief`, `audit.resolve_industries`, `assets/cliches.json`, `registry.set_fields`.
