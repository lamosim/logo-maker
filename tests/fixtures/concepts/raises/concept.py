from logomaker.kit import *

META = Meta(slug="raises", idea="broken on purpose", logo_type="abstract", motifs=[])
PARAMS = Params()
TIERS = {"full": {}}


def build(p):
    raise RuntimeError("boom")
