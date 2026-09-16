import re
from collections import Counter
from dataclasses import dataclass

from app import caches

DEFAULT_SPY = caches.DEFINITIONS_DIR / "spy.yaml"
ENGINES = ("google", "ai_overview", "chatgpt", "perplexity", "claude", "gemini")
ROLES = ("brand", "competitor")

TOP_KEYS = frozenset({"brand", "competitors", "queries", "country", "language"})
BRAND_KEYS = frozenset({"name", "domain", "aliases"})
COMPETITOR_KEYS = BRAND_KEYS | {"linkedin", "google_advertiser_id"}

_DOMAIN_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")  # lowercase host, no scheme: acme.io, crm.zoho.com
_LINKEDIN_RE = re.compile(r"^[a-z0-9-]+$")  # company page slug: hubspot, freshworks-inc
_ADVERTISER_RE = re.compile(r"^AR\d+$")  # google advertiser id: AR10072600…, AR07034216…
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")  # two-letter country code: US, GB
_LANGUAGE_RE = re.compile(r"^[a-z]{2}$")  # two-letter language code: en, es
_CODED_KEYS = (("linkedin", _LINKEDIN_RE), ("google_advertiser_id", _ADVERTISER_RE))  # optional keys, refused when malformed
_SLUG_RE = re.compile(r"[^a-z0-9]+")  # non-alphanumeric runs become dashes: best crm → best-crm
_HOST_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*://)?(?:www\.)?([^/:?#]*)")  # host only, www dropped: zoho.com, crm.zoho.com


class SpyError(ValueError):
    pass


@dataclass(frozen=True)
class Company:
    name: str
    domain: str
    aliases: tuple[str, ...]
    linkedin: str | None
    google_advertiser_id: str | None
    role: str

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


@dataclass(frozen=True)
class Definition:
    brand: Company
    competitors: tuple[Company, ...]
    queries: tuple[str, ...]
    country: str
    language: str

    @property
    def companies(self) -> tuple[Company, ...]:
        return (self.brand, *self.competitors)

    def by_domain(self, host_or_url) -> Company | None:
        return next(
            (c for c in self.companies if host_matches(host_or_url, c.domain)), None
        )

    def by_linkedin(self, handle) -> Company | None:
        return {c.linkedin: c for c in self.competitors if c.linkedin}.get(handle)

    def by_advertiser(self, advertiser_id) -> Company | None:
        return {
            c.google_advertiser_id: c
            for c in self.competitors
            if c.google_advertiser_id
        }.get(advertiser_id)


@dataclass(frozen=True)
class Mention:
    company: Company
    rank: int
    evidence: str


def load(path=None) -> dict:
    return caches.load_mapping(path or DEFAULT_SPY, SpyError)


definitions = caches.cached(load)


def _problem(reason) -> str:
    return f"spy.yaml: {reason}"


def _matches(pattern, value) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _pattern_problems(what, value, pattern) -> list[str]:
    if _matches(pattern, value):
        return []
    return [_problem(f"{what} {value!r} must match {pattern.pattern}")]


def _repeats(values) -> list:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def _company_problems(label, spec, keys) -> list[str]:
    if not isinstance(spec, dict):
        return [_problem(f"{label} must be a mapping")]
    problems = [
        _problem(f"{label} has unknown key {key!r} — known: {sorted(keys)}")
        for key in sorted(set(spec) - keys)
    ]
    name = spec.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append(_problem(f"{label} is missing a string `name`"))
    domain = spec.get("domain")
    if not _matches(_DOMAIN_RE, domain):
        problems.append(
            _problem(
                f"{label} domain {domain!r} must be a lowercase host with no "
                "scheme or path"
            )
        )
    aliases = spec.get("aliases", [])
    if not isinstance(aliases, list) or not all(
        isinstance(alias, str) and alias.strip() for alias in aliases
    ):
        problems.append(
            _problem(f"{label} aliases must be a list of non-empty strings")
        )
    for key, pattern in _CODED_KEYS:
        if key in keys and key in spec:
            problems += _pattern_problems(f"{label} {key}", spec[key], pattern)
    return problems


def _competitor_label(index, spec) -> str:
    name = spec.get("name") if isinstance(spec, dict) else None
    return f"competitor {name!r}" if isinstance(name, str) else f"competitors[{index}]"


def _names_of(spec) -> list[str]:
    aliases = spec.get("aliases", [])
    candidates = [spec.get("name"), *(aliases if isinstance(aliases, list) else [])]
    return [value for value in candidates if isinstance(value, str)]


