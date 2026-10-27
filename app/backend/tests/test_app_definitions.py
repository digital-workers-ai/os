import copy
import dataclasses

import pytest
import yaml

from app import caches
from app.engine import apps, mappings, ontology
from app.enrichment import vocabulary

INPUTS = ("photo", "pdf", "scan", "voice")
KEYS = (
    "title",
    "description",
    "input",
    "roles",
    "lands_as",
    "fields",
    "template",
    "script",
)
FIELD_TYPES = (
    "text",
    "number",
    "money",
    "date",
    "one_of",
    "many_of",
    "lookup",
    "photo",
    "list",
    "screen",
)
FIELD_OPTIONS = (
    "type",
    "description",
    "labels",
    "labels_from",
    "unit",
    "entity",
    "by",
    "from",
    "history",
    "filled_by",
    "fields",
    "lands_as",
    "file",
)

NO_LABELS = (
    "has no labels — a question with no possible answer generates an empty "
    "enum, which the API rejects with a message about JSON Schema rather than "
    "about this file"
)
NOT_SNAKE_LABEL = (
    "is not snake_case. Labels are stored, compared and grouped — 'Strong' and "
    "'strong' looking like one value in a report and two in a GROUP BY is "
    "discovered a quarter later"
)
RANGE = "must be a non-empty list or a range like 1-32"

TALLY = {
    "title": "Tally",
    "description": "A count of what came in.",
    "input": ["photo", "scan"],
    "roles": ["staff", "finance"],
    "lands_as": "tally",
    "fields": {
        "vendor": {"type": "text", "description": "Who sold it"},
        "odometer": {"type": "number", "unit": "mi"},
        "total": {"type": "money"},
        "day": {"type": "date"},
        "category": {
            "type": "one_of",
            "labels": {"fuel": "Gas or diesel", "meals": "Food and drink"},
        },
        "damage": {"type": "many_of", "labels": ["broken", "dented"]},
        "customer": {"type": "lookup", "entity": "company", "by": "name"},
        "asset": {
            "type": "lookup",
            "entity": "asset",
            "by": "code",
            "from": "scan",
            "history": True,
        },
        "snapshot": {"type": "photo"},
        "lines": {
            "type": "list",
            "lands_as": "tally_line",
            "fields": {
                "description": {"type": "text"},
                "amount": {"type": "money"},
            },
        },
    },
}
CHART = {
    "title": "Chart",
    "input": "voice",
    "roles": ["dentist"],
    "lands_as": "chart",
    "fields": {"patient": {"type": "text"}},
    "template": {
        "grid": {
            "rows": {
                "name": "tooth",
                "values": "1-3",
                "lands_as": "chart_tooth",
                "fields": {
                    "status": {"type": "one_of", "labels": ["present", "missing"]}
                },
            },
            "columns": {"name": "site", "values": ["B", "L"]},
            "cells": {
                "lands_as": "chart_site",
                "fields": {"depth": {"type": "number", "unit": "mm"}},
            },
        }
    },
}
PRETRIP = {
    "title": "Pre-trip",
    "input": "voice",
    "roles": ["driver"],
    "lands_as": "pretrip",
    "fields": {"vehicle": {"type": "text"}},
    "template": {
        "checklist": {
            "sections": {"vehicle": ["tires", "horn"]},
            "items": {
                "lands_as": "pretrip_item",
                "fields": {"result": {"type": "one_of", "labels": ["pass", "fail"]}},
            },
        }
    },
}
MILEAGE = {
    "title": "Mileage",
    "input": "photo",
    "roles": ["staff"],
    "lands_as": "trip",
    "fields": {
        "odometer": {"type": "number", "unit": "mi"},
        "miles": {"type": "number", "unit": "mi", "filled_by": "script"},
    },
    "script": "script.py",
}
DELIVERY = {
    "title": "Delivery",
    "input": "photo",
    "roles": ["driver"],
    "lands_as": "delivery",
    "fields": {
        "signature": {"type": "screen", "file": "screen.tsx"},
        "interest": {"type": "one_of", "labels_from": "sales_call.interest"},
    },
}
APPS = {
    "tally": TALLY,
    "chart": CHART,
    "pretrip": PRETRIP,
    "mileage": MILEAGE,
    "delivery": DELIVERY,
}

