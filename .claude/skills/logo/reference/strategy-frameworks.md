# Strategy frameworks

Read this when: inferring archetype and personality at the end of intake, and writing strategy.md and strategy.json (phase 2).

Each framework below fills one or more sections of strategy.md and fields of `strategy.json` (`schemas.Strategy`) [spec §4.3] [code].

## Onliness and positioning

Two templates, both required in strategy.md section 1 (`onliness`, `positioning`):

- Neumeier's onliness statement: "Our company is the only [category] that [point of radical differentiation] for [customer] in [market] who want [need] in an era of [trend]" [05 §3.1].
- Moore's positioning statement: "For [target] who [need], [brand] is a [category] that [key benefit]. Unlike [alternative], [brand] [proof]" [05 §3.1].

Filled example (a fictional backup service):

- Onliness: "Brolly is the only backup service that restores a whole small office in one click for office managers at five-to-fifty-person firms in the UK who want yesterday's files back before lunch, in an era of ransomware."
- Positioning: "For office managers at small firms who dread losing a day to a dead laptop, Brolly is a cloud backup service that restores everything in one click. Unlike enterprise backup suites, Brolly needs no IT department to run it."
- One idea (`one_idea`, section 4): "cover for the day it pours."

Rules:

1. If the founder cannot fill the "only" slot truthfully, the logo brief is premature; say so and work the slot with them [05 §3.1]. Collins rule 68: "Work with clients to help them become the only" [01 §4].
2. The one idea answers Haviv's forcing question: "if there were one idea you could instill into a simple logo, what would it be?" [01 §1.1]. One sentence, no "and".
3. Fill every slot concretely, as Dan Mall's Harley-Davidson example does: "The only motorcycle manufacturer that makes big, loud motorcycles for macho guys (and macho wannabes) mostly in the United States who want to join a gang of cowboys in an era of decreasing personal freedom" [05 §3.1].

## Archetypes to visual language

Mark and Pearson's twelve archetypes, grouped by motivation: stability and control (Ruler, Creator, Caregiver), independence and fulfilment (Innocent, Sage, Explorer), belonging and enjoyment (Everyman, Lover, Jester), risk and mastery (Hero, Outlaw, Magician). Choose one primary (60 to 80 percent of the brand's behaviour) and one secondary [05 §3.2]. The rows are a practitioner synthesis, not a measured result [05 §3.2].

| Archetype | Form | Type | Colour | Mark type bias |
|---|---|---|---|---|
| Ruler | symmetric, geometric, crest or emblem | high-contrast serif or engraved caps | black, navy, gold, burgundy | monogram, emblem |
| Creator | modular, constructive, grid-born | geometric sans, custom wordmark | primaries, bold accents | abstract or system |
| Caregiver | rounded, enclosing, soft | humanist sans, rounded | warm neutrals, soft greens and blues | pictorial, combination |
| Innocent | simple, open, light | light sans, friendly script | white, pastels, sky blue | wordmark |
| Sage | precise, orderly, editorial | serif or neo-grotesque, small caps | deep blue, grey, ochre | wordmark, lettermark |
| Explorer | rugged, directional, textured | condensed, slab, stencil | earth, forest, rust | badge or emblem, pictorial |
| Everyman | plain, sturdy, unpretentious | grotesque, slab | denim blue, red, kraft | wordmark |
| Lover | sensual curves, high contrast | didone, calligraphic script | red, rose, black, cream | wordmark, script |
| Jester | irregular, bouncy, mascot-friendly | chunky display, hand-drawn | saturated clashing brights | mascot, combination |
| Hero | bold, angular, forward motion | heavy condensed sans, italics | red, black, gold | abstract, lettermark |
| Outlaw | raw, broken grids, distressed | stencil, blackletter, grunge | black, acid colours | wordmark, badge |
| Magician | transformational, spirals, light | elegant sans with a twist | purple, iridescent gradients | abstract (but see the AI-era cliché in trends.md) |

Kapferer's identity prism has six facets (physique, personality, culture, relationship, reflection, self-image): the logo lives in physique, and the other five constrain it [05 §3.2]. Infer the archetype from the persona answer and the admired brands (questionnaire.md), then write both rows into strategy.md section 2.

## Aaker personality

Aaker's five dimensions, with the example brands of the original study: sincerity (Hallmark), excitement (MTV), competence (WSJ), sophistication (Guess), ruggedness (Nike) [05 §3.2]. Their facets are in evidence-rules.md. Logos, colour and typography are listed as indirect causes of perceived personality [05 §3.2].

Scoring each dimension 0 to 1 for `brief.json` and `strategy.json` (`schemas.Personality`, default 0.5) [synthesis] [code]:

