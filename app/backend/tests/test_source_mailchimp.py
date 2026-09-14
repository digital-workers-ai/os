import json
from datetime import UTC, datetime

from app.engine import checks
from app.engine.pipeline import observed_at_for
from app.sources import registry
from app.sources.paginators import Offset
from tools.pull_source import key_types

FIXTURES = checks.REAL_FIXTURES.parent / "mock" / "mailchimp"
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)

LIVE_LIST_KEY_TYPES = {
    "_links": {"list"},
    "_links[].href": {"string"},
    "_links[].method": {"string"},
    "_links[].rel": {"string"},
    "_links[].schema": {"string"},
    "_links[].targetSchema": {"string"},
    "beamer_address": {"string"},
    "campaign_defaults": {"object"},
    "campaign_defaults.from_email": {"string"},
    "campaign_defaults.from_name": {"string"},
    "campaign_defaults.language": {"string"},
    "campaign_defaults.subject": {"string"},
    "contact": {"object"},
    "contact.address1": {"string"},
    "contact.address2": {"string"},
    "contact.city": {"string"},
    "contact.company": {"string"},
    "contact.country": {"string"},
    "contact.phone": {"string"},
    "contact.state": {"string"},
    "contact.zip": {"string"},
    "date_created": {"string"},
    "double_optin": {"bool"},
    "email_type_option": {"bool"},
    "has_welcome": {"bool"},
    "id": {"string"},
    "list_rating": {"number"},
    "marketing_permissions": {"bool"},
    "modules": {"list"},
    "name": {"string"},
    "notify_on_subscribe": {"string"},
    "notify_on_unsubscribe": {"string"},
    "permission_reminder": {"string"},
    "stats": {"object"},
    "stats.avg_sub_rate": {"number"},
    "stats.avg_unsub_rate": {"number"},
    "stats.campaign_count": {"number"},
    "stats.campaign_last_sent": {"string"},
    "stats.cleaned_count": {"number"},
    "stats.cleaned_count_since_send": {"number"},
    "stats.click_rate": {"number"},
    "stats.last_sub_date": {"string"},
    "stats.last_unsub_date": {"string"},
    "stats.member_count": {"number"},
    "stats.member_count_since_send": {"number"},
    "stats.merge_field_count": {"number"},
    "stats.open_rate": {"number"},
    "stats.target_sub_rate": {"number"},
    "stats.unsubscribe_count": {"number"},
    "stats.unsubscribe_count_since_send": {"number"},
    "subscribe_url_long": {"string"},
    "subscribe_url_short": {"string"},
    "use_archive_bar": {"bool"},
    "visibility": {"string"},
    "web_id": {"number"},
}

VENDOR_CAMPAIGN_STATUSES = {
    "save",
    "paused",
    "schedule",
    "sending",
    "sent",
    "canceled",
    "canceling",
    "archived",
}

LIST_TIMESTAMPS = (
    ("date_created",),
    ("stats", "campaign_last_sent"),
    ("stats", "last_sub_date"),
    ("stats", "last_unsub_date"),
)

CAMPAIGN_TIMESTAMPS = (("create_time",), ("send_time",))


def payloads(name):
    rows = json.loads((FIXTURES / f"{name}.json").read_text())
    return [row["payload"] for row in rows]


def dig(payload, path):
    for segment in path:
        payload = payload[segment]
    return payload


class TestTheAudienceFixtureCarriesWhatTheLiveApiAnswered:
    def test_every_key_and_type_is_one_the_live_account_returned(self):
        assert key_types(payloads("lists")) == LIVE_LIST_KEY_TYPES

    def test_both_audiences_carry_the_whole_record_not_a_subset(self):
        for payload in payloads("lists"):
            assert key_types([payload]) == LIVE_LIST_KEY_TYPES


class TestTheCampaignFixtureIsEveryCampaignTheStandInServes:
    def test_all_eight_campaigns_are_captured(self):
        assert len(payloads("campaigns")) == 8

    def test_both_audiences_are_captured(self):
        assert len(payloads("lists")) == 2


class TestCampaignStatusUsesTheVendorsOwnWords:
    def test_no_campaign_carries_a_status_outside_the_vendor_enum(self):
        seen = {payload["status"] for payload in payloads("campaigns")}
        assert seen <= VENDOR_CAMPAIGN_STATUSES

    def test_an_unsent_campaign_arrives_as_save_which_is_our_draft(self):
        seen = {payload["status"] for payload in payloads("campaigns")}
        assert "save" in seen
        assert "draft" not in seen


class TestTimestampsCarryAnOffsetTheWayMailchimpWritesThem:
    def test_audience_timestamps_end_in_an_offset(self):
        for payload in payloads("lists"):
            for path in LIST_TIMESTAMPS:
                value = dig(payload, path)
                assert isinstance(value, str)
                assert not value or value.endswith("+00:00")

    def test_campaign_timestamps_end_in_an_offset(self):
        for payload in payloads("campaigns"):
            for path in CAMPAIGN_TIMESTAMPS:
                value = dig(payload, path)
                assert isinstance(value, str)
                assert not value or value.endswith("+00:00")

    def test_a_campaign_that_never_went_out_has_a_blank_send_time(self):
        blank = [p for p in payloads("campaigns") if not p["send_time"]]
        assert len(blank) == 2
        assert all(p["send_time"] == "" for p in blank)

    def test_only_a_sent_campaign_reports_its_opens_and_clicks(self):
        for payload in payloads("campaigns"):
            assert ("report_summary" in payload) == bool(payload["send_time"])


class TestOffsetReadsTheEnvelopeMailchimpReturns:
    def test_the_audience_envelope_yields_its_records(self):
        envelope = {
            "lists": payloads("lists")[:1],
            "total_items": 1,
            "constraints": {
                "may_create": False,
                "max_instances": 1,
                "current_total_instances": 1,
            },
            "_links": [],
        }
        assert Offset("lists").extract(envelope) == envelope["lists"]

    def test_a_single_audience_ends_the_walk_after_one_request(self):
        envelope = {"lists": payloads("lists")[:1], "total_items": 1, "_links": []}
        assert Offset("lists").next_params(envelope, {"count": 5, "offset": 0}) is None

    def test_an_account_with_no_campaigns_ends_the_walk_too(self):
        envelope = {"campaigns": [], "total_items": 0, "_links": []}
        paginator = Offset("campaigns")
        assert paginator.extract(envelope) == []
        assert paginator.next_params(envelope, {"count": 5, "offset": 0}) is None

    def test_a_second_page_is_asked_for_while_records_remain(self):
        envelope = {"campaigns": payloads("campaigns")[:5], "total_items": 8}
        assert Offset("campaigns").next_params(envelope, {"count": 5, "offset": 0}) == {
            "count": 5,
            "offset": 5,
        }


class TestNeitherObjectExposesAnUpdateTimestamp:
    def test_the_connector_declares_no_observation_path(self):
        assert registry.get("mailchimp").OBSERVED_AT == {}

    def test_every_record_falls_back_to_the_ingest_clock(self):
        module = registry.get("mailchimp")
        for name in ("lists", "campaigns"):
            for payload in payloads(name):
                assert observed_at_for(module, name, payload, INGESTED) == (
                    INGESTED,
                    "ingested",
                )
