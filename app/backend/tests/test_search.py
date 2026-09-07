import hashlib
import importlib
import re
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, update

from app import config, llm
from app.coaching import briefer
from app.config import Settings, settings
from app.db import get_session
from app.engine import ontology, run, search
from app.enrichment import reader, vocabulary
from app.enrichment import store as enrichment_store
from app.main import app
from app.models import (
    BriefingRun,
    CanonicalMember,
    EmbeddingRun,
    EnrichedFact,
    Entity,
    EntityCanonical,
    EntityFact,
    FactCurrent,
    RawEvent,
    SearchChunk,
    SearchDocument,
)
from app.search_vocab import (
    DEFINITION_KINDS,
    MARK_CLOSE,
    MARK_OPEN,
    NON_ENTITY_KINDS,
    QUOTE_PREFIX,
    READING_PREFIX,
    UNKNOWN_KIND,
    Attr,
    Kind,
    Mode,
    Weight,
)

SEEN = datetime(2026, 8, 1, tzinfo=UTC)
DIMS = 1536
TOPICS = ("pricing", "reporting", "kryptonite")
TRANSCRIPT = (
    "Bruce Wayne: marketing wants the same reporting.\n"
    "Jane Smith: pricing is the blocker."
)
RESPONSE_KEYS = {
    "q",
    "kind",
    "mode",
    "meaning_enabled",
    "rerank_enabled",
    "reranked",
    "total",
    "limit",
    "offset",
    "by_kind",
    "results",
}
EMBED_KEYS = {
    "model",
    "embedded",
    "skipped",
    "failed",
    "truncated_at_cap",
    "duration_ms",
    "error",
}


def fake_vector(text: str) -> list[float]:
    words = set(re.findall(r"[a-z]+", text.lower()))
    vec = [0.0] * DIMS
    for i, topic in enumerate(TOPICS):
        if topic in words:
            vec[i] = 1.0
    if not any(vec):
        vec[len(TOPICS)] = 1.0
    return vec


class FakeEmbedder:
    def __init__(self, fail_batches=()):
        self.calls: list = []
        self.fail_batches = set(fail_batches)

    async def __call__(self, texts, **kwargs):
        index = len(self.calls)
        self.calls.append(list(texts))
        if index in self.fail_batches:
            raise llm.LLMError(f"batch {index} down")
        return [fake_vector(t) for t in texts]


class FakeReranker:
    def __init__(self, scores=None, raises=None):
        self.scores, self.raises = scores or {}, raises
        self.calls: list = []

    async def __call__(self, query, documents, **kwargs):
        self.calls.append((query, list(documents)))
        if self.raises:
            raise self.raises
        return [
            next((s for label, s in self.scores.items() if d.startswith(label)), 0.0)
            for d in documents
        ]


class StubModel:
    def __init__(self, text):
        self.text = text

    @property
    def messages(self):
        return self

    async def create(self, **kwargs):
        block = type("Block", (), {"type": "text", "text": self.text})()
        return type(
            "Reply",
            (),
            {"content": [block], "stop_reason": "end_turn", "model": "claude-test"},
        )()


def briefing_row(role="ceo", text="Churn is rising.", ok=True, created_at=SEEN):
    return BriefingRun(
        role=role,
        ok=ok,
        model="claude-test",
        prompt_version="2026-08-02.1",
        prompts_sha="a" * 64,
        input_sha="b" * 64,
        read_manifest={},
        briefing=text if ok else None,
        error=None if ok else "model refused",
        duration_ms=1,
        created_at=created_at,
    )


def raw_row(
    source="hubspot", object_type="contacts", source_id="con_001", payload=None
):
    payload = payload if payload is not None else {"name": "Bruce"}
    return RawEvent(
        source=source,
        object_type=object_type,
        source_id=source_id,
        raw_payload=payload,
        payload_sha=hashlib.sha256(repr(payload).encode()).hexdigest(),
    )


def enriched_row(canonical_id, attr="interest", value="strong", quote="budget is set"):
    return EnrichedFact(
        canonical_id=canonical_id,
        entity_type="meeting",
        reading="sales_call",
        attr=attr,
        value=value,
        quote=quote,
        quote_verified=True,
        input_sha="c" * 64,
        vocabulary_sha="d" * 64,
        model="m",
        prompt_version="2026-08-02.1",
    )


async def documents(session, **where):
    rows = (
        (
            await session.execute(
                select(SearchDocument)
                .execution_options(populate_existing=True)
                .order_by(SearchDocument.kind, SearchDocument.attr, SearchDocument.text)
            )
        )
        .scalars()
        .all()
    )
    return [r for r in rows if all(getattr(r, k) == v for k, v in where.items())]


async def chunk_rows(session, canonical_id=None):
    query = (
        select(SearchChunk)
        .execution_options(populate_existing=True)
        .order_by(SearchChunk.canonical_id, SearchChunk.attr, SearchChunk.chunk_index)
    )
    if canonical_id is not None:
        query = query.where(SearchChunk.canonical_id == canonical_id)
    return (await session.execute(query)).scalars().all()


async def embedding_runs(session):
    return (
        (await session.execute(select(EmbeddingRun).order_by(EmbeddingRun.seq)))
        .scalars()
        .all()
    )


async def set_transcript(session, canonical_id, text):
    member_ids = select(CanonicalMember.entity_id).where(
        CanonicalMember.canonical_id == canonical_id
    )
    await session.execute(
        update(EntityFact)
        .where(EntityFact.entity_id.in_(member_ids), EntityFact.attr == "transcript")
        .values(value=text)
    )
    await session.execute(
        update(FactCurrent)
        .where(
            FactCurrent.canonical_id == canonical_id,
            FactCurrent.attr == "transcript",
        )
        .values(value=text)
    )


async def drop_canonical(session, canonical_id):
    member_ids = select(CanonicalMember.entity_id).where(
        CanonicalMember.canonical_id == canonical_id
    )
    entity_ids = list((await session.execute(member_ids)).scalars().all())
    await session.execute(
        delete(FactCurrent).where(FactCurrent.canonical_id == canonical_id)
    )
    await session.execute(
        delete(EntityFact).where(EntityFact.entity_id.in_(entity_ids))
    )
    await session.execute(
        delete(CanonicalMember).where(CanonicalMember.canonical_id == canonical_id)
    )
    await session.execute(
        delete(EntityCanonical).where(EntityCanonical.canonical_id == canonical_id)
    )
    await session.execute(delete(Entity).where(Entity.id.in_(entity_ids)))


def ids(result) -> list:
    return [r["id"] for r in result["results"]]


def of_kind(result, kind) -> list:
    return [r for r in result["results"] if r["kind"] == kind]


