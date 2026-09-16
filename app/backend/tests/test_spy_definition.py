import pytest
import yaml

from app import caches
from app.engine import spy

BRAND = {"name": "Pipedrive", "domain": "pipedrive.com", "aliases": []}
HUBSPOT = {
    "name": "HubSpot",
    "domain": "hubspot.com",
    "aliases": ["HubSpot CRM"],
    "linkedin": "hubspot",
    "google_advertiser_id": "AR123",
}
ZOHO = {
    "name": "Zoho CRM",
    "domain": "zoho.com",
    "aliases": ["Zoho"],
    "linkedin": "zoho",
}
DOC = {
    "brand": BRAND,
    "competitors": [HUBSPOT, ZOHO],
    "queries": ["best crm for small business", "hubspot alternatives"],
    "country": "US",
    "language": "en",
}


def _doc(**overrides):
    return {**DOC, **overrides}


def _without(spec, key):
    return {k: v for k, v in spec.items() if k != key}


def _brand(**overrides):
    return _doc(brand={**BRAND, **overrides})


def _competitor(**overrides):
    return _doc(competitors=[{**HUBSPOT, **overrides}, ZOHO])


@pytest.fixture
def tracked():
    return spy.parse(DOC)


class TestConstants:
    def test_the_six_engines_in_order(self):
        assert spy.ENGINES == (
            "google",
            "ai_overview",
            "chatgpt",
            "perplexity",
            "claude",
            "gemini",
        )

    def test_the_two_roles(self):
        assert spy.ROLES == ("brand", "competitor")

    def test_the_error_is_a_value_error(self):
        assert issubclass(spy.SpyError, ValueError)

    def test_the_default_path_sits_beside_the_other_definitions(self):
        assert spy.DEFAULT_SPY == caches.DEFINITIONS_DIR / "spy.yaml"


class TestParse:
    def test_a_valid_document_parses_into_a_definition(self, tracked):
        assert tracked.brand == spy.Company(
            "Pipedrive", "pipedrive.com", (), None, None, "brand"
        )
        assert tracked.competitors == (
            spy.Company(
                "HubSpot",
                "hubspot.com",
                ("HubSpot CRM",),
                "hubspot",
                "AR123",
                "competitor",
            ),
            spy.Company("Zoho CRM", "zoho.com", ("Zoho",), "zoho", None, "competitor"),
        )
        assert tracked.queries == (
            "best crm for small business",
            "hubspot alternatives",
        )
        assert tracked.country == "US"
        assert tracked.language == "en"

    def test_every_role_is_a_declared_one(self, tracked):
        assert {company.role for company in tracked.companies} == set(spy.ROLES)

    def test_a_company_without_aliases_has_an_empty_tuple(self):
        tracked = spy.parse(_doc(brand=_without(BRAND, "aliases")))
        assert tracked.brand.aliases == ()

    def test_names_are_the_name_then_its_aliases(self, tracked):
        assert tracked.competitors[0].names == ("HubSpot", "HubSpot CRM")
        assert tracked.brand.names == ("Pipedrive",)

    def test_companies_are_the_brand_then_the_competitors(self, tracked):
        assert tracked.companies == (tracked.brand, *tracked.competitors)

    def test_a_definition_is_frozen(self, tracked):
        with pytest.raises(AttributeError):
            tracked.country = "GB"

    def test_a_valid_document_has_no_problems(self):
        assert spy.check(DOC) == []

    def test_parse_raises_the_first_problem(self):
        doc = _doc(country="usa", language="EN")
        problems = spy.check(doc)
        assert len(problems) == 2
        with pytest.raises(spy.SpyError) as caught:
            spy.parse(doc)
        assert str(caught.value) == problems[0]
        assert "country" in problems[0]
        assert "language" in problems[1]

    def test_every_problem_names_the_file(self):
        doc = _doc(brand=None, competitors=[], queries=[], country=1, language=2)
        problems = spy.check(doc)
        assert len(problems) == 5
        assert all(problem.startswith("spy.yaml: ") for problem in problems)

    def test_check_never_raises_on_a_document_that_is_not_a_mapping(self):
        [problem] = spy.check(["brand"])
        assert problem == "spy.yaml: top level must be a mapping"


