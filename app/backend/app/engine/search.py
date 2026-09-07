import hashlib
import math
import re
import time
import uuid
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import String, and_, cast, delete, func, or_, select, text

from app import caches, llm
from app.api import entities_api
from app.config import settings
from app.engine import goals, metrics, ontology, rules
from app.engine.resolver import NAMESPACE
from app.enrichment import vocabulary
from app.llm import embeddings, rerank
from app.models import (
    BriefingRun,
    CanonicalMember,
    EmbeddingRun,
    EnrichedFact,
    EntityCanonical,
    EntityFact,
    FactCurrent,
    SearchChunk,
    SearchDocument,
)
from app.search_vocab import (
    ANCHOR_SEP,
    BRIEFING_REF_SEP,
    DEFAULT_LIMIT,
    DEFINITION_KINDS,
    EVIDENCE_SEP,
    HEADLINE_OPTIONS,
    LABEL_CHARS,
    LABEL_SEP,
    MIN_QUERY_CHARS,
    NON_ENTITY_KINDS,
    QUOTE_PREFIX,
    READING_PREFIX,
    STRONG_ATTRS,
    TEXT_SEARCH_CONFIG,
    TRIGRAM_THRESHOLD,
    UNINDEXED_TYPES,
    UNKNOWN_KIND,
    UNKNOWN_MODE,
    Attr,
    Kind,
    Mode,
    Param,
    Weight,
)
from app.sources import registry
from app.store import latest_rows_query

TOKEN = re.compile(r"[\w@.+-]+")
SENTENCE_END = re.compile(r"(?<=[.?!]) ")
RRF_K = 60
MEANING_CANDIDATES = 50
EVIDENCE_CHARS = 120
CHUNK_EVIDENCE_CHARS = 200
_EMBED_LOCK_ID = 0x_E3BED

WORDS_SQL = text(
    f"""
    WITH hits AS (
        SELECT DISTINCT ON (d.kind, d.ref_id)
               d.kind, d.ref_id, d.label, d.attr, d.weight, d.value, d.text,
               d.happened_at,
               ts_rank_cd(d.tsv, to_tsquery('{TEXT_SEARCH_CONFIG}', :expr)) AS score
        FROM search_document d
        WHERE d.tsv @@ to_tsquery('{TEXT_SEARCH_CONFIG}', :expr)
        ORDER BY d.kind, d.ref_id, score DESC, d.attr, d.text
    )
    SELECT kind, ref_id, label, attr, weight, value, happened_at, score,
           CASE WHEN weight = '{Weight.LONG}' THEN ts_headline(
               '{TEXT_SEARCH_CONFIG}', text, to_tsquery('{TEXT_SEARCH_CONFIG}', :expr),
               '{HEADLINE_OPTIONS}'
           ) END AS headline
    FROM hits
    """
)

TRIGRAM_SQL = text(
    f"""
    SELECT DISTINCT ON (d.kind, d.ref_id)
           d.kind, d.ref_id, d.label, d.attr, d.weight, d.value, d.happened_at,
           similarity(d.text, :q) AS score, NULL AS headline
    FROM search_document d
    WHERE d.weight IN ('{Weight.STRONG}', '{Weight.NORMAL}')
      AND similarity(d.text, :q) > {TRIGRAM_THRESHOLD}
    ORDER BY d.kind, d.ref_id, score DESC, d.attr, d.text
    """
)


class SearchError(RuntimeError):
    pass


def _uuid(*parts) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, "|".join(str(p) for p in parts))


def kinds() -> list[str]:
    return sorted(
        map(str, [*ontology.load().entities, *NON_ENTITY_KINDS, *DEFINITION_KINDS])
    )


def parse_query(q: str) -> tuple[str, str | None]:
    head, sep, tail = q.partition(":")
    if sep and head.strip() in kinds():
        return tail.strip(), head.strip()
    return q.strip(), None


