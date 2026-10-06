from logomaker.kit import *

META = Meta(slug="near-miss", idea="a quadrilateral with one edge 2 degrees off", logo_type="abstract", motifs=["block"])
PARAMS = Params()
TIERS = {"full": {}}


def build(p):
    return Mark(symbol=polygon([(0, 0), (300, 10), (300, 310), (0, 300)], free=True))
