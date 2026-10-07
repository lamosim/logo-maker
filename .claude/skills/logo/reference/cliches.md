# Cliché blacklist

Read this when: writing the category audit in strategy, striking ideas in concepts/ideas.md, checking a motif the owner asks for, or justifying a twisted motif.

This page is generated from `assets/cliches.json` by `scripts/build_reference.py`. The audit reads the same JSON, so edit the JSON and re-run `uv run python scripts/build_reference.py`; never edit this page by hand.

A motif on this list is famous but not unique: it signals the category, not the brand [05 §3.3]. Use one only when the brief makes it the strategy, and then twist it until it scores as unique against the five nearest competitors [05 §5.5]. The AI-era cliché (hexagons, sparkles, concentric apertures, blue-violet gradients), with its evidence and what to reach for instead, is in `trends.md` under "The AI-era cliche" [05 §1.3].

## How the audit reads this list

- The audit's `cliche` check compares every entry of `META.motifs` with the Any category motifs and with the motifs of each industry the brand resolves to [code].
- The industry tag is brand.json's `industry` (`uv run logomaker brand set <slug> --industry "<tag>"`), else brief.json's `industry`. Every industry whose key or alias appears in the tag as whole words counts. The audit's `industry` info line names them, or says that none matched and only the Any category list was used [code].
- Terms match as whole words, so "key" does not find "keystone"; a term of three or more letters also matches its plural with -s or -es, so "hexagon" finds "hexagons" [code].
- A match is a warning that names the term, never a failure. Address it in critique.md: twist and justify it, or kill the idea [spec §8.1].
- Styles are not checked by the audit. Check them yourself against the territory's palette and the wordmark's typeface [code].
- The check only sees what `META.motifs` says, so name each motif plainly: "hexagon", not "six-sided cell".

## Any category

These apply to every brand, whatever its industry.

Motifs: script l, flourish monogram, feather, pennant, watermelon, stick figure, v ball, generic asterisk, trans-letter swoosh, letter in a circle, swoosh, infinity, globe

Styles: mesh gradient, metaball, helvetica default, futura default, montserrat default

## By industry

Each heading is an industry key. Any of its aliases, or the key itself, in the brand's industry tag selects it.

### ai

Aliases: ai, ml, machine learning, artificial intelligence, tech, software, llm, agent

Motifs: hexagon, sparkle, star, concentric, aperture, orbit, node, neural, brain, circuit, cube, pixel

Styles: blue-violet gradient, glow, inter-only wordmark

### saas

Aliases: saas, startup, app, platform, productivity

Motifs: s swoosh, three overlapping circles, chat bubble, rocket, lightning, infinity loop

Styles: rounded geometric sans with one pastel

### crypto

Aliases: crypto, web3, blockchain, defi, token

Motifs: hexagon, coin, chain, cube, v wings

Styles: metallic gradient

### fintech

Aliases: fintech, finance, banking, payment, payments, payments processing, invoicing, accounting, insurance, lending, investing

Motifs: upward arrow, bar chart, shield, pillar, column, globe, handshake, pie, dollar sign, coin, piggy bank

Styles: all-caps navy serif, bank blue

### real-estate

Aliases: real estate, realty, construction, property, housing, architecture

Motifs: roof, house, building, key, skyline, chimney

Styles: serif and gold

### healthcare

Aliases: health, healthcare, medical, wellness, clinic, pharma, therapy

Motifs: caduceus, rod of asclepius, cross, heart, swoosh people, leaf in hand, heartbeat, dna, pill

Styles: teal rounded sans

### dental

Aliases: dental, dentist, dentistry, orthodontics, orthodontist, orthodontic

Motifs: tooth, smiling tooth, tooth with leaf, tooth with sparkle

Styles: pastel blue

### legal

Aliases: legal, law, attorney, lawyer

Motifs: scales, gavel, pillar, lion, shield, serif monogram in a box

Styles: black and gold serif

### consulting

Aliases: consulting, hr, coaching, advisory, recruiting, agency

Motifs: abstract figures in a circle, puzzle, three people, lightbulb, compass, mountain peak