def _pieces(text_: str, max_chars: int):
    for line in text_.splitlines():
        line = line.strip()
        if not line:
            continue
        if len(line) <= max_chars:
            yield line
            continue
        packed = ""
        for sentence in SENTENCE_END.split(line):
            if packed and len(packed) + 1 + len(sentence) > max_chars:
                yield packed
                packed = sentence
            else:
                packed = f"{packed} {sentence}" if packed else sentence
        yield packed


def chunks(text_: str, *, max_chars: int | None = None) -> list[str]:
    max_chars = max_chars or settings.SEARCH_CHUNK_CHARS
    out: list[str] = []
    current: list[str] = []
    for piece in _pieces(text_, max_chars):
        if current and len("\n".join(current)) + 1 + len(piece) > max_chars:
            out.append("\n".join(current))
            last = current[-1]
            current = [last] if len(last) + 1 + len(piece) <= max_chars else []
        current.append(piece)
    if current:
        out.append("\n".join(current))
    return out


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def document_text_for_raw(payload: dict) -> str:
    return LABEL_SEP.join(_strings(payload))


def _derived(attr: str, value: str) -> list[str]:
    if attr == "email":
        local, _, domain = value.partition("@")
        return [local, domain, domain.rsplit(".", 1)[0]]
    if attr == "domain":
        return [value.rsplit(".", 1)[0]]
    return []


def _happened_at(onto, entity_type: str, facts: dict):
    if entity_type != "meeting":
        return None
    dates = [
        value
        for attr, value in facts.items()
        if onto.attr_type(entity_type, attr) == "date"
    ]
    return datetime.fromisoformat(min(dates)) if dates else None


class _Documents:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.ordinals: Counter = Counter()

    def add(
        self, kind, ref_id, label, attr, value, weight, *, words=None, happened_at=None
    ) -> None:
        ordinal = self.ordinals[(kind, ref_id, attr)]
        self.ordinals[(kind, ref_id, attr)] += 1
        self.rows.append(
            {
                "id": _uuid(kind, ref_id, attr, ordinal),
                "kind": kind,
                "ref_id": ref_id,
                "label": label[:LABEL_CHARS],
                "attr": attr,
                "value": value,
                "text": value if words is None else words,
                "weight": weight,
                "happened_at": happened_at,
            }
        )


def _scoped(stmt, column, ids):
    return stmt if ids is None else stmt.where(column.in_(ids))


