from app import caches

DEFAULT_COMPETITORS = caches.DEFINITIONS_DIR / "competitors.yaml"

PLATFORM_IDS = ("meta_page_id", "google_advertiser_id", "linkedin_url")

ENGINES = ("chatgpt", "perplexity", "gemini", "aio")

NAME_LISTS = ("keywords", "prompts", "engines")


class CompetitorError(ValueError):
    pass


def load(path=None) -> dict:
    return caches.load_mapping(path or DEFAULT_COMPETITORS, CompetitorError)


definitions = caches.cached(load)


def tracked() -> dict:
    return definitions()["competitors"]


def _names(doc, key) -> tuple[list[str], list]:
    values = doc.get(key)
    if not isinstance(values, list) or not values:
        return (
            [
                f"{key}: must be a non-empty list — an empty one asks the "
                "watchers to go and look at nothing"
            ],
            [],
        )
    problems = [
        f"{key}: entry {value!r} is not a phrase to search for"
        for value in values
        if not isinstance(value, str) or not value.strip()
    ]
    return problems, [v for v in values if isinstance(v, str) and v.strip()]


def _us_problems(us) -> list[str]:
    return [
        f"us has no {key} — the file that says who the competition is must "
        "first say who we are, or every comparison is one-sided"
        for key in ("name", "domain")
        if not us.get(key)
    ]


def check(path=None) -> list[str]:
    try:
        doc = load(path)
    except CompetitorError as e:
        return [str(e)]

    us = doc.get("us")
    if not isinstance(us, dict):
        problems = [
            "us: must be a mapping naming this company and its domain — "
            "without it nothing knows which brand the assets are for"
        ]
        us = {}
    else:
        problems = _us_problems(us)

    named: dict = {}
    for key in NAME_LISTS:
        found, named[key] = _names(doc, key)
        problems += found
    problems += [
        f"engines: {engine!r} is not an answer engine this system reads — "
        f"known: {list(ENGINES)}"
        for engine in named["engines"]
        if engine not in ENGINES
    ]

    specs = doc.get("competitors")
    if not isinstance(specs, dict):
        problems.append(
            "competitors: must be a mapping of slug to competitor — a file "
            "that tracks nobody is a connector with nothing to ask for"
        )
        specs = {}

    owners: dict = {}
    for name, spec in sorted(specs.items()):
        prefix = f"competitor {name!r}"
        if not isinstance(spec, dict):
            problems.append(f"{prefix} must be a mapping")
            continue
        domain = spec.get("domain")
        if not domain:
            problems.append(
                f"{prefix} has no domain — the estate folds a competitor on its "
                "domain, so one without it never merges across sources"
            )
        elif domain in owners:
            problems.append(
                f"{prefix} shares domain {domain!r} with {owners[domain]!r} — "
                "one domain is one competitor"
            )
        else:
            owners[domain] = str(name)
        for key in PLATFORM_IDS:
            if not spec.get(key):
                problems.append(
                    f"{prefix} is missing {key} — a connector with no id to ask "
                    "for pulls nothing for this competitor"
                )

    if us.get("domain") in owners:
        problems.append(
            f"us domain {us['domain']!r} is also tracked as competitor "
            f"{owners[us['domain']]!r} — the swipe file would fill with our "
            "own work"
        )
    return problems
