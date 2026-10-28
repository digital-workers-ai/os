import pytest
import yaml
from sqlalchemy import select

from app import caches, store, sync
from app.engine import apps, run
from app.models import CanonicalLink, CanonicalMember, Entity, EntityFact
from app.sources import hooks, registry
from app.sources.custom import connector, extract

RECORD = "5b1f3c2a-7d4e-4f60-9a8b-1c2d3e4f5a6b"
LEAK_FOUND = "d4936bbf-ea19-43aa-8a0e-e28566f13a3b"
SEAL_FITTED = "f32d8b7f-66e5-4447-830d-3f3ef8843388"
FLAGGED = {
    "title": "Flagged receipts",
    "input": "photo",
    "roles": ["admin"],
    "lands_as": "expense",
    "fields": {
        "vendor": {"type": "text"},
        "items": {
            "type": "list",
            "lands_as": "expense_item",
            "fields": {
                "description": {"type": "text"},
                "flags": {
                    "type": "many_of",
                    "labels": ["damaged", "personal", "returned"],
                },
            },
        },
    },
}
RECORDED_AT = "2026-09-04T12:00:00Z"
DIESEL = {"description": "Diesel", "amount": 45.1}
SNACKS = {"description": "Snacks", "amount": 3.1}
PHOTO = {"path": "photo-1.jpg", "media_type": "image/jpeg", "kind": "photo"}
REMOVED = {
    "record": RECORD,
    "app": "receipts",
    "removed": True,
    "recorded_at": "2026-09-04T12:05:00Z",
    "recorded_by": "admin",
}


def saved(app, fields, **extra):
    return {
        "record": RECORD,
        "app": app,
        "recorded_at": RECORDED_AT,
        "recorded_by": "admin",
        "removed": False,
        "files": [],
        "fields": fields,
        **extra,
    }


def receipt(items=(DIESEL, SNACKS)):
    return saved(
        "receipts",
        {
            "vendor": "Harbor Fuel",
            "date": "2026-09-03",
            "total": 48.2,
            "tax": 3.1,
            "category": "fuel",
            "items": list(items),
        },
        currency="USD",
        files=[PHOTO],
    )


def checkout(asset):
    return saved(
        "equipment_checkout",
        {
            "asset": asset,
            "action": "check_out",
            "location": "Site B",
            "due_back": "2026-09-10",
        },
    )


def claim(damage=("broken", "dented")):
    return saved(
        "damage_claims",
        {
            "item": "Monitor",
            "order": "1042",
            "damage": list(damage),
            "severity": "severe",
            "estimated_cost": 180.0,
            "description": "Screen cracked",
        },
        currency="USD",
        files=[PHOTO],
    )


def count(product):
    return saved(
        "inventory_count",
        {
            "location": "Back room",
            "lines": [{"product": product, "counted": 12, "change": None}],
        },
    )


def walk_in():
    return saved(
        "food_safety_log",
        {
            "shift": "opening",
            "readings": [
                {"unit": "walk_in_cooler", "temperature": 37},
                {"unit": "freezer", "temperature": -2},
            ],
        },
        transcript="walk-in cooler, 37",
    )


def perio_chart(rows=None, cells=None):
    return saved(
        "perio_charting",
        {"patient": "Jordan Rivera", "exam_date": "2026-09-02"},
        transcript="three, three two four, bleeding on the two",
        template={
            "rows": {"3": {"status": "present", "mobility": "0"}}
            if rows is None
            else rows,
            "cells": {
                "3:DB": {"depth": 3, "bleeding": "none"},
                "3:B": {"depth": 2, "bleeding": "bleeding"},
                "3:MB": {"depth": 4, "bleeding": "none"},
            }
            if cells is None
            else cells,
            "items": {},
        },
    )


