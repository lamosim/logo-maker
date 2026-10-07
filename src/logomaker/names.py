"""Name analysis (sound and letterform features) and availability checks over RDAP, whois and the GitHub API."""
from __future__ import annotations

import re
import subprocess
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from time import monotonic

import httpx

from .output import CliError

FRONT, BACK, NEUTRAL = set("ie"), set("ou"), set("a")
VOWELS = FRONT | BACK | NEUTRAL | {"y"}
ROUND, DIAGONAL, CLOSED = set("ocgsq"), set("avwkxz"), set("abdopqr")
TLDS = ("com", "co", "io", "ai", "app", "dev")
HANDLES = ("github",)
TLD = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*")  # a top-level domain as --tlds takes it: com, or co.uk
DEADLINE = 45  # seconds into a check (monotonic clock) after which no lookup starts
LIMIT = 55  # seconds into a check by which every lookup has given up: no timeout runs past it
LOOKUP_TIMEOUT = 10  # seconds a request or a whois may take at most
RDAP = "https://rdap.org/domain/{domain}"
RDAP_BOOTSTRAP = "rdap.org"  # redirects to the registry's own RDAP server, or answers 404 itself when it knows none for the TLD
GITHUB_USER = "https://api.github.com/users/{label}"
GITHUB_ORG = "https://api.github.com/orgs/{label}"
REGISTERED_MARKERS = ("domain name:", "registrar:")
NOT_FOUND_MARKERS = ("no match", "not found", "no data found", "no entries found", "nothing found")
# The whois answers that mean a domain is free: a not-found phrase at the start of a line or of a field's value (.com's
# 'No match for domain "X.COM".', .io's and .ai's "Domain not found.", .co's "The queried object does not exist: DOMAIN
# NOT FOUND"), or "available" as a field's value ("Status: available"). The registered markers are tested first, and a
# phrase in the middle of a sentence never matches; a line of prose that happens to start with one still would.
NOT_FOUND = re.compile(r"(?:^|:)[ \t]*(?:domain[ \t]+)?(?:" + "|".join(map(re.escape, NOT_FOUND_MARKERS)) + r")|:[ \t]*available\b",
                       re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class Clock:
    """A check's time on the monotonic clock: no lookup starts once `deadline` has passed, and none waits past `limit`."""

    deadline: float
    limit: float

    @classmethod
    def starting_now(cls) -> Clock:
        now = monotonic()
        return cls(now + DEADLINE, now + LIMIT)

    def passed(self) -> bool:
        """Whether the deadline has passed: no lookup may start."""
        return monotonic() >= self.deadline

    def timeout(self) -> float:
        """The timeout of a request or whois starting now: the time left before the limit, never above LOOKUP_TIMEOUT."""
        return max(0.0, min(LOOKUP_TIMEOUT, self.limit - monotonic()))


def _ascii(name: str) -> str:
    """`name` with its accents folded away (NFKD, then ASCII only): "Café" -> "Cafe"."""
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()


def domain_label(name: str) -> str:
    """`name` as a domain label: accents dropped, ASCII letters and digits only, lower case ("Café Nuit!" -> "cafenuit")."""
    return re.sub(r"[^a-z0-9]", "", _ascii(name).lower())


def top_level_domains(values: Iterable[str]) -> tuple[str, ...]:
    """`values` as top-level domains, each lower-cased without leading dots (".CO.UK" -> "co.uk"). One that is still not
    letters, digits and hyphens in dot-separated labels is a CliError (exit 2) naming it, before any lookup."""
    tlds = []
    for value in values:
        tld = value.strip().lstrip(".").lower()
        if not TLD.fullmatch(tld):
            raise CliError(f"Not a top-level domain: {value!r} (letters, digits and hyphens, dot-separated: com or co.uk)")
        tlds.append(tld)
    return tuple(tlds)


def analyze(name: str) -> dict:
    """Deterministic sound and letterform features of a candidate name.

    Syllables are vowel groups (a silent final e not counted). Vowels are front (i, e), back (o, u) or neutral (a). The
    initial letter is flagged round, diagonal, closed (has a counter) and, for an L, with a warning. Pronounceable means
    at least one vowel and no run of more than three consonants. Accented letters count as their plain letters ("Café"
    has the front vowel e).
    """
    letters = re.sub(r"[^a-z]", "", _ascii(name).lower())
    groups = re.findall(r"[aeiouy]+", letters)
    if letters.endswith("e") and len(groups) > 1 and letters[-2] not in VOWELS:
        groups = groups[:-1]  # silent e: "keystone" has two syllables, not three
    front = sum(ch in FRONT for ch in letters)
    back = sum(ch in BACK for ch in letters)
    neutral = sum(ch in NEUTRAL for ch in letters)
    runs = [len(r) for r in re.findall(r"[^aeiouy]+", letters)]
    initial = letters[:1]
    doubles = [m.group(0) for m in re.finditer(r"([a-z])\1", letters)]
    return {
        "name": name,
        "letters": letters,
        "length": len(letters),
        "syllables": max(1, len(groups)) if letters else 0,
        "vowels": {"front": front, "back": back, "neutral": neutral, "front_ratio": round(front / max(1, front + back), 2)},
        "initial": {"letter": initial, "round": initial in ROUND, "diagonal": initial in DIAGONAL, "closed_counter": initial in CLOSED,
                    "l_warning": initial == "l"},
        "double_letters": doubles,
        "camel_case": bool(re.search(r"[a-z][A-Z]", name)),
        "has_digits": bool(re.search(r"\d", name)),
        "max_consonant_run": max(runs, default=0),
        "pronounceable": max(runs, default=0) <= 3 and bool(groups),
    }


def default_transport() -> httpx.BaseTransport | None:
    """The transport `check` uses when it is given none: None, httpx's own (the network). Tests replace it."""
    return None


def _whois(domain: str, timeout: float = LOOKUP_TIMEOUT) -> tuple[str, str]:
    """(status, method) from the whois command, given `timeout` seconds: registered when the answer names a domain or a
    registrar, available when it says the domain is not found (NOT_FOUND), else unknown. The method is "none" when whois
    cannot run."""
    try:
        # errors="replace": a whois server answering in Latin-1 must not stop the check
        out = subprocess.run(["whois", domain], capture_output=True, text=True, errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return "unknown", "none"
    text = out.stdout + out.stderr
    if any(marker in text.lower() for marker in REGISTERED_MARKERS):
        return "registered", "whois"
    if NOT_FOUND.search(text):
        return "available", "whois"
    return "unknown", "whois"


def check_domain(domain: str, client: httpx.Client, warnings: list[str] | None = None, clock: Clock | None = None) -> dict:
    """Look `domain` up over RDAP, then whois. Returns {domain, status, method}.

    rdap.org redirects to the registry's own RDAP server, whose 200 means registered and 404 available. Anything else
    falls back to whois: an answer from rdap.org itself (its 404 means it knows no RDAP server for the TLD, not that the
    domain is free), another status, or a network error. Each waits at most the check's `clock` allows (a check of its
    own when None), and whois is skipped once the deadline has passed. An unknown status adds its reason to
    `warnings`, when given.
    """
    clock = clock or Clock.starting_now()
    try:
        # the bootstrap is a redirect
        resp = client.get(RDAP.format(domain=domain), follow_redirects=True, timeout=clock.timeout())
    except httpx.HTTPError as err:
        reason = type(err).__name__
    else:
        authoritative = resp.url.host != RDAP_BOOTSTRAP
        if authoritative and resp.status_code == 200:
            return {"domain": domain, "status": "registered", "method": "rdap"}
        if authoritative and resp.status_code == 404:
            return {"domain": domain, "status": "available", "method": "rdap"}
        reason = f"{resp.status_code} from {resp.url.host}"
    if clock.passed():  # RDAP took the check past its deadline: whois could run past the limit
        if warnings is not None:
            warnings.append(f"{domain}: RDAP {reason}, and the deadline passed before whois")
        return {"domain": domain, "status": "unknown", "method": "none"}
    status, method = _whois(domain, clock.timeout())
    if status == "unknown" and warnings is not None:
        warnings.append(f"{domain}: RDAP {reason} and whois gave nothing")
    return {"domain": domain, "status": status, "method": method}


def _github_lookup(key: str, url: str, client: httpx.Client, problems: list[str], clock: Clock) -> str:
    """One GitHub API lookup, waiting at most `clock` allows: registered (200), available (404) or unknown, whose reason
    is added to `problems`."""
    try:
        code = client.get(url, timeout=clock.timeout()).status_code
    except httpx.HTTPError as err:
        problems.append(f"{key} unreachable ({type(err).__name__})")
        return "unknown"
    if code == 200:
        return "registered"
    if code == 404:
        return "available"
    if code in (403, 429):  # how the API answers once the 60 unauthenticated requests an hour are used up
        problems.append(f"{key} rate limited (HTTP {code})")
    else:
        problems.append(f"{key} answered HTTP {code}")
    return "unknown"


def check_github(label: str, client: httpx.Client, warnings: list[str] | None = None, clock: Clock | None = None) -> dict:
    """GitHub user and organisation status for `label`: {user, org}, each registered, available or unknown.

    Users and organisations share one login namespace, so a login the users endpoint knows (200) is registered for an
    organisation too. The orgs endpoint is asked only when the users endpoint does not know the login (404), and an
    unknown user lookup leaves the organisation unknown, as does a deadline that passed during the user lookup (the
    check's `clock`, a check of its own when None). Unknown statuses add one warning to `warnings`, when given, with
    each reason: rate limited, another HTTP status, unreachable with the network error's class, or the deadline.
    """
    clock = clock or Clock.starting_now()
    problems: list[str] = []
    user = _github_lookup("user", GITHUB_USER.format(label=label), client, problems, clock)
    org = user
    if user == "available":
        if clock.passed():
            problems.append("org not checked (the deadline passed)")
            org = "unknown"
        else:
            org = _github_lookup("org", GITHUB_ORG.format(label=label), client, problems, clock)
    if problems and warnings is not None:
        warnings.append(f"github: {'; '.join(problems)}; try again later")
    return {"user": user, "org": org}


def check(name: str, tlds: tuple[str, ...] = TLDS, handles: tuple[str, ...] = HANDLES,
          transport: httpx.BaseTransport | None = None) -> dict:
    """Availability of `name` as <label>.<tld> for each of `tlds`, and as a handle on each service in `handles`.

    Returns {name, label, domains, handles, warnings}. A failed lookup never raises: its status is unknown and a warning
    says why. No lookup starts once DEADLINE seconds have passed since the check began: every lookup left is unknown
    (domains with method "none") and one warning names them all. Every request and whois waits at most LOOKUP_TIMEOUT
    seconds, and never past LIMIT seconds into the check (Clock). The TLDs are normalised (top_level_domains); one that
    is no TLD, or a handle service other than github, raises CliError (exit 2) before any lookup.
    """
    clock = Clock.starting_now()
    unsupported = [h for h in handles if h not in HANDLES]
    if unsupported:
        raise CliError(f"Unknown handle service {', '.join(map(repr, unsupported))}; choose one of: {', '.join(HANDLES)}")
    tlds = top_level_domains(tlds)
    label = domain_label(name)
    result = {"name": name, "label": label, "domains": [], "handles": {}, "warnings": []}
    if not label:
        result["warnings"].append("name has no letters or digits to check")
        return result
    unchecked = []
    headers = {"User-Agent": "logomaker", "Accept": "application/json"}
    transport = transport if transport is not None else default_transport()
    with httpx.Client(timeout=LOOKUP_TIMEOUT, follow_redirects=True, headers=headers, transport=transport) as client:
        for tld in tlds:
            domain = f"{label}.{tld}"
            if clock.passed():
                unchecked.append(domain)
                result["domains"].append({"domain": domain, "status": "unknown", "method": "none"})
            else:
                result["domains"].append(check_domain(domain, client, result["warnings"], clock))
        if "github" in handles:
            if clock.passed():
                unchecked.append("github")
                result["handles"]["github"] = {"user": "unknown", "org": "unknown"}
            else:
                result["handles"]["github"] = check_github(label, client, result["warnings"], clock)
    if unchecked:
        result["warnings"].append(f"deadline reached after {DEADLINE} s; not checked: {', '.join(unchecked)}")
    return result
