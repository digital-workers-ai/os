import asyncio
import importlib
import uuid
from datetime import UTC, datetime

import pytest

from app import store
from app.custom import scripts
from app.engine import apps
from app.models import CustomRecord

SCRIPT_APPS = ("mileage_log", "shelf_audit", "inventory_count")


def at(hour):
    return datetime(2026, 9, 3, hour, tzinfo=UTC)


def stamp(when):
    return when.isoformat().replace("+00:00", "Z")


def a_reading(**overrides):
    return {
        "vehicle": "Truck 7",
        "odometer": 48210,
        "stage": "end",
        "purpose": "delivery",
        "miles": None,
        **overrides,
    }


def an_item(product="Oat milk", **overrides):
    return {
        "product": product,
        "facings": 4,
        "stock": "stocked",
        "shelf_price": 4.5,
        "price": None,
        **overrides,
    }


def a_shelf(*items):
    return {"location": "Store 4, aisle 3", "items": list(items)}


def answering(answer):
    async def fill(record, ctx):
        return answer

    return fill


def mileage_with_stops():
    return apps.parse(
        "mileage_log",
        {
            "title": "Mileage log",
            "input": "photo",
            "roles": ["staff"],
            "lands_as": "odometer_reading",
            "fields": {
                "odometer": {"type": "number", "unit": "mi"},
                "miles": {"type": "number", "filled_by": "script"},
                "stops": {
                    "type": "list",
                    "lands_as": "expense_item",
                    "fields": {"place": {"type": "text"}},
                },
            },
            "script": "script.py",
        },
    )


@pytest.fixture
def scripted(monkeypatch):
    def _install(app_name, fill):
        module = importlib.import_module(f"app.custom.apps.{app_name}.script")
        monkeypatch.setattr(module, "fill", fill)

    return _install


@pytest.fixture
def mileage_log():
    return apps.load("mileage_log")


@pytest.fixture
def shelf_audit():
    return apps.load("shelf_audit")


async def a_saved_record(session, app_name, fields, when):
    record_id = uuid.uuid4()
    session.add(
        CustomRecord(
            id=record_id,
            app=app_name,
            recorded_by="admin",
            created_at=when,
            saved_at=when,
        )
    )
    await session.flush()
    await store.save_raw(
        session,
        source="custom",
        object_type=app_name,
        source_id=str(record_id),
        raw_payload={
            "record": str(record_id),
            "app": app_name,
            "recorded_at": stamp(when),
            "recorded_by": "admin",
            "removed": False,
            "fields": fields,
        },
    )
    await session.commit()
    return record_id


async def an_edit(session, record_id, app_name, fields, when):
    await store.save_raw(
        session,
        source="custom",
        object_type=app_name,
        source_id=str(record_id),
        raw_payload={
            "record": str(record_id),
            "app": app_name,
            "recorded_at": stamp(when),
            "recorded_by": "admin",
            "removed": False,
            "fields": fields,
        },
    )
    await session.commit()


async def a_removal(session, record_id, app_name, when):
    record = await session.get(CustomRecord, record_id)
    record.removed_at = when
    await store.save_raw(
        session,
        source="custom",
        object_type=app_name,
        source_id=str(record_id),
        raw_payload={
            "record": str(record_id),
            "app": app_name,
            "removed": True,
            "recorded_at": stamp(when),
            "recorded_by": "admin",
        },
    )
    await session.commit()


async def an_unsaved_record(session, app_name, when):
    session.add(
        CustomRecord(
            id=uuid.uuid4(), app=app_name, recorded_by="admin", created_at=when
        )
    )
    await session.commit()


class TestTheModule:
    @pytest.mark.parametrize("app_name", SCRIPT_APPS)
    def test_the_module_is_the_apps_own_script(self, app_name):
        assert scripts.module_for(apps.load(app_name)) is importlib.import_module(
            f"app.custom.apps.{app_name}.script"
        )

    def test_a_script_has_five_seconds(self):
        assert scripts.SCRIPT_SECONDS == 5


