import pytest

from app.engine import dashboards, derived, metrics, ontology

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

TABLE = {
    "table": "social_post",
    "label": "Top posts",
    "rank": "likes",
    "columns": ["name", "likes"],
}

ATTRS = {
    "subscription": {"mrr": "number", "status": "string", "started_at": "date"},
    "deal": {"amount": "number", "status": "string", "closed_at": "date"},
    "social_post": {
        "name": "string",
        "platform": "string",
        "likes": "number",
        "posted_at": "date",
    },
}


def attrs_of(entity):
    return ATTRS[entity]


def _page(**overrides):
    return {**OVERVIEW, **overrides}


def _without(key):
    return {k: v for k, v in OVERVIEW.items() if k != key}


def _section(**overrides):
    return _page(sections=[{"label": "Traffic", "cards": ["mrr"], **overrides}])


def _table(**overrides):
    return {**TABLE, **overrides}


def _table_without(key):
    return {k: v for k, v in TABLE.items() if k != key}


def _tabled(card, **overrides):
    return _page(sections=[{"label": "Top", "cards": [card]}], **overrides)


def _filtered(filt, cards):
    return _page(range=False, filter=filt, sections=[{"label": "X", "cards": cards}])


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

    def test_goals_parses_true_when_declared(self):
        assert dashboards.parse("overview", _page(goals=True)).goals is True

    def test_findings_parses_true_when_declared(self):
        assert dashboards.parse("overview", _page(findings=True)).findings is True

    def test_goals_defaults_to_false(self):
        assert dashboards.parse("overview", OVERVIEW).goals is False

    def test_findings_defaults_to_false(self):
        assert dashboards.parse("overview", OVERVIEW).findings is False

    @pytest.mark.parametrize("flag", ["goals", "findings"])
    def test_a_page_carrying_goals_or_findings_needs_no_sections(self, flag):
        page = dashboards.parse("attention", {"label": "Attention", flag: True})
        assert page.sections == ()

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


class TestAPageFilterParses:
    def test_a_page_filter_parses_to_its_mapping(self):
        page = dashboards.parse("facebook", _page(filter={"platform": "facebook"}))
        assert page.filter == {"platform": "facebook"}

    def test_filter_defaults_to_empty(self):
        assert dashboards.parse("overview", OVERVIEW).filter == {}

    def test_a_numeric_filter_value_is_kept_as_given(self):
        assert dashboards.parse("tier", _page(filter={"tier": 2})).filter == {"tier": 2}

    def test_the_page_key_set_names_filter(self):
        assert "filter" in dashboards.PAGE_KEYS


