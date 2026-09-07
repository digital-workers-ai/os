import difflib
import re
from dataclasses import dataclass

from sqlalchemy import delete, insert, select

from app.engine.resolver import is_blocked
from app.models import MergeCandidate, MergeCandidateEvidence

VIRTUAL = {"email_domain": "email"}  # derived corroborators: the field they are read from
ALIKE = 0.8
PER_RECORD_CAP = 5
DECIDED = ("confirmed", "rejected")

_NOT_WORD = re.compile(r"[^\w\s]")
_NOT_DIGIT = re.compile(r"\D")


@dataclass(frozen=True)
class Candidate:
    entity_type: str
    left: str
    right: str
    score: float
    evidence: tuple

    @property
    def pair(self) -> tuple:
        return (self.entity_type, self.left, self.right)


def attrs_read(spec) -> tuple:
    return (spec.name, *(VIRTUAL.get(attr, attr) for attr in spec.corroborate))


def name_tokens(value) -> list:
    return _NOT_WORD.sub(" ", str(value or "").lower()).split()


def name_score(left, right) -> float | None:
    a, b = name_tokens(left), name_tokens(right)
    if not a or not b:
        return None
    ratio = difflib.SequenceMatcher(None, " ".join(a), " ".join(b)).ratio()
    if ratio >= ALIKE:
        return ratio
    if len(a) < 2 or len(b) < 2 or a[0][0] != b[0][0]:
        return None
    short, long = sorted((a[-1], b[-1]), key=len)
    if len(short) >= 2 and long.startswith(short):
        return ALIKE
    return None


def phone_key(value) -> str | None:
    digits = _NOT_DIGIT.sub("", str(value or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits or None


def domain_key(value) -> str | None:
    text = str(value or "").strip().lower()
    if "@" not in text:
        return None
    domain = text.rsplit("@", 1)[1]
    return None if is_blocked("domain", domain) else domain


def plain_key(value) -> str | None:
    return str(value or "").strip().lower() or None


KEYS = {"phone": phone_key, "email_domain": domain_key}


def corroborator_key(record, attr) -> str | None:
    return KEYS.get(attr, plain_key)(record.identity.get(VIRTUAL.get(attr, attr)))


def agreements(left, right, spec) -> list:
    agreed = []
    for attr in spec.corroborate:
        key = corroborator_key(left, attr)
        if key is None or key != corroborator_key(right, attr):
            continue
        shown = [
            key if attr in VIRTUAL else str(record.identity[attr])
            for record in (left, right)
        ]
        agreed.append((attr, *shown))
    return agreed


def _blocks(records, spec) -> list:
    blocks: dict = {}
    for record in records:
        tokens = name_tokens(record.identity.get(spec.name))
        if not tokens:
            continue
        blocks.setdefault(("name", tokens[0][0] + tokens[-1][:2]), []).append(record)
        for attr in spec.corroborate:
            key = corroborator_key(record, attr)
            if key is not None:
                blocks.setdefault((attr, key), []).append(record)
    return list(blocks.values())


def _nominate(entity_type, records, spec, of_record) -> list:
    found: dict = {}
    seen: set = set()
    for block in _blocks(sorted(records, key=lambda r: r.anchor_key), spec):
        for position, left in enumerate(block):
            for right in block[position + 1 :]:
                pair = (left.anchor_key, right.anchor_key)
                if pair in seen:
                    continue
                seen.add(pair)
                clusters = frozenset(
                    of_record.get(record.key, record.key) for record in (left, right)
                )
                if len(clusters) < 2:
                    continue
                names = [str(record.identity[spec.name]) for record in (left, right)]
                score = name_score(*names)
                if score is None:
                    continue
                agreed = agreements(left, right, spec)
                if not agreed:
                    continue
                candidate = Candidate(
                    entity_type, *pair, score, ((spec.name, *names), *agreed)
                )
                best = found.get(clusters)
                if best is None or _rank(candidate) < _rank(best):
                    found[clusters] = candidate
    return _capped(found.values())


def _rank(candidate) -> tuple:
    return (-candidate.score, candidate.left, candidate.right)


def _capped(found) -> list:
    ranked = sorted(found, key=_rank)
    per_record: dict = {}
    for candidate in ranked:
        for side in (candidate.left, candidate.right):
            per_record.setdefault(side, []).append(candidate)
    return [
        c
        for c in ranked
        if all(c in per_record[side][:PER_RECORD_CAP] for side in (c.left, c.right))
    ]


def generate(records, onto, of_record) -> list:
    by_type: dict = {}
    for record in records:
        by_type.setdefault(record.entity_type, []).append(record)
    nominated: list = []
    for entity_type, group in sorted(by_type.items()):
        spec = onto.candidates(entity_type)
        if spec is not None:
            nominated += _nominate(entity_type, group, spec, of_record)
    return nominated


async def decided(session) -> list:
    return (
        (
            await session.execute(
                select(MergeCandidate)
                .where(MergeCandidate.status.in_(DECIDED))
                .order_by(MergeCandidate.seq)
            )
        )
        .scalars()
        .all()
    )


def confirmed_pairs(rows) -> list:
    return [
        (row.seq, row.left_anchor, row.right_anchor)
        for row in rows
        if row.status == "confirmed"
    ]


async def persist(session, fresh, rows, records, onto) -> None:
    by_anchor = {record.anchor_key: record for record in records}
    for row in rows:
        if row.status != "confirmed":
            continue
        left, right = by_anchor.get(row.left_anchor), by_anchor.get(row.right_anchor)
        spec = onto.candidates(row.entity_type)
        row.evidence_holds = bool(
            left and right and spec and agreements(left, right, spec)
        )
    settled = {(row.entity_type, row.left_anchor, row.right_anchor) for row in rows}
    await session.execute(
        delete(MergeCandidate).where(MergeCandidate.status == "pending")
    )
    queued = [candidate for candidate in fresh if candidate.pair not in settled]
    if not queued:
        return
    seqs = (
        (
            await session.execute(
                insert(MergeCandidate).returning(
                    MergeCandidate.seq, sort_by_parameter_order=True
                ),
                [
                    {
                        "entity_type": candidate.entity_type,
                        "left_anchor": candidate.left,
                        "right_anchor": candidate.right,
                        "score": candidate.score,
                        "status": "pending",
                    }
                    for candidate in queued
                ],
            )
        )
        .scalars()
        .all()
    )
    await session.execute(
        insert(MergeCandidateEvidence),
        [
            {
                "candidate_seq": seq,
                "attr": attr,
                "left_value": left_value,
                "right_value": right_value,
            }
            for seq, candidate in zip(seqs, queued, strict=True)
            for attr, left_value, right_value in candidate.evidence
        ],
    )
