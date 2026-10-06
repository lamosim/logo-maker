import random

from logomaker.kit import *

META = Meta(slug="random", idea="nondeterministic on purpose", logo_type="abstract", motifs=[])
PARAMS = Params()
TIERS = {"full": {}}


def build(p):
    return Mark(symbol=circle(0, 0, random.uniform(100.0, 300.0), free=True))
