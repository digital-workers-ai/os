import pytest

from app.engine import dashboards, metrics

OVERVIEW = {
    "label": "Overview",
    "range": True,
    "sections": [
        {"label": "Traffic", "cards": ["sessions", "users", "sessions_by_day"]},
        {"label": "Revenue", "cards": ["won_value"]},
    ],
}

KPI = {"entity": "subscription", "expression": "SUM(mrr)"}
BREAKDOWN = {"entity": "deal", "expression": "COUNT(entity)", "group_by": "status"}
SERIES = {
    "entity": "deal",
    "expression": "COUNT(entity)",
    "group_by": "closed_at",
    "grain": "month",
}
RATIO = {
    "entity": "deal",
    "op": "/",
    "terms": [
        {"expression": "COUNT(entity)", "filter": {"status": "closed_won"}},
        {"expression": "COUNT(entity)", "filter": {}},
    ],
}
RANGEABLE = {"entity": "deal", "expression": "SUM(amount)", "window_attr": "closed_at"}


def _page(**overrides):
    return {**OVERVIEW, **overrides}


def _without(key):
    return {k: v for k, v in OVERVIEW.items() if k != key}


def _section(**overrides):
    return _page(sections=[{"label": "Traffic", "cards": ["mrr"], **overrides}])


class TestAPageParses:
    def test_a_full_page_parses_to_its_name_label_range_and_cards(self):
        page = dashboards.parse("overview", OVERVIEW)
        assert page.name == "overview"
        assert page.label == "Overview"
        assert page.range is True
        assert [section.label for section in page.sections] == ["Traffic", "Revenue"]
        assert page.sections[0].cards == ("sessions", "users", "sessions_by_day")
        assert page.sections[1].cards == ("won_value",)

    def test_range_defaults_to_false(self):
        assert dashboards.parse("overview", _without("range")).range is False

    def test_sections_keep_file_order(self):
        spec = _page(sections=list(reversed(OVERVIEW["sections"])))
        page = dashboards.parse("overview", spec)
        assert [section.label for section in page.sections] == ["Revenue", "Traffic"]

    def test_pages_parse_every_entry_in_order(self):
        defs = {"pipeline": _page(label="Pipeline"), "overview": OVERVIEW}
        assert [page.name for page in dashboards.pages(defs)] == [
            "pipeline",
            "overview",
        ]


class TestTheBuildRefusesAMalformedPage:
    @pytest.mark.parametrize(
        "spec,reason",
        [
            (["not", "a", "mapping"], "mapping"),
            (_page(colour="blue"), "colour"),
            (_without("label"), "label"),
            (_page(label=7), "label"),
            (_page(range="yes"), "range"),
            (_without("sections"), "sections"),
            (_page(sections={"label": "Traffic"}), "sections"),
            (_page(sections=[]), "sections"),
            (_page(sections=["Traffic"]), "section"),
            (_section(icon="x"), "icon"),
            (_page(sections=[{"cards": ["mrr"]}]), "label"),
            (_page(sections=[{"label": "Traffic"}]), "cards"),
            (_section(cards="mrr"), "cards"),
            (_section(cards=[]), "cards"),
            (_section(cards=["mrr", 7]), "cards"),
        ],
        ids=[
            "page_not_a_mapping",
            "unknown_page_key",
            "missing_label",
            "label_not_a_string",
            "range_not_a_bool",
            "missing_sections",
            "sections_not_a_list",
            "empty_sections",
            "section_not_a_mapping",
            "unknown_section_key",
            "section_missing_label",
            "missing_cards",
            "cards_not_a_list",
            "empty_cards",
            "card_not_a_string",
        ],
    )
    def test_a_malformed_page_is_refused_naming_the_page(self, spec, reason):
        with pytest.raises(dashboards.DashboardError, match="overview") as caught:
            dashboards.parse("overview", spec)
        assert reason in str(caught.value)

    def test_a_dashboards_file_that_is_not_a_mapping_is_refused(self, tmp_path):
        path = tmp_path / "dashboards.yaml"
        path.write_text("- a\n")
        with pytest.raises(dashboards.DashboardError, match="top level"):
            dashboards.load(path)


class TestShapeIsDerivedFromTheMetric:
    @pytest.mark.parametrize(
        "spec,shape",
        [
            (KPI, "kpi"),
            (RATIO, "ratio"),
            (BREAKDOWN, "breakdown"),
            (SERIES, "series"),
        ],
        ids=["kpi", "ratio", "breakdown", "series"],
    )
    def test_the_shape_follows_the_parsed_spec(self, spec, shape):
        assert dashboards.shape(metrics.parse_spec(spec)) == shape


class TestCheckNamesWhatIsWrong:
    def test_a_card_naming_no_metric(self):
        defs = {"overview": _section(cards=["nope"])}
        problems = dashboards.check(defs, {"mrr": KPI})
        assert len(problems) == 1, problems
        assert "overview" in problems[0]
        assert "nope" in problems[0]

    def test_a_card_twice_on_one_page(self):
        defs = {
            "pipeline": {
                "label": "Pipeline",
                "sections": [
                    {"label": "Deals", "cards": ["mrr"]},
                    {"label": "Subscriptions", "cards": ["mrr"]},
                ],
            }
        }
        problems = dashboards.check(defs, {"mrr": KPI})
        assert len(problems) == 1, problems
        assert "pipeline" in problems[0]
        assert "mrr" in problems[0]

    def test_a_card_that_cannot_be_ranged_on_a_range_page(self):
        defs = {"overview": _section(cards=["mrr"])}
        problems = dashboards.check(defs, {"mrr": KPI})
        assert len(problems) == 1, problems
        assert "overview" in problems[0]
        assert "mrr" in problems[0]
        assert "window_attr" in problems[0]

    def test_a_rangeable_card_on_a_range_page_passes(self):
        defs = {"overview": _section(cards=["won"])}
        assert dashboards.check(defs, {"won": RANGEABLE}) == []

    def test_a_malformed_page_is_one_problem(self):
        problems = dashboards.check({"overview": _page(sections=[])}, {"mrr": KPI})
        assert len(problems) == 1, problems
        assert "overview" in problems[0]

    def test_a_card_whose_metric_does_not_parse_is_left_to_the_metrics_check(self):
        defs = {"overview": _section(cards=["broken"])}
        broken = {"entity": "deal", "expression": "COUNT(entity)", "bogus": 1}
        assert dashboards.check(defs, {"broken": broken}) == []

    def test_the_shipped_dashboards_pass_against_the_shipped_metrics(self):
        assert dashboards.check(dashboards.load(), metrics.load_definitions()) == []