@pytest.fixture
def meaning_on(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDINGS_ENABLED", True)


@pytest.fixture
def embedder(monkeypatch):
    def install(fail_batches=()):
        fake = FakeEmbedder(fail_batches)
        monkeypatch.setattr("app.llm.embeddings.embed", fake)
        return fake

    return install


@pytest.fixture
def reranker(monkeypatch):
    def install(scores=None, raises=None):
        fake = FakeReranker(scores, raises)
        monkeypatch.setattr("app.llm.rerank.rerank", fake)
        return fake

    return install


@pytest_asyncio.fixture
async def api(session, sessionmaker_for_test, monkeypatch):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    for name in ("app.api.search_api", "app.api.raw_api", "app.api.coaching_api"):
        module = importlib.import_module(name)
        monkeypatch.setattr(
            module, "async_session", sessionmaker_for_test, raising=False
        )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def estate(session, canonical):
    wayne = await canonical(
        "company",
        {"name": "Wayne Enterprises", "domain": "wayne.com", "industry": "defense"},
    )
    bruce = await canonical(
        "person",
        {"name": "Bruce Wayne", "email": "bruce@wayne.com", "title": "CEO"},
        sources=["hubspot", "zendesk"],
        member_facts={"zendesk": {"name": "Batman"}},
    )
    kickoff = await canonical(
        "meeting",
        {
            "name": "Q3 kickoff",
            "transcript": TRANSCRIPT,
            "started_at": "2026-09-01T10:00:00Z",
        },
    )
    sub = await canonical("subscription", {"status": "past_due", "mrr": "100"})
    carlos = await canonical("person", {"name": "Carlos"})
    older = briefing_row(
        text="Churn is rising across the base.",
        created_at=SEEN - timedelta(days=60),
    )
    session.add(older)
    await session.flush()
    newer = briefing_row(text="Churn is rising across the base.", created_at=SEEN)
    session.add(newer)
    await session.flush()
    raw = raw_row(payload={"name": "Bruce Wayne", "city": "Gotham"})
    session.add(raw)
    await session.flush()
    await search.index(session)
    return {
        "wayne": wayne,
        "bruce": bruce,
        "kickoff": kickoff,
        "sub": sub,
        "carlos": carlos,
        "older": older,
        "newer": newer,
        "raw": raw,
    }


@pytest_asyncio.fixture
async def vectors(session, canonical, monkeypatch, meaning_on):
    monkeypatch.setattr(settings, "SEARCH_CHUNK_CHARS", 50)
    company = await canonical("company", {"name": "Kryptonite Ltd"})
    k1 = await canonical(
        "meeting",
        {
            "name": "Shipment sync",
            "transcript": (
                "Lex: kryptonite is late.\nOtis: reporting too.\nLex: pricing is fine."
            ),
        },
    )
    k2 = await canonical(
        "meeting",
        {"name": "Reporting sync", "transcript": "Alfred: reporting is due."},
    )
    k3 = await canonical(
        "meeting",
        {"name": "Pricing sync", "transcript": "Lucius: pricing is fine."},
    )
    await search.index(session)
    for row in await chunk_rows(session):
        if row.canonical_id != k2:
            row.embedding = fake_vector(row.text)
            row.model = settings.EMBEDDING_MODEL
            row.embedded_at = SEEN
    await session.flush()
    return {"company": company, "k1": k1, "k2": k2, "k3": k3}


@pytest_asyncio.fixture
async def pending(session, canonical, meaning_on):
    meetings = [
        await canonical("meeting", {"transcript": f"Speaker: line {n} about pricing."})
        for n in range(5)
    ]
    await search.index(session)
    return meetings


class TestKindsAndParsing:
    def test_kinds_cover_entity_types_briefings_raw_and_definitions(self):
        expected = (
            set(ontology.load().entities)
            | set(NON_ENTITY_KINDS)
            | set(DEFINITION_KINDS)
        )
        assert search.kinds() == sorted(expected)

    def test_the_constants_are_the_agreed_ones(self):
        assert DEFINITION_KINDS == (
            "metric",
            "rule",
            "goal",
            "source",
            "entity_type",
            "reading",
        )
        assert NON_ENTITY_KINDS == ("briefing", "raw")
        assert tuple(Mode) == ("words", "meaning", "both")
        assert tuple(Weight) == ("A", "B", "D")
        assert issubclass(search.SearchError, RuntimeError)

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("person:wayne", ("wayne", "person")),
            ("briefing: churn", ("churn", "briefing")),
            ("metric:mrr", ("mrr", "metric")),
            ("foo:bar", ("foo:bar", None)),
            ("  wayne  ", ("wayne", None)),
            ("https://acme.io", ("https://acme.io", None)),
        ],
    )
    def test_a_known_prefix_sets_the_kind(self, raw, expected):
        assert search.parse_query(raw) == expected


class TestChunks:
    def test_empty_text_is_no_chunks(self):
        assert search.chunks("") == []

    def test_one_short_line_is_one_chunk(self):
        assert search.chunks("Bruce: hello", max_chars=100) == ["Bruce: hello"]

    def test_lines_pack_greedily_and_consecutive_chunks_share_a_line(self):
        lines = [f"Speaker{i}: line number {i}" for i in range(4)]
        out = search.chunks("\n".join(lines), max_chars=47)
        assert out == [
            f"{lines[0]}\n{lines[1]}",
            f"{lines[1]}\n{lines[2]}",
            f"{lines[2]}\n{lines[3]}",
        ]
        assert all(len(chunk) <= 47 for chunk in out)

    def test_the_default_width_is_the_setting(self, monkeypatch):
        monkeypatch.setattr(settings, "SEARCH_CHUNK_CHARS", 47)
        lines = [f"Speaker{i}: line number {i}" for i in range(3)]
        assert len(search.chunks("\n".join(lines))) == 2

    def test_an_overlong_line_is_split_on_sentence_ends(self):
        line = "Bruce: A one. B two? C three! D four."
        out = search.chunks(line, max_chars=20)
        assert len(out) >= 2
        assert all(len(chunk) <= 20 for chunk in out)
        for sentence in ("A one.", "B two?", "C three!", "D four."):
            assert any(sentence in chunk for chunk in out)

    def test_blank_lines_never_become_chunks(self):
        out = search.chunks("Bruce: hi\n\nJane: yo\n", max_chars=100)
        assert out and all(chunk.strip() for chunk in out)


class TestRawText:
    def test_string_values_are_joined_recursively_without_keys(self):
        payload = {
            "id": "con_001",
            "name": "Bruce",
            "props": {"title": "CEO", "n": 3, "tags": ["a", {"x": "b"}]},
            "flag": True,
            "none": None,
        }
        assert search.document_text_for_raw(payload) == "con_001 · Bruce · CEO · a · b"

    def test_a_payload_without_strings_is_empty(self):
        assert search.document_text_for_raw({"n": 1, "ok": False}) == ""