class TestRunningAScript:
    async def test_the_script_gets_the_record_and_the_context(
        self, mileage_log, scripted
    ):
        seen = []

        async def fill(record, ctx):
            seen.append((record, ctx))
            return record

        scripted("mileage_log", fill)
        ctx = object()
        await scripts.run(mileage_log, a_reading(), ctx)
        assert seen[0][0] == a_reading()
        assert seen[0][1] is ctx

    async def test_a_top_level_script_field_takes_the_scripts_value(
        self, mileage_log, scripted
    ):
        scripted("mileage_log", answering({**a_reading(), "miles": 250}))
        result = await scripts.run(mileage_log, a_reading(miles=999), object())
        assert result == a_reading(miles=250)

    async def test_fields_the_script_does_not_own_keep_their_values(
        self, mileage_log, scripted
    ):
        scripted(
            "mileage_log",
            answering(
                {
                    "vehicle": "Truck 9",
                    "odometer": 1,
                    "stage": "start",
                    "purpose": "other",
                    "miles": 250,
                }
            ),
        )
        result = await scripts.run(mileage_log, a_reading(), object())
        assert result == a_reading(miles=250)

    async def test_a_key_the_app_does_not_declare_is_dropped(
        self, mileage_log, scripted
    ):
        scripted("mileage_log", answering({"miles": 250, "note": "long day"}))
        result = await scripts.run(mileage_log, a_reading(), object())
        assert result == a_reading(miles=250)

    async def test_a_script_field_the_script_leaves_out_comes_back_empty(
        self, mileage_log, scripted
    ):
        scripted("mileage_log", answering({}))
        result = await scripts.run(mileage_log, a_reading(miles=999), object())
        assert result == a_reading(miles=None)

    async def test_a_script_that_changes_its_input_cannot_change_other_fields(
        self, mileage_log, scripted
    ):
        async def fill(record, ctx):
            record["vehicle"] = "Truck 9"
            return {**record, "miles": 250}

        scripted("mileage_log", fill)
        result = await scripts.run(mileage_log, a_reading(), object())
        assert result == a_reading(miles=250)


class TestRunningAScriptOverListRows:
    async def test_each_row_takes_the_scripts_value_for_its_script_field(
        self, shelf_audit, scripted
    ):
        scripted(
            "shelf_audit",
            answering(a_shelf(an_item(price="matches"), an_item(price="wrong"))),
        )
        result = await scripts.run(
            shelf_audit, a_shelf(an_item(), an_item("Rye bread")), object()
        )
        assert result == a_shelf(
            an_item(price="matches"), an_item("Rye bread", price="wrong")
        )

    async def test_row_fields_the_script_does_not_own_keep_their_values(
        self, shelf_audit, scripted
    ):
        scripted(
            "shelf_audit",
            answering(
                {
                    "location": "Somewhere else",
                    "items": [
                        {
                            "product": "Rye bread",
                            "facings": 0,
                            "stock": "empty",
                            "shelf_price": 1.0,
                            "price": "wrong",
                        }
                    ],
                }
            ),
        )
        result = await scripts.run(shelf_audit, a_shelf(an_item()), object())
        assert result == a_shelf(an_item(price="wrong"))

    async def test_a_row_the_script_answers_nothing_for_gets_no_script_value(
        self, shelf_audit, scripted
    ):
        scripted("shelf_audit", answering({"items": [{"price": "matches"}]}))
        result = await scripts.run(
            shelf_audit,
            a_shelf(an_item(), an_item("Rye bread", price="wrong")),
            object(),
        )
        assert result == a_shelf(
            an_item(price="matches"), an_item("Rye bread", price=None)
        )

    async def test_rows_the_script_adds_are_dropped(self, shelf_audit, scripted):
        scripted(
            "shelf_audit",
            answering({"items": [{"price": "matches"}, {"price": "wrong"}]}),
        )
        result = await scripts.run(shelf_audit, a_shelf(an_item()), object())
        assert result == a_shelf(an_item(price="matches"))

    async def test_a_shelf_with_no_rows_keeps_no_rows(self, shelf_audit, scripted):
        scripted("shelf_audit", answering({"items": [{"price": "matches"}]}))
        result = await scripts.run(shelf_audit, a_shelf(), object())
        assert result == a_shelf()

    async def test_a_script_that_changes_a_row_cannot_change_its_other_fields(
        self, shelf_audit, scripted
    ):
        async def fill(record, ctx):
            record["items"][0]["product"] = "Rye bread"
            return {"items": [{"price": "matches"}]}

        scripted("shelf_audit", fill)
        result = await scripts.run(shelf_audit, a_shelf(an_item()), object())
        assert result == a_shelf(an_item(price="matches"))

    async def test_a_list_without_script_fields_is_left_as_it_came(self, scripted):
        scripted(
            "mileage_log",
            answering({"miles": 12, "stops": [{"place": "Somewhere else"}]}),
        )
        result = await scripts.run(
            mileage_with_stops(),
            {"odometer": 48210, "miles": None, "stops": [{"place": "Depot"}]},
            object(),
        )
        assert result == {
            "odometer": 48210,
            "miles": 12,
            "stops": [{"place": "Depot"}],
        }