class TestEachRuleIsChecked:
    @pytest.mark.parametrize(
        ("doc", "needle"),
        [
            (_doc(extra=1), "unknown key 'extra'"),
            (_without(DOC, "brand"), "brand must be a mapping"),
            (_doc(brand="Pipedrive"), "brand must be a mapping"),
            (_doc(brand=_without(BRAND, "name")), "brand is missing a string `name`"),
            (_brand(name=5), "brand is missing a string `name`"),
            (_brand(name="   "), "brand is missing a string `name`"),
            (_doc(brand=_without(BRAND, "domain")), "brand domain None"),
            (_brand(domain="https://pipedrive.com"), "brand domain 'https://"),
            (_brand(domain="Pipedrive.com"), "brand domain 'Pipedrive.com'"),
            (_brand(domain="pipedrive.com/pricing"), "no scheme or path"),
            (_brand(domain="pipedrive"), "brand domain 'pipedrive'"),
            (_brand(aliases="Pipe"), "brand aliases must be a list"),
            (_brand(aliases=[1]), "brand aliases must be a list"),
            (_brand(aliases=[""]), "brand aliases must be a list"),
            (_brand(linkedin="pipedrive"), "brand has unknown key 'linkedin'"),
            (_without(DOC, "competitors"), "competitors must be a non-empty list"),
            (_doc(competitors=[]), "competitors must be a non-empty list"),
            (_doc(competitors="HubSpot"), "competitors must be a non-empty list"),
            (_doc(competitors=["HubSpot"]), "competitors[0] must be a mapping"),
            (
                _doc(competitors=[_without(HUBSPOT, "name")]),
                "competitors[0] is missing a string `name`",
            ),
            (_competitor(domain="HubSpot.com"), "competitor 'HubSpot' domain"),
            (
                _competitor(linkedin="Hub Spot"),
                "competitor 'HubSpot' linkedin 'Hub Spot'",
            ),
            (_competitor(linkedin=5), "competitor 'HubSpot' linkedin 5"),
            (
                _competitor(google_advertiser_id="123"),
                "competitor 'HubSpot' google_advertiser_id '123'",
            ),
            (_competitor(twitter="hubspot"), "competitor 'HubSpot' has unknown key"),
            (
                _competitor(aliases=["pipedrive"]),
                "name 'pipedrive' appears more than once",
            ),
            (
                _doc(competitors=[HUBSPOT, {**ZOHO, "name": "hubspot"}]),
                "name 'hubspot' appears more than once",
            ),
            (
                _competitor(domain="pipedrive.com"),
                "domain 'pipedrive.com' appears more",
            ),
            (_without(DOC, "queries"), "queries must be a non-empty list"),
            (_doc(queries=[]), "queries must be a non-empty list"),
            (_doc(queries="best crm"), "queries must be a non-empty list"),
            (_doc(queries=[5]), "queries[0] 5 must be a non-empty string"),
            (_doc(queries=["   "]), "queries[0] '   ' must be a non-empty string"),
            (
                _doc(queries=["Best CRM", "best-crm"]),
                "more than one query slugs to 'best-crm'",
            ),
            (_doc(country="us"), "country 'us' must match"),
            (_doc(country="USA"), "country 'USA' must match"),
            (_without(DOC, "country"), "country None must match"),
            (_doc(language="EN"), "language 'EN' must match"),
            (_without(DOC, "language"), "language None must match"),
        ],
        ids=[
            "unknown_top_level_key",
            "brand_missing",
            "brand_not_a_mapping",
            "brand_name_missing",
            "brand_name_not_a_string",
            "brand_name_blank",
            "brand_domain_missing",
            "brand_domain_with_scheme",
            "brand_domain_uppercase",
            "brand_domain_with_path",
            "brand_domain_without_a_dot",
            "brand_aliases_not_a_list",
            "brand_alias_not_a_string",
            "brand_alias_blank",
            "brand_unknown_key",
            "competitors_missing",
            "competitors_empty",
            "competitors_not_a_list",
            "competitor_not_a_mapping",
            "competitor_name_missing",
            "competitor_domain_uppercase",
            "competitor_linkedin_with_a_space",
            "competitor_linkedin_not_a_string",
            "competitor_advertiser_without_prefix",
            "competitor_unknown_key",
            "alias_repeats_the_brand_case_insensitively",
            "competitor_repeats_another_case_insensitively",
            "domain_repeated",
            "queries_missing",
            "queries_empty",
            "queries_not_a_list",
            "query_not_a_string",
            "query_blank",
            "queries_collide_once_slugged",
            "country_lowercase",
            "country_three_letters",
            "country_missing",
            "language_uppercase",
            "language_missing",
        ],
    )
    def test_the_rule_is_its_own_problem(self, doc, needle):
        problems = spy.check(doc)
        matching = [problem for problem in problems if needle in problem]
        assert len(matching) == 1, problems
        assert matching[0].startswith("spy.yaml: ")

    def test_a_document_that_is_not_a_mapping_is_one_problem(self):
        assert spy.check("brand: Pipedrive") == [
            "spy.yaml: top level must be a mapping"
        ]

    def test_an_advertiser_id_of_the_declared_shape_passes(self):
        assert spy.check(_competitor(google_advertiser_id="AR01234567890")) == []

    def test_a_linkedin_slug_with_digits_and_dashes_passes(self):
        assert spy.check(_competitor(linkedin="freshworks-inc-2")) == []

    def test_a_subdomain_is_a_valid_domain(self):
        assert spy.check(_competitor(domain="crm.zoho.eu")) == []