ONTOLOGY = {
    "entities": {
        "tally": {
            "attrs": {
                "vendor": "string",
                "odometer": "number",
                "total": "number",
                "day": "date",
                "category": "string",
                "damage": "string",
                "customer": "string",
                "asset": "string",
                "snapshot": "string",
            }
        },
        "tally_line": {
            "attrs": {
                "tally_ref": "string",
                "description": "string",
                "amount": "number",
            }
        },
        "company": {"attrs": {"name": "string"}},
        "asset": {"attrs": {"code": "string", "name": "string"}},
        "chart": {"attrs": {"patient": "string"}},
        "chart_tooth": {"attrs": {"chart_ref": "string", "status": "string"}},
        "chart_site": {"attrs": {"chart_ref": "string", "depth": "number"}},
        "pretrip": {"attrs": {"vehicle": "string"}},
        "pretrip_item": {"attrs": {"pretrip_ref": "string", "result": "string"}},
        "trip": {"attrs": {"odometer": "number", "miles": "number"}},
        "delivery": {"attrs": {"signature": "string", "interest": "string"}},
        "meeting": {"attrs": {"transcript": "string"}},
    }
}
MAPPINGS = {
    "tally": {
        "custom.tally.vendor": "vendor",
        "custom.tally.odometer": "odometer",
        "custom.tally.total": "total",
        "custom.tally.day": "day",
        "custom.tally.category": "category",
        "custom.tally.damage": "damage",
        "custom.tally.customer": "customer",
        "custom.tally.asset": "asset",
        "custom.tally.snapshot": "snapshot",
    },
    "tally_line": {
        "custom.tally._lines_description": "description",
        "custom.tally._lines_amount": "amount",
    },
    "chart": {"custom.chart.patient": "patient"},
    "chart_tooth": {"custom.chart._rows_status": "status"},
    "chart_site": {"custom.chart._cells_depth": "depth"},
    "pretrip": {"custom.pretrip.vehicle": "vehicle"},
    "pretrip_item": {"custom.pretrip._items_result": "result"},
    "trip": {
        "custom.mileage.odometer": "odometer",
        "custom.mileage.miles": "miles",
    },
    "delivery": {
        "custom.delivery.signature": "signature",
        "custom.delivery.interest": "interest",
    },
}
ENRICHMENT = {
    "readings": {
        "sales_call": {
            "entity": "meeting",
            "input": "transcript",
            "fields": {
                "interest": {
                    "type": "one_of",
                    "labels": {"strong": "Ready to buy", "weak": "Just looking"},
                }
            },
        }
    }
}

STATUS = ("template", "grid", "rows", "fields", "status")
FIELD_PATHS = [
    ("tally", ("fields", "vendor")),
    ("tally", ("fields", "lines", "fields", "amount")),
    ("chart", STATUS),
    ("chart", ("template", "grid", "cells", "fields", "depth")),
    ("pretrip", ("template", "checklist", "items", "fields", "result")),
]
CONTAINERS = [
    ("tally", ()),
    ("tally", ("fields", "lines")),
    ("chart", ("template", "grid", "rows")),
    ("chart", ("template", "grid", "cells")),
    ("pretrip", ("template", "checklist", "items")),
]
CHILDREN = CONTAINERS[1:]
PARTS = [
    ("chart", "grid", "rows"),
    ("chart", "grid", "columns"),
    ("chart", "grid", "cells"),
    ("pretrip", "checklist", "sections"),
    ("pretrip", "checklist", "items"),
]
PARENT_FIELDS = [
    ("tally", "vendor"),
    ("tally", "odometer"),
    ("tally", "total"),
    ("tally", "day"),
    ("tally", "category"),
    ("tally", "damage"),
    ("tally", "customer"),
    ("tally", "asset"),
    ("tally", "snapshot"),
    ("chart", "patient"),
    ("pretrip", "vehicle"),
    ("mileage", "odometer"),
    ("mileage", "miles"),
    ("delivery", "signature"),
    ("delivery", "interest"),
]
CHILD_FIELDS = [
    ("tally", "fields.lines.fields.description", "custom.tally._lines_description"),
    ("tally", "fields.lines.fields.amount", "custom.tally._lines_amount"),
    ("chart", "template.grid.rows.fields.status", "custom.chart._rows_status"),
    ("chart", "template.grid.cells.fields.depth", "custom.chart._cells_depth"),
    (
        "pretrip",
        "template.checklist.items.fields.result",
        "custom.pretrip._items_result",
    ),
]

SHIPPED = {
    "receipts": (("photo",), "expense"),
    "supplier_invoices": (("photo", "pdf"), "bill"),
    "mileage_log": (("photo",), "odometer_reading"),
    "shelf_audit": (("photo",), "stock_check"),
    "damage_claims": (("photo",), "claim"),
    "check_deposits": (("photo",), "payment"),
    "equipment_checkout": (("scan",), "asset_move"),
    "inventory_count": (("scan",), "stock_count"),
    "event_check_in": (("scan",), "check_in"),
    "maintenance_tags": (("scan",), "service_record"),
    "mailroom": (("scan", "photo"), "package"),
    "batch_trace": (("scan",), "batch_step"),
    "perio_charting": (("voice",), "perio_chart"),
    "property_inspection": (("voice", "photo"), "inspection"),
    "vehicle_pre_trip": (("voice",), "vehicle_check"),
    "food_safety_log": (("voice",), "temperature_check"),
    "site_safety_walk": (("voice", "photo"), "safety_walk"),
    "sales_visit_debrief": (("voice",), "meeting"),
    "vet_visit_notes": (("voice",), "visit_note"),
    "field_service_report": (("voice",), "ticket"),
    "proof_of_delivery": (("photo",), "delivery"),
}
SCRIPTED = ("inventory_count", "mileage_log", "shelf_audit")

ABSENT = object()


def _dump(path, doc):
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def _part(doc, path):
    for key in path:
        doc = doc[key]
    return doc


