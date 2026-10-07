# Colour

Read this when: setting the colour targets in strategy, choosing territory palettes (phase 3), and writing `final/tokens.json` in refinement (phase 5).

Colour is the last decision and never load-bearing: the mark must keep its hierarchy in solid black and solid white first [05 §5.4] [01 §3 rule 5].

## Hue, saturation and lightness

| Lever | Personality effect | Confidence | Source |
|---|---|---|---|
| Red | excitement (beta .53) | strong | Labrecque & Milne 2012 [02 §21] |
| Blue | competence; also "corporate, cold", and the fintech uniform | strong; the caveat is practitioner | [02 §21] [05 §3.4] [01 §2 PayPal] |
| Saturation, higher | excitement (beta .20); a saturated colour also looks bigger | strong | [02 §21, §23] |
| Lightness, lower (darker) | ruggedness (lightness beta -.34); "dark is durable, light is user-friendly" | strong; moderate | [02 §21, §23] |
| Black and white | coolness, then status and willingness to pay, for a new premium brand; not for warm or famous brands | moderate | Yue & Xia 2026 [02 §23] |
| Green or blue | eco-friendliness, judged more ethical | moderate | Sundar & Kellaris 2017 [02 §23] |
| Black, purple | sophistication | moderate, not re-verified | [02 §21] |
| Brown, dark green | ruggedness | moderate, not re-verified | [02 §21] [02 §L] |
| White, pink, light yellow | sincerity | moderate, not re-verified | [02 §21] [02 §L] |
| Purple | creativity, royalty, "moody" | practitioner | Map & Fire [05 §3.4] |
| Dark blue; light pink | masculine; feminine | moderate | [02 §24] |

- Colour and shape combine additively, and a colour personality raises purchase likelihood when it matches the intended one [02 §21].
- A colour becomes distinctive only when "deployed in a very singular way" (Romaniuk) [05 §3.4].
- Colour memory is approximate: FedEx's focus groups thought its colours "were red and blue" [05 §5.1].
- Strategy.json carries the targets as `hue_family` (a word, such as "teal"), `saturation` (`low`, `medium`, `high`) and `lightness` (`dark`, `mid`, `light`) [code].

## Cross-cultural notes

- Blue, green and white travel best, with shared calm and peaceful meanings; red is consistently active and hot; other hues vary. Check red, yellow, purple and black per market [02 §22, §K rule 11; moderate, hue specifics from memory].
- The country-level colour results were not re-verified; when `brief.json`'s `cultural` names markets, look up colour meanings there before fixing the primary [02 §M] [synthesis].
- Masculine and feminine colour cues (dark blue, light pink) carry cultural assumptions; use them only when the brief asks for that register [02 §24].
- Print is another culture of its own: only about 55 percent of Pantone spot colours are reachable in CMYK, and about 20 percent cannot be shown in sRGB. Define the brand by its swatch and publish recipes per medium [03 §3]. The package's CMYK values are a naive conversion, and its README says to confirm them with the printer [code].

## Thresholds

The audit's colour checks, as `color.check_tokens` and `audit.text_roles` implement them [code]:

- Every role in the tokens file is measured against its context's paper, on light paper and on dark.
- Type roles (the roles the wordmark and tagline are drawn in, or `ink` when the mark has no type) need WCAG 4.5:1 and APCA Lc 60. Every other role needs WCAG 3.0:1 and Lc 45. Both numbers must pass; a miss is a contrast failure.
- Grayscale: two roles in one context whose OKLCH lightness differs by less than 0.15 give a warning.
- Colour vision: any role pair in a context whose simulated contrast (protan, deutan, tritan, achromatopsia) falls under 1.5:1 gives a warning.
- These checks run only when the concept folder has a `tokens.json` (or `--tokens` names one); concepts are black only, so in practice they start in refinement.
- On every audit, tokens or not, more than three roles in use gives a `colour_count` warning.

`uv run logomaker color check <tokens.json>` is only a pre-check. It cannot know which role draws the wordmark, so it holds `ink` alone to the type thresholds and every other role to 3.0 and Lc 45. A palette can pass it and still fail the audit when the wordmark is drawn in `primary`. The colour gate is the rendered `uv run logomaker concept run <slug> final`: its audit holds the roles the type really uses to 4.5 and Lc 60, and `brand advance --to package` and `package build` both need that audit fresh and passing [code].

