# Naming

Read this when: the venture is unnamed (phase 1, naming), and whenever the owner proposes a name to check.

Generate 15 to 25 candidates, at least five each of descriptive, evocative and invented. Give each a one-line meaning, a sound profile (front or back vowels, stops or fricatives), a letterform note (length, initial letter class, double letters, ligature chances, the L-flourish warning) and a fit score against the personality profile [spec §4.2].

## Name types

| Type | Examples | Gains | Costs | As a trademark [03 §5] |
|---|---|---|---|---|
| Descriptive | "Creamy" for yogurt | clear; searchable; pairs with a straightforward visual style | "most common, yet least memorable" (Kolenda) | weak: registrable only after acquired distinctiveness; a generic term ("Bicycle" for bicycles) never |
| Evocative | Coppertone (suggestive); Apple for computers (arbitrary) | personality; a metaphor the mark can use | needs teaching | strong |
| Invented | Exxon, Pepsi (fanciful) | ownable; easy to clear | needs explaining; must be pronounceable | strongest |

Rules [05 §3.6] [03 §5]:

- Concrete nouns (Dove, Apple) are encoded more easily than abstract ones (Pledge, Bold).
- An evocative name should come from the brief's one idea, not from the category's vocabulary.
- Flag descriptive or generic names, and names that lean on category clichés, as weak.
- Renaming later resets equity and search behaviour (Twitter to X, HBO Max to Max): choose as if for good [01 §3 rule 18].

## Sound symbolism

- Front vowels (i, e) connote small, light, fast, sharp and feminine; back vowels (o, u) large, heavy, slow and strong; fricatives (f, s, v, z) are softer than stops (p, t, k, b, d, g) [02 §29].
- In Kolenda's practical terms: i, e, k, t and s read small, fast and light; o, u, b, d, g and m read large, slow and heavy (bouba and kiki) [05 §3.4].
- The congruence rule: a sound helps only when what it connotes is desirable in the category, so front vowels for convertibles and knives, back vowels for SUVs and hammers; this held across English, French, Spanish and Chinese [02 §29; moderate-strong].
- Name and mark should agree: front-vowel names pair with smaller, more angular, lighter marks, and a mark consistent with its name communicates better [02 §29]. Record the note in `strategy.json`'s `targets.name_sound`.
- By Aaker dimension [02 §L]: sincerity, soft fricatives and mid vowels; excitement, front vowels; competence, stops and voiced consonants; sophistication, front vowels with fricatives; ruggedness, back vowels and stops.
- `names analyze` counts front, back and neutral vowels and gives `front_ratio`. It does not classify consonants or spot ligatures: judge stops, fricatives and ligature chances yourself [code].

## Letterform scoring

Score each candidate 1 to 5 for wordmark potential [synthesis from 05 §3.6 and 02 §K rule 13]:

| Score | The name |
|---|---|
| 5 | three to seven letters; an initial that makes a strong monogram (a closed counter or a clear diagonal); one double letter or ligature chance for an owned quirk; no ambiguous letter pairs; reads the same in lowercase and caps |
| 4 | as 5 without a quirk opportunity, or eight or nine letters |
| 3 | ten letters or more, or two words; or a round initial that pulls toward circles and the AI-era cliché; workable through a lettermark |
| 2 | ambiguous pairs (rn and m, cl and d, I, l and 1, vv and w), digits, or a case pattern that fights the silhouette; or an L initial that invites the saturated script-L flourish |
| 1 | `pronounceable` is false, or a pair misreads as another word (the Kia "KN" problem), or the initials collide with a famous monogram |

Read the inputs from `names analyze`: `length`, the `initial` flags, `double_letters`, `camel_case`, `has_digits`, `max_consonant_run`, `pronounceable` [code]. The overall fit score weighs meaning (the one idea), sound congruence, letterform and availability; show all four in naming.md's shortlist table.

## Checks

`uv run logomaker names analyze <name>` runs offline and costs nothing, so run it for every candidate [code]:

```json
{"ok": true, "errors": [], "warnings": [], "name": "Keystone", "letters": "keystone", "length": 8, "syllables": 2,
 "vowels": {"front": 2, "back": 1, "neutral": 0, "front_ratio": 0.67},
 "initial": {"letter": "k", "round": false, "diagonal": true, "closed_counter": false, "l_warning": false},
 "double_letters": [], "camel_case": false, "has_digits": false, "max_consonant_run": 2, "pronounceable": true}
```

Syllables are vowel groups, less a silent final e. `pronounceable` means at least one vowel and no run of more than three consonants. Accented letters count as their plain letters. The initial's letter sets: round o, c, g, s, q; diagonal a, v, w, k, x, z; closed counter a, b, d, o, p, q, r [code].

`uv run logomaker names check <name>` uses the network; the defaults are `--tlds com,co,io,ai,app,dev` and `--handles github` (`--handles ""` skips GitHub). The shape, abridged to two of the six domains [code]:

```json
{"ok": true, "errors": [], "warnings": ["keystone.app: RDAP 429 from rdap.org and whois gave nothing"],
 "name": "Keystone", "label": "keystone",
 "domains": [{"domain": "keystone.com", "status": "registered", "method": "rdap"},
             {"domain": "keystone.app", "status": "unknown", "method": "whois"}],
 "handles": {"github": {"user": "registered", "org": "registered"}}}
```

