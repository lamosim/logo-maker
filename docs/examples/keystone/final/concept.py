from logomaker.kit import *

META = Meta(slug="arch", idea="A heavy round arch on its own feet whose keystone rises above the crown: the piece that holds everything together",
            logo_type="pictorial", motifs=["arch", "keystone"], territory="hearth-stone")
# radius: the arch's outer radius; band: its thickness at the feet; drop: how far the intrados' centre sits below the
# springing line, which thickens the crown by that much (curves look thinner than straight strokes, so the crown carries
# about 5 percent more than the feet); leg: the straight feet under the springing line; half: half the keystone's angle
# (15 degrees each side of vertical); rise: how far the keystone's flat top stands above the crown; joint: the mortar
# joint either side of the keystone (0 merges the three stones into one silhouette); cap, weight and tracking: the wordmark;
# gap: the space between symbol and wordmark in both lockups, about two thirds of x, so the stacked primary reads as one.
PARAMS = Params(radius=400, band=180, drop=9, leg=200, half=15, rise=70, joint=30, cap=260, weight=700, tracking=10, gap=170)
TIERS = {
    "full": {},
    "compact": {"wordmark": False, "joint": 40},
    "small": {"wordmark": False, "band": 200, "rise": 90, "joint": 60},
    # the favicon on a 16 px grid, 50 units a pixel: band 4 px, opening 8 px, feet 3 px, keystone 2 px proud, no joints
    "favicon": {"wordmark": False, "band": 200, "drop": 0, "leg": 150, "rise": 100, "joint": 0},
}


def build(p):
    inner = p.radius - p.band
    outline = union(intersect(circle(0, 0, p.radius), rect(-p.radius, 0, 2 * p.radius, p.radius)),
                    rect(-p.radius, -p.leg, 2 * p.radius, p.leg))
    opening = union(circle(0, -p.drop, inner), rect(-inner, -p.leg - 1, 2 * inner, p.leg + 1))
    arch = subtract(outline, opening)
    top = p.radius + p.rise
    # the keystone: radial sides at 90 +- half degrees, a flat top `rise` above the crown, its underside on the intrados
    sector = wedge(0, 0, 2 * top, 90 - p.half, 90 + p.half)
    keystone = subtract(intersect(sector, rect(-top, 0, 2 * top, top)), opening)
    if p.joint > 0:
        symbol = union(subtract(arch, offset(keystone, p.joint)), keystone)
    else:
        symbol = union(arch, keystone)
    # The wordmark: Bricolage Grotesque as the territory set it, with no quirk (the symbol carries the idea), tracked
    # open by 10/1000 em because its display cut sets tight for a 32 px header
    word = text("Keystone", "Bricolage Grotesque", weight=p.weight, cap_height=p.cap, tracking=p.tracking)
    # Stacked, the primary lockup (brand.json): the top surface, the app icon, is a square placement
    return Mark(symbol=symbol, wordmark=word, lockup="stacked", gap=p.gap)