class TestLoading:
    def test_the_shipped_file_parses(self):
        tracked = spy.definition()
        assert tracked.brand.name == "Pipedrive"
        assert tracked.brand.domain == "pipedrive.com"
        assert [c.name for c in tracked.competitors] == [
            "HubSpot",
            "Zoho CRM",
            "Freshsales",
        ]
        assert [c.linkedin for c in tracked.competitors] == [
            "hubspot",
            "zoho",
            "freshworks-inc",
        ]
        assert len(tracked.queries) == 8
        assert tracked.queries[0] == "best crm for small business"
        assert (tracked.country, tracked.language) == ("US", "en")

    def test_the_shipped_file_has_no_problems(self):
        assert spy.check(spy.definitions()) == []

    def test_definitions_is_the_raw_mapping(self):
        assert spy.definitions() == spy.load()
        assert spy.definitions()["brand"]["name"] == "Pipedrive"

    def test_load_reads_the_given_path(self, tmp_path):
        path = tmp_path / "spy.yaml"
        path.write_text(yaml.safe_dump(DOC))
        assert spy.load(path) == DOC

    def test_a_file_that_is_not_a_mapping_is_refused(self, tmp_path):
        path = tmp_path / "spy.yaml"
        path.write_text("- a\n")
        with pytest.raises(spy.SpyError, match="top level"):
            spy.load(path)

    def test_the_parsed_definition_is_cached_until_the_caches_reset(self):
        caches.reset_all()
        first = spy.definition()
        assert spy.definition() is first
        caches.reset_all()
        assert spy.definition() is not first
        assert spy.definition() == first


class TestLookups:
    def test_by_domain_accepts_a_host_a_url_and_a_subdomain(self, tracked):
        hubspot, zoho = tracked.competitors
        assert tracked.by_domain("hubspot.com") is hubspot
        assert tracked.by_domain("https://www.hubspot.com/pricing") is hubspot
        assert tracked.by_domain("blog.zoho.com") is zoho
        assert tracked.by_domain("PIPEDRIVE.COM") is tracked.brand

    def test_by_domain_finds_nothing_for_a_stranger(self, tracked):
        assert tracked.by_domain("https://g2.com/compare") is None
        assert tracked.by_domain("nothubspot.com") is None

    def test_by_linkedin_finds_a_competitor(self, tracked):
        assert tracked.by_linkedin("zoho") is tracked.competitors[1]

    def test_by_linkedin_finds_nothing_for_a_stranger_or_nothing(self, tracked):
        assert tracked.by_linkedin("salesforce") is None
        assert tracked.by_linkedin(None) is None

    def test_by_advertiser_finds_a_competitor(self, tracked):
        assert tracked.by_advertiser("AR123") is tracked.competitors[0]

    def test_by_advertiser_finds_nothing_for_a_stranger_or_nothing(self, tracked):
        assert tracked.by_advertiser("AR999") is None
        assert tracked.by_advertiser(None) is None


class TestSlug:
    def test_lowercases_and_joins_with_dashes(self):
        assert spy.slug("Best CRM for Small Business!") == "best-crm-for-small-business"

    def test_strips_the_dashes_at_both_ends(self):
        assert spy.slug("  hubspot alternatives  ") == "hubspot-alternatives"

    def test_collapses_a_run_of_separators(self):
        assert spy.slug("crm -- with / ai") == "crm-with-ai"

    def test_nothing_slugs_to_nothing(self):
        assert spy.slug("!!!") == ""


