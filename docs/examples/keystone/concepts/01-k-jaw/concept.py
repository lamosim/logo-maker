import math

from logomaker.kit import *

META = Meta(slug="k-jaw", idea="Keystone's K is held together by a keystone: the stone at its junction, where the arm and the leg lean in, noses into the jaw",
            logo_type="lettermark", motifs=["letter K", "keystone"], territory="hearth-stone")
# Round 3: the stone moved from the jaw's mouth to the junction. The K is an arch lying on its side, the jaw its opening,
# so its keystone sits at the junction, wide against the stem and narrow towards the jaw, its sides at 15 degrees.
# kweight: the K's weight; back: the stone's height against the stem; reach: how far it noses past the jaw's tip;
# joint: the gap around the stone (0 at favicon sizes, where the joints would close up anyway).
PARAMS = Params(kweight=800, back=190, reach=80, joint=30, cap=300, weight=700)
TIERS = {
    "full": {},
    "compact": {"wordmark": False, "joint": 40},
    "small": {"wordmark": False, "joint": 52, "back": 210, "reach": 100},
    "favicon": {"wordmark": False, "joint": 0, "back": 210, "reach": 110},
}


def build(p):
    k = center(glyph("K", "Bricolage Grotesque", weight=p.kweight, cap_height=700))
    box = k.bounds
    counters = subtract(rect(box.x0, box.y0, box.w, box.h), k).subpaths()
    upper = max(counters, key=lambda part: part.bounds.cy)  # the counter between the stem and the arm
    jaw = max(counters, key=lambda part: part.bounds.cx)    # the counter between the arm and the leg
    stem = upper.bounds.x0                                  # the stem's right edge
    tip = jaw.bounds.x0                                     # where the jaw's two sides meet
    length = tip + p.reach - stem
    nose = p.back - 2 * length * math.tan(math.radians(15))  # the sides close in at 15 degrees
    stone = polygon([(stem, p.back / 2), (tip + p.reach, nose / 2), (tip + p.reach, -nose / 2), (stem, -p.back / 2)])
    symbol = union(subtract(k, offset(stone, p.joint)), stone) if p.joint > 0 else union(k, stone)
    word = text("Keystone", "Bricolage Grotesque", weight=p.weight, cap_height=p.cap)
    return Mark(symbol=symbol, wordmark=word, lockup="horizontal")
