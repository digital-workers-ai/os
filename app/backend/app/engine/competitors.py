from app import caches

DEFAULT_COMPETITORS = caches.DEFINITIONS_DIR / "competitors.yaml"

PLATFORM_IDS = ("meta_page_id", "google_advertiser_id")


class CompetitorError(ValueError):
    pass


def load(path=None) -> dict:
    return caches.load_mapping(path or DEFAULT_COMPETITORS, CompetitorError)


definitions = caches.cached(load)


def check(path=None) -> list[str]:
    try:
        specs = load(path)
    except CompetitorError as e:
        return [str(e)]
    problems: list[str] = []
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
    return problems