def _put(part, key, value):
    if value is ABSENT:
        part.pop(key)
    else:
        part[key] = value


def _shown(value):
    return None if value is ABSENT else value


def _dotted(path):
    return ".".join(path)


def _refused(app, problem):
    return [f"apps/{app}/app.yaml: {problem}"]


def _field(name, kind, **given):
    values = {
        "description": "",
        "labels": (),
        "unit": None,
        "entity": None,
        "by": None,
        "from_scan": False,
        "history": False,
        "by_script": False,
        "fields": (),
        "lands_as": None,
        "file": None,
        **given,
    }
    return apps.Field(name=name, type=kind, **values)


def _named(fields):
    return {field.name: field for field in fields}


class Tree:
    def __init__(self, root):
        self.definitions = root / "definitions"
        self.apps_dir = self.definitions / "apps"
        self.scripts = root / "scripts"

    def write(self, name, doc):
        folder = self.apps_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        _dump(folder / "app.yaml", doc)

    def edit(self, name, mutate):
        path = self.apps_dir / name / "app.yaml"
        doc = yaml.safe_load(path.read_text())
        mutate(doc)
        _dump(path, doc)

    def unmap(self, key):
        path = self.definitions / "mappings.yaml"
        doc = yaml.safe_load(path.read_text())
        for lines in doc.values():
            lines.pop(key, None)
        _dump(path, doc)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    built = Tree(tmp_path)
    built.definitions.mkdir()
    _dump(built.definitions / "ontology.yaml", ONTOLOGY)
    _dump(built.definitions / "mappings.yaml", MAPPINGS)
    _dump(built.definitions / "enrichment.yaml", ENRICHMENT)
    for name, doc in APPS.items():
        built.write(name, doc)
    (built.scripts / "mileage").mkdir(parents=True)
    (built.scripts / "mileage" / "script.py").write_text("")
    monkeypatch.setattr(
        ontology, "DEFAULT_ONTOLOGY", built.definitions / "ontology.yaml"
    )
    monkeypatch.setattr(
        mappings, "DEFAULT_MAPPINGS", built.definitions / "mappings.yaml"
    )
    monkeypatch.setattr(
        vocabulary,
        "DEFAULT_ENRICHMENT_FILES",
        [built.definitions / "enrichment.yaml"],
    )
    monkeypatch.setattr(apps, "APPS_DIR", built.apps_dir)
    monkeypatch.setattr(apps, "SCRIPTS_DIR", built.scripts)
    caches.reset_all()
    yield built
    caches.reset_all()


class TestTheConstants:
    def test_the_inputs(self):
        assert apps.INPUTS == INPUTS

    def test_the_keys(self):
        assert apps.KEYS == KEYS

    def test_the_field_types(self):
        assert apps.FIELD_TYPES == FIELD_TYPES

    def test_the_field_options(self):
        assert apps.FIELD_OPTIONS == FIELD_OPTIONS

    def test_the_apps_live_under_definitions(self):
        assert apps.APPS_DIR == caches.DEFINITIONS_DIR / "apps"

    def test_the_scripts_live_under_the_custom_engine(self):
        assert apps.SCRIPTS_DIR == caches.BACKEND_DIR / "app" / "custom" / "apps"

    def test_an_app_error_is_a_value_error(self):
        assert issubclass(apps.AppError, ValueError)


class TestNamesAndLoad:
    def test_names_lists_the_app_folders_sorted(self, tree):
        (tree.apps_dir / "notes.txt").write_text("x")
        assert apps.names() == sorted(APPS)

    def test_apps_maps_each_name_to_its_app(self, tree):
        loaded = {name: app.name for name, app in apps.apps().items()}
        assert loaded == {name: name for name in APPS}

    def test_load_returns_the_named_app(self, tree):
        assert apps.load("tally").name == "tally"

    def test_load_refuses_an_unknown_app(self, tree):
        with pytest.raises(apps.AppError) as refused:
            apps.load("nope")
        assert str(refused.value) == f"no app named 'nope' — known: {sorted(APPS)}"

    def test_load_refuses_a_malformed_app(self, tree):
        tree.edit("tally", lambda d: d.update({"colour": "red"}))
        with pytest.raises(apps.AppError) as refused:
            apps.load("tally")
        assert [str(refused.value)] == _refused(
            "tally", f"unknown key 'colour' — known: {list(KEYS)}"
        )

    def test_apps_are_read_once_until_the_caches_reset(self, tree):
        first = apps.apps()
        assert apps.apps() is first
        tree.write("spare", TALLY)
        assert "spare" not in apps.apps()
        caches.reset_all()
        assert "spare" in apps.apps()


