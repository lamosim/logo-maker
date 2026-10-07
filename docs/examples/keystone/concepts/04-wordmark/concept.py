from logomaker.kit import *

META = Meta(slug="wordmark", idea="The name in Bricolage Grotesque with one quirk: the counter of the o is cut as a round arch with a flat sill",
            logo_type="wordmark", motifs=["wordmark", "arch counter"], territory="hearth-stone")
# weight and cap: the wordmark; width: the arch counter's width as a share of the o's own counter; sill: how far the flat
# bottom of the arch sits above the counter's lowest point, as a share of its height; icon: 1 draws the o alone, the
# compact, small and favicon tiers' symbol.
PARAMS = Params(weight=700, cap=300, width=0.86, sill=0.08, icon=0)
TIERS = {
    "full": {},
    "compact": {"icon": 1},
    "small": {"icon": 1, "width": 0.92},
    "favicon": {"icon": 1, "width": 0.95, "weight": 800},
}


def arch_counter(word, index, p):
    """The word with the counter of its o (glyph `index`) re-cut as an arch: a semicircle on a rectangle, its sill flat."""
    o = word.glyph_bounds[index]
    counter = min(intersect(word, rect(o.x0, o.y0, o.w, o.h)).subpaths(), key=lambda part: part.area)
    c = counter.bounds
    w = c.w * p.width
    sill = c.y0 + c.h * p.sill
    spring = c.y1 - w / 2  # the springing line: the semicircle's centre, so its top meets the old counter's top
    arch = union(rect(c.cx - w / 2, sill, w, spring - sill), circle(c.cx, spring, w / 2))
    return subtract(union(word, counter), arch)


def build(p):
    if p.icon:
        o = text("o", "Bricolage Grotesque", weight=p.weight, cap_height=700)
        return Mark(symbol=arch_counter(o, 0, p))
    word = text("Keystone", "Bricolage Grotesque", weight=p.weight, cap_height=p.cap)
    return Mark(wordmark=arch_counter(word, 5, p))
