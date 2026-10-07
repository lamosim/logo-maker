from logomaker.kit import *

META = Meta(slug="ring-gap", idea="A heavy ring with a gap at the top that only its keystone closes: the loop holds once the last piece is in",
            logo_type="abstract", motifs=["ring", "keystone"], territory="hearth-stone")
# radius and band: the ring; half: half the keystone's angle; joint: the mortar joint either side of the keystone;
# key: 1 seats the keystone in the gap, 0 leaves the gap open.
PARAMS = Params(radius=400, band=150, half=15, joint=30, key=1, cap=300, weight=700)
TIERS = {
    "full": {},
    "compact": {"wordmark": False, "joint": 44},
    "small": {"wordmark": False, "band": 175, "joint": 62},
    "favicon": {"wordmark": False, "band": 190, "joint": 0},
}


def build(p):
    inner = p.radius - p.band
    if p.key and p.joint <= 0:  # at favicon sizes the joints cannot stay open: the keystone closes the ring
        symbol = ring(0, 0, p.radius, p.band)
    elif p.key:
        band = ring(0, 0, p.radius, p.band)
        joints = [line(0, 0, 0, p.radius + 40, p.joint) for _ in range(2)]
        joints = union(rotate(joints[0], -p.half), rotate(joints[1], p.half))
        symbol = subtract(band, subtract(joints, circle(0, 0, inner - 20)))
    else:
        symbol = ring(0, 0, p.radius, p.band, start=90 + p.half, end=90 - p.half)
    word = text("Keystone", "Bricolage Grotesque", weight=p.weight, cap_height=p.cap)
    return Mark(symbol=symbol, wordmark=word, lockup="horizontal")
