import base64
import json

import pydantic
import pytest

from app import llm, prompts
from app.config import settings
from app.custom import reader
from app.engine import apps
from app.enrichment import vocabulary

JPEG = b"\xff\xd8\xff\xe0 a receipt"
PNG = b"\x89PNG\r\n\x1a\n a shelf"
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 an odometer"
PDF = b"%PDF-1.7 an invoice"
NOT_FOUND = {"value": None, "found": False}
NOWHERE = {"row": None, "column": None, "section": None, "item": None, "list": None}


def found(value):
    return {"value": value, "found": True}


def an_app(fields, description="A test app the reader fills."):
    return apps.parse(
        "draft",
        {
            "title": "Draft",
            "description": description,
            "input": "photo",
            "roles": ["staff"],
            "lands_as": "expense",
            "fields": fields,
        },
    )


def a_receipt():
    return an_app(
        {
            "vendor": {"type": "text"},
            "date": {"type": "date"},
            "total": {"type": "money"},
        }
    )


def an_update(field, value, **where):
    return {**NOWHERE, **where, "field": field, "value": value}


def a_place(**where):
    return {**NOWHERE, **where}


def a_shelf_item(**overrides):
    return {
        "product": "Oat milk",
        "facings": 4,
        "stock": "stocked",
        "shelf_price": 4.5,
        **overrides,
    }


def a_finding(**overrides):
    return {
        "hazard": "trip",
        "severity": "low",
        "location": "Stairwell B",
        "action": "Taped the cable down",
        **overrides,
    }


def a_pre_trip_item(**overrides):
    return {
        "section": "vehicle",
        "item": "tires",
        "result": "fail",
        "defect": "Front left tread low",
        **overrides,
    }


def a_perio_answer(rows=(), cells=()):
    return {
        "patient": found("Jordan Rivera"),
        "exam_date": found("2026-09-02"),
        "template": {"rows": list(rows), "cells": list(cells)},
    }


def a_pre_trip_answer(*items):
    return {
        "vehicle": found("Truck 7"),
        "odometer": found(48210),
        "template": {"items": list(items)},
    }


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "CUSTOM_ENABLED", True)


@pytest.fixture
def answered(monkeypatch):
    def _install(answer):
        calls = []

        async def fake_parse(**kwargs):
            calls.append(kwargs)
            return kwargs["output_format"].model_validate(answer), "claude-test"

        monkeypatch.setattr(llm, "parse", fake_parse)
        return calls

    return _install


@pytest.fixture
def failing(monkeypatch):
    calls = []

    async def fake_parse(**kwargs):
        calls.append(kwargs)
        raise llm.LLMError("upstream down")

    monkeypatch.setattr(llm, "parse", fake_parse)
    return calls