def pre_trip(items=None):
    return saved(
        "vehicle_pre_trip",
        {"vehicle": "Truck 7", "odometer": 48210},
        transcript="tires fail, front left tread low. horn pass",
        template={
            "rows": {},
            "cells": {},
            "items": {
                "vehicle:tires": {"result": "fail", "defect": "Front left tread low"},
                "vehicle:horn": {"result": "pass"},
            }
            if items is None
            else items,
        },
    )


def parent(app, payload):
    return extract.reshape(app, payload)[0]


def children(app, payload):
    return sorted(extract.reshape(app, payload)[1:], key=lambda r: r["_source_id"])


@pytest.fixture
def flagged(tmp_path, monkeypatch):
    folder = tmp_path / "flagged_receipts"
    folder.mkdir()
    (folder / "app.yaml").write_text(yaml.safe_dump(FLAGGED))
    monkeypatch.setattr(apps, "APPS_DIR", tmp_path)
    caches.reset_all()
    yield
    caches.reset_all()


def flagged_receipt(flags):
    return saved(
        "flagged_receipts",
        {
            "vendor": "Harbor Fuel",
            "items": [{"description": "Diesel", "flags": list(flags)}],
        },
    )


class TestTheCustomConnector:
    def test_the_source_is_custom(self):
        assert connector.SOURCE == "custom"

    async def test_a_pull_hands_the_store_nothing(self, session):
        handed = []

        async def recording(session, **record):
            handed.append(record)

        await connector.pull(session, recording)
        assert handed == []

    async def test_a_pull_returns_what_an_empty_pull_returns(self, session):
        async def recording(session, **record):
            raise AssertionError(record)

        assert await connector.pull(session, recording) is None

    async def test_a_sync_of_custom_succeeds_with_nothing_fetched_or_written(
        self, session, sessionmaker_for_test
    ):
        result = await sync.run_connector("custom", sessionmaker_for_test)
        assert (
            result["ok"],
            result["rows_fetched"],
            result["rows_written"],
            result["detail"],
        ) == (True, 0, 0, None)

    def test_the_registry_serves_custom_from_this_connector(self):
        assert registry.discover()["custom"] is connector

    def test_the_rebuild_reshapes_custom_through_this_extract(self):
        assert hooks.hooks()["custom"] is extract.reshape


class TestTheParentRecord:
    def test_the_parent_comes_first_named_by_the_record_id(self):
        assert parent("receipts", receipt())["_source_id"] == RECORD

    def test_the_parent_carries_the_fields_but_not_the_lists(self):
        assert parent("receipts", receipt()) == {
            "_source_id": RECORD,
            "vendor": "Harbor Fuel",
            "date": "2026-09-03",
            "total": 48.2,
            "tax": 3.1,
            "category": "fuel",
            "currency": "USD",
            "recorded_at": RECORDED_AT,
            "recorded_by": "admin",
        }

    def test_a_record_with_no_money_carries_no_currency(self):
        assert "currency" not in parent("equipment_checkout", checkout("LAP-014"))

    def test_a_voice_record_carries_its_transcript(self):
        assert (
            parent("food_safety_log", walk_in())["transcript"] == "walk-in cooler, 37"
        )

    def test_a_record_that_was_not_spoken_carries_no_transcript(self):
        assert "transcript" not in parent("receipts", receipt())

    def test_the_template_stays_off_the_parent(self):
        assert parent("perio_charting", perio_chart()) == {
            "_source_id": RECORD,
            "patient": "Jordan Rivera",
            "exam_date": "2026-09-02",
            "recorded_at": RECORDED_AT,
            "recorded_by": "admin",
            "transcript": "three, three two four, bleeding on the two",
        }

    def test_a_number_field_stays_a_number(self):
        assert parent("vehicle_pre_trip", pre_trip())["odometer"] == 48210

    def test_a_many_of_answer_lands_on_the_parent_as_its_labels_joined(self):
        assert parent("damage_claims", claim())["damage"] == "broken, dented"

    def test_a_many_of_answer_keeps_the_order_its_labels_were_given_in(self):
        joined = parent("damage_claims", claim(("water", "broken")))["damage"]
        assert joined == "water, broken"

    def test_an_empty_many_of_answer_lands_as_none(self):
        assert parent("damage_claims", claim(()))["damage"] is None

    def test_a_many_of_answer_adds_no_children(self):
        assert len(extract.reshape("damage_claims", claim())) == 1


