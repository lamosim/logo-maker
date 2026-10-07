import json
import subprocess

import httpx
import pytest
from click.testing import CliRunner

from logomaker import names
from logomaker.cli import main

REGISTRY = "rdap.registry.test"  # the registry's own RDAP server, where rdap.org redirects

# whois answers as macOS whois prints them, trimmed from real ones (October 2026) unless marked as made up.
COM_NO_MATCH = (
    '# whois.verisign-grs.com\n\nNo match for domain "KEYSTONE.COM".\n'
    ">>> Last update of whois database: 2026-10-07T14:55:18Z <<<\n"
)
IO_NOT_FOUND = "# whois.nic.io\n\nDomain not found.\n>>> Last update of WHOIS database: 2026-10-07T14:54:39Z <<<\n"
CO_NOT_FOUND = (
    "# whois.registry.co\n\nThe queried object does not exist: DOMAIN NOT FOUND\n\n"
    ">>> Last update of WHOIS database: 2026-10-07T14:54:40.0Z <<<\n"
)
IANA_ONLY = (  # .app and .dev have no whois server: only IANA's record of the TLD comes back
    "% IANA WHOIS server\n\ndomain:       DEV\n\nwhois:        \n\nstatus:       ACTIVE\n"
    "remarks:      Registration information: https://www.registry.google\n"
)
IO_REGISTERED = (  # made-up terms of use whose lines start with not-found phrases
    "# whois.nic.io\n\nDomain Name: keystone.io\nRegistrar: MarkMonitor Inc.\nDomain Status: clientTransferProhibited\n\n"
    "Not found in this answer: the registrant's contact details.\nAvailable on request from the registrar.\n"
)
OTHER_LABELS = (  # made up: a registered domain under other field labels, inside prose that says "not found" and "available"
    "% The whois service on port 43 does not disclose the domain holder, which is not found\n"
    "% here but is available through the registry's web whois.\n\nDomain: keystone.io\nStatus: connect\n"
)


class Whois:
    """Stands in for the whois command (`names.subprocess.run`): it prints answers[domain], or fails as if whois were not
    installed for a domain with no answer. `asked` lists the domains looked up; each must be given `timeout` seconds."""

    def __init__(self):
        self.answers: dict[str, str] = {}
        self.asked: list[str] = []
        self.timeout = names.LOOKUP_TIMEOUT

    def __call__(self, argv, **kwargs):
        assert argv[0] == "whois", argv
        assert kwargs.get("timeout") == self.timeout, kwargs
        self.asked.append(argv[-1])
        if argv[-1] not in self.answers:
            raise FileNotFoundError(2, "No such file or directory", "whois")
        return subprocess.CompletedProcess(argv, 0, stdout=self.answers[argv[-1]], stderr="")


@pytest.fixture(autouse=True)
def whois(request, monkeypatch):
    """No test shells out to whois but the live one."""
    if request.node.get_closest_marker("live"):
        return None
    stub = Whois()
    monkeypatch.setattr(names.subprocess, "run", stub)
    return stub


def test_analyze_features():
    k = names.analyze("Keystone")
    assert k["length"] == 8 and k["syllables"] == 2 and k["initial"]["diagonal"] and not k["initial"]["round"]
    assert k["vowels"]["front"] == 2 and k["vowels"]["back"] == 1 and k["double_letters"] == []
    assert k["pronounceable"] and not k["camel_case"]
    assert names.analyze("Lumen")["initial"]["l_warning"]
    assert names.analyze("Coffee")["double_letters"] == ["ff", "ee"]
    assert names.analyze("PayPal")["camel_case"] and names.analyze("Octo")["initial"]["round"]
    assert not names.analyze("Strngth")["pronounceable"]
    assert names.domain_label("Café Nuit!") == "cafenuit"
    cafe = names.analyze("Café Nuit")  # the accent folds away; the é still counts as a front vowel
    assert cafe["letters"] == "cafenuit" and cafe["vowels"] == {"front": 2, "back": 1, "neutral": 1, "front_ratio": 0.67}