class TestTheAnswerShape:
    def test_a_text_field_is_a_value_with_a_found_flag(self):
        model = reader.answer_model(an_app({"vendor": {"type": "text"}}))
        parsed = model.model_validate({"vendor": found("Harbor Fuel")})
        assert parsed.model_dump(mode="json") == {
            "vendor": {"value": "Harbor Fuel", "found": True}
        }

    def test_a_field_not_found_carries_no_value(self):
        model = reader.answer_model(an_app({"vendor": {"type": "text"}}))
        parsed = model.model_validate({"vendor": NOT_FOUND})
        assert parsed.model_dump(mode="json") == {"vendor": NOT_FOUND}

    def test_the_found_flag_is_required(self):
        model = reader.answer_model(an_app({"vendor": {"type": "text"}}))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate({"vendor": {"value": "Harbor Fuel"}})

    def test_every_field_is_required(self):
        model = reader.answer_model(a_receipt())
        with pytest.raises(pydantic.ValidationError):
            model.model_validate({"vendor": found("Harbor Fuel")})

    def test_a_field_the_app_does_not_declare_is_refused(self):
        model = reader.answer_model(an_app({"vendor": {"type": "text"}}))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate(
                {"vendor": found("Harbor Fuel"), "colour": found("red")}
            )

    def test_a_number_field_takes_a_number(self):
        model = reader.answer_model(an_app({"weight": {"type": "number"}}))
        parsed = model.model_validate({"weight": found(12.5)})
        assert parsed.model_dump(mode="json")["weight"]["value"] == 12.5

    def test_a_number_field_refuses_words(self):
        model = reader.answer_model(an_app({"weight": {"type": "number"}}))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate({"weight": found("heavy")})

    def test_a_money_field_is_an_amount(self):
        model = reader.answer_model(an_app({"total": {"type": "money"}}))
        parsed = model.model_validate({"total": found(48.2)})
        assert parsed.model_dump(mode="json")["total"]["value"] == 48.2

    def test_a_money_field_refuses_words(self):
        model = reader.answer_model(an_app({"total": {"type": "money"}}))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate({"total": found("forty-eight")})

    def test_a_date_field_takes_an_iso_date(self):
        model = reader.answer_model(an_app({"due": {"type": "date"}}))
        parsed = model.model_validate({"due": found("2026-09-03")})
        assert parsed.model_dump(mode="json")["due"]["value"] == "2026-09-03"

    def test_a_date_field_refuses_text_that_is_not_a_date(self):
        model = reader.answer_model(an_app({"due": {"type": "date"}}))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate({"due": found("next tuesday")})

    def test_a_one_of_field_takes_a_label_from_its_mapping(self):
        model = reader.answer_model(
            an_app(
                {
                    "category": {
                        "type": "one_of",
                        "labels": {"fuel": "Gas or diesel", "meals": "Food"},
                    }
                }
            )
        )
        parsed = model.model_validate({"category": found("fuel")})
        assert parsed.model_dump(mode="json")["category"]["value"] == "fuel"

    def test_a_one_of_field_takes_a_label_from_its_list(self):
        model = reader.answer_model(
            an_app({"stage": {"type": "one_of", "labels": ["start", "end"]}})
        )
        parsed = model.model_validate({"stage": found("end")})
        assert parsed.model_dump(mode="json")["stage"]["value"] == "end"

    def test_a_one_of_field_refuses_a_label_it_does_not_declare(self):
        model = reader.answer_model(
            an_app({"stage": {"type": "one_of", "labels": ["start", "end"]}})
        )
        with pytest.raises(pydantic.ValidationError):
            model.model_validate({"stage": found("middle")})

    def test_a_many_of_field_takes_a_list_of_its_labels(self):
        model = reader.answer_model(
            an_app(
                {"damage": {"type": "many_of", "labels": ["broken", "dented", "water"]}}
            )
        )
        parsed = model.model_validate({"damage": found(["broken", "water"])})
        assert parsed.model_dump(mode="json")["damage"]["value"] == ["broken", "water"]

    def test_a_many_of_field_refuses_a_label_it_does_not_declare(self):
        model = reader.answer_model(
            an_app(
                {"damage": {"type": "many_of", "labels": ["broken", "dented", "water"]}}
            )
        )
        with pytest.raises(pydantic.ValidationError):
            model.model_validate({"damage": found(["broken", "melted"])})

    def test_a_lookup_field_is_the_name_or_code_read(self):
        model = reader.answer_model(
            an_app({"customer": {"type": "lookup", "entity": "company", "by": "name"}})
        )
        parsed = model.model_validate({"customer": found("Acme Corp")})
        assert parsed.model_dump(mode="json")["customer"]["value"] == "Acme Corp"

    def test_labels_from_takes_every_label_of_the_reading(self):
        model = reader.answer_model(
            an_app(
                {"interest": {"type": "one_of", "labels_from": "sales_call.interest"}}
            )
        )
        reading = vocabulary.load()["sales_call"]
        labels = next(f.labels for f in reading.fields if f.name == "interest")
        for label in labels:
            parsed = model.model_validate({"interest": found(label)})
            assert parsed.model_dump(mode="json")["interest"]["value"] == label

    def test_labels_from_refuses_a_label_the_reading_does_not_have(self):
        model = reader.answer_model(
            an_app(
                {"interest": {"type": "one_of", "labels_from": "sales_call.interest"}}
            )
        )
        with pytest.raises(pydantic.ValidationError):
            model.model_validate({"interest": found("lukewarm")})

    def test_a_photo_field_is_left_out_for_the_person_to_take(self):
        model = reader.answer_model(
            an_app({"vendor": {"type": "text"}, "snapshot": {"type": "photo"}})
        )
        assert set(model.model_fields) == {"vendor"}

    def test_a_screen_field_is_left_out_for_its_screen_to_fill(self):
        model = reader.answer_model(apps.load("proof_of_delivery"))
        assert set(model.model_fields) == {
            "customer",
            "order_number",
            "signed_by",
            "condition",
            "note",
        }

    def test_a_field_the_script_fills_is_left_out(self):
        model = reader.answer_model(apps.load("mileage_log"))
        assert set(model.model_fields) == {"vehicle", "odometer", "stage", "purpose"}

    def test_a_field_description_reaches_the_schema(self):
        model = reader.answer_model(
            an_app(
                {
                    "po_number": {
                        "type": "text",
                        "description": "The purchase order number, if printed",
                    }
                }
            )
        )
        schema = json.dumps(model.model_json_schema())
        assert "The purchase order number, if printed" in schema

    def test_a_number_unit_reaches_the_schema(self):
        model = reader.answer_model(
            an_app({"depth": {"type": "number", "unit": "millimetres"}})
        )
        assert "millimetres" in json.dumps(model.model_json_schema())