class TestAnAppLoads:
    def test_the_app_carries_its_title_and_description(self, tree):
        app = apps.load("tally")
        assert (app.title, app.description) == ("Tally", "A count of what came in.")

    def test_a_missing_description_reads_as_empty(self, tree):
        assert apps.load("chart").description == ""

    def test_a_list_of_inputs_keeps_its_order(self, tree):
        assert apps.load("tally").inputs == ("photo", "scan")

    def test_a_single_input_is_a_one_item_tuple(self, tree):
        assert apps.load("chart").inputs == ("voice",)

    def test_the_roles_are_a_tuple(self, tree):
        assert apps.load("tally").roles == ("staff", "finance")

    def test_lands_as_names_the_entity(self, tree):
        assert apps.load("tally").lands_as == "tally"

    def test_the_fields_keep_their_order(self, tree):
        assert [field.name for field in apps.load("tally").fields] == list(
            TALLY["fields"]
        )

    def test_an_app_without_a_template_or_a_script(self, tree):
        app = apps.load("tally")
        assert (app.template, app.script) == (None, None)

    def test_a_script_is_named(self, tree):
        assert apps.load("mileage").script == "script.py"

    @pytest.mark.parametrize(
        "app,name,kind,given",
        [
            ("tally", "vendor", "text", {"description": "Who sold it"}),
            ("tally", "odometer", "number", {"unit": "mi"}),
            ("tally", "total", "money", {}),
            ("tally", "day", "date", {}),
            (
                "tally",
                "category",
                "one_of",
                {"labels": (("fuel", "Gas or diesel"), ("meals", "Food and drink"))},
            ),
            (
                "tally",
                "damage",
                "many_of",
                {"labels": (("broken", ""), ("dented", ""))},
            ),
            ("tally", "customer", "lookup", {"entity": "company", "by": "name"}),
            (
                "tally",
                "asset",
                "lookup",
                {"entity": "asset", "by": "code", "from_scan": True, "history": True},
            ),
            ("tally", "snapshot", "photo", {}),
            ("mileage", "miles", "number", {"unit": "mi", "by_script": True}),
            ("delivery", "signature", "screen", {"file": "screen.tsx"}),
        ],
        ids=[
            "text",
            "number",
            "money",
            "date",
            "one_of_mapping",
            "many_of_list",
            "lookup",
            "lookup_from_scan_with_history",
            "photo",
            "filled_by_script",
            "screen",
        ],
    )
    def test_a_field_loads_with_its_options(self, tree, app, name, kind, given):
        assert _named(apps.load(app).fields)[name] == _field(name, kind, **given)

    def test_labels_from_take_the_readings_labels_and_meanings(self, tree):
        assert _named(apps.load("delivery").fields)["interest"] == _field(
            "interest",
            "one_of",
            labels=(("strong", "Ready to buy"), ("weak", "Just looking")),
        )

    def test_a_list_holds_its_fields_and_lands_as(self, tree):
        assert _named(apps.load("tally").fields)["lines"] == _field(
            "lines",
            "list",
            lands_as="tally_line",
            fields=(_field("description", "text"), _field("amount", "money")),
        )

    def test_a_grid_loads_its_rows_columns_and_cells(self, tree):
        assert apps.load("chart").template == apps.Template(
            kind="grid",
            rows={
                "name": "tooth",
                "values": ("1", "2", "3"),
                "lands_as": "chart_tooth",
                "fields": (
                    _field(
                        "status", "one_of", labels=(("present", ""), ("missing", ""))
                    ),
                ),
            },
            columns={"name": "site", "values": ("B", "L")},
            cells={
                "lands_as": "chart_site",
                "fields": (_field("depth", "number", unit="mm"),),
            },
            sections=None,
            items=None,
        )

    def test_a_checklist_loads_its_sections_and_items(self, tree):
        assert apps.load("pretrip").template == apps.Template(
            kind="checklist",
            rows=None,
            columns=None,
            cells=None,
            sections={"vehicle": ("tires", "horn")},
            items={
                "lands_as": "pretrip_item",
                "fields": (
                    _field("result", "one_of", labels=(("pass", ""), ("fail", ""))),
                ),
            },
        )

    @pytest.mark.parametrize(
        "values,expected",
        [
            ("1-32", tuple(str(n) for n in range(1, 33))),
            ("8-11", ("8", "9", "10", "11")),
            ("3-3", ("3",)),
        ],
        ids=["teeth", "past_one_digit", "one_value"],
    )
    def test_an_integer_range_expands_to_its_values(self, tree, values, expected):
        tree.edit("chart", lambda d: _part(d, STATUS[:3]).update({"values": values}))
        assert apps.load("chart").template.rows["values"] == expected

    def test_whole_number_labels_load_as_text(self, tree):
        tree.edit("chart", lambda d: _part(d, STATUS).update({"labels": ["0", "1"]}))
        status = apps.load("chart").template.rows["fields"][0]
        assert status.labels == (("0", ""), ("1", ""))

    def test_a_lookup_without_by_reads_by_as_none(self, tree):
        tree.edit("tally", lambda d: d["fields"]["customer"].pop("by"))
        assert _named(apps.load("tally").fields)["customer"].by is None

    def test_an_app_is_frozen(self, tree):
        with pytest.raises(dataclasses.FrozenInstanceError):
            apps.load("tally").title = "Other"

    def test_a_field_is_frozen(self, tree):
        with pytest.raises(dataclasses.FrozenInstanceError):
            apps.load("tally").fields[0].name = "other"

    def test_a_template_is_frozen(self, tree):
        with pytest.raises(dataclasses.FrozenInstanceError):
            apps.load("chart").template.kind = "checklist"