class TestAScriptThatFails:
    async def test_a_script_that_raises_is_a_script_error_naming_its_file(
        self, mileage_log, scripted
    ):
        async def fill(record, ctx):
            raise ValueError("odometer went backwards")

        scripted("mileage_log", fill)
        with pytest.raises(
            scripts.ScriptError,
            match=r"^mileage_log/script\.py: .*odometer went backwards",
        ):
            await scripts.run(mileage_log, a_reading(), object())

    async def test_a_script_that_runs_too_long_is_a_script_error_naming_its_file(
        self, mileage_log, scripted, monkeypatch
    ):
        async def fill(record, ctx):
            await asyncio.sleep(5)
            return record

        scripted("mileage_log", fill)
        monkeypatch.setattr(scripts, "SCRIPT_SECONDS", 0.05)
        with pytest.raises(
            scripts.ScriptError, match=r"^mileage_log/script\.py: .*timed out"
        ):
            await scripts.run(mileage_log, a_reading(), object())

    async def test_a_script_that_answers_with_no_record_is_a_script_error(
        self, mileage_log, scripted
    ):
        scripted("mileage_log", answering(None))
        with pytest.raises(scripts.ScriptError, match=r"^mileage_log/script\.py: "):
            await scripts.run(mileage_log, a_reading(), object())


