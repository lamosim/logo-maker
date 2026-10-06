"""Where things live. The project root is the folder whose pyproject.toml has [tool.logomaker]."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .output import CliError

MARKER = "[tool.logomaker]"


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @property
    def brands(self) -> Path:
        return self.root / "brands"

    @property
    def registry(self) -> Path:
        return self.root / "registry"

    @property
    def assets(self) -> Path:
        return self.root / "assets"

    @property
    def fonts(self) -> Path:
        return self.assets / "fonts"

    @property
    def templates(self) -> Path:
        return self.root / "templates"

    @property
    def cliches(self) -> Path:
        return self.assets / "cliches.json"

    def brand(self, slug: str) -> Path:
        return self.brands / slug


def find_root(start: Path | None = None) -> Path:
    env = os.environ.get("LOGOMAKER_ROOT")
    if env:
        return Path(env).resolve()
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        py = candidate / "pyproject.toml"
        if py.is_file() and MARKER in py.read_text(encoding="utf-8"):
            return candidate
    raise CliError("Not inside a logo-maker project (no pyproject.toml with [tool.logomaker] above the current folder)")


def project(root: Path | None = None) -> ProjectPaths:
    return ProjectPaths(root=root.resolve() if root else find_root())