def _duplicate_problems(specs) -> list[str]:
    names = [name.lower() for spec in specs for name in _names_of(spec)]
    domains = [
        spec.get("domain") for spec in specs if isinstance(spec.get("domain"), str)
    ]
    problems = [
        _problem(
            f"name {name!r} appears more than once across brand and competitors — "
            "names and aliases compare case-insensitively"
        )
        for name in _repeats(names)
    ]
    problems += [
        _problem(f"domain {domain!r} appears more than once")
        for domain in _repeats(domains)
    ]
    return problems


def _query_problems(queries) -> list[str]:
    if not isinstance(queries, list) or not queries:
        return [_problem("queries must be a non-empty list")]
    problems = [
        _problem(f"queries[{index}] {query!r} must be a non-empty string")
        for index, query in enumerate(queries)
        if not isinstance(query, str) or not query.strip()
    ]
    slugs = [slug(query) for query in queries if isinstance(query, str)]
    problems += [
        _problem(f"more than one query slugs to {slugged!r}")
        for slugged in _repeats(slugs)
    ]
    return problems


def check(doc) -> list[str]:
    if not isinstance(doc, dict):
        return [_problem("top level must be a mapping")]
    problems = [
        _problem(f"unknown key {key!r} — known: {sorted(TOP_KEYS)}")
        for key in sorted(set(doc) - TOP_KEYS)
    ]
    problems += _company_problems("brand", doc.get("brand"), BRAND_KEYS)
    competitors = doc.get("competitors")
    if isinstance(competitors, list) and competitors:
        for index, spec in enumerate(competitors):
            problems += _company_problems(
                _competitor_label(index, spec), spec, COMPETITOR_KEYS
            )
    else:
        problems.append(_problem("competitors must be a non-empty list"))
        competitors = []
    specs = [
        spec for spec in (doc.get("brand"), *competitors) if isinstance(spec, dict)
    ]
    problems += _duplicate_problems(specs)
    problems += _query_problems(doc.get("queries"))
    problems += _pattern_problems("country", doc.get("country"), _COUNTRY_RE)
    problems += _pattern_problems("language", doc.get("language"), _LANGUAGE_RE)
    return problems


def _company(spec, role) -> Company:
    return Company(
        name=spec["name"],
        domain=spec["domain"],
        aliases=tuple(spec.get("aliases", ())),
        linkedin=spec.get("linkedin"),
        google_advertiser_id=spec.get("google_advertiser_id"),
        role=role,
    )


def parse(doc) -> Definition:
    problems = check(doc)
    if problems:
        raise SpyError(problems[0])
    return Definition(
        brand=_company(doc["brand"], "brand"),
        competitors=tuple(_company(spec, "competitor") for spec in doc["competitors"]),
        queries=tuple(doc["queries"]),
        country=doc["country"],
        language=doc["language"],
    )


definition = caches.cached(lambda: parse(definitions()))


def slug(text) -> str:
    return _SLUG_RE.sub("-", str(text).lower()).strip("-")


def host(url_or_host) -> str:
    return _HOST_RE.match(str(url_or_host).strip().lower()).group(1)


def host_matches(url_or_host, domain) -> bool:
    found = host(url_or_host)
    return found == domain or found.endswith(f".{domain}")


def _first_in_text(company, text):
    found = None
    for name in company.names:
        match = re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text, re.IGNORECASE)
        if match and (found is None or match.start() < found.start()):
            found = match
    return found


def _link_index(company, links):
    return next(
        (i for i, link in enumerate(links) if host_matches(link, company.domain)),
        None,
    )


def _by_position(hit):
    return hit[:2]


def mentions(definition, text, links) -> list[Mention]:
    in_text = []
    in_links = []
    for company in definition.companies:
        match = _first_in_text(company, text)
        if match is not None:
            in_text.append((match.start(), company.name, company, match.group(0)))
            continue
        link_at = _link_index(company, links)
        if link_at is not None:
            in_links.append((link_at, company.name, company, host(links[link_at])))
    ordered = sorted(in_text, key=_by_position) + sorted(in_links, key=_by_position)
    return [
        Mention(company, rank, evidence)
        for rank, (_, _, company, evidence) in enumerate(ordered, start=1)
    ]


def serp_mentions(definition, results) -> list[Mention]:
    found = []
    for company in definition.companies:
        hits = [
            (result["position"], host(result["link"]))
            for result in results
            if host_matches(result.get("link", ""), company.domain)
        ]
        if hits:
            rank, evidence = min(hits)
            found.append(Mention(company, rank, evidence))
    return sorted(found, key=lambda m: (m.rank, m.company.name))
