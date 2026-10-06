"""Pydantic models for brand state, brief and strategy. Audit and token models are added by later tasks."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Phase(str, Enum):
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
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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