class TestThePreviousRecord:
    async def test_the_latest_matching_record_is_the_previous_one(
        self, session, mileage_log
    ):
        await a_saved_record(
            session,
            "mileage_log",
            a_reading(stage="start", odometer=1000),
            at(9),
        )
        await a_saved_record(
            session,
            "mileage_log",
            a_reading(stage="start", odometer=1100),
            at(10),
        )
        ctx = scripts.Context(session, mileage_log)
        assert await ctx.previous(
            {"vehicle": "Truck 7", "stage": "start"}
        ) == a_reading(stage="start", odometer=1100)

    async def test_an_app_with_no_records_has_no_previous(self, session, mileage_log):
        ctx = scripts.Context(session, mileage_log)
        assert await ctx.previous({"vehicle": "Truck 7", "stage": "start"}) is None

    async def test_every_key_of_where_must_match(self, session, mileage_log):
        await a_saved_record(
            session, "mileage_log", a_reading(stage="end", odometer=1250), at(9)
        )
        await a_saved_record(
            session,
            "mileage_log",
            a_reading(vehicle="Truck 9", stage="start", odometer=500),
            at(10),
        )
        ctx = scripts.Context(session, mileage_log)
        assert await ctx.previous({"vehicle": "Truck 7", "stage": "start"}) is None

    async def test_a_removed_record_is_not_previous(self, session, mileage_log):
        await a_saved_record(
            session,
            "mileage_log",
            a_reading(stage="start", odometer=1000),
            at(9),
        )
        removed = await a_saved_record(
            session,
            "mileage_log",
            a_reading(stage="start", odometer=1100),
            at(10),
        )
        await a_removal(session, removed, "mileage_log", at(11))
        ctx = scripts.Context(session, mileage_log)
        assert await ctx.previous(
            {"vehicle": "Truck 7", "stage": "start"}
        ) == a_reading(stage="start", odometer=1000)

    async def test_another_apps_records_are_not_previous(self, session, mileage_log):
        await a_saved_record(
            session,
            "vehicle_pre_trip",
            {"vehicle": "Truck 7", "stage": "start", "odometer": 1000},
            at(9),
        )
        ctx = scripts.Context(session, mileage_log)
        assert await ctx.previous({"vehicle": "Truck 7", "stage": "start"}) is None

    async def test_an_unsaved_record_is_not_previous(self, session, mileage_log):
        await an_unsaved_record(session, "mileage_log", at(9))
        ctx = scripts.Context(session, mileage_log)
        assert await ctx.previous({"vehicle": "Truck 7", "stage": "start"}) is None

    async def test_an_edited_record_is_matched_on_its_latest_fields(
        self, session, mileage_log
    ):
        record_id = await a_saved_record(
            session,
            "mileage_log",
            a_reading(stage="start", odometer=1000),
            at(9),
        )
        await an_edit(
            session,
            record_id,
            "mileage_log",
            a_reading(stage="start", odometer=1005),
            at(9),
        )
        ctx = scripts.Context(session, mileage_log)
        assert await ctx.previous(
            {"vehicle": "Truck 7", "stage": "start"}
        ) == a_reading(stage="start", odometer=1005)

    async def test_an_edit_that_no_longer_matches_leaves_the_record_out(
        self, session, mileage_log
    ):
        record_id = await a_saved_record(
            session,
            "mileage_log",
            a_reading(stage="start", odometer=1000),
            at(9),
        )
        await an_edit(
            session,
            record_id,
            "mileage_log",
            a_reading(stage="end", odometer=1000),
            at(9),
        )
        ctx = scripts.Context(session, mileage_log)
        assert await ctx.previous({"vehicle": "Truck 7", "stage": "start"}) is None


class TestAnEntityFact:
    async def test_the_current_fact_of_the_matching_entity_comes_back(
        self, session, canonical, shelf_audit
    ):
        await canonical("product", {"name": "Oat milk", "price": "4.5"})
        ctx = scripts.Context(session, shelf_audit)
        assert await ctx.entity("product", "name", "Oat milk", "price") == "4.5"

    async def test_an_entity_nobody_has_is_none(self, session, canonical, shelf_audit):
        await canonical("product", {"name": "Oat milk", "price": "4.5"})
        ctx = scripts.Context(session, shelf_audit)
        assert await ctx.entity("product", "name", "Rye bread", "price") is None

    async def test_an_attribute_the_entity_lacks_is_none(
        self, session, canonical, shelf_audit
    ):
        await canonical("product", {"name": "Oat milk"})
        ctx = scripts.Context(session, shelf_audit)
        assert await ctx.entity("product", "name", "Oat milk", "price") is None

    async def test_another_entity_type_with_the_same_value_is_not_matched(
        self, session, canonical, shelf_audit
    ):
        await canonical("company", {"name": "Oat milk", "price": "9"})
        ctx = scripts.Context(session, shelf_audit)
        assert await ctx.entity("product", "name", "Oat milk", "price") is None

    async def test_the_value_is_matched_on_the_by_attribute_only(
        self, session, canonical, shelf_audit
    ):
        await canonical("product", {"name": "Oat milk", "sku": "OAT-1", "price": "4.5"})
        ctx = scripts.Context(session, shelf_audit)
        assert await ctx.entity("product", "sku", "Oat milk", "price") is None

    async def test_an_entity_is_found_by_any_attribute_named_as_by(
        self, session, canonical, shelf_audit
    ):
        await canonical("product", {"name": "Oat milk", "sku": "OAT-1", "price": "4.5"})
        ctx = scripts.Context(session, shelf_audit)
        assert await ctx.entity("product", "sku", "OAT-1", "price") == "4.5"