async def _index_entities(session, docs: _Documents, ids) -> int:
    onto = ontology.load()
    if ids is not None:
        await session.execute(
            delete(SearchDocument).where(
                SearchDocument.kind.not_in(NON_ENTITY_KINDS),
                SearchDocument.ref_id.in_([str(i) for i in ids]),
            )
        )
    member_facts: dict = {}
    for cid, attr, value in (
        await session.execute(
            _scoped(
                select(CanonicalMember.canonical_id, EntityFact.attr, EntityFact.value)
                .join(EntityFact, EntityFact.entity_id == CanonicalMember.entity_id)
                .where(EntityFact.value.is_not(None))
                .order_by(EntityFact.attr, EntityFact.value),
                CanonicalMember.canonical_id,
                ids,
            )
        )
    ).all():
        member_facts.setdefault(cid, []).append((attr, value))
    current: dict = {}
    for cid, attr, value in (
        await session.execute(
            _scoped(
                select(FactCurrent.canonical_id, FactCurrent.attr, FactCurrent.value),
                FactCurrent.canonical_id,
                ids,
            )
        )
    ).all():
        current.setdefault(cid, {})[attr] = value
    readings: dict = {}
    for cid, reading, attr, value, quote in (
        await session.execute(
            _scoped(
                select(
                    EnrichedFact.canonical_id,
                    EnrichedFact.reading,
                    EnrichedFact.attr,
                    EnrichedFact.value,
                    EnrichedFact.quote,
                ).order_by(EnrichedFact.reading, EnrichedFact.attr, EnrichedFact.value),
                EnrichedFact.canonical_id,
                ids,
            )
        )
    ).all():
        readings.setdefault(cid, []).append((reading, attr, value, quote))

    transcripts: dict = {}
    for cid, entity_type, anchor_key in (
        await session.execute(
            _scoped(
                select(
                    EntityCanonical.canonical_id,
                    EntityCanonical.entity_type,
                    EntityCanonical.anchor_key,
                ).order_by(EntityCanonical.minted_seq),
                EntityCanonical.canonical_id,
                ids,
            )
        )
    ).all():
        facts = current.get(cid, {})
        ref, label = str(cid), entities_api._label(anchor_key, facts)
        when = _happened_at(onto, entity_type, facts)
        source_id = anchor_key.split(ANCHOR_SEP, 2)[-1]
        anchor_words = f"{anchor_key.replace(ANCHOR_SEP, ' ')} {source_id}"
        docs.add(
            entity_type,
            ref,
            label,
            Attr.ANCHOR,
            anchor_key,
            Weight.STRONG,
            words=anchor_words,
            happened_at=when,
        )
        seen: set = set()
        for attr, value in member_facts.get(cid, []):
            skip = onto.attr_type(entity_type, attr) in UNINDEXED_TYPES
            if skip or (attr, value) in seen:
                continue
            seen.add((attr, value))
            weight = (
                Weight.STRONG
                if attr in STRONG_ATTRS
                else Weight.LONG
                if attr == Attr.TRANSCRIPT
                else Weight.NORMAL
            )
            words = " ".join(filter(None, [value, *_derived(attr, value)]))
            docs.add(
                entity_type,
                ref,
                label,
                attr,
                value,
                weight,
                words=words,
                happened_at=when,
            )
        for reading, attr, value, quote in readings.get(cid, []):
            reading_attr = f"{READING_PREFIX}{reading}"
            reading_value = f"{attr}{EVIDENCE_SEP}{value}"
            docs.add(
                entity_type,
                ref,
                label,
                reading_attr,
                reading_value,
                Weight.NORMAL,
                happened_at=when,
            )
            if quote:
                quote_attr = f"{QUOTE_PREFIX}{reading}"
                docs.add(
                    entity_type,
                    ref,
                    label,
                    quote_attr,
                    quote,
                    Weight.LONG,
                    happened_at=when,
                )
        if facts.get(Attr.TRANSCRIPT):
            transcripts[cid] = facts[Attr.TRANSCRIPT]
    return await _sync_chunks(session, transcripts, ids)


async def _sync_chunks(session, transcripts: dict, ids) -> int:
    existing = {
        (row.canonical_id, row.attr, row.chunk_index): row
        for row in (
            await session.execute(
                _scoped(select(SearchChunk), SearchChunk.canonical_id, ids)
            )
        ).scalars()
    }
    wanted = {
        (cid, Attr.TRANSCRIPT, index): piece
        for cid, transcript in transcripts.items()
        for index, piece in enumerate(chunks(transcript))
    }
    for key, piece in wanted.items():
        sha = hashlib.sha256(piece.encode()).hexdigest()
        row = existing.pop(key, None)
        if row is None:
            session.add(
                SearchChunk(
                    id=_uuid(*key),
                    canonical_id=key[0],
                    attr=key[1],
                    chunk_index=key[2],
                    text=piece,
                    sha=sha,
                )
            )
        elif row.sha != sha:
            row.text, row.sha = piece, sha
            row.model = row.embedding = row.embedded_at = None
    for row in existing.values():
        await session.delete(row)
    await session.flush()
    return len(wanted)


