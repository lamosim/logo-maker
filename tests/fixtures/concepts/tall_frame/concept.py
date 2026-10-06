from logomaker.kit import *

META = Meta(slug="tall-frame", idea="a frame twice as tall as wide, measured by its height", logo_type="abstract", motifs=["frame"])
PARAMS = Params()
TIERS = {"full": {}, "favicon": {}}


def build(p):
    return Mark(symbol=subtract(rect_centered(0, 0, 160, 320), rect_centered(0, 0, 130, 290)))
