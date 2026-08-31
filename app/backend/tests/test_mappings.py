import pytest

from app.engine import mappings as m


class TestKeySplitting:
    def test_plain_dots_split(self):
        assert m.split_key("hubspot.companies.properties.domain") == [
            "hubspot",
            "companies",
            "properties",
            "domain",
        ]

    def test_escaped_dot_stays_inside_one_segment(self):
        assert m.split_key(r"amplitude.events.user_properties.utm\.source") == [
            "amplitude",
            "events",
            "user_properties",
            "utm.source",
        ]

    def test_google_ads_needs_no_escaping(self):
        assert m.split_key("google_ads.campaigns.campaign.name") == [
            "google_ads",
            "campaigns",
            "campaign",
            "name",
        ]

    def test_two_segments_is_not_a_mapping_line(self):
        with pytest.raises(m.MappingError):
            m.parse_line("company", "hubspot.domain", "domain", "test")

    def test_empty_segment_is_rejected(self):
        with pytest.raises(m.MappingError):
            m.parse_line("company", "hubspot..domain", "domain", "test")

    def test_label_is_required(self):
        with pytest.raises(m.MappingError):
            m.parse_line("company", "hubspot.companies.domain", "", "test")


class TestPathExtraction:
    def test_nested_walk(self):
        payload = {"campaign": {"name": "Brand Search"}}
        assert m.extract_path(payload, ("campaign", "name")) == "Brand Search"

    def test_absent_path_is_distinguishable_from_null(self):
        assert m.is_missing(m.extract_path({"a": 1}, ("b",)))
        assert not m.is_missing(m.extract_path({"b": None}, ("b",)))

    def test_walking_through_a_non_dict_is_absent_not_a_crash(self):
        assert m.is_missing(m.extract_path({"a": "scalar"}, ("a", "b")))

    def test_escaped_key_extracts(self):
        payload = {"props": {"utm.source": "google"}}
        path = tuple(m.split_key(r"x.y.props.utm\.source")[2:])
        assert m.extract_path(payload, path) == "google"


class TestShippedFile:
    def test_loads(self):
        assert len(m.load()) > 0

    def test_no_record_id_is_ever_mapped(self):
        lines = m.load()
        for line in lines:
            leaf = line.path[-1]
            assert leaf not in ("id", "Id", "hs_object_id"), line.key

    def test_by_object_index_covers_every_line(self):
        lines = m.load()
        assert sum(len(v) for v in m.by_object(lines).values()) == len(lines)
