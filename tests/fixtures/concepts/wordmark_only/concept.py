from logomaker.kit import *

META = Meta(slug="wordmark-only", idea="the name alone: no symbol and no small tiers", logo_type="wordmark")
PARAMS = Params()
TIERS = {"full": {}}


def build(p):
    return Mark(wordmark=text("Keystone", "Fira Code", weight=600, cap_height=180))
