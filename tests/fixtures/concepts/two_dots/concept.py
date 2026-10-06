from logomaker.kit import *

META = Meta(slug="two-dots", idea="two dots a hairline apart that merge at favicon size", logo_type="abstract", motifs=["dots"])
PARAMS = Params()
TIERS = {"full": {}, "favicon": {}}


def build(p):
    # A 2-unit gap: about 12 px wide at 512 px, under half a pixel at 16 px. (At x = +-25 the 10-unit gap stays open at 16 px.)
    return Mark(symbol=union(circle(-21, 0, 20), circle(21, 0, 20)))
