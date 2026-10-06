from logomaker.kit import *

META = Meta(slug="thin-stroke", idea="a hairline ring", logo_type="abstract", motifs=["ring"])
PARAMS = Params()
TIERS = {"full": {}, "favicon": {}}


def build(p):
    return Mark(symbol=ring(0, 0, 300, 6))