class TestIndexEntities:
    async def test_every_member_fact_is_a_row(self, session, canonical):
        bruce = await canonical(
            "person",
            {"name": "Bruce Wayne"},
            sources=["hubspot", "zendesk"],
            member_facts={"zendesk": {"name": "Batman"}},
        )
        counts = await search.index(session)
        rows = await documents(session, kind="person", attr="name")
        assert {r.text for r in rows} == {"Bruce Wayne", "Batman"}
        assert {(r.ref_id, r.label, r.weight) for r in rows} == {
            (str(bruce), "Bruce Wayne", Weight.STRONG)
        }
        assert counts == {"documents": 3, "chunks": 0}

    async def test_members_agreeing_on_a_value_share_one_row(self, session, canonical):
        await canonical("company", {"name": "Acme"}, sources=["hubspot", "stripe"])
        await search.index(session)
        assert len(await documents(session, attr="name")) == 1

    async def test_null_values_are_skipped(self, session, canonical):
        await canonical(
            "person", {"name": "Bruce"}, member_facts={"hubspot": {"phone": None}}
        )
        await search.index(session)
        assert {r.attr for r in await documents(session)} == {"name", Attr.ANCHOR}

    async def test_date_and_number_attrs_are_left_out(self, session, canonical):
        await canonical(
            "deal",
            {
                "name": "Big deal",
                "amount": "100",
                "closed_at": "2026-01-01T00:00:00Z",
                "status": "open",
            },
        )
        await search.index(session)
        assert {r.attr for r in await documents(session)} == {
            "name",
            "status",
            Attr.ANCHOR,
        }

    async def test_weights_follow_the_attr(self, session, canonical):
        await canonical(
            "person",
            {
                "name": "Bruce",
                "email": "b@w.com",
                "title": "CEO",
                "external_ref": "x1",
                "phone": "+1555",
            },
        )
        await canonical("ticket", {"subject": "Help", "priority": "high"})
        await canonical("meeting", {"transcript": "Bruce: hi", "status": "held"})
        await search.index(session)
        weights = {(r.kind, r.attr): r.weight for r in await documents(session)}
        assert weights == {
            ("person", "name"): Weight.STRONG,
            ("person", "email"): Weight.STRONG,
            ("person", "title"): Weight.STRONG,
            ("person", "external_ref"): Weight.STRONG,
            ("person", "phone"): Weight.NORMAL,
            ("person", Attr.ANCHOR): Weight.STRONG,
            ("ticket", "subject"): Weight.STRONG,
            ("ticket", "priority"): Weight.NORMAL,
            ("ticket", Attr.ANCHOR): Weight.STRONG,
            ("meeting", Attr.TRANSCRIPT): Weight.LONG,
            ("meeting", "status"): Weight.NORMAL,
            ("meeting", Attr.ANCHOR): Weight.STRONG,
        }

    async def test_an_email_carries_its_derived_forms(self, session, canonical):
        await canonical("person", {"email": "hello@acme.io"})
        await search.index(session)
        (row,) = await documents(session, attr="email")
        assert row.value == "hello@acme.io"
        assert row.text == "hello@acme.io hello acme.io acme"

    async def test_a_domain_carries_its_form_without_tld(self, session, canonical):
        await canonical("company", {"domain": "acme.io"})
        await search.index(session)
        (row,) = await documents(session, attr="domain")
        assert row.value == "acme.io"
        assert row.text == "acme.io acme"

    async def test_the_anchor_row_spells_the_key_out(self, session, canonical):
        acme = await canonical("company", {"name": "Acme"})
        await search.index(session)
        (row,) = await documents(session, attr=Attr.ANCHOR)
        assert (row.kind, row.ref_id, row.weight) == (
            "company",
            str(acme),
            Weight.STRONG,
        )
        assert row.value == "test|company|1"
        assert row.text == "test company 1 1"

    async def test_the_label_is_the_first_labeling_fact(self, session, canonical):
        await canonical("company", {"domain": "acme.io", "name": "Acme"})
        await canonical("subscription", {"status": "active"})
        await search.index(session)
        labels = {r.kind: r.label for r in await documents(session)}
        assert labels == {"company": "Acme", "subscription": "test|subscription|2"}

    async def test_a_meeting_is_dated_by_its_date_fact(self, session, canonical):
        await canonical(
            "meeting", {"name": "Kickoff", "started_at": "2026-09-01T10:00:00Z"}
        )
        await canonical("meeting", {"name": "Undated"})
        await canonical("company", {"name": "Acme"})
        await search.index(session)
        stamped = {
            r.label: r.happened_at for r in await documents(session, attr="name")
        }
        assert stamped == {
            "Kickoff": datetime(2026, 9, 1, 10, tzinfo=UTC),
            "Undated": None,
            "Acme": None,
        }

    async def test_enriched_facts_become_a_reading_row_and_a_quote_row(
        self, session, canonical
    ):
        meeting = await canonical("meeting", {"name": "Kickoff"})
        session.add(enriched_row(meeting))
        session.add(
            enriched_row(meeting, attr="pain_points", value="pricing", quote="")
        )
        await session.flush()
        await search.index(session)
        rows = [
            r
            for r in await documents(session, kind="meeting")
            if r.attr.startswith((READING_PREFIX, QUOTE_PREFIX))
        ]
        assert sorted((r.attr, r.weight, r.text) for r in rows) == [
            (f"{QUOTE_PREFIX}sales_call", Weight.LONG, "budget is set"),
            (f"{READING_PREFIX}sales_call", Weight.NORMAL, "interest=strong"),
            (f"{READING_PREFIX}sales_call", Weight.NORMAL, "pain_points=pricing"),
        ]
        assert all(r.value == r.text for r in rows)

    async def test_a_second_full_index_replaces_the_first(self, session, canonical):
        await canonical("company", {"name": "Acme"})
        first = await search.index(session)
        second = await search.index(session)
        assert first == second
        assert len(await documents(session)) == first["documents"]


class TestIndexBriefingsAndRaw:
    async def test_only_successful_briefings_with_text_are_rows(self, session):
        good = briefing_row(
            role="head_of_sales",
            text="Wayne is churning.",
            created_at=datetime(2026, 9, 4, 12, tzinfo=UTC),
        )
        session.add(good)
        await session.flush()
        session.add(briefing_row(ok=False))
        session.add(briefing_row(text=None))
        await session.flush()
        await search.index(session)
        (row,) = await documents(session, kind=Kind.BRIEFING)
        assert row.ref_id == f"head_of_sales/{good.seq}"
        assert row.label == "Head of sales · 4 Sep 2026"
        assert (row.attr, row.weight, row.value, row.text) == (
            Attr.BRIEFING,
            Weight.LONG,
            "Wayne is churning.",
            "Wayne is churning.",
        )
        assert row.happened_at == good.created_at

    async def test_only_the_latest_version_of_a_raw_event_is_a_row(self, session):
        older = raw_row(payload={"name": "old"})
        session.add(older)
        await session.flush()
        newer = raw_row(payload={"name": "new", "meta": {"note": "fresh"}})
        session.add(newer)
        other = raw_row(source="stripe", object_type="customers", payload={"n": "x"})
        session.add(other)
        await session.flush()
        await search.index(session)
        rows = await documents(session, kind=Kind.RAW)
        assert {(r.ref_id, r.text) for r in rows} == {
            (str(newer.id), "new · fresh"),
            (str(other.id), "x"),
        }
        (row,) = [r for r in rows if r.ref_id == str(newer.id)]
        assert row.value == "new · fresh"
        assert row.label == "hubspot · contacts · con_001"
        assert (row.attr, row.weight) == (Attr.PAYLOAD, Weight.LONG)
        assert row.happened_at is None


