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

    def test_another_sources_token_leaves_stripe_on_the_mock(self, monkeypatch):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", TOKEN)
        found = creds.credentials_for("stripe")
        assert found.base_url == f"{settings.MOCK_BASE_URL}/stripe"
        assert found.headers == {"Authorization": "Bearer mock_stripe_key"}