Where the numbers come from: WCAG 2.2 exempts logo text but asks a logo used as a link or control for a 4.5:1 variant (3:1 for large text), and 3:1 for non-text graphics (1.4.11); APCA's Bronze level asks Lc 60 for content text and Lc 45 for text over 36 px, and does not cover logos [03 §3] [spec §8.1]. The research's pass criterion: hierarchy survives the grayscale and deuteranopia views [03 §3].

## Building a palette in OKLCH

1. Start from the targets (`hue_family`, `saturation`, `lightness`) and the chosen territory's palette of two to six colours [spec §4.6].
2. `uv run logomaker color info <hex>` gives HEX, RGB, HSL, OKLCH, CMYK and luminance [code].
3. `uv run logomaker color ramp <hex> --steps 9` returns nine colours at the hue and chroma of `<hex>`, with OKLCH lightness running evenly from 0.95 down to 0.15, each fitted into sRGB [code]. Take the light-context primary from the middle of the ramp and the dark-context primary from its lighter steps.
4. Use at most two colours plus ink by default: `primary` (the symbol's default role), optionally `secondary` or `accent`, and `ink` (the wordmark's default role). `paper` is the background, never a part's colour [spec §4.6] [code].
5. Pick inside sRGB; a Display P3 value is only an optional enhancement over an sRGB fallback [03 §3].
6. Run `color check` as the pre-check, then `concept run <slug> final` as the gate, and read the refine sheet's contrast table and colour-vision strip [code].

## Designing the reverse

- The reverse is a designed dark-context role map, never an automatic inversion. "Confirm that the intended reversed version is designed, not merely auto-inverted" (DesignAuditly) [03 §1.4] [spec §4.6].
- Lighten the primary: use a lighter step of its own ramp for `roles.dark.primary`; a mid-tone primary on dark paper loses both contrast and vibrancy.
- Swap the neutrals: the dark context's `ink` is usually the light paper colour, and its `paper` is usually the ink colour.
- Re-check: the lighter primary drifts toward the light ink, so keep at least 0.15 of OKLCH lightness between them (in the example below, ramp step 2, `#89e0d6` at lightness 0.85, sits only 0.135 from Chalk's 0.985; step 3, at 0.75, passes).
- The iOS and Android app icons draw the art in the light paper colour on a primary-colour tile, as the concept sheet's phone mockup does. No check measures that pair, so judge it on the mockup [code].
- BRAND.md's background rules follow from the roles: `color` on light fields, `reverse` on dark, `white` or `black` on photographs inside a clear-space zone, `white` on primary-colour fields [code].

## tokens.json format

`final/tokens.json` validates as `color.Tokens` in `src/logomaker/color.py`; the refinement gate refuses anything else [code]. This file passes `color check`:

```json
{
  "colors": {
    "tide": {"name": "Tide", "hex": "#0f766e"},
    "tide-light": {"name": "Tide Light", "hex": "#68c0b6"},
    "squall": {"name": "Squall", "hex": "#1e293b"},
    "chalk": {"name": "Chalk", "hex": "#fbfaf7"}
  },
  "roles": {
    "light": {"primary": "tide", "ink": "squall"},
    "dark": {"primary": "tide-light", "ink": "chalk"}
  },
  "paper": {"light": "chalk", "dark": "squall"}
}
```

- `colors` maps a key to a `name` and a `hex`; `rgb`, `hsl`, `oklch` and `cmyk` are optional, and the package fills them in.
- `roles.light` and `roles.dark` map roles to colour keys. Both need `primary` and `ink`; `secondary` and `accent` are optional; `paper` is not allowed there.
- `paper.light` and `paper.dark` name the background colour key of each context.
- Tide Light is step 3 of `color ramp "#0f766e" --steps 9`. With the wordmark in `ink` (the default role) this palette passes the audit too; with the wordmark in `primary`, the dark context fails at Lc 56.73, under 60.
- To preview a palette on a concept without writing into its folder: `concept run <slug> <NN-slug> --tokens <file> --variants black,white,color,reverse`. That audit's fingerprint includes the file, so re-run `concept run <slug> <NN-slug>` without `--tokens` before `sheet concepts`, which compares the audit with the folder's own files [code].

## Sources

02 §F entries 21 to 24, §K rule 11, §L, §M; 03 §1.4 (designed reverses), §3 (colour specification, WCAG, APCA, CVD, sRGB, CMYK and Pantone); 05 §3.4, §5.1, §5.4; 01 §2 (PayPal), §3 rule 5; spec §4.6, §8.1; code: `color.check_tokens`, `color.ramp`, `color.Tokens`, `audit.text_roles`, `export.PackageBuilder._on_primary`, `templates/brand.md.j2`.