async def _index_briefings(session, docs: _Documents, seqs) -> None:
    runs = (
        (
            await session.execute(
                _scoped(
                    select(BriefingRun)
                    .where(BriefingRun.ok.is_(True), BriefingRun.briefing.is_not(None))
                    .order_by(BriefingRun.seq),
                    BriefingRun.seq,
                    seqs,
                )
            )
        )
        .scalars()
        .all()
    )
    if seqs is not None:
        await session.execute(
            delete(SearchDocument).where(
                SearchDocument.kind == Kind.BRIEFING,
                SearchDocument.ref_id.in_(
                    [f"{r.role}{BRIEFING_REF_SEP}{r.seq}" for r in runs]
                ),
            )
        )
    for run in runs:
        role = run.role.replace("_", " ").capitalize()
        label = f"{role}{LABEL_SEP}{run.created_at:%-d %b %Y}"
        ref = f"{run.role}{BRIEFING_REF_SEP}{run.seq}"
        docs.add(
            Kind.BRIEFING,
            ref,
            label,
            Attr.BRIEFING,
            run.briefing,
            Weight.LONG,
            happened_at=run.created_at,
        )


async def _index_raw(session, docs: _Documents) -> None:
    for event in (await session.execute(latest_rows_query())).scalars():
        label = LABEL_SEP.join((event.source, event.object_type, event.source_id))
        words = document_text_for_raw(event.raw_payload)
        docs.add(Kind.RAW, str(event.id), label, Attr.PAYLOAD, words, Weight.LONG)


async def index(session, *, canonical_ids=None, briefing_seqs=None) -> dict:
    full = canonical_ids is None and briefing_seqs is None
    docs = _Documents()
    chunk_count = 0
    if full:
        await session.execute(delete(SearchDocument))
        await _index_raw(session, docs)
    if full or canonical_ids is not None:
        chunk_count = await _index_entities(session, docs, canonical_ids)
    if full or briefing_seqs is not None:
        await _index_briefings(session, docs, briefing_seqs)
    if docs.rows:
        await session.execute(SearchDocument.__table__.insert(), docs.rows)
    return {"documents": len(docs.rows), "chunks": chunk_count}


async def embed(session, *, limit: int | None = None) -> dict:
    if not settings.EMBEDDINGS_ENABLED:
        raise SearchError(
            "EMBEDDINGS_ENABLED is off. Embedding calls a model, and it is "
            "opt-in on purpose."
        )
    got_lock = (
        await session.execute(select(func.pg_try_advisory_xact_lock(_EMBED_LOCK_ID)))
    ).scalar_one()
    if not got_lock:
        raise SearchError("an embedding run is already in progress")

    started = time.monotonic()
    model, batch = settings.EMBEDDING_MODEL, settings.EMBEDDING_BATCH
    cap = (limit or settings.EMBEDDINGS_MAX_CALLS_PER_RUN) * batch
    pending = (
        (
            await session.execute(
                select(SearchChunk)
                .where(or_(SearchChunk.embedding.is_(None), SearchChunk.model != model))
                .order_by(
                    SearchChunk.canonical_id, SearchChunk.attr, SearchChunk.chunk_index
                )
                .limit(cap + 1)
            )
        )
        .scalars()
        .all()
    )
    skipped = (
        await session.execute(
            select(func.count())
            .select_from(SearchChunk)
            .where(SearchChunk.model == model)
        )
    ).scalar_one()
    embedded, failed, error = 0, 0, None
    for start in range(0, min(len(pending), cap), batch):
        rows = pending[start : start + batch]
        try:
            vectors = await embeddings.embed([row.text for row in rows])
        except llm.LLMError as exc:
            failed += len(rows)
            error = error or str(exc)
            continue
        now = datetime.now(UTC)
        for row, vector in zip(rows, vectors, strict=True):
            row.embedding, row.model, row.embedded_at = vector, model, now
        embedded += len(rows)
        await session.commit()
    receipt = {
        "model": model,
        "embedded": embedded,
        "skipped": skipped,
        "failed": failed,
        "truncated_at_cap": len(pending) > cap,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "error": error,
    }
    session.add(EmbeddingRun(ok=error is None, **receipt))
    await session.commit()
    return receipt


