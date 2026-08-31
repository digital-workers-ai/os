import pytest
from sqlalchemy import func, select

from app import store
from app.models import RawEvent


class TestPayloadValidation:
    def test_a_payload_hashes_stably_regardless_of_key_order(self):
        assert store.payload_sha({"a": 1, "b": 2}) == store.payload_sha(
            {"b": 2, "a": 1}
        )

    @pytest.mark.parametrize("source", ["", None, 42])
    def test_a_source_that_is_not_a_name_is_refused(self, source):
        with pytest.raises(ValueError, match="source must be"):
            store._validate(source, "companies", "c1", {})

    @pytest.mark.parametrize("object_type", ["", None, 42])
    def test_an_object_type_is_required_because_it_is_part_of_identity(
        self, object_type
    ):
        with pytest.raises(ValueError, match="object_type is required"):
            store._validate("activecampaign", object_type, "1", {})

    @pytest.mark.parametrize("source_id", [None, "", "   ", 42])
    def test_a_blank_or_non_string_id_is_refused(self, source_id):
        with pytest.raises(ValueError, match="source_id must be"):
            store._validate("hubspot", "companies", source_id, {})

    def test_an_overlong_id_is_refused_and_the_message_is_truncated(self):
        with pytest.raises(ValueError) as caught:
            store._validate("hubspot", "companies", "x" * 5000, {})
        assert "exceeds" in str(caught.value)
        assert len(str(caught.value)) < 200

    @pytest.mark.parametrize("payload", ["a string", ["a", "list"], None, 42])
    def test_a_payload_that_is_not_an_object_names_what_it_got(self, payload):
        with pytest.raises(ValueError, match="raw_payload must be a dict") as caught:
            store._validate("hubspot", "companies", "c1", payload)
        assert type(payload).__name__ in str(caught.value)

    def test_a_null_byte_in_a_value_is_refused(self):
        with pytest.raises(ValueError, match="null byte"):
            store._validate("hubspot", "companies", "c1", {"name": "a\x00b"})

    def test_a_null_byte_in_a_dict_key_is_refused(self):
        with pytest.raises(ValueError, match="null byte"):
            store._validate("hubspot", "companies", "c1", {"a\x00b": "name"})

    def test_a_null_byte_nested_in_a_list_is_refused(self):
        with pytest.raises(ValueError, match="null byte"):
            store._validate("hubspot", "companies", "c1", {"tags": ["ok", "a\x00b"]})

    def test_the_escaped_form_is_not_a_null_byte(self):
        assert (
            store._validate("hubspot", "companies", "c1", {"name": "\\u0000"}) is None
        )

    def test_a_well_formed_record_passes(self):
        assert store._validate("hubspot", "companies", "c1", {"name": "Acme"}) is None

    def test_non_string_scalars_pass_the_nul_walk(self):
        payload = {"count": 42, "active": True, "score": 1.5, "note": None}
        assert store._validate("hubspot", "companies", "c1", payload) is None


async def _rows(session):
    result = await session.execute(select(RawEvent).order_by(RawEvent.seq))
    return list(result.scalars())


async def _count(session):
    return await session.scalar(select(func.count()).select_from(RawEvent))


class TestSaveRaw:
    async def test_an_unchanged_payload_is_not_stored_again(self, session):
        first = await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={"name": "Acme"},
        )
        second = await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={"name": "Acme"},
        )
        assert first is True
        assert second is False
        assert await _count(session) == 1

    async def test_a_changed_payload_appends_a_new_row_with_a_higher_seq(self, session):
        await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={"name": "Acme"},
        )
        changed = await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={"name": "Acme Inc"},
        )
        assert changed is True
        rows = await _rows(session)
        assert len(rows) == 2
        assert rows[1].seq > rows[0].seq
        assert rows[1].raw_payload == {"name": "Acme Inc"}

    async def test_a_reverted_payload_is_stored_as_a_third_row(self, session):
        for payload in ({"name": "A"}, {"name": "B"}, {"name": "A"}):
            assert (
                await store.save_raw(
                    session,
                    source="hubspot",
                    object_type="companies",
                    source_id="c1",
                    raw_payload=payload,
                )
                is True
            )
        assert await _count(session) == 3

    async def test_the_same_id_under_different_object_types_is_two_identities(
        self, session
    ):
        for object_type in ("contacts", "campaigns"):
            assert (
                await store.save_raw(
                    session,
                    source="activecampaign",
                    object_type=object_type,
                    source_id="1",
                    raw_payload={"n": object_type},
                )
                is True
            )
        assert await _count(session) == 2

    async def test_an_invalid_payload_raises_and_the_session_stays_usable(
        self, session
    ):
        with pytest.raises(ValueError):
            await store.save_raw(
                session,
                source="hubspot",
                object_type="companies",
                source_id="c1",
                raw_payload="not a dict",
            )
        assert await _count(session) == 0
        assert (
            await store.save_raw(
                session,
                source="hubspot",
                object_type="companies",
                source_id="c1",
                raw_payload={"name": "Acme"},
            )
            is True
        )
        assert await _count(session) == 1


class TestQueries:
    async def _seed(self, session):
        await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={"name": "Acme"},
        )
        await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={"name": "Acme Inc"},
        )
        await store.save_raw(
            session,
            source="stripe",
            object_type="customers",
            source_id="cus_1",
            raw_payload={"email": "a@b.c"},
        )

    async def test_latest_rows_returns_one_newest_row_per_identity(self, session):
        await self._seed(session)
        result = await session.execute(store.latest_rows_query())
        rows = {(r.source, r.object_type, r.source_id): r for r in result.scalars()}
        assert set(rows) == {
            ("hubspot", "companies", "c1"),
            ("stripe", "customers", "cus_1"),
        }
        assert rows[("hubspot", "companies", "c1")].raw_payload == {"name": "Acme Inc"}

    async def test_first_seen_returns_min_seq_and_min_ingested_at_per_identity(
        self, session
    ):
        await self._seed(session)
        all_rows = await _rows(session)
        by_identity = {}
        for row in all_rows:
            key = (row.source, row.object_type, row.source_id)
            by_identity.setdefault(key, row)
        result = await session.execute(store.first_seen_query())
        seen = {tuple(row) for row in result}
        assert seen == {
            (
                key[0],
                key[1],
                key[2],
                row.seq,
                row.ingested_at,
            )
            for key, row in by_identity.items()
        }

    async def test_an_edit_moves_the_latest_row_but_not_the_first_seen_seq(
        self, session
    ):
        await self._seed(session)
        rows_before = await _rows(session)
        original_seq = rows_before[0].seq
        await store.save_raw(
            session,
            source="hubspot",
            object_type="companies",
            source_id="c1",
            raw_payload={"name": "Acme Corp"},
        )
        first_seen = {
            (row[0], row[1], row[2]): row[3]
            for row in await session.execute(store.first_seen_query())
        }
        assert first_seen[("hubspot", "companies", "c1")] == original_seq
        latest = {
            (r.source, r.object_type, r.source_id): r
            for r in (await session.execute(store.latest_rows_query())).scalars()
        }
        newest = latest[("hubspot", "companies", "c1")]
        assert newest.raw_payload == {"name": "Acme Corp"}
        assert newest.seq > original_seq