class TestTheAnswerShapeOfAList:
    def test_a_list_is_a_list_of_rows(self):
        model = reader.answer_model(apps.load("receipts"))
        parsed = model.model_validate(
            {
                "vendor": found("Harbor Fuel"),
                "date": found("2026-09-03"),
                "total": found(48.2),
                "tax": NOT_FOUND,
                "category": found("fuel"),
                "items": found([{"description": "Diesel", "amount": 48.2}]),
            }
        )
        assert parsed.model_dump(mode="json")["items"] == {
            "value": [{"description": "Diesel", "amount": 48.2}],
            "found": True,
        }

    def test_a_list_row_may_leave_a_value_unread(self):
        model = reader.answer_model(apps.load("receipts"))
        parsed = model.model_validate(
            {
                "vendor": found("Harbor Fuel"),
                "date": found("2026-09-03"),
                "total": found(48.2),
                "tax": NOT_FOUND,
                "category": found("fuel"),
                "items": found([{"description": "Diesel", "amount": None}]),
            }
        )
        assert parsed.model_dump(mode="json")["items"]["value"] == [
            {"description": "Diesel", "amount": None}
        ]

    def test_a_list_row_refuses_a_field_the_list_does_not_declare(self):
        model = reader.answer_model(apps.load("receipts"))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate(
                {
                    "vendor": found("Harbor Fuel"),
                    "date": found("2026-09-03"),
                    "total": found(48.2),
                    "tax": NOT_FOUND,
                    "category": found("fuel"),
                    "items": found(
                        [{"description": "Diesel", "amount": 48.2, "sku": "D-1"}]
                    ),
                }
            )

    def test_a_list_row_refuses_a_label_its_field_does_not_declare(self):
        model = reader.answer_model(apps.load("shelf_audit"))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate(
                {
                    "location": found("Store 4, aisle 3"),
                    "items": found([a_shelf_item(stock="half")]),
                }
            )

    def test_a_list_row_answers_every_field_but_the_scripts(self):
        model = reader.answer_model(apps.load("shelf_audit"))
        parsed = model.model_validate(
            {"location": found("Store 4, aisle 3"), "items": found([a_shelf_item()])}
        )
        assert parsed.model_dump(mode="json")["items"]["value"] == [a_shelf_item()]

    def test_a_list_row_refuses_the_field_its_script_fills(self):
        model = reader.answer_model(apps.load("shelf_audit"))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate(
                {
                    "location": found("Store 4, aisle 3"),
                    "items": found([a_shelf_item(price="matches")]),
                }
            )

    def test_a_list_row_answers_every_field_but_its_photo(self):
        model = reader.answer_model(apps.load("site_safety_walk"))
        parsed = model.model_validate(
            {"site": found("Pier 4"), "findings": found([a_finding()])}
        )
        assert parsed.model_dump(mode="json")["findings"]["value"] == [a_finding()]

    def test_a_list_row_refuses_its_photo_field(self):
        model = reader.answer_model(apps.load("site_safety_walk"))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate(
                {
                    "site": found("Pier 4"),
                    "findings": found([a_finding(photo="photo-1.jpg")]),
                }
            )


class TestTheAnswerShapeOfAGrid:
    def test_a_grid_app_answers_its_fields_and_its_template(self):
        model = reader.answer_model(apps.load("perio_charting"))
        assert set(model.model_fields) == {"patient", "exam_date", "template"}

    def test_a_grid_answers_rows_by_their_value(self):
        model = reader.answer_model(apps.load("perio_charting"))
        row = {"row": "3", "status": "present", "mobility": "1"}
        parsed = model.model_validate(a_perio_answer(rows=[row]))
        assert parsed.model_dump(mode="json")["template"]["rows"] == [row]

    def test_the_first_and_last_values_of_a_row_range_are_answerable(self):
        model = reader.answer_model(apps.load("perio_charting"))
        rows = [
            {"row": "1", "status": "missing", "mobility": None},
            {"row": "32", "status": "implant", "mobility": None},
        ]
        parsed = model.model_validate(a_perio_answer(rows=rows))
        assert parsed.model_dump(mode="json")["template"]["rows"] == rows

    def test_a_grid_refuses_a_row_outside_its_values(self):
        model = reader.answer_model(apps.load("perio_charting"))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate(
                a_perio_answer(
                    rows=[{"row": "33", "status": "present", "mobility": "0"}]
                )
            )

    def test_a_grid_answers_cells_by_row_and_column(self):
        model = reader.answer_model(apps.load("perio_charting"))
        cell = {"row": "3", "column": "B", "depth": 3, "bleeding": "none"}
        parsed = model.model_validate(a_perio_answer(cells=[cell]))
        assert parsed.model_dump(mode="json")["template"]["cells"] == [cell]

    def test_a_grid_refuses_a_column_outside_its_values(self):
        model = reader.answer_model(apps.load("perio_charting"))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate(
                a_perio_answer(
                    cells=[{"row": "3", "column": "X", "depth": 3, "bleeding": None}]
                )
            )

    def test_a_grid_cell_refuses_a_label_its_field_does_not_declare(self):
        model = reader.answer_model(apps.load("perio_charting"))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate(
                a_perio_answer(
                    cells=[{"row": "3", "column": "B", "depth": 3, "bleeding": "some"}]
                )
            )


