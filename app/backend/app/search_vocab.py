from enum import StrEnum


class Mode(StrEnum):
    WORDS = "words"
    MEANING = "meaning"
    BOTH = "both"


class Kind(StrEnum):
    BRIEFING = "briefing"
    RAW = "raw"
    METRIC = "metric"
    RULE = "rule"
    GOAL = "goal"
    SOURCE = "source"
    ENTITY_TYPE = "entity_type"
    READING = "reading"


DEFINITION_KINDS = (
    Kind.METRIC,
    Kind.RULE,
    Kind.GOAL,
    Kind.SOURCE,
    Kind.ENTITY_TYPE,
    Kind.READING,
)
NON_ENTITY_KINDS = (Kind.BRIEFING, Kind.RAW)


class Weight(StrEnum):
    STRONG = "A"
    NORMAL = "B"
    LONG = "D"


class Attr(StrEnum):
    ANCHOR = "anchor"
    BRIEFING = "briefing"
    PAYLOAD = "payload"
    TRANSCRIPT = "transcript"


READING_PREFIX = "reading:"
QUOTE_PREFIX = "quote:"


class Param(StrEnum):
    Q = "q"
    KIND = "kind"
    MODE = "mode"
    LIMIT = "limit"
    OFFSET = "offset"


MARK_OPEN = "«"
MARK_CLOSE = "»"
EVIDENCE_SEP = "="
LABEL_SEP = " · "
ANCHOR_SEP = "|"
BRIEFING_REF_SEP = "/"
TEXT_SEARCH_CONFIG = "simple"
HEADLINE_OPTIONS = (
    f"MaxFragments=1,MaxWords=18,MinWords=8,StartSel={MARK_OPEN},StopSel={MARK_CLOSE}"
)
STRONG_ATTRS = ("name", "title", "subject", "email", "domain", "external_ref")
UNINDEXED_TYPES = ("date", "number")
MIN_QUERY_CHARS = 2
DEFAULT_LIMIT = 10
MAX_LIMIT = 500
LABEL_CHARS = 512
TRIGRAM_THRESHOLD = 0.3
UNKNOWN_KIND = "unknown kind"
UNKNOWN_MODE = "unknown mode"