class TestParse:
    def test_parse_builds_the_app_that_load_builds(self, tree):
        assert apps.parse("tally", copy.deepcopy(TALLY)) == apps.load("tally")

    def test_a_draft_needs_no_mapping_line_to_be_tried(self, tree):
        assert apps.parse("draft", copy.deepcopy(TALLY)).name == "draft"

    def test_a_draft_needs_no_script_file_to_be_tried(self, tree):
        assert apps.parse("draft", copy.deepcopy(MILEAGE)).script == "script.py"

    def test_a_malformed_draft_is_refused_with_an_app_error(self, tree):
        with pytest.raises(apps.AppError) as refused:
            apps.parse("draft", {**copy.deepcopy(TALLY), "colour": "red"})
        assert [str(refused.value)] == _refused(
            "draft", f"unknown key 'colour' — known: {list(KEYS)}"
        )

    @pytest.mark.parametrize("raw", [["title"], "Tally"], ids=["a_list", "a_string"])
    def test_a_draft_that_is_not_a_mapping_is_refused(self, tree, raw):
        with pytest.raises(apps.AppError) as refused:
            apps.parse("draft", raw)
        assert [str(refused.value)] == _refused("draft", "top level must be a mapping")


class TestCheckPassesCleanApps:
    def test_clean_apps_pass(self, tree):
        assert apps.check(tree.apps_dir) == []

    def test_check_reads_the_apps_dir_by_default(self, tree):
        tree.edit("tally", lambda d: d.update({"colour": "red"}))
        assert apps.check() == _refused(
            "tally", f"unknown key 'colour' — known: {list(KEYS)}"
        )

    def test_an_empty_folder_passes(self, tmp_path):
        assert apps.check(tmp_path) == []

    def test_a_file_beside_the_apps_is_not_an_app(self, tree):
        (tree.apps_dir / "README.md").write_text("x")
        assert apps.check(tree.apps_dir) == []

    def test_whole_number_labels_pass(self, tree):
        tree.edit(
            "chart",
            lambda d: _part(d, STATUS).update({"labels": ["0", "1", "2", "3"]}),
        )
        assert apps.check(tree.apps_dir) == []

    def test_a_lookup_without_by_passes(self, tree):
        tree.edit("tally", lambda d: d["fields"]["customer"].pop("by"))
        assert apps.check(tree.apps_dir) == []


class TestCheckRefusesTheFile:
    def test_a_missing_folder_is_one_problem(self, tmp_path):
        folder = tmp_path / "nowhere"
        assert apps.check(folder) == [f"apps/: {folder} is not a directory"]

    def test_a_folder_without_an_app_file(self, tree):
        (tree.apps_dir / "bare").mkdir()
        assert apps.check(tree.apps_dir) == _refused(
            "bare", "the folder has no app.yaml"
        )

    def test_an_app_file_that_is_not_a_mapping(self, tree):
        (tree.apps_dir / "tally" / "app.yaml").write_text("- a\n")
        assert apps.check(tree.apps_dir) == _refused(
            "tally", "top level must be a mapping"
        )

    def test_an_app_file_that_does_not_parse(self, tree):
        (tree.apps_dir / "tally" / "app.yaml").write_text("title: [\n")
        problems = apps.check(tree.apps_dir)
        assert len(problems) == 1, problems
        assert problems[0].startswith("apps/tally/app.yaml: does not parse — ")

    @pytest.mark.parametrize("name", ["Receipts", "receipt-log", "2nd_shift"])
    def test_a_folder_name_that_is_not_snake_case(self, tree, name):
        tree.write(name, TALLY)
        assert apps.check(tree.apps_dir) == _refused(
            name, f"app name {name!r} is not snake_case"
        )

    def test_every_app_is_checked_in_folder_order(self, tree):
        tree.edit("tally", lambda d: d.pop("title"))
        tree.edit("chart", lambda d: d.pop("title"))
        assert apps.check(tree.apps_dir) == [
            *_refused("chart", "title must be non-empty text"),
            *_refused("tally", "title must be non-empty text"),
        ]


