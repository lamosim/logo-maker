from logomaker.kit import *

META = Meta(slug="arch", idea="A heavy round arch on its own feet whose keystone rises above the crown: the piece that holds everything together",
            logo_type="pictorial", motifs=["arch", "keystone"], territory="hearth-stone")
# radius: the arch's outer radius; band: its thickness; leg: the straight feet under the springing line; half: half the
# keystone's angle (15 degrees each side of vertical); rise: how far the keystone's flat top stands above the crown;
# joint: the mortar joint either side of the keystone (0 merges the three stones into one silhouette).
PARAMS = Params(radius=400, band=180, leg=200, half=15, rise=70, joint=30, cap=300, weight=700)
TIERS = {
    "full": {},
    "compact": {"wordmark": False, "joint": 40},
    "small": {"wordmark": False, "band": 200, "rise": 90, "joint": 72},
    "favicon": {"wordmark": False, "band": 215, "rise": 100, "joint": 0},
}


def build(p):
    inner = p.radius - p.band
    crown = ring(0, 0, p.radius, p.band, start=0, end=180)
    feet = union(rect(-p.radius, -p.leg, p.band, p.leg), rect(p.radius - p.band, -p.leg, p.band, p.leg))
    arch = union(crown, feet)
    top = p.radius + p.rise
    # the keystone: radial sides at 90 +- half degrees, a flat top `rise` above the crown, its underside on the intrados
    sector = wedge(0, 0, 2 * top, 90 - p.half, 90 + p.half)
    keystone = subtract(intersect(sector, rect(-top, 0, 2 * top, top)), circle(0, 0, inner))
    if p.joint > 0:
        symbol = union(subtract(arch, offset(keystone, p.joint)), keystone)
    else:
        symbol = union(arch, keystone)
    word = text("Keystone", "Bricolage Grotesque", weight=p.weight, cap_height=p.cap)
    return Mark(symbol=symbol, wordmark=word, lockup="horizontal")