class TestALookupLandsAsText:
    def test_a_lookup_value_becomes_a_string(self):
        assert parent("equipment_checkout", checkout(1042))["asset"] == "1042"

    def test_a_lookup_value_already_text_is_kept(self):
        assert parent("equipment_checkout", checkout("LAP-014"))["asset"] == "LAP-014"

    def test_an_empty_lookup_stays_empty(self):
        assert parent("equipment_checkout", checkout(None))["asset"] is None

    def test_a_lookup_inside_a_list_row_becomes_a_string(self):
        row = children("inventory_count", count(4011))[0]
        assert row["_lines_product"] == "4011"

    def test_a_number_inside_a_list_row_stays_a_number(self):
        row = children("food_safety_log", walk_in())[0]
        assert row["_readings_temperature"] == 37


class TestAScannedCodeIsItsOwnRecord:
    def test_a_scanned_code_lands_as_a_record_named_by_the_code(self):
        assert extract.reshape("equipment_checkout", checkout("LAP-014"))[1:] == [
            {"_source_id": "LAP-014", "_asset": "LAP-014"}
        ]

    def test_an_empty_scan_adds_no_record(self):
        assert len(extract.reshape("equipment_checkout", checkout(None))) == 1

    def test_a_scanned_text_field_adds_no_record(self):
        lot = saved("batch_trace", {"lot": "LOT-2207", "step": "received"})
        assert len(extract.reshape("batch_trace", lot)) == 1


class TestEachListRowIsAChild:
    def test_each_row_is_named_by_record_list_and_index(self):
        assert children("receipts", receipt()) == [
            {
                "_source_id": f"{RECORD}:items:0",
                "_items_parent": RECORD,
                "_items_description": "Diesel",
                "_items_amount": 45.1,
            },
            {
                "_source_id": f"{RECORD}:items:1",
                "_items_parent": RECORD,
                "_items_description": "Snacks",
                "_items_amount": 3.1,
            },
        ]

    def test_the_keys_are_prefixed_by_the_lists_own_name(self):
        assert children("food_safety_log", walk_in()) == [
            {
                "_source_id": f"{RECORD}:readings:0",
                "_readings_parent": RECORD,
                "_readings_unit": "walk_in_cooler",
                "_readings_temperature": 37,
            },
            {
                "_source_id": f"{RECORD}:readings:1",
                "_readings_parent": RECORD,
                "_readings_unit": "freezer",
                "_readings_temperature": -2,
            },
        ]

    def test_an_empty_list_adds_no_children(self):
        assert len(extract.reshape("receipts", receipt(items=()))) == 1

    def test_a_many_of_answer_inside_a_list_row_lands_as_its_labels_joined(
        self, flagged
    ):
        row = children("flagged_receipts", flagged_receipt(("returned", "damaged")))[0]
        assert row["_items_flags"] == "returned, damaged"

    def test_an_empty_many_of_answer_inside_a_list_row_lands_as_none(self, flagged):
        row = children("flagged_receipts", flagged_receipt(()))[0]
        assert row["_items_flags"] is None


