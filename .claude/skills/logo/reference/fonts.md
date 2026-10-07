# Fonts

Read this when: choosing one to three families for each territory (phase 3), setting the wordmark in refinement, and recording the wordmark font with `brand set --font`.

The "Catalogue by category" section and the Apache families under Licensing are generated from `assets/fonts/catalog.json` by `scripts/build_reference.py`; the rest of this page is `scripts/templates/fonts.md`. Edit the catalogue builder (`scripts/build_catalog.py`) or the template, then re-run `uv run python scripts/build_reference.py`; never edit this page by hand.

## Using the catalogue

- Browse: `uv run logomaker fonts list --category "<category>"` or `--personality <tag>`; each family in the JSON says whether it is `cached` [code].
- Cache before use: `uv run logomaker fonts fetch "<Family>"` downloads the family's TTF files and licence from google/fonts into `assets/fonts/<slug>/` with a `manifest.json` of URLs and sha256 sums [code]. A fetch spends one GitHub API call for a catalogue family (up to three for a family outside it) from the same 60-an-hour unauthenticated budget that `names check` uses [code].
- Fetch every family `territories/territories.json` names before `sheet territories`: the board never fetches, and exits 3 naming each uncached family with its fetch command [code].
- In a concept module, `text()` and `glyph()` refuse an uncached family with exit 3 and "run: logomaker fonts fetch ..." [code]. Fetch it; never substitute another family [spec §6.5].
- A variable family is drawn at any weight inside its `wght` range; a weight outside it is clamped to the nearest end (Fira Code runs 300 to 700, so 800 draws 700). A static family uses the file nearest the weight asked for [code].
- A family outside the catalogue can still be fetched (the fetch tries `ofl/`, `apache/` and `ufl/` folders of google/fonts), but read its licence file before using it [code] [03 §4.3].

## Catalogue by category

86 families in 10 categories, as `logomaker fonts list` reads them from `assets/fonts/catalog.json` [03 §4.4] [code]. Pass the category exactly as its heading reads, in quotes; any other string exits 2 and lists all 10. Every family is OFL unless marked Apache. Tags a whole category shares are listed once; a family's own tags follow its name.

### geometric sans

- List: `uv run logomaker fonts list --category "geometric sans"`
- Shared tags: modern, tech, confident, startup, clean
- Families (10): Montserrat; Poppins (rounded-geometric); Outfit (rounded-geometric); Jost (futura-like); Plus Jakarta Sans (friendly); Sora (crisp); DM Sans (ui); Manrope (ui); Urbanist; Figtree (friendly)

### grotesk

- List: `uv run logomaker fonts list --category "grotesk"`
- Shared tags: neutral, editorial, serious, swiss
- Families (11): Inter (ui); Space Grotesk (quirky, tech); Work Sans; Archivo (wide); Familjen Grotesk; Bricolage Grotesque (quirky, character); Instrument Sans; Public Sans (civic); IBM Plex Sans (corporate); Roboto (ui); Geist (ui, tech)

### humanist sans

- List: `uv run logomaker fonts list --category "humanist sans"`
- Shared tags: warm, approachable, trustworthy, civic
- Families (10): Open Sans; Source Sans 3; Lato; Fira Sans; Nunito Sans; Alegreya Sans (literary); PT Sans; Cabin; Inclusive Sans (accessible); Atkinson Hyperlegible (accessible)

### transitional serif

- List: `uv run logomaker fonts list --category "transitional serif"`
- Shared tags: established, credible, publishing, finance
- Families (9): Libre Baskerville; Source Serif 4; Merriweather; Lora (calligraphic); Newsreader (editorial); Literata; Spectral; Crimson Pro; Libre Caslon Text

### old-style serif

- List: `uv run logomaker fonts list --category "old-style serif"`
- Shared tags: heritage, literary, artisanal, hospitality
- Families (5): EB Garamond; Cormorant (delicate); Cardo; Alegreya; Crimson Text

### didone display

- List: `uv run logomaker fonts list --category "didone display"`
- Shared tags: luxury, fashion, editorial, elegant
- Families (8): Playfair Display; Bodoni Moda; DM Serif Display; Abril Fatface (heavy); Instrument Serif (condensed); Gilda Display; Prata; Fraunces (soft, wonky)

### slab

- List: `uv run logomaker fonts list --category "slab"`
- Shared tags: sturdy, craft, industrial, americana, outdoors
- Families (7): Roboto Slab (Apache); Zilla Slab; Arvo; Bitter; Aleo; Josefin Slab (retro); Alfa Slab One (heavy)

### display

- List: `uv run logomaker fonts list --category "display"`
- Shared tags: loud, distinctive, entertainment, sports, streetwear
- Families (10): Syne (art, bold); Unbounded (wide, bold); Bebas Neue (condensed); Anton (condensed, heavy); Oswald (condensed); Archivo Black (heavy); Righteous (retro); Climate Crisis (activist, heavy); Rozha One (heavy); Ultra (Apache, heavy)

### mono

- List: `uv run logomaker fonts list --category "mono"`
- Shared tags: technical, developer, data, retro-futurist
- Families (9): Space Mono (quirky); JetBrains Mono (code); IBM Plex Mono (corporate); Azeret Mono; DM Mono; Roboto Mono; Fira Code (ligatures, code); Geist Mono (tech); Martian Mono (wide)

