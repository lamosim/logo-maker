"""Pydantic models for brand state, brief, strategy, territories, audit results and scorecards. Token models live in color.py."""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .paths import SLUG


class Phase(str, Enum):  # noqa: UP042 - StrEnum would change str() and format() of members
    intake = "intake"
    naming = "naming"
    strategy = "strategy"
    territories = "territories"
    concepts = "concepts"
    refinement = "refinement"
    package = "package"
    done = "done"


PHASE_ORDER: list[Phase] = list(Phase)


def now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="seconds")


class Decision(BaseModel):
    at: str = Field(default_factory=now_iso)
    phase: Phase
    by: Literal["user", "claude"]
    note: str


class MinSizes(BaseModel):
    horizontal_px: int = 120
    stacked_px: int = 160
    mark_px: int = 24
    favicon_px: int = 16
    horizontal_mm: float = 25
    stacked_mm: float = 25
    mark_mm: float = 6


class FontChoice(BaseModel):
    family: str
    weight: int = 400
    italic: bool = False


class BrandState(BaseModel):
    slug: str
    name: str
    needs_name: bool = False
    track: Literal["full", "express"] = "full"
    created: str = Field(default_factory=now_iso)
    updated: str = Field(default_factory=now_iso)
    phase: Phase = Phase.intake
    industry: str | None = None
    surfaces: list[str] = Field(default_factory=list)
    primary_lockup: Literal["horizontal", "stacked"] = "horizontal"
    min_sizes: MinSizes = Field(default_factory=MinSizes)
    territory: str | None = None
    concept: str | None = None
    fonts: dict[str, FontChoice] = Field(default_factory=dict)
    decisions: list[Decision] = Field(default_factory=list)