class TestIndexChunks:
    @pytest.fixture(autouse=True)
    def narrow(self, monkeypatch):
        monkeypatch.setattr(settings, "SEARCH_CHUNK_CHARS", 47)

    LINES = [f"Speaker{i}: line number {i}" for i in range(4)]

    async def test_a_transcript_is_chunked_and_hashed(self, session, canonical):
        meeting = await canonical("meeting", {"transcript": "\n".join(self.LINES)})
        counts = await search.index(session)
        rows = await chunk_rows(session, meeting)
        assert counts["chunks"] == 3
        assert [r.chunk_index for r in rows] == [0, 1, 2]
        assert [r.text for r in rows] == search.chunks("\n".join(self.LINES))
        for row in rows:
            assert row.attr == Attr.TRANSCRIPT
            assert row.sha == hashlib.sha256(row.text.encode()).hexdigest()
            assert (row.model, row.embedding, row.embedded_at) == (None, None, None)

    async def test_an_unchanged_chunk_keeps_its_embedding(self, session, canonical):
        meeting = await canonical("meeting", {"transcript": "\n".join(self.LINES)})
        await search.index(session)
        first = await chunk_rows(session, meeting)
        first[0].embedding = fake_vector("pricing")
        first[0].model = "m"
        first[0].embedded_at = SEEN
        await session.flush()
        await search.index(session)
        again = await chunk_rows(session, meeting)
        assert again[0].model == "m"
        assert again[0].embedding is not None
        assert again[0].embedded_at == SEEN

    async def test_a_changed_chunk_loses_its_embedding(self, session, canonical):
        meeting = await canonical("meeting", {"transcript": "\n".join(self.LINES)})
        await search.index(session)
        for row in await chunk_rows(session, meeting):
            row.embedding = fake_vector("pricing")
            row.model = "m"
            row.embedded_at = SEEN
        await session.flush()
        changed = ["Speaker0: pricing comes"] + self.LINES[1:]
        await set_transcript(session, meeting, "\n".join(changed))
        await search.index(session)
        rows = await chunk_rows(session, meeting)
        assert rows[0].text == search.chunks("\n".join(changed))[0]
        assert rows[0].sha == hashlib.sha256(rows[0].text.encode()).hexdigest()
        assert (rows[0].model, rows[0].embedding, rows[0].embedded_at) == (
            None,
            None,
            None,
        )
        assert rows[2].model == "m"

    async def test_chunks_beyond_the_new_count_are_deleted(self, session, canonical):
        meeting = await canonical("meeting", {"transcript": "\n".join(self.LINES)})
        await search.index(session)
        await set_transcript(session, meeting, self.LINES[0])
        await search.index(session)
        rows = await chunk_rows(session, meeting)
        assert [(r.chunk_index, r.text) for r in rows] == [(0, self.LINES[0])]

    async def test_chunks_of_a_vanished_entity_are_deleted(self, session, canonical):
        meeting = await canonical("meeting", {"transcript": "\n".join(self.LINES)})
        kept = await canonical("meeting", {"transcript": "Alfred: still here"})
        await search.index(session)
        await drop_canonical(session, meeting)
        await search.index(session)
        assert {r.canonical_id for r in await chunk_rows(session)} == {kept}


class TestIndexPartial:
    async def test_only_the_named_entity_is_rewritten(self, session, canonical):
        acme = await canonical("company", {"name": "Acme"})
        globex = await canonical("company", {"name": "Globex"})
        await search.index(session)
        session.add(
            EntityFact(
                id=uuid.uuid5(uuid.NAMESPACE_URL, "acme-industry"),
                entity_id=uuid.uuid5(uuid.NAMESPACE_URL, "test|company|1|hubspot"),
                attr="industry",
                value="defense",
                observed_at=SEEN,
            )
        )
        session.add(
            EntityFact(
                id=uuid.uuid5(uuid.NAMESPACE_URL, "globex-industry"),
                entity_id=uuid.uuid5(uuid.NAMESPACE_URL, "test|company|2|hubspot"),
                attr="industry",
                value="energy",
                observed_at=SEEN,
            )
        )
        session.add(briefing_row())
        await session.flush()
        counts = await search.index(session, canonical_ids=[acme])
        assert counts == {"documents": 3, "chunks": 0}
        assert [r.text for r in await documents(session, attr="industry")] == [
            "defense"
        ]
        assert len(await documents(session, ref_id=str(globex))) == 2
        assert await documents(session, kind=Kind.BRIEFING) == []

    async def test_only_the_named_briefing_is_added(self, session, canonical):
        acme = await canonical("company", {"name": "Acme"})
        await search.index(session)
        first = briefing_row(text="first")
        session.add(first)
        await session.flush()
        second = briefing_row(text="second")
        session.add(second)
        await session.flush()
        counts = await search.index(session, briefing_seqs=[second.seq])
        assert counts == {"documents": 1, "chunks": 0}
        assert [r.text for r in await documents(session, kind=Kind.BRIEFING)] == [
            "second"
        ]
        assert len(await documents(session, ref_id=str(acme))) == 2

    async def test_a_named_entity_that_vanished_loses_its_rows(
        self, session, canonical
    ):
        acme = await canonical("company", {"name": "Acme"})
        await search.index(session)
        await drop_canonical(session, acme)
        counts = await search.index(session, canonical_ids=[acme])
        assert counts == {"documents": 0, "chunks": 0}
        assert await documents(session, ref_id=str(acme)) == []

    async def test_partial_chunks_follow_the_named_entity(
        self, session, canonical, monkeypatch
    ):
        monkeypatch.setattr(settings, "SEARCH_CHUNK_CHARS", 47)
        meeting = await canonical("meeting", {"transcript": "Alfred: one line"})
        await search.index(session)
        lines = [f"Speaker{i}: line number {i}" for i in range(4)]
        await set_transcript(session, meeting, "\n".join(lines))
        counts = await search.index(session, canonical_ids=[meeting])
        assert counts["chunks"] == 3
        assert len(await chunk_rows(session, meeting)) == 3


