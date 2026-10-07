# Evidence rules

Read this when: setting the feature targets in strategy.md and strategy.json (phase 2), scoring congruence (criterion 9), and whenever the owner's taste and the evidence pull apart.

These are the twenty rules of the empirical logo literature, each with the research memo's confidence: strong (replicated across labs or top journals, mechanism known), moderate-strong, moderate (one multi-study top-journal paper or several weaker ones), weak (one low-tier or industry study, or an analogy) [02]. They are defaults for `strategy.json`'s `targets`; override one only with a reason written into strategy.md. A tag such as [02 §21] cites entry 21 of report 02; [02 §K] cites its section K.

## Twenty rules

| # | Rule | Confidence | Study behind it | Sets |
|---|---|---|---|---|
| 1 | Start from the high-recognition profile: representational or organic form, balanced but not mirrored, moderately elaborate, one repeated element | strong | Henderson & Cote 1998 (195 logos); van der Lans et al. 2009 (10 countries) | `shape`, `symmetry`, `complexity` |
| 2 | Moderate complexity: too simple reads generic (false recognition), too complex is slow on first exposure; scale it to expected exposure | strong | Henderson & Cote 1998; Van Grinsven & Das 2016 | `complexity` |
| 3 | New brands lead with a legible wordmark and a descriptive category cue; the symbol-only mark is earned later | strong | Luffarelli, Mukesh & Mahmood 2019 (597 real logos); Morgan, Fajardo & Townsend 2021 | `descriptive_cue`, `logo_type` |
| 4 | No descriptive cue in a negatively valenced category (pest control, funerals) | strong | Luffarelli, Mukesh & Mahmood 2019 | `descriptive_cue` |
| 5 | Round forms for comfort, care and warmth; angular for durability, strength and precision | strong | Jiang, Gorn, Galli & Chattopadhyay 2016 | `shape` |
| 6 | Default to symmetry; dose asymmetry in proportion to the brand's excitement | strong | Bajaj & Bond 2018; Luffarelli, Stamatogiannakis & Yang 2019 | `symmetry` |
| 7 | Stable, upright, grounded forms for trust, safety and efficacy; tilt and implied motion only for excitement, openness and hedonic brands | moderate-strong | Rahinel & Nelson 2016; Huang, Cai & Xu 2021; Zhou & Chen 2026; Cian, Krishna & Elder 2014 | `dynamism` |
| 8 | Frame or badge for risky categories (finance, security, health); open marks for low-risk, hedonic ones | moderate-strong | Fajardo, Zhang & Tsiros 2016 | `frame` |
| 9 | Flat by default; subtle depth only for tangible products on clean backgrounds | moderate | Togawa & Onzo 2026 | kit marks are flat |
| 10 | Heavy strokes for power, competence and ruggedness; light strokes for sophistication and sincerity | moderate | Eyni et al. 2023 (over 4,000 participants) | `weight` |
| 11 | Red and saturation for excitement; blue for competence; dark for durability; light for friendliness; black and white for status in a new premium brand; green or blue for eco and ethics; check hues per culture | strong for red, blue and saturation; moderate otherwise | Labrecque & Milne 2012; Madden, Hewett & Roth 2000; Sundar & Kellaris 2017; Yue & Xia 2026 | `hue_family`, `saturation`, `lightness` |
| 12 | Type: harmony, naturalness and a light flourish lift every dimension; elaborate trades competence for excitement; sans for potency, serif for activity; uppercase premium, lowercase approachable; handwriting only for emotional, artisanal, new brands | moderate | Henderson, Giese & Cote 2004; Grohmann, Giese & Parkman 2013; Doyle & Bottomley 2006; Zhang et al. 2025; Wen & Lurie 2018; Schroll et al. 2018 | `typeface_class` |
| 13 | Name sound, shape and typeface agree: front vowels with small, light, angular marks; back vowels with large, heavy, round ones; round type for sweet and soft | moderate-strong | Klink 2000, 2003; Lowrey & Shrum 2007; Velasco et al. 2014 | `name_sound` |
| 14 | Incomplete or cut letterforms only when innovation outranks trust | strong | Hagtvedt 2011 | concept choice |
| 15 | Concrete imagery for heritage positioning, abstract for modern | moderate | Zheng & Zhu 2026; Machado et al. 2015 | `logo_type` |
| 16 | Ornament and craft detail signal luxury and innovativeness, but not for familiar brands or basic products | moderate-strong | Mahmood, Luffarelli & Mukesh 2019; Tang, Huang & Zhang 2025; Chen et al. 2025 | `complexity` |
| 17 | Redesign by evolution: keep silhouette and colour, change one attribute; backlash grows with the change and with the committed base | moderate-strong | Walsh, Winterich & Mittal 2010; Müller, Kocher & Crettaz 2013 | out of scope (new ventures only) |
| 18 | Memorability is one dominant distinctive silhouette plus one owned colour; test by drawing from memory and by one-second recognition | moderate | image-memorability research; Signs.com 2017 | criteria 2 and 3 |
| 19 | Small sizes: symbol-only at 64 px and below, no text under about 7 px x-height, high contrast, a closed silhouette, a distinct hue, a rounded-square app container; test at 16, 32, 48 and 180 px on light and dark | moderate | Legge & Bigelow 2011; icon-search studies | tiers, audit |
| 20 | AI provenance: quality parity, a penalty on disclosure, worst for luxury, authentic or emotional positioning; frame it as human-augmented, show process, favour restraint; never let an LLM stand in for consumer tests | moderate | Bellaiche et al. 2023; Xu & Mehta 2022; "Seeing Is Not Perceiving" 2026 | presentation |

