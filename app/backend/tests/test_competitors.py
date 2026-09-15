import pytest
import yaml

from app.engine import competitors


def _competitor(domain="acme.io", **fields):
    return {
        "name": "Acme",
        "domain": domain,
        "meta_page_id": "100",
        "google_advertiser_id": "AR100",
        **fields,
    }


def _document(**overrides):
    doc = {
        "us": {"name": "Digital Workers", "domain": "hiredigitalworkers.com"},
        "competitors": {"acme": _competitor()},
        "keywords": ["ai ugc ads"],
        "prompts": ["best ai ugc ad tool"],
        "engines": ["chatgpt"],
    }
    for key, value in overrides.items():
        if value is None:
            doc.pop(key)
        else:
            doc[key] = value
    return doc


def _file(root, doc):
    path = root / "competitors.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def _check(root, **overrides):
    return competitors.check(_file(root, _document(**overrides)))


class TestTheShippedFile:
    def test_the_shipped_file_has_no_problems(self):
        assert competitors.check() == []

    def test_load_returns_the_whole_document(self):
        doc = competitors.load()
        assert set(doc) == {"us", "competitors", "keywords", "prompts", "engines"}

    def test_us_names_this_company_and_its_domain(self):
        us = competitors.load()["us"]
        assert us["name"] == "Digital Workers"
        assert us["domain"] == "hiredigitalworkers.com"

    def test_tracked_returns_only_the_competitors(self):
        assert competitors.tracked() == competitors.load()["competitors"]

    def test_every_tracked_competitor_carries_both_platform_ids(self):
        for spec in competitors.tracked().values():
            assert all(spec[key] for key in competitors.PLATFORM_IDS)

    def test_the_three_original_competitors_kept_their_ids(self):
        tracked = competitors.tracked()
        assert {name: spec["meta_page_id"] for name, spec in tracked.items()} == {
            "vidora": "204815000001",
            "clipwise": "204815000002",
            "avatarly": "204815000003",
        }

    def test_the_engines_are_all_answer_engines_the_system_knows(self):
        assert set(competitors.load()["engines"]) <= set(competitors.ENGINES)


class TestTheDocumentShape:
    def test_a_well_formed_document_has_no_problems(self, tmp_path):
        assert _check(tmp_path) == []

    def test_a_file_that_is_not_a_mapping_is_one_problem(self, tmp_path):
        path = tmp_path / "competitors.yaml"
        path.write_text("- a\n")
        problems = competitors.check(path)
        assert len(problems) == 1, problems
        assert "competitors.yaml" in problems[0]

    def test_a_document_with_no_competitors_block_is_refused(self, tmp_path):
        problems = _check(tmp_path, competitors=None)
        assert any("competitors" in p for p in problems), problems

    def test_a_competitors_block_that_is_not_a_mapping_is_refused(self, tmp_path):
        problems = _check(tmp_path, competitors=["acme"])
        assert any("competitors" in p for p in problems), problems


class TestUsIsChecked:
    def test_a_document_with_no_us_block_is_refused(self, tmp_path):
        problems = _check(tmp_path, us=None)
        assert any("us" in p for p in problems), problems

    def test_an_us_block_that_is_not_a_mapping_is_refused(self, tmp_path):
        problems = _check(tmp_path, us="Digital Workers")
        assert any("us" in p for p in problems), problems

    @pytest.mark.parametrize("key", ["name", "domain"])
    def test_us_without_a_name_or_a_domain_names_the_key(self, tmp_path, key):
        us = {"name": "Digital Workers", "domain": "hiredigitalworkers.com"}
        us.pop(key)
        problems = _check(tmp_path, us=us)
        assert any("us" in p and key in p for p in problems), problems

    def test_our_own_domain_may_not_also_be_tracked_as_a_competitor(self, tmp_path):
        problems = _check(
            tmp_path,
            competitors={"acme": _competitor("hiredigitalworkers.com")},
        )
        assert any("hiredigitalworkers.com" in p and "acme" in p for p in problems), (
            problems
        )


class TestTheListsAreChecked:
    @pytest.mark.parametrize("key", ["keywords", "prompts", "engines"])
    def test_a_missing_list_names_the_key(self, tmp_path, key):
        problems = _check(tmp_path, **{key: None})
        assert any(key in p for p in problems), problems

    @pytest.mark.parametrize("key", ["keywords", "prompts", "engines"])
    def test_a_list_that_is_not_a_list_names_the_key(self, tmp_path, key):
        problems = _check(tmp_path, **{key: "chatgpt"})
        assert any(key in p for p in problems), problems

    @pytest.mark.parametrize("key", ["keywords", "prompts", "engines"])
    def test_an_empty_list_names_the_key(self, tmp_path, key):
        problems = _check(tmp_path, **{key: []})
        assert any(key in p for p in problems), problems

    def test_an_entry_that_is_not_a_name_is_refused(self, tmp_path):
        problems = _check(tmp_path, keywords=["ai ugc ads", "   ", 7])
        assert len([p for p in problems if "keywords" in p]) == 2, problems

    def test_an_engine_nothing_can_read_lists_the_known_ones(self, tmp_path):
        problems = _check(tmp_path, engines=["chatgpt", "askjeeves"])
        assert any("askjeeves" in p and "perplexity" in p for p in problems), problems


class TestEachCompetitorIsChecked:
    def test_a_competitor_without_a_domain_is_refused_and_named(self, tmp_path):
        spec = _competitor()
        spec.pop("domain")
        problems = _check(tmp_path, competitors={"acme": spec})
        assert any("acme" in p and "domain" in p for p in problems), problems

    def test_two_competitors_sharing_a_domain_are_refused(self, tmp_path):
        problems = _check(
            tmp_path,
            competitors={
                "acme": _competitor("acme.io"),
                "globex": _competitor(
                    "acme.io", meta_page_id="200", google_advertiser_id="AR200"
                ),
            },
        )
        assert any("acme.io" in p and "globex" in p for p in problems), problems

    @pytest.mark.parametrize("key", ["meta_page_id", "google_advertiser_id"])
    def test_a_competitor_missing_a_platform_id_names_the_key(self, tmp_path, key):
        spec = _competitor()
        spec.pop(key)
        problems = _check(tmp_path, competitors={"acme": spec})
        assert any("acme" in p and key in p for p in problems), problems

    def test_a_competitor_that_is_not_a_mapping_is_refused_and_named(self, tmp_path):
        problems = _check(tmp_path, competitors={"acme": "acme.io"})
        assert problems == ["competitor 'acme' must be a mapping"]
