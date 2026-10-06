"""Font catalogue, local cache under assets/fonts/<slug>/, resolution by weight, and fetching from google/fonts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
from fontTools.ttLib import TTFont

from .output import EXIT_EXTERNAL, CliError
from .paths import ProjectPaths
from .schemas import now_iso

GITHUB_CONTENTS = "https://api.github.com/repos/google/fonts/contents/{dir}"
LICENCE_FILES = {"OFL.txt", "LICENSE.txt", "UFL.txt", "LICENCE.txt"}
WEIGHT_NAMES = {
    100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
    600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black",
}
NAME_WEIGHTS = {v.lower(): k for k, v in WEIGHT_NAMES.items()}


@dataclass(frozen=True)
class FontFamily:
    family: str
    slug: str
    category: str
    license: str
    personality: tuple[str, ...]  # a tuple, so the frozen dataclass hashes
    google_dir: str | None


@dataclass(frozen=True)
class FontFile:
    path: Path
    family: str
    variable: bool
    italic: bool
    weight: int | None  # None for variable fonts (any weight)


def family_slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]", "", family.lower())


def load_catalog(paths: ProjectPaths) -> list[FontFamily]:
    data = json.loads((paths.fonts / "catalog.json").read_text(encoding="utf-8"))
    return [FontFamily(**{**entry, "personality": tuple(entry["personality"])}) for entry in data["families"]]


def find_family(paths: ProjectPaths, family: str) -> FontFamily | None:
    slug = family_slug(family)
    return next((f for f in load_catalog(paths) if f.slug == slug), None)


def list_fonts(paths: ProjectPaths, category: str | None = None, personality: str | None = None) -> list[FontFamily]:
    out = load_catalog(paths)
    if category:
        out = [f for f in out if f.category == category]
    if personality:
        out = [f for f in out if personality in f.personality]
    return out


def family_dir(paths: ProjectPaths, family: str) -> Path:
    slug = family_slug(family)
    if not slug:  # an empty slug would make assets/fonts itself the family's cache folder
        raise CliError(f"Not a font family name: {family!r}")
    return paths.fonts / slug


def cached_files(paths: ProjectPaths, family: str) -> list[Path]:
    folder = family_dir(paths, family)
    return sorted(folder.glob("*.ttf")) if folder.is_dir() else []


def _describe(path: Path) -> tuple[bool, bool, int | None]:
    """(variable, italic, weight) from google/fonts file naming: Family[wght].ttf or Family-StyleItalic.ttf.

    Only a wght axis makes a file variable here; ClimateCrisis[YEAR].ttf is a static Regular."""
    name, _, axes = path.stem.partition("[")
    if "wght" in axes.rstrip("]").split(","):
        return True, "italic" in name.lower(), None
    style = name.rsplit("-", 1)[1] if "-" in name else "Regular"
    italic = style.lower().endswith("italic")
    base = style[:-6] if italic else style
    weight = 400 if base in ("", "Italic") else NAME_WEIGHTS.get(base.lower(), 400)
    return False, italic, weight


def font_path(paths: ProjectPaths, family: str, weight: int = 400, italic: bool = False) -> FontFile:
    files = cached_files(paths, family)
    if not files:
        raise CliError(f"Font family {family!r} is not cached. run: logomaker fonts fetch {shlex.quote(family)}", code=EXIT_EXTERNAL)
    described = [(p, *_describe(p)) for p in files]
    variables = [d for d in described if d[1] and d[2] == italic]
    if variables:
        p, _, it, _ = variables[0]
        return FontFile(path=p, family=family, variable=True, italic=it, weight=None)
    statics = [d for d in described if not d[1] and d[2] == italic] or [d for d in described if not d[1]]
    if not statics:
        p, var, it, w = described[0]
        return FontFile(path=p, family=family, variable=var, italic=it, weight=w)
    p, _, it, w = min(statics, key=lambda d: abs((d[3] or 400) - weight))
    return FontFile(path=p, family=family, variable=False, italic=it, weight=w)


def _candidate_dirs(paths: ProjectPaths, family: str) -> list[str]:
    slug = family_slug(family)
    entry = find_family(paths, family)
    dirs = [entry.google_dir] if entry and entry.google_dir else []
    dirs += [f"ofl/{slug}", f"apache/{slug}", f"ufl/{slug}"]
    return list(dict.fromkeys(dirs))


def _github_error(family: str, folder: str, resp: httpx.Response) -> CliError:
    """Exit-3 error for a listing that is neither 200 nor 404: the HTTP status plus GitHub's JSON `message`."""
    try:
        body = resp.json()
    except ValueError:  # not JSON, e.g. an HTML error page from GitHub's edge
        body = None
    message = body.get("message") if isinstance(body, dict) else None
    return CliError(
        f"Could not fetch {family}: GitHub returned {resp.status_code} for {folder}: {message or resp.reason_phrase}",
        code=EXIT_EXTERNAL,
    )