The audit enforces part of rules 1 and 19 [code]: `generic_profile` notes a full symbol whose height is 0.72 to 0.82 of its width (the false-recognition band); `text_legibility` fails a wordmark x-height under 7 px at the brand's minimum lockup widths; `min_feature`, `tiny_parts` and `one_colour_merge` test the small tiers.

## Feature to personality table

Aaker's dimensions with their facets: sincerity (down-to-earth, honest, wholesome, cheerful), excitement (daring, spirited, imaginative, up-to-date), competence (reliable, intelligent, successful), sophistication (upper-class, charming), ruggedness (outdoorsy, tough). Each cell is the setting that raises the dimension; numbers in parentheses are entries of report 02 [02 §L].

| Feature | Sincerity | Excitement | Competence | Sophistication | Ruggedness |
|---|---|---|---|---|---|
| Shape | round, organic curves (4, 24) | angular-dynamic, diagonal, motion (4, 20) | geometric precision, stable base (4, 9) | slender refined curves, thin lines (10, 26) | hard angles, heavy forms (4, 10) |
| Symmetry and stability | symmetric, upright (6, 9) | dosed asymmetry, tilt (5, 6, 9) | symmetric, stable (6, 7) | symmetric, harmonious (6) | grounded; symmetry matters less |
| Complexity | simple to moderate, natural (1) | moderate to elaborate, active (1, 26) | simple, flat (18) | ornamented craft cues, new brands (18) | simple, bold (17) |
| Hue | white, pink, light yellow (not re-verified); green for wholesome (21, 23) | red, orange (21) | blue; black and white for status (21, 23) | black, purple, monochrome (21, 23) | brown, dark green (21, 23) |
| Value and saturation | light, moderate saturation | high saturation (21) | mid-dark, controlled | dark or monochrome, low saturation (23) | dark, low lightness (21, 23) |
| Typeface | natural or handwritten (new brands), harmonious, lowercase (25, 28) | elaborate, active, serif, flourish (26, 27) | sans serif, uppercase, moderate to heavy (26, 27) | light or extended, serif, flourish (26, 27) | heavy, condensed sans, uppercase (10, 26) |
| Name sound | soft fricatives, mid vowels | front vowels: fast, light (29) | stops, voiced consonants: potent (29) | front vowels with fricatives: delicate (29) | back vowels, stops: large, strong (29) |
| Frame | open or a gentle badge | open, unframed (8) | framed in risky categories (8) | thin frame or none | shield or badge (8) |
| Dynamism | static, calm (20) | implied motion, drag-force cues (20) | static or restrained | slow, restrained | static, weighty |

Masculinity and femininity overlay the grid: angular, dark, uppercase and geometric read masculine; organic, light or pink and lowercase read feminine [02 §24, §28].

## Boundary conditions

When a rule flips or fades [02]:

- Negative categories: a descriptive cue hurts instead of helping (rule 4) [02 §12].
- Familiar brands: descriptiveness adds little; image-based logos suit them while unfamiliar brands do better with text; complexity's craft signal and monochrome's status gain both weaken; handwriting does nothing for an already-attached brand [02 §12, §13, §18, §23, §28]. Every brand here is new, so read these as "not yet".
- Conservative or prevention-focused audiences: they dislike asymmetric logos more, punish incomplete letterforms, and download fewer apps with unstable-looking icons [02 §7, §15, §31].
- Cluttered contexts and cognitive load: round-versus-angular fades when visual imagery is blocked; 3D helps only on clean backgrounds; symmetry signals quality only under low load; slanted type raises perceived risk most under load [02 §4, §7, §9, §11].
- Luxury: complexity reads as craftsmanship and luxury; monochrome reads as status; AI as the design source cuts brand essence for emotion-driven luxury [02 §18, §23, §32].
- AI disclosure: the penalty comes from disclosure and domain, not quality; it is smaller for AI-trusting consumers and high-tech products [02 §32].
- Excitement: asymmetry raises equity for exciting brands and lowers it for sincere, competent or traditional ones [02 §6].
- Product type: implied motion pays more for hedonic than utilitarian products; serif fits hedonic, open brands and sans utilitarian, controlled ones [02 §20, §27].
- Sound symbolism helps only when the connoted attribute is desirable in the category: front vowels for knives, back vowels for SUVs [02 §29].
- Proportion: a golden-ratio box is preferred only for nature-based forms; geometric marks were preferred at 1:1 [02 §3].
- Stroke weight: the thickness effect is weaker for high-power or high-visuospatial consumers [02 §10].

## What the evidence does not say

- No peer-reviewed experiment tests consumer response to AI-generated logos; rule 20 extrapolates from AI art, advertising and product design [02 §J, §M].
- No memorability model is trained on logos; rule 18 rests on general image memorability and one industry study [02 §19, §M].
- Logo-specific small-size experiments are scarce; rule 19's thresholds come from reading and icon research [02 §31].
- Hue meanings beyond red and blue, the country-level colour results and the complexity-by-repetition direction were not re-verified; do not hard-code them [02 §M].
- Several 2026 and 2027 papers (logo facing direction, upward tilt, overlapping letters) were seen by title only and are not rules [02 §M].
- LLM judges reproduced at most two of six canonical visual-marketing effects and show a stronger pro-human bias than people; Claude's congruence score is a reasoned judgment, not a measurement [02 §32].
- Ratios and golden-ratio grids are construction aids, not evidence of quality; they never go in a rationale [02 §3] [05 §5.3].

## Sources

02 §A to §J entries 1 to 33 (the studies), §K (the twenty rules), §L (feature to personality), §M (gaps and unverified claims); 05 §5.3 (construction myths); code: `audit.py` (`GENERIC_ASPECT`, `X_HEIGHT_MIN_PX`, the raster checks).