def _load_definitions() -> list[dict]:
    entries = []

    def add(kind, name, label, words, evidence):
        entries.append(
            {
                "kind": str(kind),
                "id": name,
                "label": label,
                "text": words.lower(),
                "evidence": evidence,
            }
        )

    for name, spec in sorted(metrics.load_definitions().items()):
        label = spec.get("label", name)
        synonyms = " ".join(spec.get("synonyms") or ())
        add(
            Kind.METRIC,
            name,
            label,
            f"{name} {label} {spec.get('entity', '')} {synonyms}",
            f"label{EVIDENCE_SEP}{label}",
        )
    for name, rule in sorted(rules.load().items()):
        add(
            Kind.RULE,
            name,
            rule.label,
            f"{name} {rule.label} {rule.entity}",
            f"label{EVIDENCE_SEP}{rule.label}",
        )
    for name, spec in sorted(goals.load().items()):
        metric = spec.get("metric", "")
        add(Kind.GOAL, name, name, f"{name} {metric}", f"metric{EVIDENCE_SEP}{metric}")
    for name in sorted(registry.discover()):
        add(Kind.SOURCE, name, name, name, f"source{EVIDENCE_SEP}{name}")
    onto = ontology.load()
    for name, spec in sorted(onto.entities.items()):
        attrs = list(spec.attrs)
        aliases = [
            *spec.synonyms,
            *(
                synonym
                for attr in attrs
                if attr in onto.attributes
                for synonym in onto.attributes[attr].synonyms
            ),
        ]
        add(
            Kind.ENTITY_TYPE,
            name,
            name,
            " ".join([name, *attrs, *aliases]),
            f"attrs{EVIDENCE_SEP}{', '.join(attrs)}",
        )
    for name, reading in sorted(vocabulary.load().items()):
        values = [label for field in reading.fields for label in field.labels]
        words = f"{name} {reading.entity} {reading.input_attr} {' '.join(values)}"
        add(Kind.READING, name, name, words, f"values{EVIDENCE_SEP}{', '.join(values)}")
    return entries


definitions = caches.cached(_load_definitions)


def _names(text: str, token: str) -> bool:
    return token in text or token.removesuffix("s") in text


def _lexeme(token: str) -> str:
    return "'" + token.replace("'", "''") + "'"


def _evidence(row) -> str:
    if row.weight == Weight.LONG:
        return row.headline
    if row.attr.startswith(READING_PREFIX):
        return row.value[:EVIDENCE_CHARS]
    return f"{row.attr}{EVIDENCE_SEP}{row.value[:EVIDENCE_CHARS]}"


def _recency(happened_at) -> float:
    return math.inf if happened_at is None else -happened_at.timestamp()


def _ranked(hits: list[dict]) -> list[dict]:
    return sorted(
        hits,
        key=lambda h: (-h["score"], h["kind"], h["recency"], h["label"], h["id"]),
    )


async def _words(session, q: str, *, fallback: bool) -> list[dict]:
    tokens = TOKEN.findall(q.lower())
    if not tokens:
        return []
    lexemes = [_lexeme(token) for token in tokens]
    lexemes[-1] += ":*"
    rows = (await session.execute(WORDS_SQL, {"expr": " & ".join(lexemes)})).all()
    if not rows and fallback:
        rows = (await session.execute(TRIGRAM_SQL, {"q": q})).all()
    hits = [
        {
            "kind": row.kind,
            "id": row.ref_id,
            "label": row.label,
            "evidence": _evidence(row),
            "score": float(row.score),
            "recency": _recency(row.happened_at),
        }
        for row in rows
    ]
    hits += [
        {**entry, "score": 1.0, "recency": math.inf}
        for entry in definitions()
        if all(_names(entry["text"], token) for token in tokens)
    ]
    return _ranked(hits)