class TestTheAnswerShapeOfAChecklist:
    def test_a_checklist_app_answers_its_fields_and_its_template(self):
        model = reader.answer_model(apps.load("vehicle_pre_trip"))
        assert set(model.model_fields) == {"vehicle", "odometer", "template"}

    def test_a_checklist_answers_items_by_section_and_item(self):
        model = reader.answer_model(apps.load("vehicle_pre_trip"))
        parsed = model.model_validate(a_pre_trip_answer(a_pre_trip_item()))
        assert parsed.model_dump(mode="json")["template"]["items"] == [
            a_pre_trip_item()
        ]

    def test_a_checklist_refuses_an_item_it_does_not_list(self):
        model = reader.answer_model(apps.load("vehicle_pre_trip"))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate(a_pre_trip_answer(a_pre_trip_item(item="radio")))

    def test_a_checklist_refuses_a_section_it_does_not_have(self):
        model = reader.answer_model(apps.load("vehicle_pre_trip"))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate(a_pre_trip_answer(a_pre_trip_item(section="cab")))

    def test_a_checklist_item_refuses_its_photo_field(self):
        model = reader.answer_model(apps.load("vehicle_pre_trip"))
        with pytest.raises(pydantic.ValidationError):
            model.model_validate(
                a_pre_trip_answer(a_pre_trip_item(photo="photo-1.jpg"))
            )


class TestReadIsGated:
    async def test_reading_is_refused_while_custom_is_off(self, answered):
        calls = answered({"vendor": found("Harbor Fuel")})
        app = an_app({"vendor": {"type": "text"}})
        with pytest.raises(reader.ReadError) as caught:
            await reader.read(app, files=[("image/jpeg", JPEG)], text=None)
        assert str(caught.value) == "reading is off: set CUSTOM_ENABLED"
        assert calls == []

    async def test_nothing_to_read_is_refused_before_any_model_call(
        self, enabled, answered
    ):
        calls = answered({"vendor": found("Harbor Fuel")})
        app = an_app({"vendor": {"type": "text"}})
        with pytest.raises(reader.ReadError, match="nothing to read"):
            await reader.read(app, files=[], text=None)
        assert calls == []

    async def test_blank_text_alone_is_nothing_to_read(self, enabled, answered):
        calls = answered({"vendor": found("Harbor Fuel")})
        app = an_app({"vendor": {"type": "text"}})
        with pytest.raises(reader.ReadError, match="nothing to read"):
            await reader.read(app, files=[], text="   ")
        assert calls == []

    async def test_a_model_failure_becomes_a_read_error_with_its_message(
        self, enabled, failing
    ):
        app = an_app({"vendor": {"type": "text"}})
        with pytest.raises(reader.ReadError) as caught:
            await reader.read(app, files=[("image/jpeg", JPEG)], text=None)
        assert str(caught.value) == "upstream down"


