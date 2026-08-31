import uuid
from dataclasses import dataclass, field

NAMESPACE = uuid.UUID("6b1c9f4e-0a2d-5f83-9c17-0d4e6a8b2f10")

FREE_MAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "msn.com",
        "aol.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "proton.me",
        "protonmail.com",
        "gmx.com",
        "gmx.de",
        "mail.com",
        "yandex.ru",
        "qq.com",
        "163.com",
        "126.com",
        "naver.com",
        "zoho.com",
        "fastmail.com",
        "hey.com",
        "example.com",
        "example.org",
        "test.com",
        "localhost",
        "email.com",
    }
)

PLACEHOLDER_VALUES = frozenset(
    {
        "n/a",
        "na",
        "none",
        "null",
        "nil",
        "unknown",
        "unspecified",
        "-",
        "--",
        "no",
        "not applicable",
        "tbd",
        "test",
        "noreply",
        "no-reply",
        "no@email.com",
        "test@test.com",
        "noreply@example.com",
        "email@email.com",
    }
)

PLACEHOLDER_PREFIXES = (
    "test@",
    "noreply@",
    "no-reply@",
    "donotreply@",
    "postmaster@",
    "abuse@",
    "invalid@",
)


@dataclass(frozen=True)
class Record:
    source: str
    entity_type: str
    source_id: str
    order: int
    identity: dict = field(default_factory=dict)

    @property
    def key(self) -> tuple:
        return (self.source, self.entity_type, self.source_id)

    @property
    def anchor_key(self) -> str:
        return f"{self.source}|{self.entity_type}|{self.source_id}"


@dataclass
class Cluster:
    canonical_id: uuid.UUID
    entity_type: str
    anchor_key: str
    minted_order: int
    members: dict = field(default_factory=dict)
    sources: set = field(default_factory=set)


def canonical_id_for(anchor_key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, anchor_key)


def is_blocked(attr: str, value: str) -> str | None:
    text = (value or "").strip().lower()
    if not text:
        return "empty"
    if text in PLACEHOLDER_VALUES:
        return "placeholder"
    if any(text.startswith(p) for p in PLACEHOLDER_PREFIXES):
        return "placeholder_mailbox"
    if text in FREE_MAIL_DOMAINS:
        return "free_mail_domain"
    if "@" in text and text.rsplit("@", 1)[-1] in FREE_MAIL_DOMAINS:
        return None if attr != "domain" else "free_mail_domain"
    return None


def resolve(records, onto, report) -> dict:
    ordered = sorted(
        records, key=lambda r: (r.order, r.source, r.entity_type, r.source_id)
    )

    clusters: list = []
    index: dict = {}
    of_record: dict = {}

    for record in ordered:
        identity_attrs = onto.identity_attrs(record.entity_type)
        evidence_keys: list = []
        if identity_attrs:
            usable = 0
            for attr in identity_attrs:
                value = record.identity.get(attr)
                if value is None or not str(value).strip():
                    continue
                reason = is_blocked(attr, str(value))
                if reason:
                    report.count(
                        f"identity_blocked/{record.entity_type}/{attr}/{reason}"
                    )
                    continue
                usable += 1
                evidence_keys.append((attr, str(value)))
            if usable == 0:
                report.no_identity(record.entity_type, record.source)

        position = None
        for attr, value in evidence_keys:
            found = index.get((record.entity_type, attr, value))
            if found is None:
                continue
            cluster = clusters[found]
            cluster.members[record.key] = f"{attr}={value}"
            cluster.sources.add(record.source)
            position = found
            break

        if position is None:
            cluster = Cluster(
                canonical_id=canonical_id_for(record.anchor_key),
                entity_type=record.entity_type,
                anchor_key=record.anchor_key,
                minted_order=record.order,
            )
            evidence = (
                f"{evidence_keys[0][0]}={evidence_keys[0][1]}"
                if evidence_keys
                else "singleton"
            )
            cluster.members[record.key] = evidence
            cluster.sources.add(record.source)
            clusters.append(cluster)
            position = len(clusters) - 1

        of_record[record.key] = position
        for attr, value in evidence_keys:
            index.setdefault((record.entity_type, attr, value), position)

    return {
        "clusters": clusters,
        "of_record": {key: clusters[i].canonical_id for key, i in of_record.items()},
    }
