from logomaker.kit import *

META = Meta(slug="good", idea="A ring with a gap holding the name", logo_type="combination", motifs=["ring"])
PARAMS = Params(stroke=90, gap=None)
TIERS = {
    "full": {},
    "compact": {},
    "small": {"stroke": 130, "wordmark": False},
    "favicon": {"stroke": 170, "wordmark": False},
}


def build(p):
    symbol = ring(0, 0, 400, p.stroke, start=30, end=330)
    word = text("Good", family="Fira Code", weight=600, cap_height=180)
    return Mark(symbol=symbol, wordmark=word, lockup="horizontal", gap=p.gap)