class TestCheckRefusesTheTopLevel:
    def test_an_unknown_key(self, tree):
        tree.edit("tally", lambda d: d.update({"colour": "red"}))
        assert apps.check(tree.apps_dir) == _refused(
            "tally", f"unknown key 'colour' — known: {list(KEYS)}"
        )

    @pytest.mark.parametrize(
        "title", [ABSENT, "", "   "], ids=["absent", "empty", "blank"]
    )
    def test_a_missing_title(self, tree, title):
        tree.edit("tally", lambda d: _put(d, "title", title))
        assert apps.check(tree.apps_dir) == _refused(
            "tally", "title must be non-empty text"
        )

    @pytest.mark.parametrize(
        "value", ["fax", ["photo", "fax"]], ids=["one", "in_a_list"]
    )
    def test_an_unknown_input(self, tree, value):
        tree.edit("mileage", lambda d: d.update({"input": value}))
        assert apps.check(tree.apps_dir) == _refused(
            "mileage", f"input 'fax' is not one of {list(INPUTS)}"
        )

    @pytest.mark.parametrize(
        "value", [ABSENT, [], 7], ids=["absent", "empty", "a_number"]
    )
    def test_no_input(self, tree, value):
        tree.edit("mileage", lambda d: _put(d, "input", value))
        assert apps.check(tree.apps_dir) == _refused(
            "mileage",
            f"input must be one of {list(INPUTS)} or a non-empty list of them",
        )

    @pytest.mark.parametrize(
        "roles", [ABSENT, [], "staff"], ids=["absent", "empty", "a_string"]
    )
    def test_roles_that_are_not_a_non_empty_list(self, tree, roles):
        tree.edit("tally", lambda d: _put(d, "roles", roles))
        assert apps.check(tree.apps_dir) == _refused(
            "tally", "roles must be a non-empty list of snake_case names"
        )

    @pytest.mark.parametrize("role", ["Front Desk", "front-desk", "Staff", "2nd_shift"])
    def test_a_role_that_is_not_snake_case(self, tree, role):
        tree.edit("tally", lambda d: d.update({"roles": ["staff", role]}))
        assert apps.check(tree.apps_dir) == _refused(
            "tally", f"role {role!r} is not snake_case"
        )

    @pytest.mark.parametrize("value", [ABSENT, "invoice"], ids=["absent", "unknown"])
    def test_lands_as_outside_the_ontology(self, tree, value):
        tree.edit("tally", lambda d: _put(d, "lands_as", value))
        assert apps.check(tree.apps_dir) == _refused(
            "tally", f"lands_as {_shown(value)!r} is not an entity in ontology.yaml"
        )

    def test_a_script_other_than_script_py(self, tree):
        tree.edit("mileage", lambda d: d.update({"script": "fill.py"}))
        assert apps.check(tree.apps_dir) == _refused(
            "mileage", "script 'fill.py' must be script.py"
        )

    def test_a_script_whose_file_is_missing(self, tree):
        (tree.scripts / "mileage" / "script.py").unlink()
        assert apps.check(tree.apps_dir) == _refused(
            "mileage", "app/custom/apps/mileage/script.py is missing"
        )


