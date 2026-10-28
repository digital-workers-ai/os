from app.custom.apps.inventory_count import script as inventory_count
from app.custom.apps.mileage_log import script as mileage_log
from app.custom.apps.shelf_audit import script as shelf_audit


class FakeContext:
    def __init__(self, earlier=(), facts=None):
        self.earlier = list(earlier)
        self.facts = facts or {}

    async def previous(self, where):
        for fields in self.earlier:
            if all(fields.get(key) == value for key, value in where.items()):
                return fields
        return None

    async def entity(self, entity_type, by, value, attr):
        return self.facts.get((entity_type, by, value, attr))


def a_reading(stage, odometer, vehicle="Truck 7"):
    return {
        "vehicle": vehicle,
        "odometer": odometer,
        "stage": stage,
        "purpose": "delivery",
        "miles": None,
    }


def an_item(product="Oat milk", shelf_price=4.5):
    return {
        "product": product,
        "facings": 4,
        "stock": "stocked",
        "shelf_price": shelf_price,
        "price": None,
    }


def a_shelf(*items):
    return {"location": "Store 4, aisle 3", "items": list(items)}


def priced(prices):
    return FakeContext(
        facts={
            ("product", "name", name, "price"): price for name, price in prices.items()
        }
    )


def verdicts(result):
    return [item.get("price") for item in result["items"]]


def a_line(product="SKU-1", counted=7):
    return {"product": product, "counted": counted, "change": None}


def a_count(location, *lines):
    return {"location": location, "lines": list(lines)}


def changes(result):
    return [line.get("change") for line in result["lines"]]


class TestMileageLog:
    async def test_an_end_reading_is_the_miles_since_the_vehicles_last_start(self):
        ctx = FakeContext([a_reading("start", 1000)])
        result = await mileage_log.fill(a_reading("end", 1250), ctx)
        assert result["miles"] == 250

    async def test_the_latest_start_is_the_one_counted(self):
        ctx = FakeContext([a_reading("start", 1100), a_reading("start", 1000)])
        result = await mileage_log.fill(a_reading("end", 1250), ctx)
        assert result["miles"] == 150

    async def test_an_earlier_end_reading_is_not_a_start(self):
        ctx = FakeContext([a_reading("end", 1100), a_reading("start", 1000)])
        result = await mileage_log.fill(a_reading("end", 1250), ctx)
        assert result["miles"] == 250

    async def test_another_vehicles_start_is_not_counted(self):
        ctx = FakeContext(
            [a_reading("start", 1200, vehicle="Truck 9"), a_reading("start", 1000)]
        )
        result = await mileage_log.fill(a_reading("end", 1250), ctx)
        assert result["miles"] == 250

    async def test_an_end_reading_with_no_start_has_no_miles(self):
        result = await mileage_log.fill(a_reading("end", 1250), FakeContext())
        assert result["miles"] is None

    async def test_an_end_reading_below_the_start_has_no_miles(self):
        ctx = FakeContext([a_reading("start", 1300)])
        result = await mileage_log.fill(a_reading("end", 1250), ctx)
        assert result["miles"] is None

    async def test_an_end_reading_equal_to_the_start_is_zero_miles(self):
        ctx = FakeContext([a_reading("start", 1250)])
        result = await mileage_log.fill(a_reading("end", 1250), ctx)
        assert result["miles"] == 0

    async def test_an_end_reading_without_an_odometer_value_has_no_miles(self):
        ctx = FakeContext([a_reading("start", 1000)])
        result = await mileage_log.fill(a_reading("end", None), ctx)
        assert result["miles"] is None

    async def test_a_start_without_an_odometer_value_gives_no_miles(self):
        ctx = FakeContext([a_reading("start", None)])
        result = await mileage_log.fill(a_reading("end", 1250), ctx)
        assert result["miles"] is None

    async def test_a_start_reading_has_no_miles(self):
        ctx = FakeContext([a_reading("start", 1000)])
        result = await mileage_log.fill(a_reading("start", 1250), ctx)
        assert result.get("miles") is None