class TestTheReadRequest:
    async def test_the_model_and_token_cap_come_from_settings(
        self, enabled, answered, monkeypatch
    ):
        monkeypatch.setattr(settings, "CUSTOM_MODEL", "claude-reader-test")
        monkeypatch.setattr(settings, "CUSTOM_MAX_TOKENS", 1234)
        calls = answered({"vendor": found("Harbor Fuel")})
        await reader.read(
            an_app({"vendor": {"type": "text"}}),
            files=[("image/jpeg", JPEG)],
            text=None,
        )
        assert calls[0]["model"] == "claude-reader-test"
        assert calls[0]["max_tokens"] == 1234

    async def test_the_refusal_fallback_is_on(self, enabled, answered):
        calls = answered({"vendor": found("Harbor Fuel")})
        await reader.read(
            an_app({"vendor": {"type": "text"}}),
            files=[("image/jpeg", JPEG)],
            text=None,
        )
        assert calls[0]["fallback"] is True

    async def test_the_system_prompt_holds_the_custom_reader_read_prompt(
        self, enabled, answered
    ):
        calls = answered({"vendor": found("Harbor Fuel")})
        await reader.read(
            an_app({"vendor": {"type": "text"}}),
            files=[("image/jpeg", JPEG)],
            text=None,
        )
        assert prompts.text("custom_reader", "read") in calls[0]["system"]

    async def test_the_system_prompt_says_what_the_app_reads(self, enabled, answered):
        calls = answered({"vendor": found("Harbor Fuel")})
        await reader.read(
            an_app({"vendor": {"type": "text"}}, description="A paper fuel receipt."),
            files=[("image/jpeg", JPEG)],
            text=None,
        )
        assert "A paper fuel receipt." in calls[0]["system"]

    async def test_the_answer_shape_is_the_apps_answer_model(self, enabled, answered):
        app = a_receipt()
        calls = answered(
            {"vendor": found("Harbor Fuel"), "date": NOT_FOUND, "total": NOT_FOUND}
        )
        await reader.read(app, files=[("image/jpeg", JPEG)], text=None)
        assert (
            calls[0]["output_format"].model_json_schema()
            == reader.answer_model(app).model_json_schema()
        )

    async def test_the_client_override_reaches_the_model_call(self, enabled, answered):
        calls = answered({"vendor": found("Harbor Fuel")})
        override = object()
        await reader.read(
            an_app({"vendor": {"type": "text"}}),
            files=[("image/jpeg", JPEG)],
            text=None,
            client_override=override,
        )
        assert calls[0]["client_override"] is override

    @pytest.mark.parametrize(
        ("media_type", "data"),
        [("image/jpeg", JPEG), ("image/png", PNG), ("image/webp", WEBP)],
    )
    async def test_a_photo_becomes_a_base64_image_block(
        self, enabled, answered, media_type, data
    ):
        calls = answered({"vendor": found("Harbor Fuel")})
        await reader.read(
            an_app({"vendor": {"type": "text"}}),
            files=[(media_type, data)],
            text=None,
        )
        assert calls[0]["user"][0] == {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.b64encode(data).decode(),
            },
        }

    async def test_a_pdf_becomes_a_base64_document_block(self, enabled, answered):
        calls = answered({"vendor": found("Harbor Fuel")})
        await reader.read(
            an_app({"vendor": {"type": "text"}}),
            files=[("application/pdf", PDF)],
            text=None,
        )
        assert calls[0]["user"][0] == {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.b64encode(PDF).decode(),
            },
        }

    async def test_files_keep_their_order(self, enabled, answered):
        calls = answered({"vendor": found("Harbor Fuel")})
        await reader.read(
            an_app({"vendor": {"type": "text"}}),
            files=[("image/png", PNG), ("application/pdf", PDF), ("image/jpeg", JPEG)],
            text=None,
        )
        assert [block["source"]["media_type"] for block in calls[0]["user"][:3]] == [
            "image/png",
            "application/pdf",
            "image/jpeg",
        ]

    async def test_the_text_block_comes_last(self, enabled, answered):
        calls = answered({"vendor": found("Harbor Fuel")})
        await reader.read(
            an_app({"vendor": {"type": "text"}}),
            files=[("image/jpeg", JPEG), ("application/pdf", PDF)],
            text="Paid in cash at pump 4",
        )
        blocks = calls[0]["user"]
        assert [block["type"] for block in blocks] == ["image", "document", "text"]
        assert "Paid in cash at pump 4" in blocks[-1]["text"]

    async def test_photos_alone_still_end_with_a_text_block(self, enabled, answered):
        calls = answered({"vendor": found("Harbor Fuel")})
        await reader.read(
            an_app({"vendor": {"type": "text"}}),
            files=[("image/jpeg", JPEG)],
            text=None,
        )
        assert [block["type"] for block in calls[0]["user"]] == ["image", "text"]

    async def test_text_alone_is_one_text_block(self, enabled, answered):
        calls = answered({"vendor": found("Harbor Fuel")})
        await reader.read(
            an_app({"vendor": {"type": "text"}}),
            files=[],
            text="Harbor Fuel, forty-eight twenty, diesel",
        )
        blocks = calls[0]["user"]
        assert [block["type"] for block in blocks] == ["text"]
        assert "Harbor Fuel, forty-eight twenty, diesel" in blocks[0]["text"]