class TestHost:
    def test_scheme_port_path_query_and_www_are_stripped(self):
        assert spy.host("https://www.HubSpot.com:443/pricing?x=1#top") == "hubspot.com"

    def test_a_bare_host_passes_through(self):
        assert spy.host("hubspot.com") == "hubspot.com"

    def test_www_without_a_scheme_is_stripped(self):
        assert spy.host("www.hubspot.com/x") == "hubspot.com"

    def test_a_subdomain_is_kept(self):
        assert spy.host("https://blog.hubspot.com") == "blog.hubspot.com"

    def test_a_query_without_a_path_is_stripped(self):
        assert spy.host("hubspot.com?ref=1") == "hubspot.com"

    def test_surrounding_whitespace_is_ignored(self):
        assert spy.host("  https://zoho.com  ") == "zoho.com"


class TestHostMatches:
    @pytest.mark.parametrize(
        "value",
        [
            "hubspot.com",
            "www.hubspot.com",
            "https://www.hubspot.com/x",
            "blog.hubspot.com",
            "https://a.b.hubspot.com:8443/y",
        ],
    )
    def test_the_domain_its_www_and_its_subdomains_match(self, value):
        assert spy.host_matches(value, "hubspot.com") is True

    @pytest.mark.parametrize(
        "value",
        [
            "nothubspot.com",
            "hubspot.com.evil.io",
            "https://g2.com/hubspot.com",
            "hubspot.co",
            "",
        ],
    )
    def test_a_lookalike_does_not_match(self, value):
        assert spy.host_matches(value, "hubspot.com") is False


def _found(mentions):
    return [(m.company.name, m.rank, m.evidence) for m in mentions]


class TestMentions:
    def test_names_are_found_as_whole_words_case_insensitively(self, tracked):
        found = spy.mentions(tracked, "I moved from HUBSPOT to pipedrive.", [])
        assert _found(found) == [
            ("HubSpot", 1, "HUBSPOT"),
            ("Pipedrive", 2, "pipedrive"),
        ]

    def test_hubspots_is_not_hubspot(self, tracked):
        assert spy.mentions(tracked, "HubSpots are everywhere", []) == []

    def test_an_underscore_glues_a_word_together(self, tracked):
        assert spy.mentions(tracked, "try hubspot_crm", []) == []

    def test_punctuation_beside_a_name_still_counts(self, tracked):
        found = spy.mentions(tracked, "HubSpot, Zoho.", [])
        assert _found(found) == [("HubSpot", 1, "HubSpot"), ("Zoho CRM", 2, "Zoho")]

    def test_an_alias_is_a_mention_of_its_company(self, tracked):
        found = spy.mentions(tracked, "Zoho is fine", [])
        assert _found(found) == [("Zoho CRM", 1, "Zoho")]

    def test_the_earliest_of_a_companys_names_sets_its_position(self, tracked):
        found = spy.mentions(tracked, "Use Zoho, or Zoho CRM", [])
        assert _found(found) == [("Zoho CRM", 1, "Zoho")]

    def test_a_later_alias_does_not_move_a_company_back(self, tracked):
        found = spy.mentions(tracked, "HubSpot beats HubSpot CRM", [])
        assert _found(found) == [("HubSpot", 1, "HubSpot")]

    def test_the_name_wins_the_evidence_when_it_shares_the_position_with_an_alias(
        self, tracked
    ):
        found = spy.mentions(tracked, "Zoho CRM leads", [])
        assert _found(found) == [("Zoho CRM", 1, "Zoho CRM")]

    def test_a_name_with_regex_characters_is_taken_literally(self):
        tracked = spy.parse(_competitor(name="Sales.io", aliases=[]))
        assert _found(spy.mentions(tracked, "Sales.io rocks", [])) == [
            ("Sales.io", 1, "Sales.io")
        ]
        assert spy.mentions(tracked, "SalesXio rocks", []) == []

    def test_link_only_mentions_rank_after_text_mentions(self, tracked):
        found = spy.mentions(
            tracked,
            "Pipedrive is good",
            ["https://www.hubspot.com/x", "https://zoho.com/y"],
        )
        assert _found(found) == [
            ("Pipedrive", 1, "Pipedrive"),
            ("HubSpot", 2, "hubspot.com"),
            ("Zoho CRM", 3, "zoho.com"),
        ]

    def test_link_only_mentions_order_by_the_link_position(self, tracked):
        found = spy.mentions(tracked, "", ["https://zoho.com", "https://hubspot.com"])
        assert _found(found) == [
            ("Zoho CRM", 1, "zoho.com"),
            ("HubSpot", 2, "hubspot.com"),
        ]

    def test_the_first_matching_link_is_the_evidence(self, tracked):
        found = spy.mentions(
            tracked, "", ["https://blog.hubspot.com/a", "https://hubspot.com/b"]
        )
        assert _found(found) == [("HubSpot", 1, "blog.hubspot.com")]

    def test_a_company_in_the_text_and_the_links_is_a_text_mention(self, tracked):
        found = spy.mentions(tracked, "HubSpot", ["https://hubspot.com"])
        assert _found(found) == [("HubSpot", 1, "HubSpot")]

    def test_a_link_to_a_stranger_is_ignored(self, tracked):
        found = spy.mentions(
            tracked, "", ["https://g2.com/x", "https://nothubspot.com"]
        )
        assert found == []

    def test_a_tie_on_text_position_breaks_by_name(self):
        tracked = spy.parse(
            _doc(
                brand={"name": "Sales Hub", "domain": "saleshub.io", "aliases": []},
                competitors=[{"name": "Sales", "domain": "sales.io", "aliases": []}],
            )
        )
        found = spy.mentions(tracked, "Sales Hub wins", [])
        assert _found(found) == [("Sales", 1, "Sales"), ("Sales Hub", 2, "Sales Hub")]

    def test_a_tie_on_link_position_breaks_by_name(self):
        tracked = spy.parse(
            _doc(
                competitors=[
                    ZOHO,
                    {"name": "Bigin", "domain": "crm.zoho.com", "aliases": []},
                ]
            )
        )
        found = spy.mentions(tracked, "", ["https://crm.zoho.com/x"])
        assert _found(found) == [
            ("Bigin", 1, "crm.zoho.com"),
            ("Zoho CRM", 2, "crm.zoho.com"),
        ]

    def test_a_mention_carries_its_company(self, tracked):
        [mention] = spy.mentions(tracked, "pipedrive", [])
        assert mention.company is tracked.brand
        assert mention == spy.Mention(tracked.brand, 1, "pipedrive")


