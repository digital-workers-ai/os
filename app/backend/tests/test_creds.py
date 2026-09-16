import os

import pytest

from app.config import Settings, settings
from app.sources import creds

TOKEN = "pat-test-0000"


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("HUBSPOT_ACCESS_TOKEN", "HUBSPOT_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


class TestTheMockIsTheDefault:
    def test_no_variable_set_means_the_mock(self, clean_env):
        found = creds.credentials_for("hubspot")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/hubspot"
        assert found.headers == {"Authorization": "Bearer mock_hs_token"}

    def test_an_empty_variable_counts_as_unset(self, clean_env, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "")
        found = creds.credentials_for("hubspot")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/hubspot"

    def test_a_base_url_override_alone_does_not_leave_the_mock(
        self, clean_env, monkeypatch
    ):
        monkeypatch.setenv("HUBSPOT_BASE_URL", "https://hubspot.example.test/v3")
        found = creds.credentials_for("hubspot")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/hubspot"


class TestRealCredentialsComeFromTheEnvironment:
    def test_the_token_becomes_a_bearer_header_on_the_real_api(
        self, clean_env, monkeypatch
    ):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", TOKEN)
        found = creds.credentials_for("hubspot")
        assert found.base_url == "https://api.hubapi.com"
        assert found.headers == {"Authorization": f"Bearer {TOKEN}"}
        assert found.auth is None
        assert found.params == {}

    def test_the_base_url_can_be_overridden(self, clean_env, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", TOKEN)
        monkeypatch.setenv("HUBSPOT_BASE_URL", "https://hubspot.example.test/v3")
        found = creds.credentials_for("hubspot")
        assert found.base_url == "https://hubspot.example.test/v3"
        assert found.headers == {"Authorization": f"Bearer {TOKEN}"}


class TestAPartialEnvironmentIsRefused:
    NAMES = ("TWILIO_TEST_SID", "TWILIO_TEST_TOKEN")

    @pytest.fixture
    def two_variable_source(self, monkeypatch):
        monkeypatch.setitem(
            creds._REAL,
            "twilio",
            (
                "https://twilio.example.test",
                self.NAMES,
                lambda sid, token: ({}, (sid, token), {}, {}),
            ),
        )
        for name in self.NAMES:
            monkeypatch.delenv(name, raising=False)

    def test_the_missing_variable_is_named(self, two_variable_source, monkeypatch):
        monkeypatch.setenv("TWILIO_TEST_SID", "sid-test")
        with pytest.raises(creds.CredentialsError) as caught:
            creds.credentials_for("twilio")
        assert "twilio" in str(caught.value)
        assert "TWILIO_TEST_TOKEN" in str(caught.value)

    def test_the_name_follows_whichever_is_missing(
        self, two_variable_source, monkeypatch
    ):
        monkeypatch.setenv("TWILIO_TEST_TOKEN", "token-test")
        with pytest.raises(creds.CredentialsError, match="TWILIO_TEST_SID"):
            creds.credentials_for("twilio")

    def test_every_variable_set_builds_from_all_of_them(
        self, two_variable_source, monkeypatch
    ):
        monkeypatch.setenv("TWILIO_TEST_SID", "sid-test")
        monkeypatch.setenv("TWILIO_TEST_TOKEN", "token-test")
        found = creds.credentials_for("twilio")
        assert found.base_url == "https://twilio.example.test"
        assert found.auth == ("sid-test", "token-test")

    def test_none_set_is_still_the_mock(self, two_variable_source):
        found = creds.credentials_for("twilio")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/twilio"
        assert found.auth == ("mock_account_sid", "mock_auth_token")


class TestSourcesWithoutARealEntryAreUntouched:
    def test_an_unknown_source_still_names_itself(self, monkeypatch):
        monkeypatch.setenv("NOPE_ACCESS_TOKEN", TOKEN)
        with pytest.raises(KeyError, match="nope"):
            creds.credentials_for("nope")

    def test_another_sources_token_leaves_zendesk_on_the_mock(self, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", TOKEN)
        found = creds.credentials_for("zendesk")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/zendesk/api/v2"
        assert found.headers == {"Authorization": "Bearer mock_zendesk_token"}


STRIPE_KEY = "stripe-key-test-0000"
INTERCOM_TOKEN = "intercom-token-test-0000"
AMPLITUDE_KEY = "amplitude-key-test-0000"
AMPLITUDE_SECRET = "amplitude-secret-test-0000"
SHOPIFY_DOMAIN = "store-test.myshopify.test"
SHOPIFY_TOKEN = "shopify-token-test-0000"


@pytest.fixture
def clean_stripe(monkeypatch):
    for name in ("STRIPE_API_KEY", "STRIPE_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def clean_intercom(monkeypatch):
    for name in ("INTERCOM_ACCESS_TOKEN", "INTERCOM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def clean_amplitude(monkeypatch):
    for name in ("AMPLITUDE_API_KEY", "AMPLITUDE_SECRET_KEY", "AMPLITUDE_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def clean_shopify(monkeypatch):
    for name in ("SHOPIFY_STORE_DOMAIN", "SHOPIFY_ACCESS_TOKEN", "SHOPIFY_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


class TestStripeTakesItsKeyFromTheEnvironment:
    def test_no_variable_set_means_the_mock(self, clean_stripe):
        found = creds.credentials_for("stripe")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/stripe"
        assert found.headers == {"Authorization": "Bearer mock_stripe_key"}

    def test_the_key_becomes_a_bearer_header_on_the_real_api(
        self, clean_stripe, monkeypatch
    ):
        monkeypatch.setenv("STRIPE_API_KEY", STRIPE_KEY)
        found = creds.credentials_for("stripe")
        assert found.base_url == "https://api.stripe.com"
        assert found.headers == {"Authorization": f"Bearer {STRIPE_KEY}"}
        assert found.auth is None
        assert found.params == {}

    def test_the_base_url_can_be_overridden(self, clean_stripe, monkeypatch):
        monkeypatch.setenv("STRIPE_API_KEY", STRIPE_KEY)
        monkeypatch.setenv("STRIPE_BASE_URL", "https://stripe.example.test")
        found = creds.credentials_for("stripe")
        assert found.base_url == "https://stripe.example.test"


class TestIntercomCarriesItsVersionHeader:
    def test_no_variable_set_means_the_mock(self, clean_intercom):
        found = creds.credentials_for("intercom")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/intercom"

    def test_the_token_and_the_version_reach_the_real_api(
        self, clean_intercom, monkeypatch
    ):
        monkeypatch.setenv("INTERCOM_ACCESS_TOKEN", INTERCOM_TOKEN)
        found = creds.credentials_for("intercom")
        assert found.base_url == "https://api.intercom.io"
        assert found.headers == {
            "Authorization": f"Bearer {INTERCOM_TOKEN}",
            "Accept": "application/json",
            "intercom-version": "2.10",
        }
        assert found.auth is None
        assert found.params == {}

    def test_the_version_header_matches_the_stand_in(self, clean_intercom, monkeypatch):
        monkeypatch.setenv("INTERCOM_ACCESS_TOKEN", INTERCOM_TOKEN)
        found = creds.credentials_for("intercom")
        mock_headers = creds._MOCK["intercom"][1]
        assert found.headers["intercom-version"] == mock_headers["intercom-version"]

    def test_the_base_url_can_be_overridden(self, clean_intercom, monkeypatch):
        monkeypatch.setenv("INTERCOM_ACCESS_TOKEN", INTERCOM_TOKEN)
        monkeypatch.setenv("INTERCOM_BASE_URL", "https://intercom.example.test")
        found = creds.credentials_for("intercom")
        assert found.base_url == "https://intercom.example.test"


class TestAmplitudeSignsWithAKeyAndASecret:
    def test_no_variable_set_means_the_mock(self, clean_amplitude):
        found = creds.credentials_for("amplitude")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/amplitude"
        assert found.auth == ("mock_amplitude_key", "mock_amplitude_secret")

    def test_both_variables_become_basic_auth_on_the_real_api(
        self, clean_amplitude, monkeypatch
    ):
        monkeypatch.setenv("AMPLITUDE_API_KEY", AMPLITUDE_KEY)
        monkeypatch.setenv("AMPLITUDE_SECRET_KEY", AMPLITUDE_SECRET)
        found = creds.credentials_for("amplitude")
        assert found.base_url == "https://amplitude.com"
        assert found.auth == (AMPLITUDE_KEY, AMPLITUDE_SECRET)
        assert found.headers == {}
        assert found.params == {}

    def test_the_base_url_reaches_the_export_endpoint(
        self, clean_amplitude, monkeypatch
    ):
        monkeypatch.setenv("AMPLITUDE_API_KEY", AMPLITUDE_KEY)
        monkeypatch.setenv("AMPLITUDE_SECRET_KEY", AMPLITUDE_SECRET)
        found = creds.credentials_for("amplitude")
        assert f"{found.base_url}/api/2/export" == "https://amplitude.com/api/2/export"

    def test_the_key_alone_names_the_missing_secret(self, clean_amplitude, monkeypatch):
        monkeypatch.setenv("AMPLITUDE_API_KEY", AMPLITUDE_KEY)
        with pytest.raises(creds.CredentialsError, match="AMPLITUDE_SECRET_KEY"):
            creds.credentials_for("amplitude")

    def test_the_secret_alone_names_the_missing_key(self, clean_amplitude, monkeypatch):
        monkeypatch.setenv("AMPLITUDE_SECRET_KEY", AMPLITUDE_SECRET)
        with pytest.raises(creds.CredentialsError, match="AMPLITUDE_API_KEY"):
            creds.credentials_for("amplitude")

    def test_the_base_url_can_be_overridden(self, clean_amplitude, monkeypatch):
        monkeypatch.setenv("AMPLITUDE_API_KEY", AMPLITUDE_KEY)
        monkeypatch.setenv("AMPLITUDE_SECRET_KEY", AMPLITUDE_SECRET)
        monkeypatch.setenv("AMPLITUDE_BASE_URL", "https://amplitude.example.test")
        found = creds.credentials_for("amplitude")
        assert found.base_url == "https://amplitude.example.test"


class TestShopifyBuildsItsBaseUrlFromTheStoreDomain:
    def test_no_variable_set_means_the_mock(self, clean_shopify):
        found = creds.credentials_for("shopify")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/shopify"
        assert found.headers == {"X-Shopify-Access-Token": "mock_shopify_token"}

    def test_the_domain_becomes_the_host_and_the_token_a_header(
        self, clean_shopify, monkeypatch
    ):
        monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", SHOPIFY_DOMAIN)
        monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", SHOPIFY_TOKEN)
        found = creds.credentials_for("shopify")
        assert found.base_url == f"https://{SHOPIFY_DOMAIN}"
        assert found.headers == {"X-Shopify-Access-Token": SHOPIFY_TOKEN}
        assert found.auth is None
        assert found.params == {}

    def test_neither_base_repeats_the_versioned_path(self, clean_shopify, monkeypatch):
        assert "/admin/api" not in creds._MOCK["shopify"][0]
        monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", SHOPIFY_DOMAIN)
        monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", SHOPIFY_TOKEN)
        assert "/admin/api" not in creds.credentials_for("shopify").base_url

    def test_the_domain_alone_names_the_missing_token(self, clean_shopify, monkeypatch):
        monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", SHOPIFY_DOMAIN)
        with pytest.raises(creds.CredentialsError, match="SHOPIFY_ACCESS_TOKEN"):
            creds.credentials_for("shopify")

    def test_the_token_alone_names_the_missing_domain(self, clean_shopify, monkeypatch):
        monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", SHOPIFY_TOKEN)
        with pytest.raises(creds.CredentialsError, match="SHOPIFY_STORE_DOMAIN"):
            creds.credentials_for("shopify")

    def test_the_base_url_override_wins_over_the_store_domain(
        self, clean_shopify, monkeypatch
    ):
        monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", SHOPIFY_DOMAIN)
        monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", SHOPIFY_TOKEN)
        monkeypatch.setenv("SHOPIFY_BASE_URL", "https://shopify.example.test")
        found = creds.credentials_for("shopify")
        assert found.base_url == "https://shopify.example.test"
        assert found.headers == {"X-Shopify-Access-Token": SHOPIFY_TOKEN}

    def test_a_base_url_override_alone_does_not_leave_the_mock(
        self, clean_shopify, monkeypatch
    ):
        monkeypatch.setenv("SHOPIFY_BASE_URL", "https://shopify.example.test")
        found = creds.credentials_for("shopify")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/shopify"


KLAVIYO_KEY = "klaviyo-key-test-0000"
CALENDLY_TOKEN = "calendly-token-test-0000"
CALENDLY_USER = "https://api.calendly.com/users/USER-TEST-0000"
MAILCHIMP_KEY = "mailchimp-key-test-us42"
TWILIO_ACCOUNT = "AC-account-test-0000"
TWILIO_KEY_SID = "SK-key-test-0000"
TWILIO_KEY_SECRET = "twilio-secret-test-0000"
MIXPANEL_USERNAME = "mixpanel-user-test-0000"
MIXPANEL_SECRET = "mixpanel-secret-test-0000"
MIXPANEL_PROJECT = "7654321"
ACTIVECAMPAIGN_BASE = "https://account-test.api-us1.test"
ACTIVECAMPAIGN_KEY = "activecampaign-key-test-0000"
TWITTER_TOKEN = "twitter-bearer-test-0000"
TWITTER_USER = "4030300010"


@pytest.fixture
def clean_klaviyo(monkeypatch):
    for name in ("KLAVIYO_API_KEY", "KLAVIYO_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def clean_calendly(monkeypatch):
    for name in ("CALENDLY_ACCESS_TOKEN", "CALENDLY_USER_URI", "CALENDLY_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def clean_mailchimp(monkeypatch):
    for name in ("MAILCHIMP_API_KEY", "MAILCHIMP_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def clean_twilio(monkeypatch):
    for name in (
        "TWILIO_ACCOUNT_SID",
        "TWILIO_API_KEY_SID",
        "TWILIO_API_KEY_SECRET",
        "TWILIO_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def clean_mixpanel(monkeypatch):
    for name in (
        "MIXPANEL_SERVICE_ACCOUNT_USERNAME",
        "MIXPANEL_SERVICE_ACCOUNT_SECRET",
        "MIXPANEL_PROJECT_ID",
        "MIXPANEL_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def clean_activecampaign(monkeypatch):
    for name in ("ACTIVECAMPAIGN_BASE_URL", "ACTIVECAMPAIGN_API_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def clean_twitter(monkeypatch):
    for name in ("TWITTER_BEARER_TOKEN", "TWITTER_USER_ID", "TWITTER_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


class TestKlaviyoCarriesItsOwnKeyScheme:
    def test_no_variable_set_means_the_mock(self, clean_klaviyo):
        found = creds.credentials_for("klaviyo")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/klaviyo"
        assert found.headers["Authorization"] == "Klaviyo-API-Key mock_klaviyo_key"

    def test_the_key_and_the_revision_reach_the_real_api(
        self, clean_klaviyo, monkeypatch
    ):
        monkeypatch.setenv("KLAVIYO_API_KEY", KLAVIYO_KEY)
        found = creds.credentials_for("klaviyo")
        assert found.base_url == "https://a.klaviyo.com"
        assert found.headers == {
            "Authorization": f"Klaviyo-API-Key {KLAVIYO_KEY}",
            "revision": "2026-07-15",
        }
        assert found.auth is None
        assert found.params == {}
        assert found.values == {}

    def test_the_revision_matches_the_stand_in(self, clean_klaviyo, monkeypatch):
        monkeypatch.setenv("KLAVIYO_API_KEY", KLAVIYO_KEY)
        found = creds.credentials_for("klaviyo")
        assert found.headers["revision"] == creds._MOCK["klaviyo"][1]["revision"]

    def test_the_base_url_can_be_overridden(self, clean_klaviyo, monkeypatch):
        monkeypatch.setenv("KLAVIYO_API_KEY", KLAVIYO_KEY)
        monkeypatch.setenv("KLAVIYO_BASE_URL", "https://klaviyo.example.test")
        assert (
            creds.credentials_for("klaviyo").base_url == "https://klaviyo.example.test"
        )


class TestCalendlyCarriesTheUserItPullsFor:
    def test_no_variable_set_means_the_mock(self, clean_calendly):
        found = creds.credentials_for("calendly")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/calendly"
        assert found.params == {}

    def test_the_token_authenticates_and_the_uri_becomes_a_query_parameter(
        self, clean_calendly, monkeypatch
    ):
        monkeypatch.setenv("CALENDLY_ACCESS_TOKEN", CALENDLY_TOKEN)
        monkeypatch.setenv("CALENDLY_USER_URI", CALENDLY_USER)
        found = creds.credentials_for("calendly")
        assert found.base_url == "https://api.calendly.com"
        assert found.headers == {"Authorization": f"Bearer {CALENDLY_TOKEN}"}
        assert found.auth is None
        assert found.params == {"user": CALENDLY_USER}

    def test_the_uri_is_never_sent_as_a_credential(self, clean_calendly, monkeypatch):
        monkeypatch.setenv("CALENDLY_ACCESS_TOKEN", CALENDLY_TOKEN)
        monkeypatch.setenv("CALENDLY_USER_URI", CALENDLY_USER)
        found = creds.credentials_for("calendly")
        assert CALENDLY_USER not in found.headers["Authorization"]

    def test_the_token_alone_names_the_missing_uri(self, clean_calendly, monkeypatch):
        monkeypatch.setenv("CALENDLY_ACCESS_TOKEN", CALENDLY_TOKEN)
        with pytest.raises(creds.CredentialsError, match="CALENDLY_USER_URI"):
            creds.credentials_for("calendly")

    def test_the_uri_alone_names_the_missing_token(self, clean_calendly, monkeypatch):
        monkeypatch.setenv("CALENDLY_USER_URI", CALENDLY_USER)
        with pytest.raises(creds.CredentialsError, match="CALENDLY_ACCESS_TOKEN"):
            creds.credentials_for("calendly")

    def test_the_base_url_can_be_overridden(self, clean_calendly, monkeypatch):
        monkeypatch.setenv("CALENDLY_ACCESS_TOKEN", CALENDLY_TOKEN)
        monkeypatch.setenv("CALENDLY_USER_URI", CALENDLY_USER)
        monkeypatch.setenv("CALENDLY_BASE_URL", "https://calendly.example.test")
        found = creds.credentials_for("calendly")
        assert found.base_url == "https://calendly.example.test"
        assert found.params == {"user": CALENDLY_USER}


class TestMailchimpFindsItsDataCentreInTheKey:
    def test_no_variable_set_means_the_mock(self, clean_mailchimp):
        found = creds.credentials_for("mailchimp")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/mailchimp"
        assert found.auth == ("anystring", "mock_mailchimp_key")

    def test_the_suffix_after_the_last_dash_becomes_the_host(
        self, clean_mailchimp, monkeypatch
    ):
        monkeypatch.setenv("MAILCHIMP_API_KEY", MAILCHIMP_KEY)
        found = creds.credentials_for("mailchimp")
        assert found.base_url == "https://us42.api.mailchimp.com"
        assert found.auth == ("anystring", MAILCHIMP_KEY)
        assert found.headers == {}
        assert found.values == {"dc": "us42"}

    def test_another_key_moves_to_another_data_centre(
        self, clean_mailchimp, monkeypatch
    ):
        monkeypatch.setenv("MAILCHIMP_API_KEY", "mailchimp-key-test-eu7")
        found = creds.credentials_for("mailchimp")
        assert found.base_url == "https://eu7.api.mailchimp.com"

    def test_the_base_does_not_repeat_the_version_the_paths_carry(
        self, clean_mailchimp, monkeypatch
    ):
        monkeypatch.setenv("MAILCHIMP_API_KEY", MAILCHIMP_KEY)
        found = creds.credentials_for("mailchimp")
        assert "/3.0" not in found.base_url
        assert (
            f"{found.base_url}/3.0/lists" == "https://us42.api.mailchimp.com/3.0/lists"
        )

    def test_a_key_with_no_data_centre_is_refused_without_echoing_it(
        self, clean_mailchimp, monkeypatch
    ):
        monkeypatch.setenv("MAILCHIMP_API_KEY", "keywithnodatacentre")
        with pytest.raises(creds.CredentialsError) as caught:
            creds.credentials_for("mailchimp")
        assert "MAILCHIMP_API_KEY" in str(caught.value)
        assert "keywithnodatacentre" not in str(caught.value)

    def test_the_base_url_can_be_overridden(self, clean_mailchimp, monkeypatch):
        monkeypatch.setenv("MAILCHIMP_API_KEY", MAILCHIMP_KEY)
        monkeypatch.setenv("MAILCHIMP_BASE_URL", "https://mailchimp.example.test")
        found = creds.credentials_for("mailchimp")
        assert found.base_url == "https://mailchimp.example.test"


class TestTwilioSignsWithAnApiKeyAndPathsByAccount:
    def test_no_variable_set_means_the_mock(self, clean_twilio):
        found = creds.credentials_for("twilio")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/twilio"
        assert found.auth == ("mock_account_sid", "mock_auth_token")
        assert found.values == {"account_sid": "mock_account_sid"}

    def test_the_api_key_pair_signs_and_the_account_stays_a_path_value(
        self, clean_twilio, monkeypatch
    ):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT)
        monkeypatch.setenv("TWILIO_API_KEY_SID", TWILIO_KEY_SID)
        monkeypatch.setenv("TWILIO_API_KEY_SECRET", TWILIO_KEY_SECRET)
        found = creds.credentials_for("twilio")
        assert found.base_url == "https://api.twilio.com"
        assert found.auth == (TWILIO_KEY_SID, TWILIO_KEY_SECRET)
        assert found.headers == {}
        assert found.params == {}
        assert found.values == {"account_sid": TWILIO_ACCOUNT}

    @pytest.mark.parametrize(
        "missing",
        ["TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET"],
    )
    def test_any_one_missing_is_named(self, clean_twilio, monkeypatch, missing):
        for name, value in (
            ("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT),
            ("TWILIO_API_KEY_SID", TWILIO_KEY_SID),
            ("TWILIO_API_KEY_SECRET", TWILIO_KEY_SECRET),
        ):
            if name != missing:
                monkeypatch.setenv(name, value)
        with pytest.raises(creds.CredentialsError, match=missing):
            creds.credentials_for("twilio")

    def test_the_base_url_can_be_overridden(self, clean_twilio, monkeypatch):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT)
        monkeypatch.setenv("TWILIO_API_KEY_SID", TWILIO_KEY_SID)
        monkeypatch.setenv("TWILIO_API_KEY_SECRET", TWILIO_KEY_SECRET)
        monkeypatch.setenv("TWILIO_BASE_URL", "https://twilio.example.test")
        assert creds.credentials_for("twilio").base_url == "https://twilio.example.test"


class TestMixpanelCarriesItsProjectOnEveryRequest:
    def test_no_variable_set_means_the_mock(self, clean_mixpanel):
        found = creds.credentials_for("mixpanel")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/mixpanel"
        assert found.auth == ("mock_mixpanel_secret", "")
        assert found.params == {}

    def test_the_service_account_signs_and_the_project_is_a_query_parameter(
        self, clean_mixpanel, monkeypatch
    ):
        monkeypatch.setenv("MIXPANEL_SERVICE_ACCOUNT_USERNAME", MIXPANEL_USERNAME)
        monkeypatch.setenv("MIXPANEL_SERVICE_ACCOUNT_SECRET", MIXPANEL_SECRET)
        monkeypatch.setenv("MIXPANEL_PROJECT_ID", MIXPANEL_PROJECT)
        found = creds.credentials_for("mixpanel")
        assert found.base_url == "https://data.mixpanel.com"
        assert found.auth == (MIXPANEL_USERNAME, MIXPANEL_SECRET)
        assert found.headers == {}
        assert found.params == {"project_id": MIXPANEL_PROJECT}

    @pytest.mark.parametrize(
        "missing",
        [
            "MIXPANEL_SERVICE_ACCOUNT_USERNAME",
            "MIXPANEL_SERVICE_ACCOUNT_SECRET",
            "MIXPANEL_PROJECT_ID",
        ],
    )
    def test_any_one_missing_is_named(self, clean_mixpanel, monkeypatch, missing):
        for name, value in (
            ("MIXPANEL_SERVICE_ACCOUNT_USERNAME", MIXPANEL_USERNAME),
            ("MIXPANEL_SERVICE_ACCOUNT_SECRET", MIXPANEL_SECRET),
            ("MIXPANEL_PROJECT_ID", MIXPANEL_PROJECT),
        ):
            if name != missing:
                monkeypatch.setenv(name, value)
        with pytest.raises(creds.CredentialsError, match=missing):
            creds.credentials_for("mixpanel")

    def test_the_base_url_reaches_the_export_endpoint(
        self, clean_mixpanel, monkeypatch
    ):
        monkeypatch.setenv("MIXPANEL_SERVICE_ACCOUNT_USERNAME", MIXPANEL_USERNAME)
        monkeypatch.setenv("MIXPANEL_SERVICE_ACCOUNT_SECRET", MIXPANEL_SECRET)
        monkeypatch.setenv("MIXPANEL_PROJECT_ID", MIXPANEL_PROJECT)
        found = creds.credentials_for("mixpanel")
        assert (
            f"{found.base_url}/api/2.0/export"
            == "https://data.mixpanel.com/api/2.0/export"
        )

    def test_the_base_url_can_be_overridden(self, clean_mixpanel, monkeypatch):
        monkeypatch.setenv("MIXPANEL_SERVICE_ACCOUNT_USERNAME", MIXPANEL_USERNAME)
        monkeypatch.setenv("MIXPANEL_SERVICE_ACCOUNT_SECRET", MIXPANEL_SECRET)
        monkeypatch.setenv("MIXPANEL_PROJECT_ID", MIXPANEL_PROJECT)
        monkeypatch.setenv("MIXPANEL_BASE_URL", "https://mixpanel.example.test")
        found = creds.credentials_for("mixpanel")
        assert found.base_url == "https://mixpanel.example.test"
        assert found.params == {"project_id": MIXPANEL_PROJECT}


class TestActivecampaignIsHostedPerAccount:
    def test_no_variable_set_means_the_mock(self, clean_activecampaign):
        found = creds.credentials_for("activecampaign")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/activecampaign"
        assert found.headers == {"Api-Token": "mock_ac_token"}

    def test_the_account_url_becomes_the_base_and_the_key_a_header(
        self, clean_activecampaign, monkeypatch
    ):
        monkeypatch.setenv("ACTIVECAMPAIGN_BASE_URL", ACTIVECAMPAIGN_BASE)
        monkeypatch.setenv("ACTIVECAMPAIGN_API_KEY", ACTIVECAMPAIGN_KEY)
        found = creds.credentials_for("activecampaign")
        assert found.base_url == ACTIVECAMPAIGN_BASE
        assert found.headers == {"Api-Token": ACTIVECAMPAIGN_KEY}
        assert found.auth is None
        assert found.params == {}

    @pytest.mark.parametrize("suffix", ["/", "/api/3", "/api/3/"])
    def test_what_the_paths_already_carry_is_stripped(
        self, clean_activecampaign, monkeypatch, suffix
    ):
        monkeypatch.setenv("ACTIVECAMPAIGN_BASE_URL", f"{ACTIVECAMPAIGN_BASE}{suffix}")
        monkeypatch.setenv("ACTIVECAMPAIGN_API_KEY", ACTIVECAMPAIGN_KEY)
        found = creds.credentials_for("activecampaign")
        assert found.base_url == ACTIVECAMPAIGN_BASE
        assert f"{found.base_url}/api/3/contacts".count("/api/3") == 1

    def test_the_url_alone_names_the_missing_key(
        self, clean_activecampaign, monkeypatch
    ):
        monkeypatch.setenv("ACTIVECAMPAIGN_BASE_URL", ACTIVECAMPAIGN_BASE)
        with pytest.raises(creds.CredentialsError, match="ACTIVECAMPAIGN_API_KEY"):
            creds.credentials_for("activecampaign")

    def test_the_key_alone_names_the_missing_url(
        self, clean_activecampaign, monkeypatch
    ):
        monkeypatch.setenv("ACTIVECAMPAIGN_API_KEY", ACTIVECAMPAIGN_KEY)
        with pytest.raises(creds.CredentialsError, match="ACTIVECAMPAIGN_BASE_URL"):
            creds.credentials_for("activecampaign")


class TestTwitterReadsABearerTokenAndPathsByUser:
    def test_no_variable_set_means_the_mock(self, clean_twitter):
        found = creds.credentials_for("twitter")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/twitter"
        assert found.headers == {"Authorization": "Bearer mock_twitter_token"}
        assert found.values == {"user_id": "me"}

    def test_the_token_becomes_a_bearer_header_and_the_user_stays_a_path_value(
        self, clean_twitter, monkeypatch
    ):
        monkeypatch.setenv("TWITTER_BEARER_TOKEN", TWITTER_TOKEN)
        monkeypatch.setenv("TWITTER_USER_ID", TWITTER_USER)
        found = creds.credentials_for("twitter")
        assert found.base_url == "https://api.x.com"
        assert found.headers == {"Authorization": f"Bearer {TWITTER_TOKEN}"}
        assert found.auth is None
        assert found.params == {}
        assert found.values == {"user_id": TWITTER_USER}

    def test_the_user_is_never_sent_as_a_credential(self, clean_twitter, monkeypatch):
        monkeypatch.setenv("TWITTER_BEARER_TOKEN", TWITTER_TOKEN)
        monkeypatch.setenv("TWITTER_USER_ID", TWITTER_USER)
        found = creds.credentials_for("twitter")
        assert TWITTER_USER not in found.headers["Authorization"]

    def test_the_token_alone_names_the_missing_user(self, clean_twitter, monkeypatch):
        monkeypatch.setenv("TWITTER_BEARER_TOKEN", TWITTER_TOKEN)
        with pytest.raises(creds.CredentialsError, match="TWITTER_USER_ID"):
            creds.credentials_for("twitter")

    def test_the_user_alone_names_the_missing_token(self, clean_twitter, monkeypatch):
        monkeypatch.setenv("TWITTER_USER_ID", TWITTER_USER)
        with pytest.raises(creds.CredentialsError, match="TWITTER_BEARER_TOKEN"):
            creds.credentials_for("twitter")

    def test_the_base_url_can_be_overridden(self, clean_twitter, monkeypatch):
        monkeypatch.setenv("TWITTER_BEARER_TOKEN", TWITTER_TOKEN)
        monkeypatch.setenv("TWITTER_USER_ID", TWITTER_USER)
        monkeypatch.setenv("TWITTER_BASE_URL", "https://twitter.example.test")
        assert (
            creds.credentials_for("twitter").base_url == "https://twitter.example.test"
        )


class TestTheStandInSuppliesEveryIdAPathNames:
    @pytest.mark.parametrize(
        "source,values",
        [
            ("twilio", {"account_sid": "mock_account_sid"}),
            ("google_sheets", {"spreadsheet_id": "mock_spreadsheet_id"}),
            ("google_analytics", {"property_id": "123456789"}),
            ("google_ads", {"customer_id": "1234567890"}),
            ("twitter", {"user_id": "me"}),
            ("linkedin", {"organization": "urn:li:organization:1"}),
            (
                "meta",
                {
                    "account_ids": [
                        "act_000001",
                        "act_000002",
                        "act_000006",
                        "act_000007",
                    ]
                },
            ),
        ],
    )
    def test_the_stand_in_carries_the_id_its_paths_name(self, source, values):
        assert creds.credentials_for(source).values == values

    def test_every_source_with_stand_in_values_has_a_stand_in(self):
        assert set(creds._MOCK_VALUES) <= set(creds._MOCK)

    def test_a_source_whose_paths_name_no_id_carries_none(self):
        assert creds.credentials_for("stripe").values == {}


class TestEverySourceWithRealCredentialsStillHasAStandIn:
    def test_each_real_entry_names_a_mock_entry(self):
        assert set(creds._REAL) <= set(creds._MOCK)

    def test_the_nineteen_configured_sources_are_the_ones_the_environment_names(self):
        assert set(creds._REAL) == {
            "hubspot",
            "stripe",
            "intercom",
            "amplitude",
            "shopify",
            "klaviyo",
            "calendly",
            "mailchimp",
            "twilio",
            "mixpanel",
            "activecampaign",
            "twitter",
            "google_ads_transparency",
            "chatgpt",
            "perplexity",
            "gemini",
            "linkedin_posts",
            "google_serp",
            "claude",
        }


def real_value(source: str, name: str) -> str:
    if name.endswith("_BASE_URL"):
        return f"https://{source}.example.test"
    return f"{name.lower()}-test-0000"


def sources_with_more_than_one_variable() -> list[str]:
    return sorted(source for source, entry in creds._REAL.items() if len(entry[1]) > 1)


@pytest.fixture
def every_real_credential(monkeypatch):
    for source, (_base, names, _build) in creds._REAL.items():
        for name in (*names, f"{source.upper()}_BASE_URL"):
            monkeypatch.setenv(name, real_value(source, name))


@pytest.fixture
def stand_ins_only(monkeypatch):
    monkeypatch.setattr(settings, "STAND_INS_ONLY", True)


class TestStandInsOnlyOutranksTheEnvironment:
    def test_the_setting_ships_off(self):
        assert Settings.model_fields["STAND_INS_ONLY"].default is False

    def test_the_environment_is_fully_populated_first(self, every_real_credential):
        for source, (_base, names, _build) in creds._REAL.items():
            assert os.environ[f"{source.upper()}_BASE_URL"]
            for name in names:
                assert os.environ[name]

    @pytest.mark.parametrize("source", sorted(creds._MOCK))
    def test_every_source_answers_with_its_stand_in(
        self, source, every_real_credential, stand_ins_only
    ):
        prefix, headers, auth, params = creds._MOCK[source]
        found = creds.credentials_for(source)
        assert found.base_url == f"{settings.MOCK_BASE_URL}{prefix}"
        assert found.headers == headers
        assert found.auth == auth
        assert found.params == params
        assert found.values == creds._MOCK_VALUES.get(source, {})

    @pytest.mark.parametrize("source", sorted(creds._REAL))
    def test_no_credential_and_no_override_reaches_the_result(
        self, source, every_real_credential, stand_ins_only
    ):
        _base, names, _build = creds._REAL[source]
        rendered = repr(creds.credentials_for(source))
        assert "example.test" not in rendered
        for name in names:
            assert real_value(source, name) not in rendered

    @pytest.mark.parametrize("source", sources_with_more_than_one_variable())
    def test_a_half_set_environment_raises_nothing(
        self, source, stand_ins_only, monkeypatch
    ):
        first = creds._REAL[source][1][0]
        monkeypatch.setenv(first, real_value(source, first))
        found = creds.credentials_for(source)
        assert found.base_url == f"{settings.MOCK_BASE_URL}{creds._MOCK[source][0]}"

    def test_an_unknown_source_still_names_itself(self, stand_ins_only):
        with pytest.raises(KeyError, match="nope"):
            creds.credentials_for("nope")

    @pytest.mark.parametrize("source", sorted(creds._REAL))
    def test_switched_off_the_environment_is_in_charge_again(
        self, source, every_real_credential
    ):
        found = creds.credentials_for(source)
        assert found.base_url == f"https://{source}.example.test"
        assert not found.base_url.startswith(settings.MOCK_BASE_URL)


class TestCredentialsSayWhetherTheyAreReal:
    def test_the_flag_defaults_off(self):
        assert creds.Credentials(base_url="http://x").real is False

    def test_a_stand_in_is_not_real(self, clean_env):
        assert creds.credentials_for("hubspot").real is False

    def test_a_source_with_no_real_entry_is_not_real(self):
        assert creds.credentials_for("zendesk").real is False

    def test_the_environment_makes_them_real(self, clean_env, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", TOKEN)
        assert creds.credentials_for("hubspot").real is True

    def test_stand_ins_only_keeps_them_unreal(
        self, every_real_credential, stand_ins_only
    ):
        assert creds.credentials_for("hubspot").real is False