class TestWhatAReadReturns:
    async def test_found_fields_come_back_by_name(self, enabled, answered):
        answered(
            {
                "vendor": found("Harbor Fuel"),
                "date": found("2026-09-03"),
                "total": found(48.2),
            }
        )
        result = await reader.read(a_receipt(), files=[("image/jpeg", JPEG)], text=None)
        assert result == {
            "fields": {"vendor": "Harbor Fuel", "date": "2026-09-03", "total": 48.2},
            "missing": [],
        }

    async def test_a_field_not_found_is_missing(self, enabled, answered):
        answered(
            {
                "vendor": found("Harbor Fuel"),
                "date": found("2026-09-03"),
                "total": NOT_FOUND,
            }
        )
        result = await reader.read(a_receipt(), files=[("image/jpeg", JPEG)], text=None)
        assert result["missing"] == ["total"]

    async def test_a_field_not_found_comes_back_empty_whatever_value_it_carried(
        self, enabled, answered
    ):
        answered(
            {
                "vendor": found("Harbor Fuel"),
                "date": found("2026-09-03"),
                "total": {"value": 99.0, "found": False},
            }
        )
        result = await reader.read(a_receipt(), files=[("image/jpeg", JPEG)], text=None)
        assert result["fields"]["total"] is None

    async def test_missing_follows_the_definition_order(self, enabled, answered):
        answered(
            {"total": NOT_FOUND, "date": NOT_FOUND, "vendor": found("Harbor Fuel")}
        )
        result = await reader.read(a_receipt(), files=[("image/jpeg", JPEG)], text=None)
        assert result["missing"] == ["date", "total"]

    async def test_a_date_comes_back_as_iso_text(self, enabled, answered):
        answered({"due": found("2026-09-03")})
        result = await reader.read(
            an_app({"due": {"type": "date"}}), files=[("image/jpeg", JPEG)], text=None
        )
        assert result["fields"]["due"] == "2026-09-03"

    async def test_a_label_comes_back_as_plain_text(self, enabled, answered):
        answered({"stage": found("end")})
        result = await reader.read(
            an_app({"stage": {"type": "one_of", "labels": ["start", "end"]}}),
            files=[("image/jpeg", JPEG)],
            text=None,
        )
        assert result["fields"]["stage"] == "end"
        assert type(result["fields"]["stage"]) is str

    async def test_labels_come_back_as_a_list_of_plain_text(self, enabled, answered):
        answered({"damage": found(["dented", "water"])})
        result = await reader.read(
            an_app({"damage": {"type": "many_of", "labels": ["dented", "water"]}}),
            files=[("image/jpeg", JPEG)],
            text=None,
        )
        assert result["fields"]["damage"] == ["dented", "water"]
        assert all(type(label) is str for label in result["fields"]["damage"])

    async def test_a_list_comes_back_as_rows(self, enabled, answered):
        answered(
            {
                "vendor": found("Harbor Fuel"),
                "date": found("2026-09-03"),
                "total": found(48.2),
                "tax": NOT_FOUND,
                "category": found("fuel"),
                "items": found([{"description": "Diesel", "amount": 48.2}]),
            }
        )
        result = await reader.read(
            apps.load("receipts"), files=[("image/jpeg", JPEG)], text=None
        )
        assert result["fields"]["items"] == [{"description": "Diesel", "amount": 48.2}]

    async def test_a_list_not_found_comes_back_empty_and_missing(
        self, enabled, answered
    ):
        answered(
            {
                "vendor": found("Harbor Fuel"),
                "date": found("2026-09-03"),
                "total": found(48.2),
                "tax": NOT_FOUND,
                "category": found("fuel"),
                "items": NOT_FOUND,
            }
        )
        result = await reader.read(
            apps.load("receipts"), files=[("image/jpeg", JPEG)], text=None
        )
        assert result["fields"]["items"] is None
        assert result["missing"] == ["tax", "items"]

    async def test_a_field_the_script_fills_is_neither_read_nor_missing(
        self, enabled, answered
    ):
        answered(
            {
                "vehicle": NOT_FOUND,
                "odometer": found(48210),
                "stage": found("end"),
                "purpose": found("delivery"),
            }
        )
        result = await reader.read(
            apps.load("mileage_log"), files=[("image/webp", WEBP)], text=None
        )
        assert result == {
            "fields": {
                "vehicle": None,
                "odometer": 48210,
                "stage": "end",
                "purpose": "delivery",
            },
            "missing": ["vehicle"],
        }

    async def test_a_photo_field_is_neither_read_nor_missing(self, enabled, answered):
        answered({"vendor": NOT_FOUND})
        result = await reader.read(
            an_app({"vendor": {"type": "text"}, "snapshot": {"type": "photo"}}),
            files=[("image/jpeg", JPEG)],
            text=None,
        )
        assert result == {"fields": {"vendor": None}, "missing": ["vendor"]}