class TestEachGridRowAndCellIsAChild:
    def test_each_row_is_named_by_record_and_row(self):
        rows = [
            child
            for child in children("perio_charting", perio_chart())
            if child["_source_id"].startswith(f"{RECORD}:row:")
        ]
        assert rows == [
            {
                "_source_id": f"{RECORD}:row:3",
                "_rows_parent": RECORD,
                "_rows_row": "3",
                "_rows_status": "present",
                "_rows_mobility": "0",
            }
        ]

    def test_each_cell_is_named_by_record_row_and_column(self):
        cells = [
            child
            for child in children("perio_charting", perio_chart())
            if child["_source_id"].startswith(f"{RECORD}:cell:")
        ]
        assert cells == [
            {
                "_source_id": f"{RECORD}:cell:3:B",
                "_cells_parent": RECORD,
                "_cells_row": "3",
                "_cells_column": "B",
                "_cells_depth": 2,
                "_cells_bleeding": "bleeding",
            },
            {
                "_source_id": f"{RECORD}:cell:3:DB",
                "_cells_parent": RECORD,
                "_cells_row": "3",
                "_cells_column": "DB",
                "_cells_depth": 3,
                "_cells_bleeding": "none",
            },
            {
                "_source_id": f"{RECORD}:cell:3:MB",
                "_cells_parent": RECORD,
                "_cells_row": "3",
                "_cells_column": "MB",
                "_cells_depth": 4,
                "_cells_bleeding": "none",
            },
        ]

    def test_a_grid_with_only_cells_adds_no_row_children(self):
        ids = [c["_source_id"] for c in children("perio_charting", perio_chart({}))]
        assert ids == [
            f"{RECORD}:cell:3:B",
            f"{RECORD}:cell:3:DB",
            f"{RECORD}:cell:3:MB",
        ]

    def test_a_grid_with_nothing_called_out_adds_no_children(self):
        assert len(extract.reshape("perio_charting", perio_chart({}, {}))) == 1


class TestEachChecklistItemIsAChild:
    def test_each_item_is_named_by_record_section_and_item(self):
        assert children("vehicle_pre_trip", pre_trip()) == [
            {
                "_source_id": f"{RECORD}:item:vehicle:horn",
                "_items_parent": RECORD,
                "_items_section": "vehicle",
                "_items_item": "horn",
                "_items_result": "pass",
            },
            {
                "_source_id": f"{RECORD}:item:vehicle:tires",
                "_items_parent": RECORD,
                "_items_section": "vehicle",
                "_items_item": "tires",
                "_items_result": "fail",
                "_items_defect": "Front left tread low",
            },
        ]

    def test_a_checklist_with_nothing_called_out_adds_no_children(self):
        assert len(extract.reshape("vehicle_pre_trip", pre_trip({}))) == 1


class TestARemovedRecord:
    def test_a_removed_record_reshapes_to_nothing(self):
        assert extract.reshape("receipts", REMOVED) == []


async def rebuilt_with(session, raw_payload):
    await store.save_raw(
        session,
        source="custom",
        object_type="receipts",
        source_id=RECORD,
        raw_payload=raw_payload,
    )
    await session.commit()
    await run.rebuild(session)


async def custom_ids(session, entity_type):
    rows = await session.execute(
        select(Entity.source_id)
        .where(Entity.source == "custom", Entity.entity_type == entity_type)
        .order_by(Entity.source_id)
    )
    return list(rows.scalars())


async def custom_types(session):
    rows = await session.execute(
        select(Entity.entity_type).where(Entity.source == "custom")
    )
    return set(rows.scalars())


async def custom_facts(session, entity_type, attr):
    rows = await session.execute(
        select(Entity.source_id, EntityFact.value)
        .join(EntityFact, EntityFact.entity_id == Entity.id)
        .where(
            Entity.source == "custom",
            Entity.entity_type == entity_type,
            EntityFact.attr == attr,
        )
    )
    return dict(rows.all())


async def canonical_of(session, entity_type, source_id):
    return (
        await session.execute(
            select(CanonicalMember.canonical_id)
            .join(Entity, Entity.id == CanonicalMember.entity_id)
            .where(
                Entity.source == "custom",
                Entity.entity_type == entity_type,
                Entity.source_id == source_id,
            )
        )
    ).scalar_one()


