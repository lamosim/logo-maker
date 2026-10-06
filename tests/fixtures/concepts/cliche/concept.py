from logomaker.kit import *

META = Meta(slug="cliche", idea="an AI hexagon with a sparkle", logo_type="abstract", motifs=["hexagon", "sparkle", "wave"])
PARAMS = Params()
TIERS = {"full": {}}


def build(p):
    return Mark(symbol=union(regular_polygon(0, 0, 300, 6), regular_polygon(0, 0, 60, 4, rotation=45)))