def _download(client: httpx.Client, entry: dict, staging: Path) -> dict:
    """Download one listed file into `staging` and return its manifest row.

    The byte count must match the listing's `size`, and a .ttf must parse with fontTools."""
    try:
        data = client.get(entry["download_url"]).raise_for_status().content
    except httpx.HTTPError as err:
        raise CliError(f"Network error downloading {entry['name']}: {err}", code=EXIT_EXTERNAL) from err
    if len(data) != entry["size"]:
        raise CliError(f"{entry['name']}: downloaded {len(data)} bytes, GitHub lists {entry['size']}", code=EXIT_EXTERNAL)
    target = staging / entry["name"]
    target.write_bytes(data)
    if target.suffix == ".ttf":
        try:
            TTFont(str(target)).close()
        except Exception as err:  # noqa: BLE001
            raise CliError(f"{entry['name']} is not a valid TrueType file: {err}", code=EXIT_EXTERNAL) from err
    return {"name": entry["name"], "url": entry["download_url"], "sha256": hashlib.sha256(data).hexdigest()}


def fetch(paths: ProjectPaths, family: str, timeout: float = 30.0) -> dict:
    folder = family_dir(paths, family)
    for stale in paths.fonts.glob(f"{folder.name}.*.tmp"):  # staging left by an earlier fetch of this family that was killed
        if stale.is_dir():
            shutil.rmtree(stale)
    listing = None
    used_dir = None
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "logomaker"}) as client:
        for d in _candidate_dirs(paths, family):
            try:
                resp = client.get(GITHUB_CONTENTS.format(dir=d))
            except httpx.HTTPError as err:
                raise CliError(f"Network error fetching {family}: {err}", code=EXIT_EXTERNAL) from err
            if resp.status_code == 200:
                listing, used_dir = resp.json(), d
                break
            if resp.status_code != 404:  # only a 404 means "not in this folder"; a rate limit or outage stops the probe
                raise _github_error(family, d, resp)
        if listing is None:
            tried = ", ".join(_candidate_dirs(paths, family))
            raise CliError(f"Family {family!r} not found in google/fonts (tried {tried})", code=EXIT_EXTERNAL)
        wanted = [e for e in listing if e["name"].endswith(".ttf") or e["name"] in LICENCE_FILES]
        if not any(e["name"].endswith(".ttf") for e in wanted):
            raise CliError(f"No .ttf files listed for {family} in {used_dir}", code=EXIT_EXTERNAL)
        # Download into a staging folder of this run's own (<slug>.<random>.tmp) beside the cache and swap it in
        # only once every file checks out, so a failed fetch or re-fetch never leaves a partial or mixed cache.
        staging = Path(tempfile.mkdtemp(prefix=f"{folder.name}.", suffix=".tmp", dir=paths.fonts))
        os.chmod(staging, 0o755)  # mkdtemp makes it 0o700; the cache it becomes should read like any other folder
        try:
            files = [_download(client, entry, staging) for entry in wanted]
            manifest = {"family": family, "google_dir": used_dir, "fetched_at": now_iso(), "files": files}
            (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            if folder.exists():
                shutil.rmtree(folder)
            try:
                os.replace(staging, folder)
            except OSError as err:
                raise CliError(f"Could not move the fetched files from {staging} to {folder}: {err}", code=EXIT_EXTERNAL) from err
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    return manifest


def family_to_dict(f: FontFamily) -> dict:
    return asdict(f)