async def belongs_to(session):
    rows = await session.execute(
        select(CanonicalLink.from_canonical, CanonicalLink.to_canonical).where(
            CanonicalLink.rel == "belongs_to"
        )
    )
    return set(rows.all())


class TestARebuildTurnsAReceiptIntoAnExpense:
    async def test_a_saved_receipt_becomes_one_expense_named_by_its_record(
        self, session
    ):
        await rebuilt_with(session, receipt())
        assert await custom_ids(session, "expense") == [RECORD]

    async def test_the_expense_carries_the_vendor_on_the_receipt(self, session):
        await rebuilt_with(session, receipt())
        assert await custom_facts(session, "expense", "vendor") == {
            RECORD: "Harbor Fuel"
        }

    async def test_each_line_item_becomes_an_expense_item(self, session):
        await rebuilt_with(session, receipt())
        assert await custom_ids(session, "expense_item") == [
            f"{RECORD}:items:0",
            f"{RECORD}:items:1",
        ]

    async def test_each_expense_item_carries_its_description(self, session):
        await rebuilt_with(session, receipt())
        assert await custom_facts(session, "expense_item", "description") == {
            f"{RECORD}:items:0": "Diesel",
            f"{RECORD}:items:1": "Snacks",
        }

    async def test_each_expense_item_belongs_to_its_expense(self, session):
        await rebuilt_with(session, receipt())
        expense = await canonical_of(session, "expense", RECORD)
        items = [
            await canonical_of(session, "expense_item", f"{RECORD}:items:{index}")
            for index in (0, 1)
        ]
        assert await belongs_to(session) == {(item, expense) for item in items}

    async def test_an_edit_that_drops_an_item_removes_it_on_the_next_rebuild(
        self, session
    ):
        await rebuilt_with(session, receipt())
        before = await custom_ids(session, "expense_item")
        await rebuilt_with(session, receipt(items=(DIESEL,)))
        after = await custom_ids(session, "expense_item")
        assert (before, after) == (
            [f"{RECORD}:items:0", f"{RECORD}:items:1"],
            [f"{RECORD}:items:0"],
        )

    async def test_a_removed_marker_drops_the_expense_and_its_items(self, session):
        await rebuilt_with(session, receipt())
        before = await custom_types(session)
        await rebuilt_with(session, REMOVED)
        after = await custom_types(session)
        assert (before, after) == ({"expense", "expense_item"}, set())


def tagged(record, work_done):
    return {
        **saved(
            "maintenance_tags",
            {"asset": "PRESS-02", "work_done": work_done, "status": "working"},
        ),
        "record": record,
    }


async def rebuilt_with_tags(session):
    for record, work_done in (
        (LEAK_FOUND, "Found a slow leak"),
        (SEAL_FITTED, "Replaced hydraulic seal"),
    ):
        await store.save_raw(
            session,
            source="custom",
            object_type="maintenance_tags",
            source_id=record,
            raw_payload=tagged(record, work_done),
        )
    await session.commit()
    return await run.rebuild(session)


async def services(session):
    rows = await session.execute(
        select(CanonicalLink.from_canonical, CanonicalLink.to_canonical).where(
            CanonicalLink.rel == "services"
        )
    )
    return set(rows.all())


class TestTwoServicesOfOneMachine:
    async def test_both_tags_land_on_one_asset_named_by_its_code(self, session):
        await rebuilt_with_tags(session)
        assert await custom_ids(session, "asset") == ["PRESS-02"]

    async def test_each_service_record_links_to_that_asset(self, session):
        await rebuilt_with_tags(session)
        press = await canonical_of(session, "asset", "PRESS-02")
        records = [
            await canonical_of(session, "service_record", record)
            for record in (LEAK_FOUND, SEAL_FITTED)
        ]
        assert await services(session) == {(record, press) for record in records}

    async def test_the_shared_code_is_neither_oversized_nor_quarantined(self, session):
        report = (await rebuilt_with_tags(session))["report"]
        assert (report["oversized"], report["quarantines"]) == ([], [])
