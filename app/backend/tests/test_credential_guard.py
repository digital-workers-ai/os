import os

import pytest

from app.config import CREDENTIALS, Settings, settings
from app.sources import creds


def credential_names() -> list[str]:
    return sorted(
        {name for _base, names, _build in creds._REAL.values() for name in names}
    )


def base_url_names() -> list[str]:
    return sorted(f"{source.upper()}_BASE_URL" for source in creds._REAL)


def flag_names() -> list[str]:
    return sorted({flag for flags in CREDENTIALS.values() for flag in flags})


def vendor_names() -> list[str]:
    return sorted(CREDENTIALS)


class TestNoLiveCredentialIsVisibleToATest:
    def test_the_real_table_names_the_variables_this_file_guards(self):
        assert credential_names()
        assert base_url_names()

    @pytest.mark.parametrize("name", credential_names())
    def test_no_variable_the_real_table_consults_is_set(self, name):
        assert os.environ.get(name, "") == ""

    @pytest.mark.parametrize("name", base_url_names())
    def test_no_base_url_override_is_set(self, name):
        assert os.environ.get(name, "") == ""

    @pytest.mark.parametrize("source", sorted(creds._REAL))
    def test_every_source_with_real_credentials_falls_back_to_the_stand_in(
        self, source
    ):
        found = creds.credentials_for(source)
        assert found.base_url == f"{settings.MOCK_BASE_URL}{creds._MOCK[source][0]}"


class TestTheStandInIsLeftFullyWorking:
    @pytest.mark.parametrize("source", sorted(creds._MOCK))
    def test_every_stand_in_still_answers_with_its_own_prefix_and_headers(self, source):
        prefix, headers, auth, params = creds._MOCK[source]
        found = creds.credentials_for(source)
        assert found.base_url == f"{settings.MOCK_BASE_URL}{prefix}"
        assert found.headers == headers
        assert found.auth == auth
        assert found.params == params

    def test_a_credential_set_inside_a_test_still_reaches_the_real_api(
        self, monkeypatch
    ):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "pat-test-0000")
        assert creds.credentials_for("hubspot").base_url == "https://api.hubapi.com"


class TestNoModelLayerIsOnInATest:
    def test_the_credential_map_names_the_flags_this_file_guards(self):
        assert flag_names() == [
            "COACHING_ENABLED",
            "CONVERSATION_ENABLED",
            "EMBEDDINGS_ENABLED",
            "ENRICHMENT_ENABLED",
            "RERANK_ENABLED",
        ]

    @pytest.mark.parametrize("flag", flag_names())
    def test_every_flag_reads_as_the_default_it_ships_with(self, flag):
        assert getattr(settings, flag) == Settings.model_fields[flag].default

    @pytest.mark.parametrize("flag", flag_names())
    def test_a_flag_a_test_turns_on_stays_on(self, flag, monkeypatch):
        monkeypatch.setattr(settings, flag, True)
        assert getattr(settings, flag) is True


class TestNoVendorCredentialIsVisibleToATest:
    def test_the_credential_map_names_the_variables_this_file_guards(self):
        assert vendor_names() == [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "ZEROENTROPY_API_KEY",
        ]

    @pytest.mark.parametrize("name", vendor_names())
    def test_no_vendor_credential_is_set(self, name):
        assert os.environ.get(name, "") == ""

    @pytest.mark.parametrize("name", vendor_names())
    def test_a_key_set_inside_a_test_is_still_visible(self, name, monkeypatch):
        monkeypatch.setenv(name, "key-test-0000")
        assert os.environ[name] == "key-test-0000"