class TestWhatAReadReturnsForATemplate:
    async def test_an_app_without_a_template_reads_no_template(self, enabled, answered):
        answered({"vendor": found("Harbor Fuel")})
        result = await reader.read(
            an_app({"vendor": {"type": "text"}}),
            files=[("image/jpeg", JPEG)],
            text=None,
        )
        assert "template" not in result

    async def test_a_grid_comes_back_keyed_by_row_and_by_cell(self, enabled, answered):
        answered(
            a_perio_answer(
                rows=[{"row": "3", "status": "present", "mobility": "1"}],
                cells=[
                    {"row": "3", "column": "DB", "depth": 3, "bleeding": None},
                    {"row": "3", "column": "B", "depth": 2, "bleeding": "bleeding"},
                ],
            )
        )
        result = await reader.read(
            apps.load("perio_charting"), files=[], text="three, three two four"
        )
        assert result["template"] == {
            "rows": {"3": {"status": "present", "mobility": "1"}},
            "cells": {
                "3:DB": {"depth": 3, "bleeding": None},
                "3:B": {"depth": 2, "bleeding": "bleeding"},
            },
            "items": {},
        }

    async def test_a_grid_apps_fields_hold_only_its_own_fields(self, enabled, answered):
        answered(a_perio_answer())
        result = await reader.read(
            apps.load("perio_charting"), files=[], text="Jordan Rivera, September 2"
        )
        assert result["fields"] == {
            "patient": "Jordan Rivera",
            "exam_date": "2026-09-02",
        }
        assert result["missing"] == []

    async def test_a_grid_with_nothing_charted_is_empty(self, enabled, answered):
        answered(a_perio_answer())
        result = await reader.read(
            apps.load("perio_charting"), files=[], text="Jordan Rivera, September 2"
        )
        assert result["template"] == {"rows": {}, "cells": {}, "items": {}}

    async def test_a_checklist_comes_back_keyed_by_section_and_item(
        self, enabled, answered
    ):
        answered(a_pre_trip_answer(a_pre_trip_item()))
        result = await reader.read(
            apps.load("vehicle_pre_trip"),
            files=[],
            text="tires fail, front left tread low",
        )
        assert result["template"] == {
            "rows": {},
            "cells": {},
            "items": {
                "vehicle:tires": {"result": "fail", "defect": "Front left tread low"}
            },
        }

    async def test_a_pair_the_checklist_does_not_have_is_dropped(
        self, enabled, answered
    ):
        answered(
            {
                "property": found("12 Elm St, unit 4"),
                "kind": found("move_in"),
                "template": {
                    "items": [
                        {
                            "section": "safety",
                            "item": "toilet",
                            "condition": "poor",
                            "defect": None,
                        },
                        {
                            "section": "bathroom",
                            "item": "toilet",
                            "condition": "good",
                            "defect": None,
                        },
                    ]
                },
            }
        )
        result = await reader.read(
            apps.load("property_inspection"),
            files=[("image/jpeg", JPEG)],
            text=None,
        )
        assert result["template"]["items"] == {
            "bathroom:toilet": {"condition": "good", "defect": None}
        }


class TestHearIsGated:
    async def test_hearing_is_refused_while_custom_is_off(self, answered):
        calls = answered({"updates": [], "cursor": None, "readback": ""})
        with pytest.raises(reader.ReadError) as caught:
            await reader.hear(
                apps.load("food_safety_log"), text="walk-in cooler, 37", cursor=None
            )
        assert str(caught.value) == "reading is off: set CUSTOM_ENABLED"
        assert calls == []

    async def test_a_blank_utterance_is_nothing_to_read(self, enabled, answered):
        calls = answered({"updates": [], "cursor": None, "readback": ""})
        with pytest.raises(reader.ReadError, match="nothing to read"):
            await reader.hear(apps.load("food_safety_log"), text="  ", cursor=None)
        assert calls == []

    async def test_a_model_failure_becomes_a_read_error_with_its_message(
        self, enabled, failing
    ):
        with pytest.raises(reader.ReadError) as caught:
            await reader.hear(
                apps.load("food_safety_log"), text="walk-in cooler, 37", cursor=None
            )
        assert str(caught.value) == "upstream down"


class TestTheHearRequest:
    async def test_hearing_uses_the_custom_reader_hear_prompt(self, enabled, answered):
        calls = answered({"updates": [], "cursor": None, "readback": ""})
        await reader.hear(
            apps.load("food_safety_log"), text="walk-in cooler, 37", cursor=None
        )
        assert prompts.text("custom_reader", "hear") in calls[0]["system"]

    async def test_the_system_prompt_says_what_the_app_hears(self, enabled, answered):
        app = apps.load("food_safety_log")
        calls = answered({"updates": [], "cursor": None, "readback": ""})
        await reader.hear(app, text="walk-in cooler, 37", cursor=None)
        assert app.description in calls[0]["system"]

    async def test_hearing_uses_the_reading_model_with_the_fallback(
        self, enabled, answered, monkeypatch
    ):
        monkeypatch.setattr(settings, "CUSTOM_MODEL", "claude-reader-test")
        monkeypatch.setattr(settings, "CUSTOM_MAX_TOKENS", 1234)
        calls = answered({"updates": [], "cursor": None, "readback": ""})
        await reader.hear(
            apps.load("food_safety_log"), text="walk-in cooler, 37", cursor=None
        )
        assert calls[0]["model"] == "claude-reader-test"
        assert calls[0]["max_tokens"] == 1234
        assert calls[0]["fallback"] is True

    async def test_the_utterance_reaches_the_model(self, enabled, answered):
        calls = answered({"updates": [], "cursor": None, "readback": ""})
        await reader.hear(
            apps.load("perio_charting"),
            text="three, three two four",
            cursor={"row": "3", "column": "DB"},
        )
        assert "three, three two four" in json.dumps(calls[0]["user"])

    async def test_the_cursor_reaches_the_model(self, enabled, answered):
        calls = answered({"updates": [], "cursor": None, "readback": ""})
        app = apps.load("perio_charting")
        await reader.hear(app, text="three", cursor={"row": "3", "column": "DB"})
        await reader.hear(app, text="three", cursor={"row": "14", "column": "DB"})
        assert calls[0]["user"] != calls[1]["user"]

    async def test_the_client_override_reaches_the_model_call(self, enabled, answered):
        calls = answered({"updates": [], "cursor": None, "readback": ""})
        override = object()
        await reader.hear(
            apps.load("food_safety_log"),
            text="walk-in cooler, 37",
            cursor=None,
            client_override=override,
        )
        assert calls[0]["client_override"] is override


