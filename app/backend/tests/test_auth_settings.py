import pytest

from app.config import (
    AUTH_SIGNING_KEY_ENV,
    CREDENTIALS,
    GOOGLE_CLIENT_ID_ENV,
    GOOGLE_CLIENT_SECRET_ENV,
    Settings,
    StartupError,
    allowed_emails,
    settings,
    validate_startup,
)

AUTH_CREDENTIALS = (
    GOOGLE_CLIENT_ID_ENV,
    GOOGLE_CLIENT_SECRET_ENV,
    AUTH_SIGNING_KEY_ENV,
)
ENV = {
    GOOGLE_CLIENT_ID_ENV: "test-client.apps.googleusercontent.com",
    GOOGLE_CLIENT_SECRET_ENV: "test-client-secret",
    AUTH_SIGNING_KEY_ENV: "test-signing-key",
}


class TestDefaults:
    def test_auth_ships_off_on_a_local_url_with_nobody_allowed(self):
        fields = Settings.model_fields
        assert fields["AUTH_ENABLED"].default is False
        assert fields["PUBLIC_URL"].default == "http://localhost:8092"
        assert fields["AUTH_ALLOWED_EMAILS"].default == ""

    def test_a_trailing_slash_on_the_public_url_is_dropped(self):
        assert Settings(PUBLIC_URL="https://os.example.com/").PUBLIC_URL == (
            "https://os.example.com"
        )

    def test_the_three_auth_credentials_guard_the_auth_flag(self):
        assert AUTH_CREDENTIALS == (
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "AUTH_JWT_SIGNING_KEY",
        )
        for name in AUTH_CREDENTIALS:
            assert CREDENTIALS[name] == ("AUTH_ENABLED",)


class TestAllowedEmails:
    def test_nothing_set_allows_nobody(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ALLOWED_EMAILS", "")
        assert allowed_emails() == frozenset()

    def test_entries_are_stripped_lowercased_and_blanks_dropped(self, monkeypatch):
        monkeypatch.setattr(
            settings, "AUTH_ALLOWED_EMAILS", " Ana@Example.com, ,bo@example.com ,,"
        )
        assert allowed_emails() == {"ana@example.com", "bo@example.com"}


class TestAuthOnRefusesAnUnsafeBoot:
    @pytest.fixture(autouse=True)
    def auth_on(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ENABLED", True)
        monkeypatch.setattr(settings, "AUTH_ALLOWED_EMAILS", "ana@example.com")
        monkeypatch.setattr(settings, "PUBLIC_URL", "http://localhost:8092")

    @pytest.mark.parametrize("missing", AUTH_CREDENTIALS)
    def test_each_missing_credential_is_named(self, missing):
        env = {name: value for name, value in ENV.items() if name != missing}
        with pytest.raises(StartupError, match="AUTH_ENABLED") as info:
            validate_startup(env=env)
        assert missing in str(info.value)

    def test_an_empty_allowlist_means_nobody_could_sign_in(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ALLOWED_EMAILS", " , ")
        with pytest.raises(StartupError, match="AUTH_ALLOWED_EMAILS") as info:
            validate_startup(env=ENV)
        assert "nobody" in str(info.value).lower()

    def test_a_missing_credential_wins_over_an_empty_allowlist(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ALLOWED_EMAILS", "")
        with pytest.raises(StartupError, match=GOOGLE_CLIENT_ID_ENV) as info:
            validate_startup(env={})
        assert "AUTH_ALLOWED_EMAILS" not in str(info.value)

    def test_a_plain_http_public_host_would_leak_the_consent_cookie(self, monkeypatch):
        monkeypatch.setattr(settings, "PUBLIC_URL", "http://example.com")
        with pytest.raises(StartupError, match="PUBLIC_URL") as info:
            validate_startup(env=ENV)
        assert "in the clear" in str(info.value)

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:8092",
            "http://127.0.0.1:8092",
            "http://[::1]:8092",
            "https://os.example.com",
        ],
    )
    def test_a_loopback_or_https_public_url_boots(self, url, monkeypatch):
        monkeypatch.setattr(settings, "PUBLIC_URL", url)
        assert validate_startup(env=ENV) is None


class TestAuthOffNeedsNothing:
    def test_no_credential_no_allowlist_and_a_plain_url_still_boot(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ENABLED", False)
        monkeypatch.setattr(settings, "AUTH_ALLOWED_EMAILS", "")
        monkeypatch.setattr(settings, "PUBLIC_URL", "http://example.com")
        assert validate_startup(env={}) is None