class TestCheckRefusesAField:
    @pytest.mark.parametrize(
        "app,path", CONTAINERS, ids=["app", "list", "rows", "cells", "items"]
    )
    @pytest.mark.parametrize(
        "value",
        [ABSENT, None, {}, [], "vendor"],
        ids=["absent", "null", "empty", "a_list", "a_string"],
    )
    def test_fields_that_are_not_a_non_empty_mapping(self, tree, app, path, value):
        tree.edit(app, lambda d: _put(_part(d, path), "fields", value))
        assert apps.check(tree.apps_dir) == _refused(
            app,
            f"{_dotted((*path, 'fields'))} must be a non-empty mapping of field name "
            "to options",
        )

    @pytest.mark.parametrize(
        "app,path",
        [FIELD_PATHS[0], FIELD_PATHS[1], FIELD_PATHS[3]],
        ids=["app", "list", "cells"],
    )
    @pytest.mark.parametrize(
        "value", [None, "text", ["text"]], ids=["null", "a_string", "a_list"]
    )
    def test_a_field_that_is_not_a_mapping_of_options(self, tree, app, path, value):
        tree.edit(app, lambda d: _part(d, path[:-1]).update({path[-1]: value}))
        assert apps.check(tree.apps_dir) == _refused(
            app, f"{_dotted(path)} must be a mapping of options"
        )

    @pytest.mark.parametrize(
        "app,path", FIELD_PATHS, ids=["app", "list", "rows", "cells", "items"]
    )
    @pytest.mark.parametrize(
        "value", [ABSENT, "string", "cash"], ids=["absent", "string", "cash"]
    )
    def test_an_unknown_field_type(self, tree, app, path, value):
        tree.edit(app, lambda d: _put(_part(d, path), "type", value))
        assert apps.check(tree.apps_dir) == _refused(
            app,
            f"{_dotted(path)} type {_shown(value)!r} is not one of {list(FIELD_TYPES)}",
        )

    @pytest.mark.parametrize(
        "app,path", FIELD_PATHS, ids=["app", "list", "rows", "cells", "items"]
    )
    def test_an_unknown_field_option(self, tree, app, path):
        tree.edit(app, lambda d: _part(d, path).update({"colour": "red"}))
        assert apps.check(tree.apps_dir) == _refused(
            app,
            f"{_dotted(path)}: unknown option 'colour' — known: {list(FIELD_OPTIONS)}",
        )

    @pytest.mark.parametrize(
        "labels,problem",
        [
            ("fuel", "labels must be a list or a label: meaning mapping, got str"),
            (
                ABSENT,
                "labels must be a list or a label: meaning mapping, got NoneType",
            ),
            ([], NO_LABELS),
            ({}, NO_LABELS),
            (["fuel", "fuel"], "has duplicate label 'fuel'"),
            (["Fuel"], f"label 'Fuel' {NOT_SNAKE_LABEL}"),
            (["very fuel"], f"label 'very fuel' {NOT_SNAKE_LABEL}"),
        ],
        ids=[
            "a_string",
            "absent",
            "an_empty_list",
            "an_empty_mapping",
            "a_duplicate",
            "capitalised",
            "with_a_space",
        ],
    )
    def test_labels_that_do_not_parse(self, tree, labels, problem):
        tree.edit("tally", lambda d: _put(d["fields"]["category"], "labels", labels))
        assert apps.check(tree.apps_dir) == _refused(
            "tally", f"fields.category {problem}"
        )

    def test_many_of_labels_parse_the_same_way(self, tree):
        tree.edit("tally", lambda d: d["fields"]["damage"].update({"labels": []}))
        assert apps.check(tree.apps_dir) == _refused(
            "tally", f"fields.damage {NO_LABELS}"
        )

    @pytest.mark.parametrize(
        "source,problem",
        [
            (
                "nope.interest",
                "labels_from 'nope.interest' names no reading in enrichment.yaml",
            ),
            (
                "sales_call.nope",
                "labels_from 'sales_call.nope' names no field of reading 'sales_call'",
            ),
            (
                "sales_call",
                "labels_from 'sales_call' names no field of reading 'sales_call'",
            ),
        ],
        ids=["unknown_reading", "unknown_field", "no_field"],
    )
    def test_labels_from_that_resolve_to_nothing(self, tree, source, problem):
        tree.edit(
            "delivery",
            lambda d: d["fields"]["interest"].update({"labels_from": source}),
        )
        assert apps.check(tree.apps_dir) == _refused(
            "delivery", f"fields.interest {problem}"
        )

    @pytest.mark.parametrize("entity", [ABSENT, "client"], ids=["absent", "unknown"])
    def test_a_lookup_to_an_entity_outside_the_ontology(self, tree, entity):
        tree.edit("tally", lambda d: _put(d["fields"]["customer"], "entity", entity))
        assert apps.check(tree.apps_dir) == _refused(
            "tally",
            f"fields.customer entity {_shown(entity)!r} is not an entity in "
            "ontology.yaml",
        )

    def test_a_lookup_by_an_attr_the_entity_lacks(self, tree):
        tree.edit("tally", lambda d: d["fields"]["customer"].update({"by": "nickname"}))
        assert apps.check(tree.apps_dir) == _refused(
            "tally",
            "fields.customer by 'nickname' is not an attr of company in ontology.yaml",
        )

    def test_from_scan_on_an_app_without_scan(self, tree):
        tree.edit("tally", lambda d: d.update({"input": "photo"}))
        assert apps.check(tree.apps_dir) == _refused(
            "tally", "fields.asset from: scan needs scan in input"
        )

    def test_from_anything_but_scan(self, tree):
        tree.edit("tally", lambda d: d["fields"]["asset"].update({"from": "photo"}))
        assert apps.check(tree.apps_dir) == _refused(
            "tally", "fields.asset from 'photo' can only be scan"
        )

    def test_filled_by_script_on_an_app_without_a_script(self, tree):
        tree.edit("mileage", lambda d: d.pop("script"))
        assert apps.check(tree.apps_dir) == _refused(
            "mileage", "fields.miles filled_by: script needs a script"
        )

    def test_filled_by_anything_but_script(self, tree):
        tree.edit(
            "mileage", lambda d: d["fields"]["miles"].update({"filled_by": "hand"})
        )
        assert apps.check(tree.apps_dir) == _refused(
            "mileage", "fields.miles filled_by 'hand' can only be script"
        )

    @pytest.mark.parametrize(
        "file", [ABSENT, "pad.tsx", "screen.jsx"], ids=["absent", "other", "jsx"]
    )
    def test_a_screen_whose_file_is_not_screen_tsx(self, tree, file):
        tree.edit("delivery", lambda d: _put(d["fields"]["signature"], "file", file))
        assert apps.check(tree.apps_dir) == _refused(
            "delivery", f"fields.signature file {_shown(file)!r} must be screen.tsx"
        )

    @pytest.mark.parametrize(
        "app,path", CHILDREN, ids=["list", "rows", "cells", "items"]
    )
    @pytest.mark.parametrize("value", [ABSENT, "nowhere"], ids=["absent", "unknown"])
    def test_a_child_that_lands_outside_the_ontology(self, tree, app, path, value):
        tree.edit(app, lambda d: _put(_part(d, path), "lands_as", value))
        assert apps.check(tree.apps_dir) == _refused(
            app,
            f"{_dotted(path)} lands_as {_shown(value)!r} is not an entity in "
            "ontology.yaml",
        )