class TestSerpMentions:
    def test_the_rank_is_the_organic_position_not_a_renumbering(self, tracked):
        results = [
            {"position": 3, "link": "https://www.hubspot.com/x"},
            {"position": 7, "link": "https://pipedrive.com/y"},
        ]
        found = spy.serp_mentions(tracked, results)
        assert _found(found) == [
            ("HubSpot", 3, "hubspot.com"),
            ("Pipedrive", 7, "pipedrive.com"),
        ]

    def test_the_lowest_position_of_a_company_wins(self, tracked):
        results = [
            {"position": 5, "link": "https://hubspot.com/x"},
            {"position": 2, "link": "https://blog.hubspot.com/y"},
        ]
        assert _found(spy.serp_mentions(tracked, results)) == [
            ("HubSpot", 2, "blog.hubspot.com")
        ]

    def test_mentions_come_back_sorted_by_rank(self, tracked):
        results = [
            {"position": 9, "link": "https://zoho.com"},
            {"position": 1, "link": "https://pipedrive.com"},
            {"position": 4, "link": "https://hubspot.com"},
        ]
        assert [m.rank for m in spy.serp_mentions(tracked, results)] == [1, 4, 9]

    def test_a_tie_on_position_breaks_by_name(self):
        tracked = spy.parse(
            _doc(
                competitors=[
                    ZOHO,
                    {"name": "Bigin", "domain": "crm.zoho.com", "aliases": []},
                ]
            )
        )
        found = spy.serp_mentions(
            tracked, [{"position": 1, "link": "https://crm.zoho.com"}]
        )
        assert _found(found) == [
            ("Bigin", 1, "crm.zoho.com"),
            ("Zoho CRM", 1, "crm.zoho.com"),
        ]

    def test_strangers_and_linkless_results_are_ignored(self, tracked):
        results = [{"position": 1, "link": "https://g2.com"}, {"position": 2}]
        assert spy.serp_mentions(tracked, results) == []

    def test_no_results_is_no_mentions(self, tracked):
        assert spy.serp_mentions(tracked, []) == []