class TestEmbed:
    async def test_the_layer_refuses_while_it_is_off(self, session, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDINGS_ENABLED", False)
        with pytest.raises(search.SearchError, match="EMBEDDINGS_ENABLED"):
            await search.embed(session)

    async def test_a_second_concurrent_run_is_refused(
        self, session, pending, embedder, sessionmaker_for_test
    ):
        embedder()
        async with sessionmaker_for_test() as holder:
            await holder.execute(
                select(func.pg_try_advisory_xact_lock(search._EMBED_LOCK_ID))
            )
            with pytest.raises(search.SearchError, match="already in progress"):
                await search.embed(session)

    async def test_chunks_are_sent_in_batches_in_a_fixed_order(
        self, session, pending, embedder, monkeypatch
    ):
        monkeypatch.setattr(settings, "EMBEDDING_BATCH", 2)
        fake = embedder()
        result = await search.embed(session)
        assert [len(call) for call in fake.calls] == [2, 2, 1]
        assert [t for call in fake.calls for t in call] == [
            r.text for r in await chunk_rows(session)
        ]
        assert set(result) == EMBED_KEYS
        assert result["model"] == settings.EMBEDDING_MODEL
        assert (result["embedded"], result["skipped"], result["failed"]) == (5, 0, 0)
        assert result["truncated_at_cap"] is False
        assert result["error"] is None
        assert result["duration_ms"] >= 0

    async def test_a_success_writes_vectors_and_a_receipt(
        self, session, pending, embedder
    ):
        embedder()
        await search.embed(session)
        for row in await chunk_rows(session):
            assert len(row.embedding) == DIMS
            assert row.model == settings.EMBEDDING_MODEL
            assert row.embedded_at is not None
        (receipt,) = await embedding_runs(session)
        assert receipt.ok is True
        assert (receipt.embedded, receipt.skipped, receipt.failed) == (5, 0, 0)
        assert receipt.model == settings.EMBEDDING_MODEL
        assert receipt.error is None
        assert receipt.truncated_at_cap is False
        assert receipt.duration_ms >= 0
        assert receipt.created_at is not None

    async def test_a_failed_batch_is_counted_and_the_run_goes_on(
        self, session, pending, embedder, monkeypatch
    ):
        monkeypatch.setattr(settings, "EMBEDDING_BATCH", 2)
        fake = embedder(fail_batches=[1])
        result = await search.embed(session)
        assert len(fake.calls) == 3
        assert (result["embedded"], result["failed"]) == (3, 2)
        assert result["error"] == "batch 1 down"
        rows = await chunk_rows(session)
        assert [r.embedding is None for r in rows] == [
            False,
            False,
            True,
            True,
            False,
        ]
        (receipt,) = await embedding_runs(session)
        assert receipt.ok is False
        assert (receipt.embedded, receipt.failed) == (3, 2)
        assert receipt.error == "batch 1 down"

    async def test_the_first_error_is_the_one_recorded(
        self, session, pending, embedder, monkeypatch
    ):
        monkeypatch.setattr(settings, "EMBEDDING_BATCH", 2)
        embedder(fail_batches=[0, 2])
        result = await search.embed(session)
        assert result["error"] == "batch 0 down"
        assert (result["embedded"], result["failed"]) == (2, 3)

    async def test_the_call_cap_truncates_the_run(
        self, session, pending, embedder, monkeypatch
    ):
        monkeypatch.setattr(settings, "EMBEDDING_BATCH", 2)
        monkeypatch.setattr(settings, "EMBEDDINGS_MAX_CALLS_PER_RUN", 1)
        fake = embedder()
        result = await search.embed(session)
        assert len(fake.calls) == 1
        assert result["embedded"] == 2
        assert result["truncated_at_cap"] is True
        (receipt,) = await embedding_runs(session)
        assert receipt.truncated_at_cap is True

    async def test_an_explicit_limit_counts_batches(
        self, session, pending, embedder, monkeypatch
    ):
        monkeypatch.setattr(settings, "EMBEDDING_BATCH", 2)
        fake = embedder()
        result = await search.embed(session, limit=2)
        assert len(fake.calls) == 2
        assert result["embedded"] == 4
        assert result["truncated_at_cap"] is True

    async def test_current_vectors_are_skipped_and_stale_models_redone(
        self, session, pending, embedder
    ):
        rows = await chunk_rows(session)
        rows[0].embedding = fake_vector(rows[0].text)
        rows[0].model = settings.EMBEDDING_MODEL
        rows[0].embedded_at = SEEN
        rows[1].embedding = fake_vector(rows[1].text)
        rows[1].model = "retired-model"
        rows[1].embedded_at = SEEN
        await session.flush()
        fake = embedder()
        result = await search.embed(session)
        assert [t for call in fake.calls for t in call] == [r.text for r in rows[1:]]
        assert (result["embedded"], result["skipped"]) == (4, 1)

    async def test_nothing_pending_is_a_receipt_with_zero_work(
        self, session, pending, embedder
    ):
        fake = embedder()
        await search.embed(session)
        again = await search.embed(session)
        assert len(fake.calls) == 1
        assert (again["embedded"], again["skipped"], again["failed"]) == (0, 5, 0)
        assert len(await embedding_runs(session)) == 2


class TestQueryWords:
    async def test_a_query_under_two_characters_is_empty_without_a_query(
        self, session, count_queries
    ):
        with count_queries() as counter:
            result = await search.query(session, "w")
        assert counter.total == 0
        assert result == {
            "q": "w",
            "kind": None,
            "mode": Mode.WORDS,
            "meaning_enabled": False,
            "rerank_enabled": False,
            "reranked": False,
            "total": 0,
            "limit": 10,
            "offset": 0,
            "by_kind": {},
            "results": [],
        }

    async def test_a_prefix_leaving_a_short_query_keeps_the_kind(self, session):
        result = await search.query(session, "person:w")
        assert (result["q"], result["kind"], result["total"]) == ("w", "person", 0)

    @pytest.mark.parametrize(
        "junk", [".", "-", "@@", "+", "a.b.", "x-", "'", "wayne'", "!! ??", "&|:*"]
    )
    async def test_junk_never_raises(self, session, estate, junk):
        result = await search.query(session, junk)
        assert set(result) == RESPONSE_KEYS

    async def test_no_tokens_is_an_empty_result(self, session, estate):
        result = await search.query(session, "!! ??")
        assert (result["total"], result["results"], result["by_kind"]) == (0, [], {})

    async def test_the_last_token_matches_as_a_prefix(self, session, estate):
        result = await search.query(session, "wayne enterpr")
        assert ids(result) == [str(estate["wayne"])]
        assert result["results"][0] == {
            "kind": "company",
            "id": str(estate["wayne"]),
            "label": "Wayne Enterprises",
            "evidence": "name=Wayne Enterprises",
        }

    async def test_every_token_must_match(self, session, estate):
        result = await search.query(session, "wayne gotham")
        assert ids(result) == [str(estate["raw"].id)]

    async def test_a_name_outranks_a_transcript(self, session, estate):
        found = ids(await search.query(session, "wayne"))
        assert found.index(str(estate["wayne"])) < found.index(str(estate["kickoff"]))

    async def test_a_merged_member_is_found_by_its_other_name(self, session, estate):
        result = await search.query(session, "batman")
        assert ids(result) == [str(estate["bruce"])]
        assert result["results"][0]["label"] == "Bruce Wayne"
        assert result["results"][0]["evidence"] == "name=Batman"

    async def test_an_email_hit_shows_the_address_not_its_derived_words(
        self, session, estate
    ):
        result = await search.query(session, "bruce@wayne.com")
        (hit,) = of_kind(result, "person")
        assert hit["id"] == str(estate["bruce"])
        assert hit["evidence"] == "email=bruce@wayne.com"

    async def test_a_short_fact_is_its_own_evidence(self, session, estate):
        result = await search.query(session, "past_due")
        (hit,) = of_kind(result, "subscription")
        assert hit["id"] == str(estate["sub"])
        assert hit["evidence"] == "status=past_due"

    async def test_an_anchor_hit_shows_the_key(self, session, estate):
        result = await search.query(session, "test subscription")
        (hit,) = of_kind(result, "subscription")
        assert hit["label"] == "test|subscription|4"
        assert hit["evidence"] == "anchor=test|subscription|4"

    async def test_a_reading_hit_shows_the_stored_pair(self, session, estate):
        session.add(enriched_row(estate["kickoff"], quote="budget is approved"))
        await session.flush()
        await search.index(session, canonical_ids=[estate["kickoff"]])
        result = await search.query(session, "strong")
        (hit,) = of_kind(result, "meeting")
        assert hit["evidence"] == "interest=strong"
        quoted = await search.query(session, "approved")
        (hit,) = of_kind(quoted, "meeting")
        assert f"{MARK_OPEN}approved{MARK_CLOSE}" in hit["evidence"]

    async def test_a_transcript_hit_is_marked_in_context(self, session, estate):
        result = await search.query(session, "reporting")
        (hit,) = of_kind(result, "meeting")
        assert hit["id"] == str(estate["kickoff"])
        assert hit["label"] == "Q3 kickoff"
        assert f"{MARK_OPEN}reporting{MARK_CLOSE}" in hit["evidence"]

    async def test_a_raw_payload_hit_is_marked_in_context(self, session, estate):
        result = await search.query(session, "gotham")
        assert result["by_kind"] == {Kind.RAW: 1}
        (hit,) = result["results"]
        assert hit["id"] == str(estate["raw"].id)
        assert hit["label"] == "hubspot · contacts · con_001"
        assert f"{MARK_OPEN}Gotham{MARK_CLOSE}" in hit["evidence"]

    async def test_a_briefing_hit_carries_its_role_and_seq(self, session, estate):
        result = await search.query(session, "churn", kind=Kind.BRIEFING)
        assert [h["id"] for h in result["results"]] == [
            f"ceo/{estate['newer'].seq}",
            f"ceo/{estate['older'].seq}",
        ]
        assert result["results"][0]["label"] == "Ceo · 1 Aug 2026"
        assert f"{MARK_OPEN}Churn{MARK_CLOSE}" in result["results"][0]["evidence"]

    async def test_the_newer_of_two_equal_briefings_comes_first(self, session, estate):
        found = [
            h["id"]
            for h in of_kind(await search.query(session, "churn"), Kind.BRIEFING)
        ]
        assert found == [f"ceo/{estate['newer'].seq}", f"ceo/{estate['older'].seq}"]

    async def test_the_kind_filter_narrows_results_but_not_the_counts(
        self, session, estate
    ):
        result = await search.query(session, "wayne", kind="company")
        assert result["kind"] == "company"
        assert result["total"] == 1
        assert {h["kind"] for h in result["results"]} == {"company"}
        assert result["by_kind"]["company"] == 1
        assert result["by_kind"]["person"] == 1
        assert result["by_kind"]["meeting"] == 1

    async def test_the_prefix_is_parsed_and_an_explicit_kind_wins(
        self, session, estate
    ):
        parsed = await search.query(session, "company:wayne")
        assert (parsed["q"], parsed["kind"]) == ("wayne", "company")
        assert {h["kind"] for h in parsed["results"]} == {"company"}
        explicit = await search.query(session, "person:wayne", kind="company")
        assert explicit["kind"] == "company"

    async def test_an_unknown_kind_is_refused(self, session, estate):
        with pytest.raises(search.SearchError, match=UNKNOWN_KIND):
            await search.query(session, "wayne", kind="nope")

    async def test_an_unknown_mode_is_refused(self, session, estate):
        with pytest.raises(search.SearchError):
            await search.query(session, "wayne", mode="nope")

    async def test_paging_walks_the_same_list(self, session, estate):
        full = await search.query(session, "wayne")
        assert full["total"] >= 3
        page = await search.query(session, "wayne", limit=1, offset=1)
        assert (page["limit"], page["offset"], page["total"]) == (1, 1, full["total"])
        assert page["results"] == [full["results"][1]]
        assert page["by_kind"] == full["by_kind"]
        beyond = await search.query(session, "wayne", limit=5, offset=50)
        assert beyond["results"] == [] and beyond["total"] == full["total"]

    async def test_a_typo_falls_back_to_similar_names(self, session, estate):
        result = await search.query(session, "carlso")
        assert result["by_kind"] == {"person": 1}
        assert result["results"] == [
            {
                "kind": "person",
                "id": str(estate["carlos"]),
                "label": "Carlos",
                "evidence": "name=Carlos",
            }
        ]

    async def test_nothing_similar_is_simply_empty(self, session, estate):
        result = await search.query(session, "zzzzqqqq")
        assert (result["total"], result["results"]) == (0, [])


class TestQueryDefinitions:
    async def test_a_metric_is_found_by_name(self, session):
        (hit,) = [
            h
            for h in of_kind(await search.query(session, "mrr"), "metric")
            if h["id"] == "mrr"
        ]
        assert hit == {
            "kind": "metric",
            "id": "mrr",
            "label": "MRR",
            "evidence": "label=MRR",
        }

    async def test_a_metric_is_found_by_a_business_synonym(self, session):
        await search.index(session)
        found = of_kind(await search.query(session, "revenue"), "metric")
        assert "mrr" in [hit["id"] for hit in found]

    async def test_an_entity_type_is_found_by_a_business_synonym(self, session):
        await search.index(session)
        found = of_kind(await search.query(session, "clients"), "entity_type")
        assert [hit["id"] for hit in found] == ["company"]

    async def test_a_plural_query_finds_the_singular_definition(self, session):
        singular = of_kind(await search.query(session, "ticket"), "entity_type")
        plural = of_kind(await search.query(session, "tickets"), "entity_type")
        assert [h["id"] for h in singular] == [h["id"] for h in plural] == ["ticket"]

    async def test_a_plural_of_nothing_still_matches_nothing(self, session):
        assert of_kind(await search.query(session, "unicorns"), "entity_type") == []

    async def test_every_token_must_be_in_the_text(self, session):
        result = await search.query(session, "average mrr")
        assert [h["id"] for h in of_kind(result, "metric")] == ["avg_mrr"]

    async def test_a_rule_is_found_by_name(self, session):
        (hit,) = of_kind(await search.query(session, "subscription_past_due"), "rule")
        assert hit == {
            "kind": "rule",
            "id": "subscription_past_due",
            "label": "Subscription Past Due",
            "evidence": "label=Subscription Past Due",
        }

    async def test_a_goal_is_found_by_name(self, session):
        (hit,) = of_kind(await search.query(session, "grow_mrr"), "goal")
        assert hit == {
            "kind": "goal",
            "id": "grow_mrr",
            "label": "grow_mrr",
            "evidence": "metric=mrr",
        }

    async def test_a_source_is_found_by_name(self, session):
        (hit,) = of_kind(await search.query(session, "hubspot"), "source")
        assert hit == {
            "kind": "source",
            "id": "hubspot",
            "label": "hubspot",
            "evidence": "source=hubspot",
        }

    async def test_an_entity_type_lists_its_attrs(self, session):
        (hit,) = of_kind(await search.query(session, "ticket"), "entity_type")
        assert (hit["id"], hit["label"]) == ("ticket", "ticket")
        assert hit["evidence"].startswith("attrs=")
        assert "subject" in hit["evidence"] and "opened_at" in hit["evidence"]

    async def test_a_reading_lists_its_values(self, session):
        (hit,) = of_kind(await search.query(session, "sales_call"), "reading")
        assert (hit["id"], hit["label"]) == ("sales_call", "sales_call")
        assert hit["evidence"].startswith("values=")
        assert "strong" in hit["evidence"] and "pricing" in hit["evidence"]

    async def test_a_reading_is_found_by_the_attr_it_reads(self, session):
        found = of_kind(await search.query(session, "transcript"), "reading")
        assert "sales_call" in [h["id"] for h in found]

    async def test_the_kind_filter_applies_to_definitions_too(self, session):
        result = await search.query(session, "mrr", kind="metric")
        assert {h["kind"] for h in result["results"]} == {"metric"}
        assert result["by_kind"]["goal"] >= 1
        assert result["total"] == result["by_kind"]["metric"]


class TestQueryMeaning:
    async def test_meaning_while_embeddings_are_off_is_refused(self, session, estate):
        with pytest.raises(search.SearchError, match="EMBEDDINGS_ENABLED"):
            await search.query(session, "pricing", mode=Mode.MEANING)

    async def test_both_while_embeddings_are_off_is_refused(self, session, estate):
        with pytest.raises(search.SearchError, match="EMBEDDINGS_ENABLED"):
            await search.query(session, "pricing", mode=Mode.BOTH)

    async def test_the_closest_embedded_chunk_wins(self, session, vectors, embedder):
        fake = embedder()
        result = await search.query(session, "pricing", mode=Mode.MEANING)
        assert fake.calls == [["pricing"]]
        assert (result["mode"], result["meaning_enabled"]) == (Mode.MEANING, True)
        assert result["reranked"] is False
        assert ids(result) == [str(vectors["k3"]), str(vectors["k1"])]
        assert result["results"][0] == {
            "kind": "meeting",
            "id": str(vectors["k3"]),
            "label": "Pricing sync",
            "evidence": "Lucius: pricing is fine.",
        }
        assert result["results"][1]["evidence"] == (
            "Otis: reporting too.\nLex: pricing is fine."
        )
        assert result["by_kind"] == {"meeting": 2}
        assert result["total"] == 2

    async def test_an_entity_appears_once_with_its_best_chunk(
        self, session, vectors, embedder
    ):
        embedder()
        result = await search.query(session, "kryptonite", mode=Mode.MEANING)
        assert ids(result) == [str(vectors["k1"]), str(vectors["k3"])]
        assert result["results"][0]["evidence"] == (
            "Lex: kryptonite is late.\nOtis: reporting too."
        )

    async def test_unembedded_chunks_and_definitions_are_absent(
        self, session, vectors, embedder
    ):
        embedder()
        result = await search.query(session, "mrr reporting", mode=Mode.MEANING)
        assert str(vectors["k2"]) not in ids(result)
        assert "metric" not in result["by_kind"]

    async def test_the_kind_filter_and_paging_apply(self, session, vectors, embedder):
        embedder()
        result = await search.query(
            session, "pricing", mode=Mode.MEANING, kind="meeting", limit=1, offset=1
        )
        assert ids(result) == [str(vectors["k1"])]
        assert result["total"] == 2

    async def test_a_model_failure_propagates(self, session, vectors, monkeypatch):
        async def down(texts, **kwargs):
            raise llm.LLMError("down")

        monkeypatch.setattr("app.llm.embeddings.embed", down)
        with pytest.raises(llm.LLMError, match="down"):
            await search.query(session, "pricing", mode=Mode.MEANING)


class TestQueryBoth:
    async def test_fusion_orders_by_reciprocal_rank(self, session, vectors, embedder):
        embedder()
        result = await search.query(session, "kryptonite", mode=Mode.BOTH)
        assert result["mode"] == Mode.BOTH
        assert ids(result) == [
            str(vectors["k1"]),
            str(vectors["company"]),
            str(vectors["k3"]),
        ]
        assert result["by_kind"] == {"meeting": 2, "company": 1}
        assert (result["rerank_enabled"], result["reranked"]) == (False, False)

    async def test_a_rerank_reorders_the_fused_list(
        self, session, vectors, embedder, reranker, monkeypatch
    ):
        embedder()
        fused = await search.query(session, "kryptonite", mode=Mode.BOTH)
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        fake = reranker(
            {"Pricing sync": 0.9, "Kryptonite Ltd": 0.5, "Shipment sync": 0.1}
        )
        result = await search.query(session, "kryptonite", mode=Mode.BOTH)
        assert fake.calls == [
            (
                "kryptonite",
                [f"{h['label']} — {h['evidence']}" for h in fused["results"]],
            )
        ]
        assert (result["rerank_enabled"], result["reranked"]) == (True, True)
        assert ids(result) == [
            str(vectors["k3"]),
            str(vectors["company"]),
            str(vectors["k1"]),
        ]

    async def test_only_the_top_n_are_reranked(
        self, session, vectors, embedder, reranker, monkeypatch
    ):
        embedder()
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        monkeypatch.setattr(settings, "RERANK_TOP", 2)
        fake = reranker({"Kryptonite Ltd": 0.9, "Shipment sync": 0.1})
        result = await search.query(session, "kryptonite", mode=Mode.BOTH)
        assert len(fake.calls[0][1]) == 2
        assert ids(result) == [
            str(vectors["company"]),
            str(vectors["k1"]),
            str(vectors["k3"]),
        ]

    async def test_a_rerank_failure_keeps_the_fusion_order(
        self, session, vectors, embedder, reranker, monkeypatch
    ):
        embedder()
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        reranker(raises=llm.LLMError("rerank down"))
        result = await search.query(session, "kryptonite", mode=Mode.BOTH)
        assert (result["rerank_enabled"], result["reranked"]) == (True, False)
        assert ids(result) == [
            str(vectors["k1"]),
            str(vectors["company"]),
            str(vectors["k3"]),
        ]

    async def test_words_mode_never_reranks(
        self, session, vectors, reranker, monkeypatch
    ):
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        fake = reranker({"Kryptonite Ltd": 0.9})
        result = await search.query(session, "kryptonite")
        assert (result["rerank_enabled"], result["reranked"]) == (True, False)
        assert fake.calls == []


class TestSearchApi:
    async def test_a_hit_comes_back_in_the_documented_shape(self, api, session, estate):
        await session.commit()
        response = await api.get("/api/search", params={"q": "wayne enterpr"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == RESPONSE_KEYS
        assert body["results"] == [
            {
                "kind": "company",
                "id": str(estate["wayne"]),
                "label": "Wayne Enterprises",
                "evidence": "name=Wayne Enterprises",
            }
        ]
        assert (body["total"], body["limit"], body["offset"]) == (1, 10, 0)
        assert body["meaning_enabled"] is False

    @pytest.mark.parametrize(
        "params",
        [
            {"q": "wayne", "kind": "nope"},
            {"q": "wayne", "mode": "nope"},
            {"q": ""},
            {"q": "x" * 201},
            {},
            {"q": "wayne", "limit": 0},
            {"q": "wayne", "limit": 501},
            {"q": "wayne", "offset": -1},
            {"q": "wayne", "offset": 2**63},
        ],
    )
    async def test_bad_input_is_a_422(self, api, params):
        assert (await api.get("/api/search", params=params)).status_code == 422

    async def test_the_largest_legal_offset_is_an_empty_page(self, api):
        response = await api.get(
            "/api/search", params={"q": "wayne", "offset": 2**63 - 1}
        )
        assert response.status_code == 200
        assert response.json()["results"] == []

    async def test_the_kind_prefix_is_parsed_server_side(self, api):
        body = (await api.get("/api/search", params={"q": "company:wayne"})).json()
        assert (body["q"], body["kind"]) == ("wayne", "company")

    async def test_paging_parameters_are_echoed(self, api):
        body = (
            await api.get("/api/search", params={"q": "wayne", "limit": 1, "offset": 1})
        ).json()
        assert (body["limit"], body["offset"]) == (1, 1)

    async def test_meaning_while_embeddings_are_off_is_a_409(self, api):
        response = await api.get(
            "/api/search", params={"q": "pricing", "mode": "meaning"}
        )
        assert response.status_code == 409
        assert "EMBEDDINGS_ENABLED" in response.json()["detail"]

    async def test_a_model_failure_is_a_502(self, api, meaning_on, monkeypatch):
        async def down(texts, **kwargs):
            raise llm.LLMError("embeddings down")

        monkeypatch.setattr("app.llm.embeddings.embed", down)
        response = await api.get(
            "/api/search", params={"q": "pricing", "mode": "meaning"}
        )
        assert response.status_code == 502
        assert response.json()["detail"] == "embeddings down"

    async def test_embed_runs_when_the_layer_is_on(
        self, api, session, pending, embedder, monkeypatch
    ):
        await session.commit()
        monkeypatch.setattr(settings, "EMBEDDING_BATCH", 2)
        embedder()
        response = await api.post("/api/search/embed", params={"limit": 1})
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == EMBED_KEYS
        assert (body["embedded"], body["truncated_at_cap"]) == (2, True)

    async def test_embed_while_off_is_a_409(self, api):
        response = await api.post("/api/search/embed")
        assert response.status_code == 409
        assert "EMBEDDINGS_ENABLED" in response.json()["detail"]


class TestRawDetail:
    async def test_an_event_is_served_by_id(self, api, session):
        event = raw_row(payload={"name": "Bruce", "city": "Gotham"})
        session.add(event)
        await session.flush()
        await session.refresh(event)
        await session.commit()
        response = await api.get(f"/api/raw/{event.id}")
        assert response.status_code == 200, response.text
        assert response.json() == {
            "id": str(event.id),
            "seq": event.seq,
            "source": "hubspot",
            "object_type": "contacts",
            "source_id": "con_001",
            "ingested_at": event.ingested_at.isoformat(),
            "raw_payload": {"name": "Bruce", "city": "Gotham"},
        }

    async def test_an_unknown_id_is_a_404(self, api):
        response = await api.get(f"/api/raw/{uuid.uuid4()}")
        assert response.status_code == 404
        assert response.json()["detail"] == "no such event"

    @pytest.mark.parametrize(
        "bad_id",
        ["not-a-uuid", "12345", "%20", "00000000-0000-0000-0000-00000000000"],
    )
    async def test_an_id_that_is_not_a_uuid_is_a_404_not_a_500(self, api, bad_id):
        response = await api.get(f"/api/raw/{bad_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "no such event"


class TestHooks:
    async def test_a_rebuild_refills_the_index(self, session):
        session.add(briefing_row(text="Pipeline is up."))
        await session.flush()
        result = await run.rebuild(session, run_checks=False)
        assert result["search"] == {"documents": 1, "chunks": 0}
        assert "embeddings" not in result
        assert [r.text for r in await documents(session, kind=Kind.BRIEFING)] == [
            "Pipeline is up."
        ]

    async def test_a_rebuild_embeds_when_the_layer_is_on(
        self, session, meaning_on, embedder
    ):
        embedder()
        result = await run.rebuild(session, run_checks=False)
        assert set(result["embeddings"]) == EMBED_KEYS
        assert result["embeddings"]["embedded"] == 0
        assert len(await embedding_runs(session)) == 1

    @pytest.mark.parametrize(
        "failure",
        [
            lambda: search.SearchError("locked out"),
            lambda: llm.LLMError("model down"),
        ],
    )
    async def test_an_embedding_failure_never_fails_the_rebuild(
        self, session, meaning_on, monkeypatch, failure
    ):
        async def broken(session, **kwargs):
            raise failure()

        monkeypatch.setattr(search, "embed", broken)
        result = await run.rebuild(session, run_checks=False)
        assert result["ok"] is True
        assert result["embeddings"] == {"error": str(failure())}

    async def test_an_enrichment_write_reindexes_the_entity(self, session, canonical):
        meeting = await canonical("meeting", {"transcript": TRANSCRIPT})
        await search.index(session)
        reading = vocabulary.load()["sales_call"]
        result = reader.ReadingResult(
            reading=reading.name,
            findings=(
                reader.Finding(
                    field="interest",
                    label="strong",
                    quote="pricing is the blocker",
                    quote_verified=True,
                ),
            ),
            model="m",
            prompt_version=reader.PROMPT_VERSION,
            input_sha=reader.input_sha(TRANSCRIPT),
            vocabulary_sha=reading.sha,
        )
        await enrichment_store.write(session, meeting, reading, result)
        rows = await documents(
            session, ref_id=str(meeting), attr=f"{READING_PREFIX}sales_call"
        )
        assert [r.text for r in rows] == ["interest=strong"]
        (quote,) = await documents(
            session, ref_id=str(meeting), attr=f"{QUOTE_PREFIX}sales_call"
        )
        assert quote.text == "pricing is the blocker"

    async def test_a_generated_briefing_is_indexed(self, session, monkeypatch):
        monkeypatch.setattr(settings, "COACHING_ENABLED", True)
        await briefer.generate(
            session, "ceo", model_client=StubModel("Churn is rising.")
        )
        stored = (await session.execute(select(BriefingRun))).scalar_one()
        (row,) = await documents(session, kind=Kind.BRIEFING)
        assert row.ref_id == f"ceo/{stored.seq}"
        assert row.text == "Churn is rising."

    async def test_briefing_history_carries_the_seq(self, api, session):
        stored = briefing_row(text="Pipeline is up.")
        session.add(stored)
        await session.flush()
        await session.commit()
        rows = await briefer.history(session, "ceo", 5)
        assert rows[0]["seq"] == stored.seq
        body = (await api.get("/api/coaching/ceo/history")).json()
        assert body["briefings"][0]["seq"] == stored.seq


class TestStartupCredentials:
    @pytest.fixture(autouse=True)
    def anthropic_layers_off(self, monkeypatch):
        for flag in config.LLM_FLAGS:
            monkeypatch.setattr(settings, flag, False)

    def test_the_map_names_every_flag(self):
        assert config.CREDENTIALS == {
            "ANTHROPIC_API_KEY": (
                "ENRICHMENT_ENABLED",
                "COACHING_ENABLED",
                "CONVERSATION_ENABLED",
            ),
            "OPENAI_API_KEY": ("EMBEDDINGS_ENABLED",),
            "ZEROENTROPY_API_KEY": ("RERANK_ENABLED",),
        }
        assert config.LLM_FLAGS == (
            "ENRICHMENT_ENABLED",
            "COACHING_ENABLED",
            "CONVERSATION_ENABLED",
        )
        assert config.ANTHROPIC_CREDENTIAL_ENV == "ANTHROPIC_API_KEY"

    def test_embeddings_on_without_a_key_refuses_the_boot(self, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDINGS_ENABLED", True)
        with pytest.raises(config.StartupError, match="EMBEDDINGS_ENABLED") as info:
            config.validate_startup(env={})
        assert "OPENAI_API_KEY" in str(info.value)

    def test_the_openai_key_satisfies_embeddings(self, monkeypatch):
        monkeypatch.setattr(settings, "EMBEDDINGS_ENABLED", True)
        assert config.validate_startup(env={"OPENAI_API_KEY": "sk"}) is None

    def test_rerank_on_without_a_key_refuses_the_boot(self, monkeypatch):
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        with pytest.raises(config.StartupError, match="RERANK_ENABLED") as info:
            config.validate_startup(env={})
        assert "ZEROENTROPY_API_KEY" in str(info.value)

    def test_the_zeroentropy_key_satisfies_rerank(self, monkeypatch):
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        assert config.validate_startup(env={"ZEROENTROPY_API_KEY": "ze"}) is None

    def test_each_credential_is_checked_on_its_own(self, monkeypatch):
        monkeypatch.setattr(settings, "ENRICHMENT_ENABLED", True)
        monkeypatch.setattr(settings, "EMBEDDINGS_ENABLED", True)
        with pytest.raises(config.StartupError) as info:
            config.validate_startup(env={"ANTHROPIC_API_KEY": "k"})
        assert "OPENAI_API_KEY" in str(info.value)
        assert "EMBEDDINGS_ENABLED" in str(info.value)
        assert "ANTHROPIC_API_KEY" not in str(info.value)
        assert (
            config.validate_startup(
                env={"ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": "sk"}
            )
            is None
        )

    def test_has_credential_checks_the_named_variable(self):
        assert config.has_credential({"OPENAI_API_KEY": "k"}, "OPENAI_API_KEY") is True
        assert config.has_credential({}, "OPENAI_API_KEY") is False
        assert config.has_credential({"ANTHROPIC_API_KEY": "k"}) is True

    def test_the_search_settings_ship_their_defaults(self):
        defaults = {
            name: field.default for name, field in Settings.model_fields.items()
        }
        assert defaults["EMBEDDINGS_ENABLED"] is False
        assert defaults["EMBEDDING_MODEL"] == "text-embedding-3-small"
        assert defaults["EMBEDDING_DIMS"] == 1536
        assert defaults["EMBEDDING_BATCH"] == 100
        assert defaults["EMBEDDINGS_MAX_CALLS_PER_RUN"] == 200
        assert defaults["RERANK_ENABLED"] is False
        assert defaults["RERANK_MODEL"] == "zerank-2"
        assert defaults["RERANK_TOP"] == 20
        assert defaults["SEARCH_CHUNK_CHARS"] == 1200
