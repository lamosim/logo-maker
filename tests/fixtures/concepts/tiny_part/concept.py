from logomaker.kit import *

META = Meta(slug="tiny-part", idea="a disc with a speck", logo_type="abstract", motifs=["disc"])
PARAMS = Params()
TIERS = {"full": {}, "small": {}}


def build(p):
    return Mark(symbol=union(circle(0, 0, 300), circle(400, 0, 5)))
