import os

import pytest

from app.config import (
    CREDENTIALS,
    LLM_FLAGS,
    Settings,
    StartupError,
    settings,
    validate_startup,
)
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
            "BUILDER_ENABLED",
            "COACHING_ENABLED",
            "CONVERSATION_ENABLED",
            "CUSTOM_ENABLED",
            "EMBEDDINGS_ENABLED",
            "ENRICHMENT_ENABLED",
            "RERANK_ENABLED",
            "STUDIO_ENABLED",
            "TRANSCRIBE_ENABLED",
        ]

    @pytest.mark.parametrize("flag", flag_names())
    def test_every_flag_reads_as_the_default_it_ships_with(self, flag):
        assert getattr(settings, flag) == Settings.model_fields[flag].default

    @pytest.mark.parametrize("flag", flag_names())
    def test_a_flag_a_test_turns_on_stays_on(self, flag, monkeypatch):
        monkeypatch.setattr(settings, flag, True)
        assert getattr(settings, flag) is True


class TestStudioNeedsBothVendorKeys:
    @pytest.fixture(autouse=True)
    def studio_on(self, monkeypatch):
        monkeypatch.setattr(settings, "STUDIO_ENABLED", True)

    def test_studio_on_without_the_anthropic_key_refuses_the_boot(self):
        with pytest.raises(StartupError, match="STUDIO_ENABLED") as info:
            validate_startup(env={"OPENAI_API_KEY": "sk"})
        assert "ANTHROPIC_API_KEY" in str(info.value)

    def test_studio_on_without_the_openai_key_refuses_the_boot(self):
        with pytest.raises(StartupError, match="STUDIO_ENABLED") as info:
            validate_startup(env={"ANTHROPIC_API_KEY": "k"})
        assert "OPENAI_API_KEY" in str(info.value)

    def test_studio_on_without_any_key_names_the_first_missing_one(self):
        with pytest.raises(StartupError, match="STUDIO_ENABLED"):
            validate_startup(env={})

    def test_studio_on_with_both_keys_boots(self):
        both = {"ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": "sk"}
        assert validate_startup(env=both) is None

    def test_studio_off_needs_no_key(self, monkeypatch):
        monkeypatch.setattr(settings, "STUDIO_ENABLED", False)
        assert validate_startup(env={}) is None


class TestTheCustomAppsFlagsNameTheirKeys:
    def test_custom_reading_joins_the_llm_flags(self):
        assert set(LLM_FLAGS) == {
            "ENRICHMENT_ENABLED",
            "COACHING_ENABLED",
            "CONVERSATION_ENABLED",
            "CUSTOM_ENABLED",
        }

    def test_the_anthropic_key_guards_the_llm_flags_studio_and_the_builder(self):
        assert set(CREDENTIALS["ANTHROPIC_API_KEY"]) == {
            *LLM_FLAGS,
            "STUDIO_ENABLED",
            "BUILDER_ENABLED",
        }

    def test_transcribing_needs_the_deepgram_key(self):
        assert CREDENTIALS["DEEPGRAM_API_KEY"] == ("TRANSCRIBE_ENABLED",)

    def test_the_builder_needs_the_github_token(self):
        assert CREDENTIALS["GITHUB_TOKEN"] == ("BUILDER_ENABLED",)


class TestTheCustomAppsSettingsShipTheirDefaults:
    @pytest.mark.parametrize(
        ("name", "annotation", "default"),
        [
            ("CUSTOM_ENABLED", bool, False),
            ("CUSTOM_MODEL", str, "claude-opus-5-5"),
            ("CUSTOM_MAX_TOKENS", int, 16000),
            ("TRANSCRIBE_ENABLED", bool, False),
            ("TRANSCRIBE_MODEL", str, "nova-3"),
            ("BUILDER_ENABLED", bool, False),
            ("GITHUB_REPOSITORY", str, ""),
        ],
    )
    def test_each_setting_ships_with_its_type_and_default(
        self, name, annotation, default
    ):
        field = Settings.model_fields[name]
        assert (field.annotation, field.default) == (annotation, default)


class TestCustomReadingNeedsTheAnthropicKey:
    @pytest.fixture(autouse=True)
    def custom_on(self, monkeypatch):
        monkeypatch.setattr(settings, "CUSTOM_ENABLED", True)

    def test_custom_on_without_the_anthropic_key_refuses_the_boot(self):
        with pytest.raises(StartupError, match="CUSTOM_ENABLED") as info:
            validate_startup(env={})
        assert "ANTHROPIC_API_KEY" in str(info.value)

    def test_custom_on_with_the_anthropic_key_boots(self):
        assert validate_startup(env={"ANTHROPIC_API_KEY": "k"}) is None


class TestTranscribingNeedsTheDeepgramKey:
    @pytest.fixture(autouse=True)
    def transcribe_on(self, monkeypatch):
        monkeypatch.setattr(settings, "TRANSCRIBE_ENABLED", True)

    def test_transcribing_on_without_the_deepgram_key_refuses_the_boot(self):
        with pytest.raises(StartupError, match="TRANSCRIBE_ENABLED") as info:
            validate_startup(env={"ANTHROPIC_API_KEY": "k"})
        assert "DEEPGRAM_API_KEY" in str(info.value)

    def test_transcribing_on_with_the_deepgram_key_boots(self):
        assert validate_startup(env={"DEEPGRAM_API_KEY": "dg"}) is None


class TestTheBuilderNeedsTheAnthropicKeyAndTheGithubToken:
    @pytest.fixture(autouse=True)
    def builder_on(self, monkeypatch):
        monkeypatch.setattr(settings, "BUILDER_ENABLED", True)

    def test_builder_on_without_the_anthropic_key_refuses_the_boot(self):
        with pytest.raises(StartupError, match="BUILDER_ENABLED") as info:
            validate_startup(env={"GITHUB_TOKEN": "gh"})
        assert "ANTHROPIC_API_KEY" in str(info.value)

    def test_builder_on_without_the_github_token_refuses_the_boot(self):
        with pytest.raises(StartupError, match="BUILDER_ENABLED") as info:
            validate_startup(env={"ANTHROPIC_API_KEY": "k"})
        assert "GITHUB_TOKEN" in str(info.value)

    def test_builder_on_with_both_keys_boots(self):
        both = {"ANTHROPIC_API_KEY": "k", "GITHUB_TOKEN": "gh"}
        assert validate_startup(env=both) is None


class TestNoVendorCredentialIsVisibleToATest:
    def test_the_credential_map_names_the_variables_this_file_guards(self):
        assert vendor_names() == [
            "ANTHROPIC_API_KEY",
            "DEEPGRAM_API_KEY",
            "GITHUB_TOKEN",
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