class AdjectivePair(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    adjective: str
    not_: str = Field(alias="not")


class Archetype(BaseModel):
    primary: str
    secondary: str | None = None


class Personality(BaseModel):
    sincerity: float = Field(0.5, ge=0, le=1)
    excitement: float = Field(0.5, ge=0, le=1)
    competence: float = Field(0.5, ge=0, le=1)
    sophistication: float = Field(0.5, ge=0, le=1)
    ruggedness: float = Field(0.5, ge=0, le=1)


class Brief(BaseModel):
    business: str
    audience: str
    problem: str
    one_idea: str
    onliness: str
    adjectives: list[AdjectivePair]
    persona: str
    admired: list[str] = Field(default_factory=list)
    disliked: list[str] = Field(default_factory=list)
    surfaces: list[str]
    harshest: str
    colours_wanted: list[str] = Field(default_factory=list)
    colours_forbidden: list[str] = Field(default_factory=list)
    colours_category: list[str] = Field(default_factory=list)
    off_limits: list[str] = Field(default_factory=list)
    cultural: str = ""
    needs_name: bool = False
    name: str | None = None
    name_written: str | None = None
    name_story: str = ""
    tagline: str | None = None
    archetype: Archetype
    personality: Personality
    industry: str

    @field_validator("adjectives")
    @classmethod
    def at_least_three_adjectives(cls, value: list[AdjectivePair]) -> list[AdjectivePair]:
        if len(value) < 3:
            raise ValueError("adjectives: give at least three adjective/not pairs")
        return value

    @field_validator("surfaces")
    @classmethod
    def at_least_one_surface(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("surfaces: rank at least one surface")
        return value


class LadderRung(BaseModel):
    adjective: str
    principle: str
    test: str


class CategoryUniform(BaseModel):
    type_classes: list[str] = Field(default_factory=list)
    colours: list[str] = Field(default_factory=list)
    motifs: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)


class FeatureTargets(BaseModel):
    shape: float = Field(ge=0, le=1, description="0 round .. 1 angular")
    symmetry: float = Field(ge=0, le=1, description="0 asymmetric .. 1 symmetric")
    complexity: Literal["low", "moderate", "high"]
    weight: Literal["light", "regular", "medium", "heavy"]
    hue_family: str
    saturation: Literal["low", "medium", "high"]
    lightness: Literal["dark", "mid", "light"]
    typeface_class: str
    frame: Literal["open", "framed", "badge"]
    dynamism: float = Field(ge=0, le=1)
    descriptive_cue: bool
    name_sound: str = ""


LogoType = Literal["wordmark", "lettermark", "pictorial", "abstract", "mascot", "combination", "emblem"]


class Strategy(BaseModel):
    onliness: str
    positioning: str
    archetype: Archetype
    personality: Personality
    one_idea: str
    ladder: list[LadderRung]
    category_uniform: CategoryUniform
    targets: FeatureTargets
    logo_type: LogoType
    logo_type_reason: str
    constraints: dict[str, str | int | float | bool | list] = Field(default_factory=dict)

    @field_validator("ladder")
    @classmethod
    def at_least_three_rungs(cls, value: list[LadderRung]) -> list[LadderRung]:
        if len(value) < 3:
            raise ValueError("ladder: give at least three rungs")
        return value


class Finding(BaseModel):
    check: str
    severity: Literal["fail", "warn", "info"]
    message: str
    data: dict = Field(default_factory=dict)


class AuditResult(BaseModel):
    ok: bool
    failures: list[Finding] = Field(default_factory=list)
    warnings: list[Finding] = Field(default_factory=list)
    info: list[Finding] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    rendered: bool = False
    fingerprint: str = ""  # audit.concept_fingerprint of the files audited; gates and sheets compare it with the current one


class TerritoryFont(BaseModel):
    family: str
    weight: int = Field(400, ge=100, le=900)


class TerritoryColor(BaseModel):
    hex: str
    name: str

    @field_validator("hex")
    @classmethod
    def normalised_hex(cls, value: str) -> str:
        from .color import normalize_hex  # imported here: color loads coloraide, and the CLI imports schemas at startup

        return normalize_hex(value)  # a value that is no colour raises ValueError, which pydantic reports against this field


class TerritoryShapes(BaseModel):
    corner: float = Field(0.1, ge=0, le=0.5)
    stroke: float = Field(0.12, ge=0.02, le=0.4)
    angularity: float = Field(0.5, ge=0, le=1)
    symmetry: float = Field(0.7, ge=0, le=1)


class Territory(BaseModel):
    slug: str
    name: str
    embraces: list[str]
    rejects: list[str]
    fonts: list[TerritoryFont] = Field(min_length=1, max_length=3)
    palette: list[TerritoryColor] = Field(min_length=2, max_length=6)
    shapes: TerritoryShapes = Field(default_factory=TerritoryShapes)

    @field_validator("slug")
    @classmethod
    def slug_is_a_slug(cls, value: str) -> str:
        # `brand set --territory` takes only slugs, so a territory named otherwise could never be chosen.
        if not SLUG.fullmatch(value):
            raise ValueError(f"territory slug must be lowercase letters, digits and hyphens (e.g. forge-works), got {value!r}")
        return value


class TerritoriesSpec(BaseModel):
    territories: list[Territory] = Field(min_length=2, max_length=3)

    @field_validator("territories")
    @classmethod
    def slugs_are_unique(cls, value: list[Territory]) -> list[Territory]:
        slugs = [t.slug for t in value]
        repeated = list(dict.fromkeys(s for s in slugs if slugs.count(s) > 1))
        if repeated:
            raise ValueError(f"territory slugs must be unique; repeated: {', '.join(repeated)}")
        return value


CRITERIA = ("appropriate", "distinctive", "simple", "legible", "adaptable", "timeless", "universal", "clear", "congruent", "system")
GATE = ("appropriate", "simple", "legible")
GATE_MIN = 4  # the score each GATE criterion needs


def check_scores(scores: dict[str, int]) -> None:
    """Raise ValueError unless `scores` holds every criterion, each a whole number 1 to 5: the rule of Scorecard and CriticCard."""
    missing = [c for c in CRITERIA if c not in scores]
    if missing:
        raise ValueError(f"scores missing: {', '.join(missing)}")
    bad = {k: v for k, v in scores.items() if not 1 <= v <= 5}
    if bad:
        raise ValueError(f"scores must be 1..5: {bad}")


ROUTES = ("object", "abstraction", "letterform", "negative-space", "type-quirk", "system", "metaphor-2")  # spec 2026-10-08 §6.1
LITERAL_ROUTE = "object"
PROBE_CAPS = ((8, 2), (3, 3))  # first-page hits at or above the threshold cap `distinctive` at the value


def distinctive_cap(hits: int) -> int:
    """The most `distinctive` may score after an obviousness probe found `hits` of twenty first-page results showing the
    construction: 2 from 8 hits, 3 from 3, else 5."""
    for threshold, cap in PROBE_CAPS:
        if hits >= threshold:
            return cap
    return 5


class Probe(BaseModel):
    """The obviousness probe: an image search for "<motif> logo", and how many of its first twenty results show the
    same construction (spec 2026-10-08 §6.2)."""

    query: str
    hits: int = Field(ge=0, le=20)
    date: str


class Scorecard(BaseModel):
    """<concept>/scorecard.json: Claude's ten scores (spec 8.2), each 1 to 5, with evidence, whether the concept is killed,
    `reconciled`: for each criterion the blind critic's card disagrees on by two or more, one line saying whose score
    stands and why (spec 2026-10-08 §3.3), `route`: which of ROUTES the concept took (§6.1), and `probe`: the obviousness
    probe, whose hits cap `distinctive` (§6.2)."""

    scores: dict[str, int]
    evidence: dict[str, str] = Field(default_factory=dict)
    kill: bool = False
    reason: str = ""
    reconciled: dict[str, str] = Field(default_factory=dict)
    route: str | None = None
    probe: Probe | None = None

    @model_validator(mode="after")
    def complete_and_in_range(self) -> Scorecard:
        check_scores(self.scores)
        if self.route is not None and self.route not in ROUTES:
            raise ValueError(f"route must be one of {', '.join(ROUTES)}, got {self.route!r}")
        if self.probe is not None:
            cap = distinctive_cap(self.probe.hits)
            if self.scores["distinctive"] > cap:
                raise ValueError(f"distinctive is capped at {cap} by the probe ({self.probe.hits} of 20 first-page results "
                                 "show the construction)")
        return self

    @property
    def gate_ok(self) -> bool:
        return not self.kill and all(self.scores[c] >= GATE_MIN for c in GATE)

    @property
    def total(self) -> int:
        return sum(self.scores[c] for c in CRITERIA)


class CriticCard(BaseModel):
    """<concept>/critic.json: the blind critic's merged card (spec 2026-10-08 §3.2). `scores` are the mean of the passes,
    rounded half up; `evidence` holds every pass's line per criterion; `preferred_over` the slugs this concept beat in
    every pass and both orders, `tied_with` the rest; `fingerprint` is audit.concept_fingerprint of the concept the
    critic saw, so a later change makes the card stale."""

    scores: dict[str, int]
    evidence: dict[str, list[str]] = Field(default_factory=dict)
    preferred_over: list[str] = Field(default_factory=list)
    tied_with: list[str] = Field(default_factory=list)
    sheet: int
    passes: int
    fingerprint: str

    @model_validator(mode="after")
    def complete_and_in_range(self) -> CriticCard:
        check_scores(self.scores)
        return self

    @property
    def total(self) -> int:
        return sum(self.scores[c] for c in CRITERIA)


class ImageMatch(BaseModel):
    url: str
    owner: str = ""
    note: str = ""


class ImageSearch(BaseModel):
    """One reverse-image search of the rendered mark: `tool` google-lens or wipo; `searched` with its `matches`, or
    `skipped` with the reason (the gate then needs the owner's `knock-out skipped:` decision)."""

    tool: str
    date: str = ""
    searched: bool = False
    matches: list[ImageMatch] = Field(default_factory=list)
    skipped: str | None = None

    @model_validator(mode="after")
    def searched_or_skipped(self) -> ImageSearch:
        if self.searched and self.skipped:
            raise ValueError("searched and skipped are exclusive")
        return self

    @property
    def done(self) -> bool:
        return self.searched or bool(self.skipped and self.skipped.strip())


class DescriptionQuery(BaseModel):
    query: str
    date: str = ""
    findings: str = ""


class Knockout(BaseModel):
    """<concept>/knockout.json (spec 2026-10-08 §7): the description searches, the Google Lens search of the rendered
    mark, the WIPO image search (final/ only) and the trademark caveat. `fingerprint` is audit.concept_fingerprint of the
    concept that `concept knockout` last rendered; the gates call the record stale when the concept now differs."""

    description_queries: list[DescriptionQuery] = Field(default_factory=list)
    image_matches: ImageSearch = Field(default_factory=lambda: ImageSearch(tool="google-lens"))
    wipo: ImageSearch | None = None
    caveat: str = ""
    fingerprint: str = ""

    @property
    def image_done(self) -> bool:
        return self.image_matches.done

    @property
    def wipo_done(self) -> bool:
        return self.wipo is not None and self.wipo.done


class ManifestEntry(BaseModel):
    path: str
    purpose: str
    width: int | None = None
    height: int | None = None
    sha256: str
    bytes: int


class Manifest(BaseModel):
    """package/manifest.json: every file the build wrote, its warnings, each group that could not run, with the reason,
    and `inputs`, the fingerprint of what the build read (export_docs.inputs_fingerprint), which verify and the done gate
    compare with the current one."""

    brand: str
    slug: str
    built: str
    inputs: str = ""
    files: list[ManifestEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    skipped: dict[str, str] = Field(default_factory=dict)
