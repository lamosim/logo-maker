"""Generate assets/fonts/catalog.json: logo-grade open families (docs/research/03-deliverable-spec.md section 4.4)."""
from __future__ import annotations

import json
import re
from pathlib import Path

BASE_TAGS = {
    "geometric sans": ["modern", "tech", "confident", "startup", "clean"],
    "grotesk": ["neutral", "editorial", "serious", "swiss"],
    "humanist sans": ["warm", "approachable", "trustworthy", "civic"],
    "transitional serif": ["established", "credible", "publishing", "finance"],
    "old-style serif": ["heritage", "literary", "artisanal", "hospitality"],
    "didone display": ["luxury", "fashion", "editorial", "elegant"],
    "slab": ["sturdy", "craft", "industrial", "americana", "outdoors"],
    "display": ["loud", "distinctive", "entertainment", "sports", "streetwear"],
    "mono": ["technical", "developer", "data", "retro-futurist"],
    "rounded": ["friendly", "playful", "kids", "food", "wellness"],
}

# The top folder of a family's google/fonts directory names its licence.
LICENCES = {"ofl": "OFL", "apache": "Apache", "ufl": "UFL"}

# (family, category, google_dir in google/fonts, extra personality tags)
FAMILIES = [
    ("Montserrat", "geometric sans", "ofl/montserrat", []),
    ("Poppins", "geometric sans", "ofl/poppins", ["rounded-geometric"]),
    ("Outfit", "geometric sans", "ofl/outfit", ["rounded-geometric"]),
    ("Jost", "geometric sans", "ofl/jost", ["futura-like"]),
    ("Plus Jakarta Sans", "geometric sans", "ofl/plusjakartasans", ["friendly"]),
    ("Sora", "geometric sans", "ofl/sora", ["crisp"]),
    ("DM Sans", "geometric sans", "ofl/dmsans", ["ui"]),
    ("Manrope", "geometric sans", "ofl/manrope", ["ui"]),
    ("Urbanist", "geometric sans", "ofl/urbanist", []),
    ("Figtree", "geometric sans", "ofl/figtree", ["friendly"]),
    ("Inter", "grotesk", "ofl/inter", ["ui"]),
    ("Space Grotesk", "grotesk", "ofl/spacegrotesk", ["quirky", "tech"]),
    ("Work Sans", "grotesk", "ofl/worksans", []),
    ("Archivo", "grotesk", "ofl/archivo", ["wide"]),
    ("Familjen Grotesk", "grotesk", "ofl/familjengrotesk", []),
    ("Bricolage Grotesque", "grotesk", "ofl/bricolagegrotesque", ["quirky", "character"]),
    ("Instrument Sans", "grotesk", "ofl/instrumentsans", []),
    ("Public Sans", "grotesk", "ofl/publicsans", ["civic"]),
    ("IBM Plex Sans", "grotesk", "ofl/ibmplexsans", ["corporate"]),
    ("Roboto", "grotesk", "ofl/roboto", ["ui"]),
    ("Geist", "grotesk", "ofl/geist", ["ui", "tech"]),
    ("Open Sans", "humanist sans", "ofl/opensans", []),
    ("Source Sans 3", "humanist sans", "ofl/sourcesans3", []),
    ("Lato", "humanist sans", "ofl/lato", []),
    ("Fira Sans", "humanist sans", "ofl/firasans", []),
    ("Nunito Sans", "humanist sans", "ofl/nunitosans", []),
    ("Alegreya Sans", "humanist sans", "ofl/alegreyasans", ["literary"]),
    ("PT Sans", "humanist sans", "ofl/ptsans", []),
    ("Cabin", "humanist sans", "ofl/cabin", []),
    ("Inclusive Sans", "humanist sans", "ofl/inclusivesans", ["accessible"]),
    ("Atkinson Hyperlegible", "humanist sans", "ofl/atkinsonhyperlegible", ["accessible"]),
    ("Libre Baskerville", "transitional serif", "ofl/librebaskerville", []),
    ("Source Serif 4", "transitional serif", "ofl/sourceserif4", []),
    ("Merriweather", "transitional serif", "ofl/merriweather", []),
    ("Lora", "transitional serif", "ofl/lora", ["calligraphic"]),
    ("Newsreader", "transitional serif", "ofl/newsreader", ["editorial"]),
    ("Literata", "transitional serif", "ofl/literata", []),
    ("Spectral", "transitional serif", "ofl/spectral", []),
    ("Crimson Pro", "transitional serif", "ofl/crimsonpro", []),
    ("Libre Caslon Text", "transitional serif", "ofl/librecaslontext", []),
    ("EB Garamond", "old-style serif", "ofl/ebgaramond", []),
    ("Cormorant", "old-style serif", "ofl/cormorant", ["delicate"]),
    ("Cardo", "old-style serif", "ofl/cardo", []),
    ("Alegreya", "old-style serif", "ofl/alegreya", []),
    ("Crimson Text", "old-style serif", "ofl/crimsontext", []),
    ("Playfair Display", "didone display", "ofl/playfairdisplay", []),
    ("Bodoni Moda", "didone display", "ofl/bodonimoda", []),
    ("DM Serif Display", "didone display", "ofl/dmserifdisplay", []),
    ("Abril Fatface", "didone display", "ofl/abrilfatface", ["heavy"]),
    ("Instrument Serif", "didone display", "ofl/instrumentserif", ["condensed"]),
    ("Gilda Display", "didone display", "ofl/gildadisplay", []),
    ("Prata", "didone display", "ofl/prata", []),
    ("Fraunces", "didone display", "ofl/fraunces", ["soft", "wonky"]),
    ("Roboto Slab", "slab", "apache/robotoslab", []),
    ("Zilla Slab", "slab", "ofl/zillaslab", []),
    ("Arvo", "slab", "ofl/arvo", []),
    ("Bitter", "slab", "ofl/bitter", []),
    ("Aleo", "slab", "ofl/aleo", []),
    ("Josefin Slab", "slab", "ofl/josefinslab", ["retro"]),
    ("Alfa Slab One", "slab", "ofl/alfaslabone", ["heavy"]),
    ("Syne", "display", "ofl/syne", ["art", "bold"]),
    ("Unbounded", "display", "ofl/unbounded", ["wide", "bold"]),
    ("Bebas Neue", "display", "ofl/bebasneue", ["condensed"]),
    ("Anton", "display", "ofl/anton", ["condensed", "heavy"]),
    ("Oswald", "display", "ofl/oswald", ["condensed"]),
    ("Archivo Black", "display", "ofl/archivoblack", ["heavy"]),
    ("Righteous", "display", "ofl/righteous", ["retro"]),
    ("Climate Crisis", "display", "ofl/climatecrisis", ["activist", "heavy"]),
    ("Rozha One", "display", "ofl/rozhaone", ["heavy"]),
    ("Ultra", "display", "apache/ultra", ["heavy"]),
    ("Space Mono", "mono", "ofl/spacemono", ["quirky"]),
    ("JetBrains Mono", "mono", "ofl/jetbrainsmono", ["code"]),
    ("IBM Plex Mono", "mono", "ofl/ibmplexmono", ["corporate"]),
    ("Azeret Mono", "mono", "ofl/azeretmono", []),
    ("DM Mono", "mono", "ofl/dmmono", []),
    ("Roboto Mono", "mono", "ofl/robotomono", []),
    ("Fira Code", "mono", "ofl/firacode", ["ligatures", "code"]),
    ("Geist Mono", "mono", "ofl/geistmono", ["tech"]),
    ("Martian Mono", "mono", "ofl/martianmono", ["wide"]),
    ("Nunito", "rounded", "ofl/nunito", []),
    ("Quicksand", "rounded", "ofl/quicksand", ["light"]),
    ("Varela Round", "rounded", "ofl/varelaround", []),
    ("Comfortaa", "rounded", "ofl/comfortaa", ["geometric"]),
    ("Fredoka", "rounded", "ofl/fredoka", ["chunky"]),
    ("Baloo 2", "rounded", "ofl/baloo2", ["chunky"]),
    ("M PLUS Rounded 1c", "rounded", "ofl/mplusrounded1c", ["japanese"]),
]


def slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]", "", family.lower())


def main() -> None:
    entries = []
    for family, category, google_dir, extra in FAMILIES:
        licence = LICENCES.get((google_dir or "").split("/", 1)[0])
        if licence is None:
            raise ValueError(f"{family}: google_dir must be ofl/<dir>, apache/<dir> or ufl/<dir>, not {google_dir!r}")
        entries.append({
            "family": family,
            "slug": slug(family),
            "category": category,
            "license": licence,
            "personality": BASE_TAGS[category] + extra,
            "google_dir": google_dir,
        })
    out = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "catalog.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"families": entries}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(entries)} families to {out}")


if __name__ == "__main__":
    main()