- `label` is the name in lowercase ASCII letters and digits ("Café Nuit!" becomes cafenuit).
- Statuses: `available` (the registry's own RDAP server answers 404, or whois says not found), `registered` (RDAP answers 200, or whois names a domain or registrar), `unknown` (anything else). The method is `rdap`, `whois`, or `none` when whois could not run or the deadline had passed [code].
- GitHub users and organisations share one login namespace: when the user lookup answers 200, the organisation is `registered` too. The organisation endpoint is asked only when no user holds the login, and an unknown user leaves the organisation unknown [code].
- Deadline: no lookup starts after 45 s; each request or whois waits at most 10 s, and none past 55 s. Lookups left undone come back `unknown`, with one warning naming them [code].
- Rate limits: rdap.org starts answering 429 after about ten quick requests; .app and .dev have no whois fallback, so they turn `unknown` once RDAP refuses; .co, .io and .ai have no RDAP server known to rdap.org and always go to whois. GitHub allows 60 unauthenticated requests an hour, shared with `fonts fetch`; a 403 or 429 is `unknown` with "rate limited" [code].
- So: analyze every candidate, but check only the shortlist (the top five), one name at a time. Report `unknown` as unknown, never as available, and re-run those later.
- An unknown handle service or a malformed TLD exits 2 before any lookup [code].

## Knock-out by image

A description search finds marks that are named like yours; a reverse-image search finds marks that look like yours [spec 2026-10-08 §7]. For every survivor before the concept sheet, and for `final/` before the package:

1. `uv run logomaker concept knockout <slug> <NN-slug>` (or `final`) writes `knockout/round-N/mark-512.png` and `lockup-1024.png`, black on white, and seeds `knockout.json` [code].
2. Load the Chrome tools in one ToolSearch call (`mcp__claude-in-chrome__tabs_context_mcp`, `navigate`, `tabs_create_mcp`, `file_upload`, `get_page_text`, `find`, `tabs_close_mcp`), open a new tab at `https://lens.google.com/`, upload `mark-512.png`, and read the "Visual matches" list. Record the ten nearest in `knockout.json` under `image_matches.matches` as `{"url", "owner", "note"}`, the note saying what matches (silhouette, construction, both), with `searched: true` and the date. Close the tab.
3. For `final/` only, open `https://branddb.wipo.int/`, choose the image search, upload the same PNG, and record the nearest registered marks the same way under `wipo` (`{"tool": "wipo", "searched": true, "date", "matches"}`), each note naming the Nice class and the status shown.
4. Write the prose into `final/knockout.md` as before (for a survivor, into `clear` in its `scorecard.json`), with the caveat below word for word, and copy the caveat into `knockout.json`'s `caveat`.

When the Chrome extension is unavailable, record `"skipped": "<reason>"` in place of `searched` and tell the owner: the gate accepts a skipped search only after the owner records `uv run logomaker brand decide <slug> --phase <phase> --by user --note "knock-out skipped: <reason>"`, and the note counts only in the phase the refusal names, `concepts` for a survivor and `refinement` for `final/` [code].

`knockout.json` carries the concept's fingerprint, the one the audit and the critic use. Each `concept knockout` run stamps the current one; when the mark changed since the last search, it resets each search's `searched`, `matches` and `date` (a skip reason, the description queries and the caveat stay) and reports `"reset": true`, so search again. Until then the gates refuse the record: "is stale (the mark changed since the search); re-run: logomaker concept knockout <slug> <NN-slug|final>" [code]. `final/knockout.json` is also in the package fingerprint, so a new search after `package build` makes the package out of date [code].

## Trademark caveat

Say this sentence, word for word, wherever a knock-out result is reported (canonical wording; SKILL.md quotes this):

> "These checks are a knock-out only, not legal clearance: they can surface an obvious conflict but cannot prove there is none, so have a trademark attorney run a clearance search before you file the name or spend money on it."

Where to search, for the top five names here and for the final mark in refinement [03 §5]:

1. USPTO Trademark Search (tmsearch.uspto.gov) for word marks, with design search codes (tmdesigncodes.uspto.gov) for logo shapes.
2. EUIPO eSearch plus and TMview, which also take an image.
3. WIPO's Global Brand Database, with its image-similarity search.
4. The general web, app stores and domain registries, for unregistered use; the Trademark Official Gazette and state registries for US filings.
5. Reverse image search (Google Lens, TinEye) on the rendered mark.

What counts as a conflict: similarity in "sound, appearance, or meaning", or "a similar commercial impression", with related goods or services. Stay away from famous marks even in unrelated categories [03 §5]. Record each query and finding in naming.md for names and in `final/knockout.md` for the mark, each with the caveat [spec §4.2, §4.6].

## Sources

05 §3.4 (Kolenda's sound symbolism), §3.6 (name types, naming and letterforms); 02 §G entry 29 (Klink, Lowrey and Shrum), §L (name sound by dimension), §K rule 13; 03 §5 (the distinctiveness spectrum, likelihood of confusion, the clearance workflow); 01 §3 rule 18; spec §3.3, §4.2, §4.6; spec 2026-10-08 §7 (the knock-out by image); code: `names.analyze`, `names.check`, `names.check_domain`, `names.check_github` (`DEADLINE`, `LIMIT`, `LOOKUP_TIMEOUT`), `knockout.write_images`, `knockout.knockout_problems`, `schemas.Knockout`.
