import re

import pytest

from app.caches import BACKEND_DIR
from app.sources import creds

ENV_EXAMPLE = BACKEND_DIR.parent / ".env.example"
ASSIGNMENT = re.compile(r"^([A-Z][A-Z0-9_]*)=(\S*)$")
STAND_INS_ONLY = "STAND_INS_ONLY"
COMPETITOR_CREDENTIALS = (
    "META_AD_LIBRARY_ACCESS_TOKEN",
    "SERPAPI_API_KEY",
    "FIRECRAWL_API_KEY",
    "BRIGHTDATA_API_KEY",
)
SERPAPI_KEY = "SERPAPI_API_KEY"
SERPAPI_SOURCES = ("google_ads_transparency", "serp")


def credential_names() -> list[str]:
    return sorted(
        {name for _base, names, _build in creds._REAL.values() for name in names}
    )


def base_url_names() -> list[str]:
    return sorted(f"{source.upper()}_BASE_URL" for source in creds._REAL)


def documented_lines() -> list[tuple[int, str]]:
    if not ENV_EXAMPLE.is_file():
        return []
    return [
        (number, line)
        for number, line in enumerate(ENV_EXAMPLE.read_text().splitlines(), start=1)
        if line.strip() and not line.lstrip().startswith("#")
    ]


def documented() -> list[tuple[int, str, str]]:
    matched = ((number, ASSIGNMENT.match(line)) for number, line in documented_lines())
    return [
        (number, found.group(1), found.group(2))
        for number, found in matched
        if found is not None
    ]


def documented_keys() -> list[str]:
    return [key for _number, key, _value in documented()]


def heading_above(key: str) -> str:
    heading = ""
    for line in ENV_EXAMPLE.read_text().splitlines():
        if line.startswith("#"):
            heading = line
        elif line.startswith(f"{key}="):
            return heading
    return ""


class TestEveryVariableASourceReadsIsDocumented:
    def test_the_example_file_is_mounted_so_these_checks_cannot_silently_skip(self):
        assert ENV_EXAMPLE.is_file(), (
            f"{ENV_EXAMPLE} is absent inside the stack — add "
            "'../.env.example:/.env.example:ro' to the backend volumes in "
            "app/docker-compose.yml and restart the backend"
        )

    def test_the_real_table_names_the_variables_this_file_checks(self):
        assert credential_names()

    @pytest.mark.parametrize("name", credential_names())
    def test_every_variable_the_real_table_reads_is_named(self, name):
        assert name in documented_keys(), (
            f"creds._REAL reads {name}, and app/.env.example names it nowhere. "
            "It is the only place a developer is told what to set, so a source "
            "documented nowhere is a source nobody can turn on"
        )

    def test_the_switch_that_forces_the_stand_ins_is_named(self):
        assert STAND_INS_ONLY in documented_keys(), (
            f"app/.env.example names no {STAND_INS_ONLY}, which is the documented "
            "way to hold every source to its stand-in whatever else is set"
        )


class TestEveryValueIsLeftBlank:
    @pytest.mark.parametrize("number, key, value", documented())
    def test_no_credential_carries_a_value(self, number, key, value):
        if key == STAND_INS_ONLY:
            return
        assert value == "", (
            f"app/.env.example:{number} gives {key} the value {value!r}. CI copies "
            "this file to app/.env verbatim, and creds._real() reads any non-empty "
            "value as a real credential — so a placeholder here points the "
            "connectors at live vendor hosts instead of the stand-ins. "
            "Leave the value blank and let the comment above it explain"
        )

    def test_the_stand_in_switch_carries_a_boolean_pydantic_can_read(self):
        value = {k: v for _n, k, v in documented()}[STAND_INS_ONLY]
        assert value in {"true", "false"}, (
            f"app/.env.example gives {STAND_INS_ONLY} the value {value!r}. It is "
            "typed bool on Settings, and pydantic refuses an empty string, so a "
            "blank here stops the backend booting the moment CI copies this file "
            "to app/.env"
        )


class TestNothingIsDocumentedThatNoSourceReads:
    @pytest.mark.parametrize("number, key, value", documented())
    def test_every_key_is_one_the_credentials_layer_reads(self, number, key, value):
        allowed = {*credential_names(), *base_url_names(), STAND_INS_ONLY}
        assert key in allowed, (
            f"app/.env.example:{number} documents {key}, which no source reads: it "
            "is neither a variable in creds._REAL, nor a <SOURCE>_BASE_URL override "
            "for a source in it, nor STAND_INS_ONLY"
        )


class TestTheFileParsesAsAnEnvFile:
    @pytest.mark.parametrize("number, line", documented_lines())
    def test_every_line_is_a_bare_key_and_value(self, number, line):
        assert ASSIGNMENT.match(line), (
            f"app/.env.example:{number} is neither a comment nor KEY=value: "
            f"{line!r}. docker compose reads this file literally, so 'export ' "
            "and any space around the '=' end up inside the name or the value"
        )

    @pytest.mark.parametrize("number, line", documented_lines())
    def test_no_line_quotes_its_value(self, number, line):
        assert not set(line) & set("\"'"), (
            f"app/.env.example:{number} quotes its value: {line!r}. An env file "
            "has no quoting, so the quotes themselves become the credential"
        )

    def test_no_key_is_written_twice(self):
        keys = documented_keys()
        twice = sorted({key for key in keys if keys.count(key) > 1})
        assert twice == [], (
            f"app/.env.example writes {', '.join(twice)} more than once. The last "
            "line silently shadows the ones above it, so one of them is a lie"
        )


class TestTheCompetitorSourcesAreDocumented:
    @pytest.mark.parametrize("name", COMPETITOR_CREDENTIALS)
    def test_the_variable_is_named(self, name):
        assert name in documented_keys(), (
            f"app/.env.example names no {name}, so the competitor source that "
            "reads it cannot be turned on"
        )

    @pytest.mark.parametrize("source", SERPAPI_SOURCES)
    def test_the_serpapi_key_is_the_one_variable_each_serpapi_source_reads(
        self, source
    ):
        assert creds._REAL[source][1] == (SERPAPI_KEY,)

    def test_a_variable_two_sources_share_is_written_once_and_counted_once(self):
        assert documented_keys().count(SERPAPI_KEY) == 1
        assert credential_names().count(SERPAPI_KEY) == 1

    def test_the_shared_keys_heading_names_every_source_that_reads_it(self):
        heading = heading_above(SERPAPI_KEY)
        for source in SERPAPI_SOURCES:
            assert source in heading, (
                f"the heading above {SERPAPI_KEY} is {heading!r}; a developer "
                f"reading it cannot tell that {source} is one of the sources it "
                "unlocks"
            )