class TestTheBuildRefusesAMalformedPage:
    @pytest.mark.parametrize(
        "spec,reason",
        [
            (["not", "a", "mapping"], "mapping"),
            (_page(colour="blue"), "colour"),
            (_without("label"), "label"),
            (_page(label=7), "label"),
            (_page(range="yes"), "range"),
            (_page(goals="yes"), "goals 'yes' must be true or false"),
            (_page(findings="yes"), "findings 'yes' must be true or false"),
            (_without("sections"), "sections"),
            ({"label": "Overview"}, "needs `sections`"),
            (_page(sections={"label": "Traffic"}), "sections"),
            (_page(sections=[]), "sections"),
            (_page(sections=["Traffic"]), "section"),
            (_section(icon="x"), "icon"),
            (_page(sections=[{"cards": ["mrr"]}]), "label"),
            (_page(sections=[{"label": "Traffic"}]), "cards"),
            (_section(cards="mrr"), "cards"),
            (_section(cards=[]), "cards"),
            (_section(cards=["mrr", 7]), "cards"),
            (_page(filter="facebook"), "filter must be a mapping"),
            (_page(filter={"a.b": "x"}), "filter attr 'a.b'"),
            (_page(filter={"platform": True}), "filter value"),
            (_page(filter={"platform": None}), "filter value"),
            (_page(filter={"platform": ["facebook"]}), "filter value"),
        ],
        ids=[
            "page_not_a_mapping",
            "unknown_page_key",
            "missing_label",
            "label_not_a_string",
            "range_not_a_bool",
            "goals_not_a_bool",
            "findings_not_a_bool",
            "missing_sections",
            "only_a_label",
            "sections_not_a_list",
            "empty_sections",
            "section_not_a_mapping",
            "unknown_section_key",
            "section_missing_label",
            "missing_cards",
            "cards_not_a_list",
            "empty_cards",
            "card_not_a_name_or_a_table",
            "filter_not_a_mapping",
            "filter_attr_not_plain",
            "filter_value_a_bool",
            "filter_value_none",
            "filter_value_a_list",
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


class TestATableCardParses:
    def test_a_table_card_parses_with_its_defaults(self):
        page = dashboards.parse("social", _tabled(TABLE))
        assert page.sections[0].cards == (
            dashboards.TableCard(
                "social_post", "Top posts", "likes", ("name", "likes"), None, 10, {}
            ),
        )

    def test_a_table_card_carries_its_window_attr_limit_and_filter(self):
        card = _table(window_attr="posted_at", limit=5, filter={"platform": "x"})
        page = dashboards.parse("social", _tabled(card))
        assert page.sections[0].cards[0] == dashboards.TableCard(
            "social_post",
            "Top posts",
            "likes",
            ("name", "likes"),
            "posted_at",
            5,
            {"platform": "x"},
        )

    def test_a_metric_card_beside_a_table_card_stays_a_name(self):
        spec = _page(sections=[{"label": "Top", "cards": ["posts", TABLE]}])
        page = dashboards.parse("social", spec)
        assert page.sections[0].cards[0] == "posts"

    def test_a_table_card_is_frozen(self):
        card = dashboards.parse("social", _tabled(TABLE)).sections[0].cards[0]
        with pytest.raises(AttributeError):
            card.limit = 3


class TestTheBuildRefusesAMalformedTableCard:
    @pytest.mark.parametrize(
        "card,reason",
        [
            (_table(icon="x"), "icon"),
            (_table_without("table"), "table"),
            (_table(table=7), "table"),
            (_table_without("label"), "label"),
            (_table(label=7), "label"),
            (_table_without("rank"), "rank"),
            (_table(rank=7), "rank"),
            (_table_without("columns"), "columns"),
            (_table(columns=[]), "columns"),
            (_table(columns="name"), "columns"),
            (_table(columns=["name", 7]), "columns"),
            (_table(window_attr=7), "window_attr"),
            (_table(limit=0), "limit"),
            (_table(limit=51), "limit"),
            (_table(limit=True), "limit"),
            (_table(limit="10"), "limit"),
            (_table(filter="x"), "filter must be a mapping"),
            (_table(filter={"a.b": "x"}), "filter attr 'a.b'"),
            (_table(filter={"platform": True}), "filter value"),
        ],
        ids=[
            "unknown_key",
            "missing_table",
            "table_not_a_string",
            "missing_label",
            "label_not_a_string",
            "missing_rank",
            "rank_not_a_string",
            "missing_columns",
            "empty_columns",
            "columns_not_a_list",
            "column_not_a_string",
            "window_attr_not_a_string",
            "limit_zero",
            "limit_past_fifty",
            "limit_a_bool",
            "limit_a_string",
            "filter_not_a_mapping",
            "filter_attr_not_plain",
            "filter_value_a_bool",
        ],
    )
    def test_a_malformed_table_card_is_refused_naming_the_page(self, card, reason):
        with pytest.raises(dashboards.DashboardError, match="social") as caught:
            dashboards.parse("social", _tabled(card))
        assert reason in str(caught.value)


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
        problems = dashboards.check(defs, {"mrr": KPI}, attrs_of)
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
        problems = dashboards.check(defs, {"mrr": KPI}, attrs_of)
        assert len(problems) == 1, problems
        assert "pipeline" in problems[0]
        assert "mrr" in problems[0]

    def test_a_card_that_cannot_be_ranged_on_a_range_page(self):
        defs = {"overview": _section(cards=["mrr"])}
        problems = dashboards.check(defs, {"mrr": KPI}, attrs_of)
        assert len(problems) == 1, problems
        assert "overview" in problems[0]
        assert "mrr" in problems[0]
        assert "window_attr" in problems[0]

    def test_a_rangeable_card_on_a_range_page_passes(self):
        defs = {"overview": _section(cards=["won"])}
        assert dashboards.check(defs, {"won": RANGEABLE}, attrs_of) == []

    def test_a_malformed_page_is_one_problem(self):
        problems = dashboards.check(
            {"overview": _page(sections=[])}, {"mrr": KPI}, attrs_of
        )
        assert len(problems) == 1, problems
        assert "overview" in problems[0]

    def test_a_card_whose_metric_does_not_parse_is_left_to_the_metrics_check(self):
        defs = {"overview": _section(cards=["broken"])}
        broken = {"entity": "deal", "expression": "COUNT(entity)", "bogus": 1}
        assert dashboards.check(defs, {"broken": broken}, attrs_of) == []

    def test_a_card_whose_metric_is_not_a_mapping_is_left_to_the_metrics_check(
        self,
    ):
        defs = {
            "pipeline": _page(range=False, sections=[{"label": "X", "cards": ["mrr"]}])
        }
        assert dashboards.check(defs, {"mrr": "SUM(mrr)"}, attrs_of) == []

    def test_the_shipped_dashboards_pass_against_the_shipped_metrics(self):
        problems = dashboards.check(
            dashboards.load(),
            metrics.load_definitions(),
            derived.attrs_of(ontology.load()),
        )
        assert problems == []


class TestCheckHoldsAPageFilterToEveryCard:
    def test_a_filter_attr_the_metric_cards_entity_lacks(self):
        defs = {"facebook": _filtered({"platform": "facebook"}, ["mrr"])}
        problems = dashboards.check(defs, {"mrr": KPI}, attrs_of)
        assert len(problems) == 1, problems
        assert "facebook" in problems[0]
        assert "mrr" in problems[0]
        assert "platform" in problems[0]

    def test_a_filter_attr_every_card_declares_passes(self):
        defs = {"active": _filtered({"status": "active"}, ["mrr"])}
        assert dashboards.check(defs, {"mrr": KPI}, attrs_of) == []

    def test_a_metric_on_an_undeclared_entity_is_left_to_the_metrics_check(self):
        defs = {"facebook": _filtered({"platform": "facebook"}, ["ghost"])}
        ghost = {"entity": "ghost", "expression": "COUNT(entity)"}
        assert dashboards.check(defs, {"ghost": ghost}, attrs_of) == []

    def test_a_filter_attr_the_table_cards_entity_lacks(self):
        deals = _table(
            table="deal", label="Top deals", rank="amount", columns=["status"]
        )
        defs = {"facebook": _filtered({"platform": "facebook"}, [deals])}
        problems = dashboards.check(defs, {}, attrs_of)
        assert len(problems) == 1, problems
        assert "facebook" in problems[0]
        assert "Top deals" in problems[0]
        assert "platform" in problems[0]

    def test_a_filter_attr_the_table_cards_entity_declares_passes(self):
        defs = {"facebook": _filtered({"platform": "facebook"}, [TABLE])}
        assert dashboards.check(defs, {}, attrs_of) == []


class TestCheckHoldsATableToItsEntity:
    def _problems(self, card, **page):
        defs = {"social": _tabled(card, range=False, **page)}
        return dashboards.check(defs, {}, attrs_of)

    def test_a_table_on_an_undeclared_entity(self):
        problems = self._problems(_table(table="ghost"))
        assert len(problems) == 1, problems
        assert "social" in problems[0]
        assert "ghost" in problems[0]

    def test_a_rank_the_entity_lacks(self):
        problems = self._problems(_table(rank="nope"))
        assert len(problems) == 1, problems
        assert "Top posts" in problems[0]
        assert "nope" in problems[0]

    def test_a_rank_that_is_not_a_number(self):
        problems = self._problems(_table(rank="platform"))
        assert len(problems) == 1, problems
        assert "platform" in problems[0]
        assert "number" in problems[0]

    def test_a_column_the_entity_lacks(self):
        problems = self._problems(_table(columns=["name", "nope"]))
        assert len(problems) == 1, problems
        assert "nope" in problems[0]

    def test_a_window_attr_the_entity_lacks(self):
        problems = self._problems(_table(window_attr="nope"))
        assert len(problems) == 1, problems
        assert "nope" in problems[0]

    def test_a_window_attr_that_is_not_a_date(self):
        problems = self._problems(_table(window_attr="platform"))
        assert len(problems) == 1, problems
        assert "platform" in problems[0]
        assert "date" in problems[0]

    def test_a_table_on_a_range_page_needs_a_window_attr(self):
        problems = dashboards.check({"social": _tabled(TABLE)}, {}, attrs_of)
        assert len(problems) == 1, problems
        assert "social" in problems[0]
        assert "Top posts" in problems[0]
        assert "window_attr" in problems[0]

    def test_a_filter_attr_the_entity_lacks(self):
        problems = self._problems(_table(filter={"nope": "x"}))
        assert len(problems) == 1, problems
        assert "nope" in problems[0]

    def test_a_clean_table_on_a_range_page_passes(self):
        card = _table(window_attr="posted_at", filter={"platform": "facebook"})
        assert dashboards.check({"social": _tabled(card)}, {}, attrs_of) == []

    def test_two_alike_tables_on_one_page_are_not_duplicates(self):
        spec = _page(range=False, sections=[{"label": "Top", "cards": [TABLE, TABLE]}])
        assert dashboards.check({"social": spec}, {}, attrs_of) == []