async def _meaning(session, q: str) -> list[dict]:
    if not settings.EMBEDDINGS_ENABLED:
        raise SearchError(
            "EMBEDDINGS_ENABLED is off. Searching by meaning needs vectors, "
            "and embedding calls a model, so it is opt-in on purpose."
        )
    vector = (await embeddings.embed([q]))[0]
    distance = SearchChunk.embedding.cosine_distance(vector)
    rows = (
        await session.execute(
            select(
                SearchChunk.canonical_id,
                SearchChunk.text,
                EntityCanonical.entity_type,
                SearchDocument.label,
                SearchDocument.happened_at,
                (1 - distance).label("score"),
            )
            .join(
                EntityCanonical,
                EntityCanonical.canonical_id == SearchChunk.canonical_id,
            )
            .join(
                SearchDocument,
                and_(
                    SearchDocument.kind == EntityCanonical.entity_type,
                    SearchDocument.ref_id == cast(EntityCanonical.canonical_id, String),
                    SearchDocument.attr == Attr.ANCHOR,
                ),
            )
            .where(SearchChunk.embedding.is_not(None))
            .order_by(distance, SearchChunk.canonical_id, SearchChunk.chunk_index)
            .limit(MEANING_CANDIDATES)
        )
    ).all()
    best: dict = {}
    for row in rows:
        best.setdefault(
            row.canonical_id,
            {
                "kind": row.entity_type,
                "id": str(row.canonical_id),
                "label": row.label,
                "evidence": row.text[:CHUNK_EVIDENCE_CHARS],
                "score": float(row.score),
                "recency": _recency(row.happened_at),
            },
        )
    return _ranked(list(best.values()))


def _fuse(words: list[dict], meaning: list[dict]) -> list[dict]:
    scores: Counter = Counter()
    hits: dict = {}
    for ranking in (words, meaning):
        for rank, hit in enumerate(ranking, 1):
            key = (hit["kind"], hit["id"])
            scores[key] += 1 / (RRF_K + rank)
            hits.setdefault(key, hit)
    return _ranked([{**hit, "score": scores[key]} for key, hit in hits.items()])


async def _rerank(q: str, hits: list[dict]) -> tuple[list[dict], bool]:
    top, rest = hits[: settings.RERANK_TOP], hits[settings.RERANK_TOP :]
    try:
        scores = await rerank.rerank(
            q, [f"{h['label']} — {h['evidence']}" for h in top]
        )
    except llm.LLMError:
        return hits, False
    order = sorted(range(len(top)), key=lambda i: -scores[i])
    return [top[i] for i in order] + rest, True


async def query(
    session,
    q: str,
    *,
    kind: str | None = None,
    mode: str = Mode.WORDS,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict:
    if mode not in Mode:
        raise SearchError(f"{UNKNOWN_MODE} {mode!r}; one of {[m.value for m in Mode]}")
    q, prefix = parse_query(q)
    kind = kind or prefix
    if kind is not None and kind not in kinds():
        raise SearchError(f"{UNKNOWN_KIND} {kind!r}; one of {kinds()}")
    response = {
        Param.Q: q,
        Param.KIND: kind,
        Param.MODE: str(mode),
        "meaning_enabled": settings.EMBEDDINGS_ENABLED,
        "rerank_enabled": settings.RERANK_ENABLED,
        "reranked": False,
        "total": 0,
        Param.LIMIT: limit,
        Param.OFFSET: offset,
        "by_kind": {},
        "results": [],
    }
    if len(q) < MIN_QUERY_CHARS:
        return response

    hits: list[dict] = []
    if mode != Mode.MEANING:
        hits = await _words(session, q, fallback=mode == Mode.WORDS)
    if mode != Mode.WORDS:
        meaning = await _meaning(session, q)
        hits = _fuse(hits, meaning) if mode == Mode.BOTH else meaning
    if mode == Mode.BOTH and settings.RERANK_ENABLED and hits:
        hits, response["reranked"] = await _rerank(q, hits)

    by_kind = Counter(hit["kind"] for hit in hits)
    if kind:
        hits = [hit for hit in hits if hit["kind"] == kind]
    response["total"] = len(hits)
    response["by_kind"] = dict(sorted(by_kind.items()))
    response["results"] = [
        {key: hit[key] for key in ("kind", "id", "label", "evidence")}
        for hit in hits[offset : offset + limit]
    ]
    return response