class TestCheckRefusesATemplate:
    @pytest.mark.parametrize(
        "template",
        [{}, "grid", {"table": {}}, {**CHART["template"], **PRETRIP["template"]}],
        ids=["empty", "a_string", "unknown_kind", "both_kinds"],
    )
    def test_a_template_that_is_not_exactly_one_kind(self, tree, template):
        tree.edit("chart", lambda d: d.update({"template": template}))
        assert apps.check(tree.apps_dir) == _refused(
            "chart", "template must be exactly one of ['grid', 'checklist']"
        )

    @pytest.mark.parametrize(
        "app,kind,part",
        PARTS,
        ids=["rows", "columns", "cells", "sections", "items"],
    )
    @pytest.mark.parametrize(
        "value",
        [ABSENT, {}, [], "tooth"],
        ids=["absent", "empty", "a_list", "a_string"],
    )
    def test_a_part_that_is_not_a_non_empty_mapping(self, tree, app, kind, part, value):
        tree.edit(app, lambda d: _put(d["template"][kind], part, value))
        assert apps.check(tree.apps_dir) == _refused(
            app, f"template.{kind}.{part} must be a non-empty mapping"
        )

    @pytest.mark.parametrize("part", ["rows", "columns"])
    @pytest.mark.parametrize("name", [ABSENT, ""], ids=["absent", "empty"])
    def test_a_grid_axis_without_a_name(self, tree, part, name):
        tree.edit("chart", lambda d: _put(d["template"]["grid"][part], "name", name))
        assert apps.check(tree.apps_dir) == _refused(
            "chart", f"template.grid.{part} needs a name"
        )

    @pytest.mark.parametrize(
        "values",
        [ABSENT, "3-1", "one-three", "1-", "-3", "7", 7, []],
        ids=[
            "absent",
            "backwards",
            "words",
            "no_end",
            "no_start",
            "one_number_as_text",
            "one_number",
            "an_empty_list",
        ],
    )
    def test_row_values_that_are_neither_a_list_nor_a_range(self, tree, values):
        tree.edit(
            "chart", lambda d: _put(d["template"]["grid"]["rows"], "values", values)
        )
        assert apps.check(tree.apps_dir) == _refused(
            "chart", f"template.grid.rows values {_shown(values)!r} {RANGE}"
        )

    def test_column_values_are_required(self, tree):
        tree.edit("chart", lambda d: d["template"]["grid"]["columns"].pop("values"))
        assert apps.check(tree.apps_dir) == _refused(
            "chart", f"template.grid.columns values None {RANGE}"
        )

    @pytest.mark.parametrize(
        "items", ["tires", [], None], ids=["a_string", "empty", "null"]
    )
    def test_a_section_that_is_not_a_list_of_items(self, tree, items):
        tree.edit(
            "pretrip",
            lambda d: d["template"]["checklist"]["sections"].update({"vehicle": items}),
        )
        assert apps.check(tree.apps_dir) == _refused(
            "pretrip",
            "template.checklist.sections.vehicle must be a non-empty list of items",
        )


class TestCheckWantsAMappingLine:
    @pytest.mark.parametrize(
        "app,field", PARENT_FIELDS, ids=[f"{a}.{f}" for a, f in PARENT_FIELDS]
    )
    def test_a_parent_field_without_its_mapping_line(self, tree, app, field):
        tree.unmap(f"custom.{app}.{field}")
        assert apps.check(tree.apps_dir) == _refused(
            app,
            f"fields.{field} needs a mapping line custom.{app}.{field} in "
            "mappings.yaml",
        )

    @pytest.mark.parametrize(
        "app,where,key",
        CHILD_FIELDS,
        ids=["list_row", "list_row_money", "grid_row", "grid_cell", "checklist_item"],
    )
    def test_a_child_field_without_its_mapping_line(self, tree, app, where, key):
        tree.unmap(key)
        assert apps.check(tree.apps_dir) == _refused(
            app, f"{where} needs a mapping line {key} in mappings.yaml"
        )


class TestTheShippedApps:
    def test_the_twenty_one_apps_ship(self):
        assert apps.names() == sorted(SHIPPED)

    def test_they_pass_check(self):
        assert apps.check() == []

    @pytest.mark.parametrize("name", sorted(SHIPPED))
    def test_each_loads_with_its_inputs_and_entity(self, name):
        app = apps.load(name)
        assert (app.name, app.inputs, app.lands_as) == (name, *SHIPPED[name])

    def test_three_apps_bring_a_script(self):
        scripts = {name: app.script for name, app in apps.apps().items() if app.script}
        assert scripts == dict.fromkeys(SCRIPTED, "script.py")

    def test_proof_of_delivery_draws_its_signature_on_its_own_screen(self):
        screens = [
            (name, field.name, field.file)
            for name, app in apps.apps().items()
            for field in app.fields
            if field.type == "screen"
        ]
        assert screens == [("proof_of_delivery", "signature", "screen.tsx")]

    def test_perio_charting_charts_thirty_two_teeth_at_six_sites(self):
        template = apps.load("perio_charting").template
        assert template.rows["values"] == tuple(str(n) for n in range(1, 33))
        assert template.columns["values"] == ("DB", "B", "MB", "DL", "L", "ML")

    def test_the_sales_debrief_reuses_the_sales_call_interest_labels(self):
        interest = _named(apps.load("sales_visit_debrief").fields)["interest"]
        reading = _named(vocabulary.load()["sales_call"].fields)["interest"]
        assert interest.labels == reading.glosses