### rounded

- List: `uv run logomaker fonts list --category "rounded"`
- Shared tags: friendly, playful, kids, food, wellness
- Families (7): Nunito; Quicksand (light); Varela Round; Comfortaa (geometric); Fredoka (chunky); Baloo 2 (chunky); M PLUS Rounded 1c (japanese)

## Pairing

The research's personality notes per category, with what to watch for [03 §4.4] [05 §1.4, §5.5]:

| Category | Reads as | Fits | Watch for |
|---|---|---|---|
| geometric sans | modern, confident; round "o"s read well small | tech, startups, competence with warmth | rounded geometric sans plus one pastel is the SaaS uniform; a Montserrat default is on the Any list |
| grotesk | neutral, Swiss, "serious software" | software, editorial, civic | an Inter-only wordmark is the AI uniform; quirky members (Bricolage Grotesque, Space Grotesk) add character |
| humanist sans | warm, approachable, trustworthy | healthcare, education, civic | can read as generic; give it one owned detail |
| transitional serif | established, credible | publishing, finance, law | the all-caps navy serif is the finance cliché |
| old-style serif | heritage, literary, artisanal | hospitality, craft, books | fine detail dies small; check the 16 px panel |
| didone display | luxury, fashion, editorial | beauty, fashion, premium | the default didone is a beauty cliché; hairlines fail small sizes |
| slab | sturdy, crafted, industrial | outdoors, trades, Americana | heavy slabs crowd at small sizes; open the tracking |
| display | loud, distinctive | entertainment, sports, streetwear | wordmarks only, never body text |
| mono | technical, developer, data | developer tools, data, retro-futurist | even widths make long names wide; check text legibility |
| rounded | friendly, playful | kids, food, wellness, consumer apps | rounded "Smokies" type is saturated in direct-to-consumer brands |

What the evidence says about type [02 §G]:

- Sans serif reads as potent and utilitarian; serif reads as active and hedonic. Match potency and activity to the product, not to taste [02 §27; moderate].
- Weight is the lever between rugged and competent (heavy) and sophisticated (light) [02 §26; moderate-strong].
- Harmony, naturalness and a light flourish raise every Aaker dimension; elaborate type trades competence for excitement [02 §25, §26; strong].
- Uppercase reads premium and masculine, lowercase approachable; tight tracking signals safety [02 §28; moderate].
- Handwritten type only for emotional, artisanal, new brands [02 §28; moderate].

Pairing rules [synthesis from 03 §4.4 and 02 §G]:

1. One family carries the name. Add at most one companion, for a tagline or brand text.
2. Contrast in class, not in mood: a serif with a sans of the same temperament, never two calm-and-loud opposites.
3. The cheapest pairing is one family at two weights (a 650 wordmark, a 400 tagline).
4. Never pair two display faces, and never two near-identical families of one class: it reads as a mistake.
5. A territory names one to three families; the first one sets the board's initial-letter specimen [code].
6. Record the wordmark with `uv run logomaker brand set <slug> --font "wordmark=<Family>:<weight>"` (quoted, so a family of two or more words stays one value), naming the family and weight `concept.py` draws. BRAND.md lists brand.json's fonts and every family the type is drawn in, so a mismatch shows up as two families [code].

## Licensing

- SIL OFL 1.1 (most of Google Fonts) explicitly allows using the fonts "to create logos or other graphics" with "no additional license or permission" (FAQ 1.1); the artwork is yours (1.1.1), needs no acknowledgement (1.1.2) and is not subject to the OFL (1.13); AI-based design tools may use OFL fonts "as long as the resulting work is not intended to be a font" (1.26) [03 §4.1].
- Reserved Font Names matter only if you modify or re-format the font itself (FAQ 2.2, 5.1 to 5.4). Outlined glyphs in a logo are artwork, not a font, so they do not apply to the logo. Avoid font names tied to trademarks you do not own (5.5) [03 §4.1].
- Apache 2.0 (Roboto Slab and Ultra in this catalogue) also permits logo use, but its licence and notice must travel with any redistributed font file; the UFL requires renaming a modified font [03 §4.1].
- Ship the licence file: `package build` copies each family's TTF files and licence file into `package/fonts/<slug>/` and writes `fonts/FONT-NOTICE.md`; a family cached without a licence file is copied with a warning to confirm its licence [code].
- Convert to outlines: every deliverable SVG and PDF holds paths only, never `<text>` or an embedded font, which removes the runtime font dependency and freezes the kerning and any custom letter changes [03 §4.2]. The kit outlines type when it builds, so this is automatic [code].
- The OFL licenses the font software. It does not stop the owner registering the outlined wordmark as a trademark, and that trademark covers the logo, not the typeface [03 §4.1].

## Sources

03 §4.1 (open licences), §4.2 (outlines), §4.3 (programmatic sourcing), §4.4 (logo-grade families and their personality); 02 §G entries 25 to 28 (typography and personality); 05 §1.4 and §5.5 (saturated type styles); spec §6.5; code: `assets/fonts/catalog.json`, `fonts.py`, `kit/text.py`, `sheets.territories_board`, `export_docs.fonts` and `export_docs.typefaces`.