class TestWhatHearReturns:
    async def test_a_grid_utterance_becomes_cell_and_row_updates(
        self, enabled, answered
    ):
        answered(
            {
                "updates": [
                    an_update("depth", 3, row="3", column="DB"),
                    an_update("depth", 2, row="3", column="B"),
                    an_update("depth", 4, row="3", column="MB"),
                    an_update("bleeding", "bleeding", row="3", column="B"),
                    an_update("mobility", "1", row="3"),
                ],
                "cursor": a_place(row="3", column="DL"),
                "readback": "Tooth 3: 3, 2, 4, bleeding on B, mobility 1",
            }
        )
        result = await reader.hear(
            apps.load("perio_charting"),
            text="three, three two four, bleeding on the two, mobility one",
            cursor={"row": "3", "column": "DB"},
        )
        assert result == {
            "updates": [
                {"row": "3", "column": "DB", "field": "depth", "value": 3},
                {"row": "3", "column": "B", "field": "depth", "value": 2},
                {"row": "3", "column": "MB", "field": "depth", "value": 4},
                {"row": "3", "column": "B", "field": "bleeding", "value": "bleeding"},
                {"row": "3", "field": "mobility", "value": "1"},
            ],
            "cursor": {"row": "3", "column": "DL"},
            "readback": "Tooth 3: 3, 2, 4, bleeding on B, mobility 1",
        }

    async def test_a_checklist_utterance_becomes_item_updates(self, enabled, answered):
        answered(
            {
                "updates": [
                    an_update("result", "fail", section="vehicle", item="tires"),
                    an_update(
                        "defect",
                        "Front left tread low",
                        section="vehicle",
                        item="tires",
                    ),
                ],
                "cursor": a_place(section="vehicle", item="horn"),
                "readback": "Tires: fail, front left tread low",
            }
        )
        result = await reader.hear(
            apps.load("vehicle_pre_trip"),
            text="tires fail, front left tread low",
            cursor={"section": "vehicle", "item": "tires"},
        )
        assert result == {
            "updates": [
                {
                    "section": "vehicle",
                    "item": "tires",
                    "field": "result",
                    "value": "fail",
                },
                {
                    "section": "vehicle",
                    "item": "tires",
                    "field": "defect",
                    "value": "Front left tread low",
                },
            ],
            "cursor": {"section": "vehicle", "item": "horn"},
            "readback": "Tires: fail, front left tread low",
        }

    async def test_a_list_utterance_becomes_row_updates(self, enabled, answered):
        answered(
            {
                "updates": [
                    an_update("unit", "walk_in_cooler", list="readings"),
                    an_update("temperature", 37, list="readings"),
                ],
                "cursor": a_place(list="readings"),
                "readback": "Walk-in cooler, 37°F",
            }
        )
        result = await reader.hear(
            apps.load("food_safety_log"), text="walk-in cooler, 37", cursor=None
        )
        assert result == {
            "updates": [
                {"list": "readings", "field": "unit", "value": "walk_in_cooler"},
                {"list": "readings", "field": "temperature", "value": 37},
            ],
            "cursor": {"list": "readings"},
            "readback": "Walk-in cooler, 37°F",
        }

    async def test_a_field_of_the_record_itself_names_only_the_field(
        self, enabled, answered
    ):
        answered(
            {
                "updates": [an_update("shift", "opening")],
                "cursor": None,
                "readback": "Opening shift",
            }
        )
        result = await reader.hear(
            apps.load("food_safety_log"), text="opening shift", cursor=None
        )
        assert result["updates"] == [{"field": "shift", "value": "opening"}]

    async def test_no_cursor_from_the_model_is_no_cursor(self, enabled, answered):
        answered(
            {
                "updates": [an_update("shift", "opening")],
                "cursor": None,
                "readback": "Opening shift",
            }
        )
        result = await reader.hear(
            apps.load("food_safety_log"), text="opening shift", cursor=None
        )
        assert result["cursor"] is None

    async def test_an_utterance_with_nothing_to_record_changes_nothing(
        self, enabled, answered
    ):
        answered(
            {
                "updates": [],
                "cursor": a_place(row="3", column="DB"),
                "readback": "Nothing recorded",
            }
        )
        result = await reader.hear(
            apps.load("perio_charting"),
            text="hang on a second",
            cursor={"row": "3", "column": "DB"},
        )
        assert result == {
            "updates": [],
            "cursor": {"row": "3", "column": "DB"},
            "readback": "Nothing recorded",
        }