1. Start every dimension at 0.5: no evidence either way.
2. For each adjective, move the dimension it names by 0.2 (warm, honest: sincerity; bold, playful: excitement; reliable, expert: competence; refined, premium: sophistication; tough, outdoor: ruggedness). Its unwanted neighbour sets a floor or a ceiling: "premium but not aloof" lifts sophistication and keeps sincerity at 0.5 or above; "bold but not loud" lifts excitement and caps it at 0.7.
3. Set the persona's dominant dimension to 0.8 or 0.9.
4. Nudge by 0.1 toward the dimension each admired brand is known for.
5. Keep at most two dimensions above 0.7. If three are high, ask which one wins when two conflict.
6. Write one sentence of evidence per score in strategy.md section 3.

| Score | Means |
|---|---|
| 0.8 to 1.0 | defining: the brand fails without it |
| 0.6 to 0.7 | supporting |
| 0.4 to 0.5 | neutral |
| 0.2 to 0.3 | avoided |
| 0.0 to 0.1 | rejected outright by the owner |

From scores to `targets`, using the rules in evidence-rules.md [02 §K, §L]: sincerity pulls `shape` toward round and `lightness` light; excitement lowers `symmetry`, raises `saturation` and `dynamism`; competence keeps `symmetry` high and `complexity` low; sophistication lowers `weight` and `saturation`; ruggedness raises `weight`, darkens `lightness` and favours a `badge` frame.

## Distinctive assets

Romaniuk's Distinctive Asset Grid scores an asset on fame (the share of category buyers who link it to the brand) and uniqueness (the share of those links that go only to this brand); practitioners use 50 percent on each axis as the threshold [01 §4] [05 §3.3]:

| | Unique | Shared |
|---|---|---|
| Famous | use and protect | avoid solo use: pair it with a unique asset |
| Not famous | invest: build fame | ignore |

- "Of these two, uniqueness is most important" (Romaniuk) [05 §3.3].
- A new brand starts with every asset at low fame, so choose for maximum uniqueness within the category and plan consistent repetition [05 §3.3].
- Shape-based assets are the strongest class (International Journal of Advertising, 2026) [01 §4].
- Category cues (the hexagon in AI, the roof in real estate, the tooth in dentistry) are famous but shared: they sit in "avoid" for every newcomer [05 §0, §5.5].
- In strategy.md section 6, list the category's famous-but-shared assets (type class, colours, motifs) to avoid, and the unclaimed ones a newcomer could own.

## Adjective ladder

Each adjective, paired with its unwanted neighbour, becomes a visual principle and a test that a critique sheet or an audit can settle [05 §3.5] [spec §4.3]. The first row is the spec's example; the others are worked examples [synthesis]. `strategy.json`'s `ladder` needs at least three rungs of `adjective`, `principle` and `test` [code].

| Adjective (not) | Principle | Test |
|---|---|---|
| approachable (not childish) | rounded terminals, open counters | no corner radius under 2 px at 32 px |
| steady (not boring) | level baselines, grounded forms, symmetric silhouette | the bottom edge is flat; nothing tilts in the 512 px panel |
| precise (not cold) | one 15-degree angle system, one stroke width from `PARAMS` | the audit reports no near-miss angles; every stroke uses the same parameter |
| warm (not cute) | a warm hue at medium saturation, no faces | primary hue between 20 and 70 degrees in OKLCH; no character |

The ladder sequence: (1) gather the onliness, archetype and three to five adjectives with their opposites; (2) give each a principle and a test; (3) derive constraints: logo type, geometry family, type class, palette temperature, texture tolerance, motion behaviour; (4) define two or three territories, each a coherent world that names what it rejects; (5) only then sketch [05 §3.5].

## Name to letterform

What the name does to the mark, before anything is drawn [05 §3.6]:

- Length: three to seven characters can carry a wordmark into an app icon; a longer name needs a lettermark or symbol for small sizes.
- Initial letter: a round initial (O, C, G, S, Q) invites circular monograms and the AI-era cliché; a diagonal one (A, V, W, K, X, Z) reads dynamic; a closed counter (A, B, D, O, P, R) offers negative-space play; a script-L flourish is saturated (LogoLounge 2026).
- Double letters create rhythm (Google, Coca-Cola), and ff, tt or oo give an easy owned ligature quirk, like kit-api.md's fourth example.
- Ligatures and joins must never erase a letter: 26 percent read Kia's mark as "KN" [01 §2].
- Case: CamelCase and all caps change the silhouette, so decide them before drawing; uppercase reads premium and masculine, lowercase approachable [02 §28]. Ask how the founder writes the name (question 11).
- `uv run logomaker names analyze <name>` reports the length, syllables, vowel balance, the initial's flags (`round`, `diagonal`, `closed_counter`, `l_warning`), `double_letters` and `camel_case`; it uses the letter sets above, with Q counted as closed too [code].

## Sources

05 §3.1 (onliness, positioning), §3.2 (Aaker, Kapferer, Mark and Pearson, the archetype cheat sheet), §3.3 (distinctive assets), §3.5 (the ladder), §3.6 (naming and letterforms), §0 and §5.5 (category cues); 01 §1.1 (Haviv's question), §2 (Kia), §4 (Collins rule 68, Romaniuk's grid); 02 §K, §L and entry 28; spec §4.3; code: `schemas.Strategy`, `schemas.Personality`, `names.analyze`.
