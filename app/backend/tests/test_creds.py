import pytest

from app.config import settings
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
                lambda sid, token: ({}, (sid, token), {}),
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