def fake_transport(registered: set[str], github_taken: set[str], fail: set[str] | frozenset[str] = frozenset(),
                   no_rdap: set[str] | frozenset[str] = frozenset()) -> httpx.MockTransport:
    """Stands in for RDAP and GitHub. rdap.org redirects to the registry's RDAP server, which answers 200 for a domain in
    `registered` and 404 for any other. rdap.org answers 404 itself for a TLD in `no_rdap` (it knows no RDAP server for
    it) and fails to connect for a domain in `fail`. GitHub answers 200 for a user or org in `github_taken`, else 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        host, last = request.url.host, request.url.path.rsplit("/", 1)[1]
        if host == "rdap.org":
            if last in fail:
                raise httpx.ConnectError("boom", request=request)
            tld = last.rsplit(".", 1)[1]
            if tld in no_rdap:
                return httpx.Response(404, json={"errorCode": 404, "title": "Not Found"})
            return httpx.Response(302, headers={"Location": f"https://{REGISTRY}/{tld}/v1/domain/{last}"})
        if host == REGISTRY:
            return httpx.Response(200 if last in registered else 404, json={"objectClassName": "domain"})
        if host == "api.github.com":
            return httpx.Response(200 if last in github_taken else 404, json={})
        return httpx.Response(500)

    return httpx.MockTransport(handler)


def test_check_with_mocked_services(whois):
    transport = fake_transport({"keystone.com"}, {"keystone"})
    result = names.check("Keystone", tlds=("com", "io"), transport=transport)
    statuses = {d["domain"]: d["status"] for d in result["domains"]}
    assert statuses == {"keystone.com": "registered", "keystone.io": "available"}
    assert result["handles"]["github"]["user"] == "registered" and result["handles"]["github"]["org"] == "registered"
    assert result["warnings"] == []
    assert [d["method"] for d in result["domains"]] == ["rdap", "rdap"] and whois.asked == []


def test_network_failure_degrades_to_unknown(whois):
    result = names.check("Keystone", tlds=("ai",), handles=(), transport=fake_transport(set(), set(), fail={"keystone.ai"}))
    assert result["domains"][0]["status"] == "unknown" and result["domains"][0]["method"] == "none"
    assert result["warnings"] == ["keystone.ai: RDAP ConnectError and whois gave nothing"]
    assert whois.asked == ["keystone.ai"]


def test_rdap_org_404_is_not_availability(whois):
    # rdap.org answers 404 itself for a TLD it knows no RDAP server for (.io and .co): whois decides instead.
    whois.answers = {"keystone.io": IO_REGISTERED, "keystone.co": CO_NOT_FOUND, "keystone.dev": IANA_ONLY}
    transport = fake_transport(set(), set(), no_rdap={"io", "co", "dev"})
    result = names.check("Keystone", tlds=("io", "co", "dev", "com"), handles=(), transport=transport)
    assert result["domains"] == [
        {"domain": "keystone.io", "status": "registered", "method": "whois"},
        {"domain": "keystone.co", "status": "available", "method": "whois"},
        {"domain": "keystone.dev", "status": "unknown", "method": "whois"},
        {"domain": "keystone.com", "status": "available", "method": "rdap"},  # a 404 from the registry's own server
    ]
    assert result["warnings"] == ["keystone.dev: RDAP 404 from rdap.org and whois gave nothing"]
    assert whois.asked == ["keystone.io", "keystone.co", "keystone.dev"]


@pytest.mark.parametrize(("answer", "status"), [
    pytest.param(IO_REGISTERED, "registered", id="registered-markers-first"),  # they win over not-found phrases further down
    pytest.param(COM_NO_MATCH, "available", id="com-no-match"),
    pytest.param(IO_NOT_FOUND, "available", id="io-domain-not-found"),
    pytest.param(CO_NOT_FOUND, "available", id="co-not-found-field-value"),
    pytest.param(OTHER_LABELS, "unknown", id="phrases-inside-prose"),  # "not found" and "available" mid-sentence say nothing
    pytest.param(IANA_ONLY, "unknown", id="no-whois-server"),
    pytest.param("Domain: keystone.io\nStatus: AVAILABLE\n", "available", id="available-as-a-field-value"),  # made up
    pytest.param("% whois\nAvailable domains are listed at the registry.\n", "unknown", id="available-starting-prose"),
])
def test_whois_verdicts(whois, answer, status):
    whois.answers["keystone.io"] = answer
    with httpx.Client(transport=fake_transport(set(), set(), no_rdap={"io"})) as client:
        assert names.check_domain("keystone.io", client) == {"domain": "keystone.io", "status": status, "method": "whois"}


def github_api(answers: dict[str, int | type[httpx.HTTPError]], asked: list[str] | None = None) -> httpx.MockTransport:
    """Stands in for the GitHub API: a path in `answers` gets that status, or raises that httpx error; any other path gets
    404. `asked` collects the paths requested."""

    def handler(request: httpx.Request) -> httpx.Response:
        if asked is not None:
            asked.append(request.url.path)
        answer = answers.get(request.url.path, 404)
        if isinstance(answer, int):
            return httpx.Response(answer, json={})
        raise answer("boom", request=request)

    return httpx.MockTransport(handler)


USER, ORG = "/users/keystone", "/orgs/keystone"


# Users and organisations share one login namespace: /orgs is asked only when /users does not know the login. The real
# /users also answers 200 for an organisation's login, which then takes the first case; "held-by-an-org" is a login that
# only /orgs knows.
@pytest.mark.parametrize(("answers", "handle", "asked"), [
    pytest.param({USER: 200}, {"user": "registered", "org": "registered"}, [USER], id="held-by-a-user"),
    pytest.param({ORG: 200}, {"user": "available", "org": "registered"}, [USER, ORG], id="held-by-an-org"),
    pytest.param({}, {"user": "available", "org": "available"}, [USER, ORG], id="free"),
    pytest.param({USER: 403}, {"user": "unknown", "org": "unknown"}, [USER], id="user-unknown"),
])
def test_github_logins_share_one_namespace(answers, handle, asked):
    paths: list[str] = []
    with httpx.Client(transport=github_api(answers, paths)) as client:
        assert names.check_github("keystone", client) == handle
    assert paths == asked


@pytest.mark.parametrize(("answers", "handle", "warning"), [
    pytest.param({USER: 403}, {"user": "unknown", "org": "unknown"}, "github: user rate limited (HTTP 403); try again later",
                 id="user-rate-limited"),
    pytest.param({ORG: httpx.ConnectError}, {"user": "available", "org": "unknown"},
                 "github: org unreachable (ConnectError); try again later", id="org-unreachable"),
    pytest.param({USER: 502}, {"user": "unknown", "org": "unknown"}, "github: user answered HTTP 502; try again later",
                 id="user-other-status"),
])
def test_github_unknown_names_the_reason(answers, handle, warning):
    result = names.check("Keystone", tlds=(), transport=github_api(answers))
    assert result["handles"] == {"github": handle}
    assert result["warnings"] == [warning]


def test_deadline_leaves_the_rest_unknown(monkeypatch, whois):
    clock = [1000.0]
    monkeypatch.setattr(names, "monotonic", lambda: clock[0])
    services, asked = fake_transport({"keystone.com"}, set()), []

    def slow(request: httpx.Request) -> httpx.Response:  # each RDAP lookup takes 30 s on the patched clock
        asked.append(request.url.host)
        if request.url.host == "rdap.org":
            clock[0] += 30
        return services.handle_request(request)

    result = names.check("Keystone", tlds=("com", "io", "ai", "app"), transport=httpx.MockTransport(slow))
    assert result["domains"] == [
        {"domain": "keystone.com", "status": "registered", "method": "rdap"},
        {"domain": "keystone.io", "status": "available", "method": "rdap"},
        {"domain": "keystone.ai", "status": "unknown", "method": "none"},
        {"domain": "keystone.app", "status": "unknown", "method": "none"},
    ]
    assert result["handles"] == {"github": {"user": "unknown", "org": "unknown"}}
    assert result["warnings"] == ["deadline reached after 45 s; not checked: keystone.ai, keystone.app, github"]
    assert asked.count("rdap.org") == 2 and "api.github.com" not in asked and whois.asked == []


def test_a_lookup_waits_no_longer_than_the_check_allows(monkeypatch, whois):
    clock = [1000.0]
    monkeypatch.setattr(names, "monotonic", lambda: clock[0])
    timeouts = []

    def slow(request: httpx.Request) -> httpx.Response:  # rdap.org has no server for .io: whois decides
        timeouts.append(request.extensions["timeout"]["read"])
        clock[0] += 3
        return httpx.Response(404, json={})

    whois.answers["keystone.io"] = IO_NOT_FOUND
    with httpx.Client(transport=httpx.MockTransport(slow)) as client:
        assert names.check_domain("keystone.io", client)["status"] == "available"  # 10 s for each, the most there is
        assert timeouts == [10]
        late = names.Clock(deadline=1010.0, limit=1012.0)  # a check whose limit is closer than LOOKUP_TIMEOUT
        whois.timeout = pytest.approx(12 - 6)  # RDAP ran from 3 to 6 s in: 6 s left before the limit
        assert names.check_domain("keystone.io", client, clock=late)["method"] == "whois"
        assert timeouts == [10, pytest.approx(12 - 3)]  # the request got only the time left before the limit
    assert names.Clock(deadline=1000.0, limit=1005.0).timeout() == 0.0  # past the limit, nothing is left


def test_whois_is_skipped_once_rdap_takes_the_check_past_its_deadline(monkeypatch, whois):
    clock = [1000.0]
    monkeypatch.setattr(names, "monotonic", lambda: clock[0])
    services = fake_transport(set(), set(), no_rdap={"io"})

    def slow(request: httpx.Request) -> httpx.Response:  # the RDAP lookup that starts at 0 s answers at 46 s
        clock[0] += 46
        return services.handle_request(request)

    whois.answers["keystone.io"] = IO_NOT_FOUND
    result = names.check("Keystone", tlds=("io", "co"), handles=("github",), transport=httpx.MockTransport(slow))
    assert result["domains"] == [{"domain": "keystone.io", "status": "unknown", "method": "none"},
                                 {"domain": "keystone.co", "status": "unknown", "method": "none"}]
    assert result["warnings"] == ["keystone.io: RDAP 404 from rdap.org, and the deadline passed before whois",
                                  "deadline reached after 45 s; not checked: keystone.co, github"]
    assert whois.asked == []


def test_tlds_are_normalised_and_anything_else_refused_before_a_lookup(monkeypatch):
    result = names.check("Keystone", tlds=(".COM", " .co.UK "), handles=(), transport=fake_transport({"keystone.com"}, set()))
    assert [d["domain"] for d in result["domains"]] == ["keystone.com", "keystone.co.uk"]
    monkeypatch.setattr(names, "default_transport", lambda: pytest.fail("no lookup expected"))
    for value in ("c/m", ".", "com..uk"):
        result = CliRunner().invoke(main, ["names", "check", "Keystone", "--tlds", f"io,{value}"])
        payload = json.loads(result.stdout)
        assert result.exit_code == 2 and payload["errors"] == [
            f"Not a top-level domain: {value!r} (letters, digits and hyphens, dot-separated: com or co.uk)"], value


def test_the_cli_checks_the_default_tlds_and_handles(monkeypatch):
    monkeypatch.setattr(names, "default_transport", lambda: fake_transport(set(), set()))
    payload = json.loads(CliRunner().invoke(main, ["names", "check", "Keystone"]).stdout)
    assert [d["domain"] for d in payload["domains"]] == [f"keystone.{tld}" for tld in names.TLDS]
    assert list(payload["handles"]) == list(names.HANDLES)
    payload = json.loads(CliRunner().invoke(main, ["names", "check", "Keystone", "--tlds", "com", "--handles", ""]).stdout)
    assert [d["domain"] for d in payload["domains"]] == ["keystone.com"] and payload["handles"] == {}


def test_check_needs_letters_or_digits():
    result = names.check("!!!", transport=httpx.MockTransport(lambda request: pytest.fail("no lookup expected")))
    assert result["label"] == "" and result["domains"] == [] and result["handles"] == {}
    assert result["warnings"] == ["name has no letters or digits to check"]


def test_cli(monkeypatch):
    monkeypatch.setattr(names, "default_transport", lambda: fake_transport({"keystone.com"}, set()))
    runner = CliRunner()
    payload = json.loads(runner.invoke(main, ["names", "analyze", "Keystone"]).stdout)
    assert payload["ok"] and payload["length"] == 8
    result = runner.invoke(main, ["names", "check", "Keystone", "--tlds", "com,dev", "--handles", "github"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 0 and payload["domains"][0]["status"] == "registered" and payload["handles"]["github"]["user"] == "available"


def test_cli_rejects_an_unknown_handle_service(monkeypatch):
    monkeypatch.setattr(names, "default_transport", lambda: pytest.fail("no lookup expected"))
    result = CliRunner().invoke(main, ["names", "check", "Keystone", "--handles", "github,twitter"])
    payload = json.loads(result.stdout)
    assert result.exit_code == 2 and payload["ok"] is False
    assert payload["errors"] == ["Unknown handle service 'twitter'; choose one of: github"]


@pytest.mark.live
def test_live_checks():
    result = names.check("google", tlds=("com",), handles=("github",))
    assert result["domains"][0]["status"] == "registered"
    assert names.check("zq7v3kx9plmw", tlds=("com",), handles=())["domains"][0]["status"] == "available"
    # torvalds is a personal account, so its login is no organisation's to take either
    assert names.check("torvalds", tlds=(), handles=("github",))["handles"]["github"] == {"user": "registered", "org": "registered"}