class TestShelfAudit:
    async def test_a_shelf_price_equal_to_the_products_price_matches(self):
        result = await shelf_audit.fill(
            a_shelf(an_item()), priced({"Oat milk": "4.50"})
        )
        assert verdicts(result) == ["matches"]

    async def test_a_shelf_price_that_differs_is_wrong(self):
        result = await shelf_audit.fill(
            a_shelf(an_item(shelf_price=4.99)), priced({"Oat milk": "4.50"})
        )
        assert verdicts(result) == ["wrong"]

    async def test_an_unknown_product_has_no_verdict(self):
        result = await shelf_audit.fill(
            a_shelf(an_item("Rye bread")), priced({"Oat milk": "4.50"})
        )
        assert verdicts(result) == [None]

    async def test_an_item_with_no_product_has_no_verdict(self):
        result = await shelf_audit.fill(
            a_shelf(an_item(None)), priced({"Oat milk": "4.50"})
        )
        assert verdicts(result) == [None]

    async def test_an_item_with_no_shelf_price_has_no_verdict(self):
        result = await shelf_audit.fill(
            a_shelf(an_item(shelf_price=None)), priced({"Oat milk": "4.50"})
        )
        assert verdicts(result) == [None]

    async def test_each_item_gets_its_own_verdict(self):
        result = await shelf_audit.fill(
            a_shelf(
                an_item(),
                an_item("Rye bread", shelf_price=3.5),
                an_item("Sourdough"),
            ),
            priced({"Oat milk": "4.50", "Rye bread": "3.00"}),
        )
        assert verdicts(result) == ["matches", "wrong", None]

    async def test_a_shelf_with_no_items_has_no_verdicts(self):
        result = await shelf_audit.fill(a_shelf(), priced({"Oat milk": "4.50"}))
        assert verdicts(result) == []


class TestInventoryCount:
    async def test_the_change_is_the_count_minus_the_last_count_at_the_location(
        self,
    ):
        ctx = FakeContext([a_count("Aisle 3", a_line(counted=10))])
        result = await inventory_count.fill(a_count("Aisle 3", a_line(counted=7)), ctx)
        assert changes(result) == [-3]

    async def test_a_rise_is_a_positive_change(self):
        ctx = FakeContext([a_count("Aisle 3", a_line(counted=10))])
        result = await inventory_count.fill(a_count("Aisle 3", a_line(counted=12)), ctx)
        assert changes(result) == [2]

    async def test_the_latest_count_at_the_location_is_the_one_compared(self):
        ctx = FakeContext(
            [
                a_count("Aisle 3", a_line(counted=8)),
                a_count("Aisle 3", a_line(counted=10)),
            ]
        )
        result = await inventory_count.fill(a_count("Aisle 3", a_line(counted=7)), ctx)
        assert changes(result) == [-1]

    async def test_a_count_at_another_location_is_not_compared(self):
        ctx = FakeContext([a_count("Aisle 4", a_line(counted=10))])
        result = await inventory_count.fill(a_count("Aisle 3", a_line(counted=7)), ctx)
        assert changes(result) == [None]

    async def test_a_first_count_at_a_location_has_no_change(self):
        result = await inventory_count.fill(
            a_count("Aisle 3", a_line(counted=7)), FakeContext()
        )
        assert changes(result) == [None]

    async def test_a_product_missing_from_the_last_count_has_no_change(self):
        ctx = FakeContext([a_count("Aisle 3", a_line("SKU-2", counted=10))])
        result = await inventory_count.fill(a_count("Aisle 3", a_line(counted=7)), ctx)
        assert changes(result) == [None]

    async def test_a_line_with_no_count_has_no_change(self):
        ctx = FakeContext([a_count("Aisle 3", a_line(counted=10))])
        result = await inventory_count.fill(
            a_count("Aisle 3", a_line(counted=None)), ctx
        )
        assert changes(result) == [None]

    async def test_an_earlier_line_with_no_count_gives_no_change(self):
        ctx = FakeContext([a_count("Aisle 3", a_line(counted=None))])
        result = await inventory_count.fill(a_count("Aisle 3", a_line(counted=7)), ctx)
        assert changes(result) == [None]

    async def test_each_line_gets_its_own_change(self):
        ctx = FakeContext(
            [
                a_count(
                    "Aisle 3",
                    a_line("SKU-1", counted=10),
                    a_line("SKU-2", counted=5),
                )
            ]
        )
        result = await inventory_count.fill(
            a_count(
                "Aisle 3",
                a_line("SKU-1", counted=7),
                a_line("SKU-2", counted=5),
                a_line("SKU-3", counted=4),
            ),
            ctx,
        )
        assert changes(result) == [-3, 0, None]

    async def test_a_count_with_no_lines_has_no_changes(self):
        ctx = FakeContext([a_count("Aisle 3", a_line(counted=10))])
        result = await inventory_count.fill(a_count("Aisle 3"), ctx)
        assert changes(result) == []
