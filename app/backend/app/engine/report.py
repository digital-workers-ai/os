from collections import Counter


class SyncReport:
    def __init__(self) -> None:
        self.skips: Counter = Counter()
        self.clears: Counter = Counter()
        self.path_hits: Counter = Counter()
        self.declared_paths: set = set()
        self.tombstones: Counter = Counter()
        self.quarantines: list = []
        self.dangling_refs: Counter = Counter()
        self.identity_less: Counter = Counter()
        self.oversized: list = []
        self.disagreements: Counter = Counter()
        self.match_rates: dict = {}
        self.records_skipped: Counter = Counter()
        self.counts: Counter = Counter()

    def declare_path(self, entity: str, key: str) -> None:
        self.declared_paths.add(f"{entity}:{key}")

    def hit_path(self, entity: str, key: str) -> None:
        self.path_hits[f"{entity}:{key}"] += 1

    def skip(self, label: str, source: str, reason: str) -> None:
        self.skips[f"{label}/{source}/{reason}"] += 1

    def clear(self, label: str, source: str) -> None:
        self.clears[f"{label}/{source}"] += 1

    def record_skip(self, source: str, object_type: str, reason: str) -> None:
        self.records_skipped[f"{source}/{object_type}/{reason}"] += 1

    def tombstone(self, source: str, object_type: str) -> None:
        self.tombstones[f"{source}/{object_type}"] += 1

    def quarantine(self, rel: str, subject: str, detail: str) -> None:
        self.quarantines.append({"rel": rel, "record": subject, "detail": detail})

    def dangling(self, rel: str) -> None:
        self.dangling_refs[rel] += 1

    def no_identity(self, entity_type: str, source: str) -> None:
        self.identity_less[f"{entity_type}/{source}"] += 1

    def oversize(self, kind: str, detail: dict) -> None:
        self.oversized.append({"kind": kind, **detail})

    def disagree(self, entity_type: str, attr: str, n: int) -> None:
        self.disagreements[f"{entity_type}.{attr}"] += n

    def rate(self, rel: str, candidates: int, matched: int, edges: int) -> None:
        self.match_rates[rel] = {
            "candidates": candidates,
            "matched": matched,
            "edges": edges,
            "match_rate": round(matched / candidates, 3) if candidates else None,
        }

    def count(self, key: str, n: int = 1) -> None:
        self.counts[key] += n

    def dead_paths(self) -> list:
        return sorted(p for p in self.declared_paths if not self.path_hits.get(p))

    def totals(self) -> dict:
        return {
            "skips": sum(self.skips.values()),
            "clears": sum(self.clears.values()),
            "dead_paths": len(self.dead_paths()),
            "tombstones": sum(self.tombstones.values()),
            "quarantines": len(self.quarantines),
            "dangling_refs": sum(self.dangling_refs.values()),
            "identity_less": sum(self.identity_less.values()),
            "oversized": len(self.oversized),
            "disagreements": sum(self.disagreements.values()),
            "records_skipped": sum(self.records_skipped.values()),
        }

    def clean(self) -> bool:
        totals = self.totals()
        return not any(
            totals[k]
            for k in (
                "skips",
                "dead_paths",
                "quarantines",
                "oversized",
                "records_skipped",
            )
        )

    def as_dict(self) -> dict:
        return {
            "totals": self.totals(),
            "counts": dict(sorted(self.counts.items())),
            "skips": dict(sorted(self.skips.items())),
            "records_skipped": dict(sorted(self.records_skipped.items())),
            "clears": dict(sorted(self.clears.items())),
            "dead_paths": self.dead_paths(),
            "tombstones": dict(sorted(self.tombstones.items())),
            "quarantines": self.quarantines[:200],
            "dangling_refs": dict(sorted(self.dangling_refs.items())),
            "identity_less": dict(sorted(self.identity_less.items())),
            "oversized": self.oversized[:200],
            "disagreements": dict(sorted(self.disagreements.items())),
            "match_rates": self.match_rates,
        }
