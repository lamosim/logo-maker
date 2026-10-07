import math

from logomaker.kit import *

META = Meta(slug="dovetail", idea="Two stacked stones locked by one keystone-shaped dovetail: the piece that holds everything together",
            logo_type="abstract", motifs=["stacked blocks", "dovetail", "keystone"], territory="hearth-stone")
# Round 2: no tile. A lower stone, square on the ground, grows a dovetail tail (its sides lean out at 15 degrees) into an
# upper stone with rounded shoulders. width: both stones; lower and upper: their heights; joint: the cut between them;
# neck: the tail's width where it leaves the lower stone; height: how tall the tail stands.
PARAMS = Params(width=760, lower=330, upper=300, corner=60, joint=40, neck=170, height=260, cap=300, weight=700)
TIERS = {
    "full": {},
    "compact": {"wordmark": False, "joint": 50},
    "small": {"wordmark": False, "joint": 70, "neck": 190},
    "favicon": {"wordmark": False, "joint": 110, "neck": 220, "height": 250},
}


def build(p):
    spread = p.height * math.tan(math.radians(15))
    lower = rect(-p.width / 2, -p.lower, p.width, p.lower)
    tail = polygon([(-p.neck / 2, -1), (-p.neck / 2 - spread, p.height), (p.neck / 2 + spread, p.height), (p.neck / 2, -1)])
    upper = rrect(-p.width / 2, -p.corner, p.width, p.upper + p.corner, p.corner)
    upper = subtract(subtract(upper, offset(tail, p.joint)), rect(-p.width, -p.lower, 2 * p.width, p.lower + p.joint))
    word = text("Keystone", "Bricolage Grotesque", weight=p.weight, cap_height=p.cap)
    return Mark(symbol=union(lower, tail, upper), wordmark=word, lockup="horizontal")