Styles: corporate blue swoosh

### education

Aliases: education, school, learning, tutoring, course, edtech

Motifs: open book, graduation cap, apple, torch, tree of knowledge, shield crest

Styles: collegiate serif

### nonprofit

Aliases: nonprofit, charity, community, foundation, ngo

Motifs: hands, heart, globe, circle of people, dove, ribbon

Styles: rainbow gradient

### food

Aliases: food, restaurant, cafe, catering, snack, meal, kitchen, bakery

Motifs: fork and knife, chef hat, plate, steam, slice, tomato

Styles: script on distressed badge

### coffee

Aliases: coffee, roaster, espresso

Motifs: bean, cup with steam, mug in circle

Styles: kraft brown badge

### fitness

Aliases: fitness, gym, training, sport, athletic, running

Motifs: dumbbell, flexing figure, running figure, speed lines, flame, lightning

Styles: heavy italic condensed red and black

### beauty

Aliases: beauty, fashion, cosmetic, skincare, salon, apparel

Motifs: lotus, butterfly, feather, mirrored script monogram, lips

Styles: thin all-caps sans, default didone

### sustainability

Aliases: sustainability, eco, green, climate, environment, organic, solar

Motifs: leaf, sprout, globe with leaf, recycling arrows, water drop, tree in circle, hands cradling earth

Styles: earth-tone uniform

### logistics

Aliases: logistics, delivery, shipping, freight, courier, moving

Motifs: arrow, box with arrow, truck, wing, swoosh, globe with arrow

Styles: orange and blue

### travel

Aliases: travel, hospitality, hotel, tourism, vacation, rental

Motifs: plane, sun over waves, palm tree, compass, suitcase, globe, pin

Styles: escape script

### creative

Aliases: creative, design, studio, media, marketing, branding, video

Motifs: pencil, brush, spark, asterisk, eye, colour wheel

Styles: ultra-minimal black wordmark

### pets

Aliases: pet, vet, vets, veterinary, veterinarian, animal, dog, cat

Motifs: paw, bone, dog silhouette, heart paw

Styles: friendly rounded sans

### photography

Aliases: photo, photography, photographer, photographers, camera, studio photo

Motifs: camera, aperture, lens flare

Styles: thin signature script

### trades

Aliases: plumbing, hvac, electrical, contractor, handyman, roofing, cleaning

Motifs: wrench, droplet, flame, house with swoosh, snowflake and flame

Styles: blue and red split

### cannabis

Aliases: cannabis, cbd, hemp, dispensary

Motifs: marijuana leaf, lotus, hemp leaf

Styles: green gradient

### faith

Aliases: church, faith, ministry, religious

Motifs: cross with swoosh, dove, flame, three arcs

## How to twist a justified motif

1. Name the category cue in one sentence, and the one idea the mark must carry instead [05 §5.5].
2. Change its construction logic, not its decoration: cut it from the name's letterform, build it from the product's real geometry, or make it the negative space of something ownable [05 §3.6, §5.1].
3. Remove every neighbour it usually comes with: the hexagon's sparkle, the leaf's globe, the arrow's upward slant [05 §1.3, §5.5].
4. Describe it beside the five nearest competitors from the strategy's category audit; if two of them could own it, kill it [05 §3.3, §5.4].
5. Keep it in `META.motifs` under its plain name, so the audit's warning stays on the critique sheet, and justify it in critique.md [spec §8.1].
6. Record the owner's decision: `uv run logomaker brand decide <slug> --phase concepts --by user --note "kept the <motif>, twisted: <how>"`.

## Sources

05 §5.5 (the industry cliché blacklist, synthesised from Zillion Designs, "40 Logo Design Cliches", the LogoLounge 2025 and 2026 saturation notes, Fast Company's AI-hexagon data and Free Logo Design), 05 §1.3 and §1.4 (the AI-era cliché and the saturated list), 05 §3.3 (distinctive assets), 04 §1.2 (cliché exclusion lists in Claude logo skills), spec §8.1; code: `assets/cliches.json`, `audit.check_cliches` and `audit.resolve_industries`.
