# Logo types

Read this when: making the logo-type decision in strategy (strategy.md section 8; `logo_type` and `logo_type_reason` in strategy.json), and picking structurally different directions in concepts.

The default for a new venture is a wordmark-led combination mark; any other type needs a reason in `logo_type_reason` [spec §4.3]. New brands should lead with a legible wordmark: unfamiliar brands do better with text-based logos, familiar ones with image-based logos [02 §13, §K rule 3].

## Taxonomy

The research's eight types [05 §4.2], mapped onto the seven `logo_type` values that `schemas.LogoType` accepts; a `strategy.json` with any other value fails the strategy gate [code].

| Type | `logo_type` | What it is | Right when | Wrong when |
|---|---|---|---|---|
| Wordmark (logotype) | `wordmark` | the name in custom type | a short (seven characters or fewer), distinctive name; a new brand that needs name recognition; services, SaaS, media | a long, generic or hard-to-say name; tiny hardware use |
| Lettermark or monogram | `lettermark` | initials or a single letter | long or multi-word names (IBM, HBO); professional services; one letter made ownable by one quirk | generic initials (AA, MC), or initials that collide with famous marks |
| Pictorial mark | `pictorial` | a recognisable object | the object is a real idea (Apple's bite, Twitter's bird), not the category's literal product | it only depicts what the business sells: a tooth, a roof, a coffee cup |
| Abstract mark | `abstract` | non-representational geometry | global or multilingual brands; tech or finance wanting an idea over an object; a budget to build fame | no media to teach it; a category full of similar abstractions (AI hexagons) |
| Mascot | `mascot` | a character | food and drink, consumer apps, kids, sports, any brand where warmth and story matter ("we respond to humanity", LogoLounge 2025) | luxury, law, finance; a character that cannot be simplified for small sizes |
| Combination mark | `combination` | a separable symbol plus wordmark | almost every new brand: it teaches name and symbol together and is the easiest to trademark | parts designed separately, with no shared DNA ("wandered in from someone else's brand") |
| Emblem or badge | `emblem` | text inside a shape | heritage, craft, beer, outdoor, institutions, teams; where a seal is a feature | small digital use comes first: the text inside shrinks to illegibility |
| Dynamic or generative | none | a system of rules that makes variants | culture, events, platforms with many sub-contexts (Eventbrite's "Path", London 2012) | there is no fixed anchor, or no tooling and discipline to run it |

Dynamic identities are out of scope in this version [spec §16]. When the strategy wants one, design its fixed anchor: record it as `combination`, or `abstract` for a symbol-led anchor, and say in `logo_type_reason` that the parametric tiers are the only variation shipped. Research 04 recommends exactly that: generative construction inside, one fixed, governable mark outside [04 §5].

How each type is built in a concept module (see kit-api.md) [code]:

- `wordmark`: `Mark(wordmark=text(...))`, with small and favicon tiers drawn as an initial or a ligature.
- `lettermark`: `glyph(...)` as the symbol, cut or joined parametrically, plus a full-name wordmark.
- `pictorial`, `abstract`, `mascot`: primitives and booleans as the symbol.
- `combination`: `Mark(symbol=..., wordmark=..., lockup="horizontal")`; the export derives stacked, symbol-only and wordmark-only lockups.
- `emblem`: a frame shape with type unioned into the symbol. That type is not measured as a wordmark, so draw the small tiers without it.

## Decision guide

Seven questions, in order [05 §4.3]:

1. Is the name short and distinctive, and the brand new? Yes: a wordmark-led combination mark (`combination`); design the icon from the wordmark's DNA, a letter, a ligature or a counter. No: go on.
2. Is the name long, multi-word or an acronym? Yes: a lettermark or monogram as the primary symbol (`lettermark`), paired with a full-name lockup.
3. Is there a genuine, non-literal object or character that embodies the strategy? Yes: a pictorial mark or a mascot (`pictorial`, `mascot`), after it passes the cliché blacklist in cliches.md. No: go on.
4. Must the brand span languages, product lines and sub-brands, with a budget to build fame? Yes: an abstract mark inside a combination lockup (`abstract` or `combination`), with geometry that scores high on uniqueness in its category.
5. Is heritage, craft or membership the story? Yes: an emblem or badge (`emblem`), with a simplified mark for small sizes.
6. Will the brand live in many contexts with real creative operations? Yes: a dynamic system with a fixed anchor and stated ranges of variation; here, ship the anchor only (above).
7. Symbol-only is never a launch state. It is earned at measured, majority unaided recognition: Mastercard dropped its name when "more than 80 percent of people" recognised the symbol without it [05 §2, §4.1].

Every path ends with the same deliverables: a primary lockup, horizontal and stacked variants, the icon at 16, 32, 48, 180 and 512 px, one-colour positive and reverse, a minimum-size rule and a clear-space rule [05 §4.3]. `package build` makes all of them from any type (deliverables.md) [code].

Concrete forms read older and suit heritage positioning; abstract forms suit modern positioning [02 §K rule 15]. A pictorial or abstract mark for a new brand still ships beside the wordmark [02 §K rule 3].

## App icon behaviour

| Type | As an app icon or favicon [05 §4.2] |
|---|---|
| Wordmark | needs a derived initial; unreadable at 16 px otherwise |
| Lettermark | excellent; design it as the icon from day one |
| Pictorial | strong if the silhouette is simple |
| Abstract | strong, but risks anonymity among other abstractions on a home screen |
| Mascot | needs a cropped "face" version |
| Combination | the symbol is the icon, the wordmark is the header |
| Emblem | needs a simplified crest variant |
| Dynamic | define the canonical still state first |

The split among the world's top 100 brands, from TastyPlacement's 2013 study as cited by CompanyFolders: 37 percent wordmark only, 6 percent symbol only, 56 percent text plus symbol. It stays directionally true of Interbrand's 2025 top ten, where Apple and Mercedes lead with a symbol and Amazon, Google, Microsoft, Samsung, Toyota, Coca-Cola, Instagram and McDonald's lead with a wordmark or a combination [05 §4.1]. Bolder Agency's stage table: pre-launch, wordmark; early stage, wordmark or combination; growth, combination; established, combination or logomark; global, logomark with a wordmark system. "Most companies do not begin with symbol-only branding. They earn that flexibility" [05 §4.1].

How the CLI picks what an icon shows [code]:

- Exports and mockups choose by size: the full symbol from 96 px, the `small` tier from 33 to 95 px, the `favicon` tier at 32 px and below. A missing tier falls back to the next larger build, with a warning.
- A concept without a symbol stands its wordmark lockup in for the icon, favicon and avatar; the audit and the concept sheet both warn. Draw an initial or ligature tier instead, as kit-api.md's wordmark example does.
- The concept sheet's phone mockup is the shelf test: the icon among eleven generated neighbours, read against generic tiles.

## Sources

05 §4.1 (the 37/6/56 data, dated 2013, and the stage table), §4.2 (types and app-icon behaviour), §4.3 (the decision guide), §2 (Mastercard); 02 §13 and §K rules 3 and 15; 04 §5 (dynamic identities); spec §4.3 and §16; code: `schemas.LogoType`, `kit.concept.size_tier`, `audit._checked_outputs`, `sheets.mockup_context`.
