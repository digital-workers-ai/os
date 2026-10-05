import base64
import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml


def _load() -> dict:
    path = Path(os.environ.get("WORLD_DATA") or Path(__file__).with_name("data.yaml"))
    return yaml.safe_load(path.read_text())


_DATA = _load()


@dataclass
class Company:
    id: str
    name: str
    domain: str
    industry: str | None = None
    employee_count: int | None = None
    region: str = "US"
    city: str | None = None
    state: str | None = None
    country: str = "US"
    created_at: str = "2025-01-15"


COMPANIES = [Company(**row) for row in _DATA["companies"]]
COMPANIES_BY_ID = {c.id: c for c in COMPANIES}


@dataclass
class Person:
    id: str
    first_name: str
    last_name: str
    email: str
    company_id: str
    role: str | None = None
    phone: str | None = None
    created_at: str = "2025-03-15"
    last_seen: str | None = None


PEOPLE = [Person(**row) for row in _DATA["people"]]
PEOPLE_BY_ID = {p.id: p for p in PEOPLE}
PEOPLE_BY_COMPANY: dict[str, list[Person]] = {}
for _person in PEOPLE:
    PEOPLE_BY_COMPANY.setdefault(_person.company_id, []).append(_person)


@dataclass
class Subscription:
    id: str
    company_id: str
    plan: str
    status: str
    mrr_cents: int
    currency: str = "usd"
    started_at: str = "2025-01-15"
    current_period_start: str = "2026-07-01"
    current_period_end: str = "2026-08-01"
    canceled_at: str | None = None
    trial_end: str | None = None


SUBSCRIPTIONS = [Subscription(**row) for row in _DATA["subscriptions"]]
SUBSCRIPTIONS_BY_ID = {s.id: s for s in SUBSCRIPTIONS}
SUBSCRIPTIONS_BY_COMPANY = {s.company_id: s for s in SUBSCRIPTIONS}


@dataclass
class EmailCampaign:
    id: str
    name: str
    status: str
    subject: str
    sent_at: str | None = None
    sends: int = 0
    opens: int = 0
    clicks: int = 0
    bounces: int = 0
    unsubscribes: int = 0


EMAIL_CAMPAIGNS = [EmailCampaign(**row) for row in _DATA["email_campaigns"]]


@dataclass
class AdCampaign:
    id: str
    company_id: str
    platform: str
    name: str
    status: str
    objective: str
    daily_budget_cents: int
    spend_cents: int
    impressions: int
    clicks: int
    conversions: int
    start_date: str
    end_date: str | None = None


AD_CAMPAIGNS = [AdCampaign(**row) for row in _DATA["ad_campaigns"]]


@dataclass
class Ticket:
    id: str
    company_id: str
    requester_id: str
    subject: str
    status: str
    priority: str
    created_at: str
    updated_at: str
    channel: str = "email"


TICKETS = [Ticket(**row) for row in _DATA["tickets"]]


@dataclass
class AnalyticsEvent:
    id: str
    distinct_id: str
    event: str
    timestamp: str
    properties: dict = field(default_factory=dict)


ANALYTICS_EVENTS = [AnalyticsEvent(**row) for row in _DATA["analytics_events"]]

ER_COMPANY_NAMES = {
    (row["source"], row["company_id"]): row["name"]
    for row in _DATA["er"]["company_names"]
}
ER_PERSON_NAMES = {
    (row["source"], row["person_id"]): (row["first_name"], row["last_name"])
    for row in _DATA["er"]["person_names"]
}
ER_PERSON_EMAILS = {
    (row["source"], row["person_id"]): row["email"]
    for row in _DATA["er"]["person_emails"]
}

INTEREST_LEVELS = ("strong", "moderate", "weak", "none")

PAIN_POINTS = (
    "pricing",
    "integration_complexity",
    "missing_features",
    "performance",
    "support_quality",
    "onboarding_time",
    "reporting_gaps",
    "manual_work",
    "security_compliance",
    "vendor_lock_in",
)

PURCHASE_TIMING = (
    "immediate",
    "this_quarter",
    "next_quarter",
    "next_year",
    "no_timeline",
)


@dataclass
class SalesCall:
    id: str
    company_id: str
    prospect_id: str
    host_email: str
    topic: str
    started_at: str
    duration_min: int
    transcript: list
    expected_interest: str = "moderate"
    expected_pain: tuple = ()
    expected_timing: str = "no_timeline"
    note: str = ""


def _sales_call(row: dict) -> SalesCall:
    transcript = [(turn["speaker"], turn["line"]) for turn in row["transcript"]]
    pain = tuple(row["expected_pain"])
    return SalesCall(**{**row, "transcript": transcript, "expected_pain": pain})


SALES_CALLS = [_sales_call(row) for row in _DATA["sales_calls"]]
SALES_CALLS_BY_ID = {c.id: c for c in SALES_CALLS}

VENDORS = _DATA["vendors"]

_SPY = _DATA["spy"]
SPY_BRAND = _SPY["brand"]
SPY_COMPETITORS = _SPY["competitors"]
SERP_RESULTS = 10
SPY_QUERIES = _SPY["queries"]
SPY_ANCHOR = _SPY["anchor"]
SPY_ENGINES = ("google", "ai_overview", "chatgpt", "perplexity", "claude", "gemini")
SPY_COMPANIES = [SPY_BRAND, *SPY_COMPETITORS]


def _fields(rows: dict, *keys: str) -> dict:
    return {key: tuple(row[k] for k in keys) for key, row in rows.items()}


_SPY_PAGES = {
    domain: (page["title"], page["link"]) for domain, page in _SPY["pages"].items()
}
_SPY_SNIPPETS = _SPY["snippets"]
_SPY_NEUTRAL = _SPY["neutral"]
_SPY_OPENERS = _SPY["openers"]
_SPY_PAIRS = _SPY["pairs"]
_SPY_SINGLES = _SPY["singles"]
_SPY_EXTRAS = _SPY["extras"]
_SPY_CLOSERS = _SPY["closers"]
_SPY_OVERVIEW_OPENERS = _SPY["overview_openers"]
_SPY_OVERVIEW_ITEMS = _SPY["overview_items"]
_SPY_AD_SIZES = (
    (300, 250),
    (336, 280),
    (728, 90),
    (160, 600),
    (320, 50),
    (348, 451),
    (970, 250),
    (300, 600),
)
_SPY_AD_HEADLINES = _SPY["ad_headlines"]
_SPY_AD_LINES = _SPY["ad_lines"]
_SPY_POST_TEXTS = _SPY["post_texts"]
_SPY_FEATURES = _SPY["features"]
_SPY_BENEFITS = _SPY["benefits"]
_SPY_HASHTAGS = _SPY["hashtags"]
_SPY_FOLLOWERS = _SPY["followers"]
_SPY_ADVERTISERS = {
    c["google_advertiser_id"]: c for c in SPY_COMPETITORS if "google_advertiser_id" in c
}
_SPY_LINKEDIN = {c["linkedin"]: c for c in SPY_COMPETITORS if "linkedin" in c}
_SPY_X = {c["x"].lower(): c for c in SPY_COMPETITORS if "x" in c}
_SPY_X_PROFILES = _fields(
    _SPY["x_profiles"],
    "name",
    "user_id",
    "followers",
    "following",
    "posts_count",
    "badge",
    "biography",
)
_SPY_INSTAGRAM = {c["instagram"]: c for c in SPY_COMPETITORS if "instagram" in c}
_SPY_INSTAGRAM_PROFILES = _fields(
    _SPY["instagram_profiles"],
    "name",
    "user_id",
    "followers",
    "posts_count",
    "verified",
)
_SPY_INSTAGRAM_EVENTS = _SPY["instagram_events"]
_SPY_INSTAGRAM_TYPES = (
    ("Reel", "clips"),
    ("Image", "feed"),
    ("Carousel", "carousel_container"),
    ("Reel", "clips"),
    ("Carousel", "carousel_container"),
    ("Reel", "clips"),
)
_SPY_INSTAGRAM_POPS = (
    "atl3-2",
    "ord5-1",
    "lax3-2",
    "dfw5-1",
    "sjc6-1",
    "iad6-1",
    "bos5-1",
    "sea5-1",
)
_SPY_INSTAGRAM_COMMENTS = _SPY["instagram_comments"]
_SPY_INSTAGRAM_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)
_SPY_INSTAGRAM_EPOCH_MS = 1314220021721
_SPY_LINKEDIN_TYPES = ("image", "image", "image", "video", "text", "document")
_SPY_LINKEDIN_FORMATS = {
    "image": "Single Image Ad",
    "video": "Video Ad",
    "text": "Text Ad",
    "document": "Document Ad",
    "message": "Message Ad",
}
_SPY_LINKEDIN_UNPUBLISHED = (
    "ad_format",
    "ad_type",
    "advertiser",
    "content",
    "id",
    "link",
    "paid_for_by",
)
_SPY_LINKEDIN_PEOPLE = [(p["name"], p["role"]) for p in _SPY["linkedin_people"]]
_SPY_LINKEDIN_CTAS = ("Learn more", "Sign up", "Download", "Register")
_SPY_LINKEDIN_BANDS = (
    ("< 1k", None, 1000),
    ("1k-5k", 1000, 5000),
    ("5k-10k", 5000, 10000),
    ("10k-50k", 10000, 50000),
)
_SPY_LINKEDIN_COUNTRIES = (
    "United States",
    "United Kingdom",
    "Canada",
    "Australia",
    "India",
    "Germany",
    "Ireland",
)
_SPY_LINKEDIN_TARGETING = (
    ("Audience", True),
    ("Demographic", False),
    ("Company", True),
    ("Education", False),
    ("Job", True),
    ("Member Interests and Traits", False),
)
_SPY_TIKTOK = {
    c["tiktok_advertiser_id"]: c for c in SPY_COMPETITORS if "tiktok_advertiser_id" in c
}
_SPY_TIKTOK_BANDS = (
    ("0-1K", 0, 1000),
    ("1K-10K", 1000, 10000),
    ("10K-100K", 10000, 100000),
    ("100K-1M", 100000, 1000000),
)
_SPY_TIKTOK_STAMP = int(
    datetime(
        SPY_ANCHOR.year, SPY_ANCHOR.month, SPY_ANCHOR.day, 12, tzinfo=UTC
    ).timestamp()
)
_SPY_TIKTOK_HANDLES = {c["tiktok"]: c for c in SPY_COMPETITORS if "tiktok" in c}
_SPY_TIKTOK_PROFILES = _fields(
    _SPY["tiktok_profiles"],
    "username",
    "profile_id",
    "followers",
    "verified",
    "biography",
    "avatar",
    "secu_id",
)
_SPY_TIKTOK_WINDOWS = _fields(
    _SPY["tiktok_windows"], "first_age", "span", "least", "spread"
)
_SPY_TIKTOK_COMMENTS = _SPY["tiktok_comments"]
_SPY_TIKTOK_COMMENTERS = _SPY["tiktok_commenters"]
_SPY_META = {c["meta_page_id"]: c for c in SPY_COMPETITORS if "meta_page_id" in c}
_SPY_META_PLATFORMS = (
    ("FACEBOOK", "INSTAGRAM"),
    ("FACEBOOK", "INSTAGRAM", "THREADS"),
    ("FACEBOOK", "INSTAGRAM", "AUDIENCE_NETWORK", "MESSENGER"),
    ("FACEBOOK", "INSTAGRAM", "AUDIENCE_NETWORK", "MESSENGER", "THREADS"),
)
_SPY_META_CTAS = (
    ("Learn more", "LEARN_MORE"),
    ("Sign up", "SIGN_UP"),
    ("Book now", "BOOK_NOW"),
    ("Get quote", "GET_QUOTE"),
)
_SPY_META_REGULATION = {
    "finserv": {"is_deemed_finserv": False, "is_limited_delivery": False},
    "tw_anti_scam": {"is_limited_delivery": False},
}


def _spy_digest(*parts: str) -> int:
    return int(hashlib.md5("|".join(parts).encode()).hexdigest(), 16)


def _spy_pick(seed: str, salt: str, pool):
    return pool[_spy_digest(seed, salt) % len(pool)]


def _spy_order(seed: str, items: list, key: str | None = None) -> list:
    return sorted(
        items, key=lambda item: _spy_digest(seed, item if key is None else item[key])
    )


def _spy_forced(kind: str, query: str) -> bool:
    return query in SPY_QUERIES and SPY_QUERIES.index(query) == _spy_digest(kind) % len(
        SPY_QUERIES
    )


def _spy_join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _spy_mentions(engine: str, query: str) -> list[dict]:
    seed = f"mentions|{engine}|{query}"
    absent = _spy_digest(seed, "brand") % 100 < 30 or _spy_forced(
        f"absent|{engine}", query
    )
    competitors = _spy_order(seed, SPY_COMPETITORS, "name")
    count = 2 + _spy_digest(seed, "count") % 3
    chosen = competitors[:count] if absent else competitors[: count - 1] + [SPY_BRAND]
    return _spy_order(seed + "|order", chosen, "name")


def _spy_company_result(company: dict) -> dict:
    title, link = _SPY_PAGES[company["domain"]]
    path = link.split(company["domain"], 1)[1]
    return {
        "title": title,
        "link": link,
        "displayed_link": f"https://www.{company['domain']} › "
        + " › ".join(p for p in path.split("/") if p),
        "snippet": _SPY_SNIPPETS[company["domain"]],
        "source": company["name"],
    }


def _spy_reference(index: int, row: dict) -> dict:
    return {
        "title": row["title"],
        "link": row["link"],
        "snippet": row["snippet"],
        "source": row["source"],
        "index": index,
    }


def spy_answer(engine: str, query: str) -> dict:
    seed = f"answer|{engine}|{query}"
    mentioned = _spy_mentions(engine, query)
    names = [c["name"] for c in mentioned]
    sentences = [_spy_pick(seed, "open", _SPY_OPENERS).format(a=names[0])]
    rest = names[1:]
    if len(rest) >= 2:
        sentences.append(
            _spy_pick(seed, "pair", _SPY_PAIRS).format(b=rest[0], c=rest[1])
        )
        rest = rest[2:]
    for name in rest:
        sentences.append(_spy_pick(seed, "single", _SPY_SINGLES).format(b=name))
    if _spy_digest(seed, "extra") % 2:
        sentences.append(_spy_pick(seed, "extra", _SPY_EXTRAS))
    sentences.append(_spy_pick(seed, "close", _SPY_CLOSERS))
    cited = _spy_order(seed + "|cite", mentioned, "domain")[:2]
    neutral = _spy_pick(seed, "neutral", _SPY_NEUTRAL[:3])
    sources = [
        {"url": _SPY_PAGES[c["domain"]][1], "title": _SPY_PAGES[c["domain"]][0]}
        for c in cited
    ]
    sources.insert(
        _spy_digest(seed, "slot") % 3,
        {"url": neutral["link"], "title": neutral["title"]},
    )
    return {"text": " ".join(sentences), "sources": sources}


def spy_serp(query: str) -> list[dict]:
    seed = f"serp|{query}"
    companies = [c for c in SPY_COMPETITORS if _spy_digest(seed, c["domain"]) % 4]
    if _spy_digest(seed, "brand") % 5 and not _spy_forced("serp-absent", query):
        companies.insert(0, SPY_BRAND)
    rows = [_spy_company_result(c) for c in companies[:SERP_RESULTS]]
    neutral = _spy_order(seed + "|neutral", _SPY_NEUTRAL, "link")
    rows += neutral[: SERP_RESULTS - len(rows)]
    rows = _spy_order(seed + "|rank", rows, "link")
    return [
        {
            "position": i + 1,
            **{
                k: row[k]
                for k in ("title", "link", "displayed_link", "snippet", "source")
            },
        }
        for i, row in enumerate(rows)
    ]


def spy_ai_overview_mode(query: str) -> str:
    return ("inline", "token", "absent")[_spy_digest(query) % 3]


def spy_ai_overview(query: str) -> dict | None:
    if spy_ai_overview_mode(query) == "absent":
        return None
    seed = f"ai_overview|{query}"
    mentioned = _spy_mentions("ai_overview", query)
    names = [c["name"] for c in mentioned]
    references = [
        _spy_reference(i, _spy_company_result(c)) for i, c in enumerate(mentioned)
    ]
    references.append(
        _spy_reference(len(mentioned), _spy_pick(seed, "neutral", _SPY_NEUTRAL[:3]))
    )
    paragraph = {
        "type": "paragraph",
        "snippet": _spy_pick(seed, "para", _SPY_OVERVIEW_OPENERS).format(
            names=_spy_join(names)
        ),
        "reference_indexes": [len(mentioned)],
    }
    items = [
        {
            "title": c["name"],
            "snippet": _spy_pick(seed, c["domain"], _SPY_OVERVIEW_ITEMS).format(
                a=c["name"]
            ),
            "reference_indexes": [i],
        }
        for i, c in enumerate(mentioned)
    ]
    return {
        "text_blocks": [paragraph, {"type": "list", "list": items}],
        "references": references,
    }


def spy_ads(advertiser_id: str) -> list[dict]:
    if advertiser_id not in _SPY_ADVERTISERS:
        return []
    anchor = int(
        datetime(
            SPY_ANCHOR.year, SPY_ANCHOR.month, SPY_ANCHOR.day, tzinfo=UTC
        ).timestamp()
    )
    creatives = []
    for i in range(4 + _spy_digest(advertiser_id, "count") % 9):
        seed = f"creative|{advertiser_id}|{i}"
        creative_id = "CR" + str(_spy_digest(seed, "id") % 10**20).zfill(20)
        kind = _spy_digest(seed, "format") % 4
        fmt = "video" if kind == 0 else "image" if kind == 1 else "text"
        first_age = _spy_digest(seed, "first") % (120 * 86400)
        last_age = _spy_digest(seed, "last") % (
            7 * 86400 if i % 3 == 0 else first_age + 1
        )
        row = {"ad_creative_id": creative_id, "format": fmt}
        if fmt != "video":
            row["image"] = "https://tpc.googlesyndication.com/archive/simgad/" + str(
                _spy_digest(seed, "image") % 10**20
            )
            row["width"], row["height"] = _spy_pick(seed, "size", _SPY_AD_SIZES)
        row["first_shown"] = anchor - first_age
        row["last_shown"] = anchor - min(last_age, first_age)
        row["details_link"] = (
            f"https://adstransparency.google.com/advertiser/{advertiser_id}/creative/{creative_id}?region=US"
        )
        creatives.append(row)
    return creatives


def spy_ad_text(creative_id: str) -> str:
    return (
        _spy_pick(creative_id, "headline", _SPY_AD_HEADLINES)
        + "\n"
        + _spy_pick(creative_id, "line", _SPY_AD_LINES)
    )


def spy_posts(slug: str) -> list[dict]:
    company = _SPY_LINKEDIN.get(slug)
    if company is None:
        return []
    anchor = datetime(SPY_ANCHOR.year, SPY_ANCHOR.month, SPY_ANCHOR.day, tzinfo=UTC)
    count = 3 + _spy_digest(slug, "count") % 7
    posts = []
    for i in range(count):
        seed = f"post|{slug}|{i}"
        post_id = str(10**18 + _spy_digest(seed, "id") % (9 * 10**18))
        age_days = i * 60 // count + _spy_digest(seed, "day") % max(1, 60 // count)
        posted = anchor - timedelta(
            days=age_days,
            hours=2 + _spy_digest(seed, "hour") % 14,
            minutes=_spy_digest(seed, "minute") % 60,
        )
        text = _spy_pick(seed, "text", _SPY_POST_TEXTS).format(
            name=company["name"],
            feature=_spy_pick(seed, "feature", _SPY_FEATURES),
            benefit=_spy_pick(seed, "benefit", _SPY_BENEFITS),
        )
        tags = _spy_order(seed + "|tags", list(_SPY_HASHTAGS))[
            : 1 + _spy_digest(seed, "tags") % 3
        ]
        words = "-".join(tag[1:].lower() for tag in tags)
        images = []
        if _spy_digest(seed, "images") % 2:
            images.append(
                f"https://media.licdn.com/dms/image/v2/D4E22AQ{_spy_digest(seed, 'img') % 10**12:012d}/feedshare-shrink_800/0/{int(posted.timestamp())}?e=2147483647&v=beta"
            )
        posts.append(
            {
                "id": post_id,
                "url": f"https://www.linkedin.com/posts/{slug}_{words}-activity-{post_id}-{hashlib.md5(seed.encode()).hexdigest()[:4]}",
                "user_id": slug,
                "use_url": f"https://www.linkedin.com/company/{slug}",
                "title": company["name"],
                "post_text": text,
                "post_text_html": "<p>" + text + "</p>",
                "date_posted": posted.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "hashtags": tags,
                "embedded_links": [],
                "images": images,
                "videos": None,
                "num_likes": 20 + _spy_digest(seed, "likes") % 900,
                "num_comments": _spy_digest(seed, "comments") % 60,
                "user_followers": _SPY_FOLLOWERS[slug],
                "post_type": "post",
                "account_type": "Organization",
                "repost": None,
                "tagged_companies": [],
                "tagged_people": [],
            }
        )
    return posts


def spy_x_posts(handle: str) -> list[dict]:
    company = _SPY_X.get(handle.lower())
    if company is None:
        return []
    name, user_id, followers, following, posts_count, badge, biography = (
        _SPY_X_PROFILES[handle.lower()]
    )
    anchor = datetime(SPY_ANCHOR.year, SPY_ANCHOR.month, SPY_ANCHOR.day, tzinfo=UTC)
    count = 5 + _spy_digest(handle.lower(), "x_count") % 8
    posts = []
    for i in range(count):
        seed = f"x_post|{handle.lower()}|{i}"
        post_id = str(10**18 + _spy_digest(seed, "id") % (9 * 10**18))
        age_days = i * 120 // count + _spy_digest(seed, "day") % max(1, 120 // count)
        posted = anchor - timedelta(
            days=age_days,
            hours=2 + _spy_digest(seed, "hour") % 14,
            minutes=_spy_digest(seed, "minute") % 60,
        )
        stamp = posted.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        tags = [
            tag[1:]
            for tag in _spy_order(seed + "|tags", list(_SPY_HASHTAGS))[
                : _spy_digest(seed, "tags") % 3
            ]
        ]
        repost = _spy_digest(seed, "repost") % 3 == 0
        parent = {
            "date_posted": stamp,
            "post_id": post_id,
            "profile_id": user_id,
            "profile_name": name,
        }
        tagged = None
        if repost:
            source = _spy_pick(seed, "parent", _SPY_NEUTRAL[:6])["source"]
            reposter = source.replace(" ", "")
            parent = {
                "date_posted": (
                    posted - timedelta(hours=1 + _spy_digest(seed, "lag") % 72)
                ).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "post_id": str(10**18 + _spy_digest(seed, "parent_id") % (9 * 10**18)),
                "profile_id": str(
                    10**6 + _spy_digest(reposter, "profile") % (9 * 10**8)
                ),
                "profile_name": source,
            }
            tagged = [
                {
                    "biography": None,
                    "followers": None,
                    "following": None,
                    "is_verified": None,
                    "profile_id": parent["profile_id"],
                    "profile_name": source,
                    "url": f"https://x.com/{reposter}",
                }
            ]
            text = f"RT @{reposter}: " + _spy_pick(seed, "single", _SPY_SINGLES).format(
                b=company["name"]
            )
        else:
            text = _spy_pick(seed, "text", _SPY_POST_TEXTS).format(
                name=company["name"],
                feature=_spy_pick(seed, "feature", _SPY_FEATURES),
                benefit=_spy_pick(seed, "benefit", _SPY_BENEFITS),
            )
        if tags:
            text += "\n\n" + " ".join("#" + tag for tag in tags)
        kind = _spy_digest(seed, "media") % 6
        photos = (
            [
                f"https://pbs.twimg.com/media/{_spy_digest(seed, 'photo', str(n)) % 16**15:015x}.jpg"
                for n in range(1 + kind % 2)
            ]
            if kind < 2
            else None
        )
        videos = None
        if kind == 2:
            videos = [
                {
                    "duration": 5000 + _spy_digest(seed, "duration") % 60000,
                    "video_url": f"https://video.twimg.com/amplify_video/{int(post_id) - 10**9}/vid/avc1/1080x1920/{_spy_digest(seed, 'video') % 16**15:015x}.mp4?tag=16",
                }
            ]
        likes = 5 + _spy_digest(seed, "likes") % 300
        posts.append(
            {
                "id": post_id,
                "url": f"https://x.com/{handle.lower()}/status/{post_id}",
                "user_posted": company["x"],
                "name": name,
                "user_id": user_id,
                "description": text,
                "date_posted": stamp,
                "hashtags": tags or None,
                "photos": photos,
                "videos": videos,
                "quoted_post": {"photos": None, "videos": None},
                "is_repost": repost,
                "parent_post_details": parent,
                "tagged_users": tagged,
                "external_url": _SPY_PAGES[company["domain"]][1]
                if _spy_digest(seed, "link") % 5 == 0
                else None,
                "external_image_urls": None,
                "external_video_urls": None,
                "ai_generated_images": None,
                "context_added": None,
                "likes": likes,
                "replies": _spy_digest(seed, "replies") % 12,
                "reposts": _spy_digest(seed, "reposts") % 60,
                "quotes": _spy_digest(seed, "quotes") % 5,
                "bookmarks": _spy_digest(seed, "bookmarks") % 15,
                "views": 400 + likes * 20 + _spy_digest(seed, "views") % 3000,
                "followers": followers,
                "following": following,
                "posts_count": posts_count,
                "is_verified": True,
                "verification_type": badge,
                "biography": biography,
                "profile_image_link": f"https://pbs.twimg.com/profile_images/{10**18 + _spy_digest(user_id, 'avatar') % (9 * 10**18)}/{_spy_digest(user_id, 'avatar', 'name') % 16**8:08x}_normal.jpg",
                "timestamp": f"{SPY_ANCHOR.isoformat()}T12:00:00.000Z",
                "input": {"url": f"https://x.com/{handle.lower()}/status/{post_id}"},
                "discovery_input": {
                    "url": f"https://x.com/{handle}",
                    "start_date": "",
                    "end_date": "",
                },
            }
        )
    return posts


def _spy_instagram_host(seed: str) -> str:
    return f"scontent-{_spy_pick(seed, 'pop', _SPY_INSTAGRAM_POPS)}.cdninstagram.com"


def _spy_instagram_signed(seed: str, host: str) -> str:
    return f"_nc_cat={100 + _spy_digest(seed, 'cat') % 12}&ccb=7-5&_nc_ohc={_spy_digest(seed, 'ohc') % 16**22:022x}&_nc_ht={host}&oh=00_{_spy_digest(seed, 'oh') % 16**32:032x}&oe={_spy_digest(seed, 'oe') % 16**8:08X}"


def _spy_instagram_image(seed: str, folder: str, size: str) -> str:
    host = _spy_instagram_host(seed)
    stem = f"{_spy_digest(seed, 'a') % 10**9:09d}_{_spy_digest(seed, 'b') % 10**17:017d}_{_spy_digest(seed, 'c') % 10**19:019d}_n.jpg"
    return f"https://{host}/v/{folder}/{stem}?stp=dst-jpg_{size}_tt6&{_spy_instagram_signed(seed, host)}"


def _spy_instagram_video(seed: str) -> str:
    host = _spy_instagram_host(seed)
    token = (
        base64.urlsafe_b64encode(hashlib.sha512(seed.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return f"https://{host}/o1/v/t2/f2/m86/AQ{token}.mp4?{_spy_instagram_signed(seed, host)}"


def _spy_instagram_shortcode(pk: int) -> str:
    code = ""
    while pk:
        pk, digit = divmod(pk, 64)
        code = _SPY_INSTAGRAM_ALPHABET[digit] + code
    return code


def spy_instagram_posts(handle: str) -> list[dict]:
    company = _SPY_INSTAGRAM.get(handle.lower())
    if company is None:
        return []
    slug = handle.lower()
    anchor = datetime(SPY_ANCHOR.year, SPY_ANCHOR.month, SPY_ANCHOR.day, tzinfo=UTC)
    count = 5 + _spy_digest(slug, "instagram_count") % 8
    collab = _spy_digest(slug, "instagram_collab") % count
    posts = []
    for i in range(count):
        seed = f"instagram_post|{slug}|{i}"
        author = _SPY_INSTAGRAM_EVENTS[slug] if i == collab else slug
        name, user_id, followers, posts_count, verified = _SPY_INSTAGRAM_PROFILES[
            author
        ]
        age_days = i * 120 // count + _spy_digest(seed, "day") % max(1, 120 // count)
        posted = anchor - timedelta(
            days=age_days,
            hours=2 + _spy_digest(seed, "hour") % 14,
            minutes=_spy_digest(seed, "minute") % 60,
        )
        pk = (
            int(posted.timestamp()) * 1000 - _SPY_INSTAGRAM_EPOCH_MS
        ) << 23 | _spy_digest(seed, "id") % 2**23
        shortcode = _spy_instagram_shortcode(pk)
        content_type, product_type = _SPY_INSTAGRAM_TYPES[
            (i + _spy_digest(slug, "instagram_kind")) % len(_SPY_INSTAGRAM_TYPES)
        ]
        url = f"https://www.instagram.com/{'reel' if content_type == 'Reel' else 'p'}/{shortcode}/"
        alt_text = f"{'Video' if content_type == 'Reel' else 'Photo'} by {name} on {posted.strftime('%B %d, %Y')}."
        tags = _spy_order(seed + "|tags", list(_SPY_HASHTAGS))[
            : _spy_digest(seed, "tags") % 3
        ]
        text = _spy_pick(seed, "text", _SPY_POST_TEXTS).format(
            name=company["name"],
            feature=_spy_pick(seed, "feature", _SPY_FEATURES),
            benefit=_spy_pick(seed, "benefit", _SPY_BENEFITS),
        )
        if tags:
            text += "\n\n" + " ".join(tags)
        if content_type == "Reel":
            video = _spy_instagram_video(seed)
            thumbnail = _spy_instagram_image(
                seed + "|thumbnail", "t51.82787-15", "e35_s640x640"
            )
            photos = None
            images = []
            videos = [video]
            videos_duration = [
                {
                    "url": video,
                    "video_duration": 5
                    + _spy_digest(seed, "duration") % 120
                    + _spy_digest(seed, "frames") % 10**6 / 10**6,
                }
            ]
            post_content = [
                {
                    "alt_text": alt_text,
                    "id": str(pk),
                    "index": 0,
                    "thumbnail": thumbnail,
                    "type": "Video",
                    "url": video,
                }
            ]
            thumbnail_array = [thumbnail]
        else:
            photos = [
                _spy_instagram_image(
                    f"{seed}|photo|{n}", "t51.82787-15", "e35_s640x640"
                )
                for n in range(
                    1
                    if content_type == "Image"
                    else 2 + _spy_digest(seed, "photos") % 3
                )
            ]
            children = (
                [str(pk)]
                if len(photos) == 1
                else [str(pk - 2**33 + n * 2**23) for n in range(len(photos))]
            )
            images = [
                {"id": child, "url": photo}
                for child, photo in zip(children, photos, strict=True)
            ]
            post_content = [
                {
                    "alt_text": alt_text,
                    "id": child,
                    "index": n,
                    "thumbnail": photo,
                    "type": "Photo",
                    "url": photo,
                }
                for n, (child, photo) in enumerate(zip(children, photos, strict=True))
            ]
            thumbnail = photos[0]
            thumbnail_array = photos
            videos = None
            videos_duration = None
        comments = []
        for n in range(_spy_digest(seed, "comments") % 3):
            comment_id = str(
                17 * 10**15 + _spy_digest(seed, "comment", str(n)) % 10**15
            )
            comments.append(
                {
                    "comment_id": comment_id,
                    "comment_url": f"{url}?comment_id={comment_id}",
                    "comments": _spy_pick(
                        seed, f"comment_text_{n}", _SPY_INSTAGRAM_COMMENTS
                    ),
                    "date_of_comment": (posted + timedelta(days=n)).strftime(
                        "%Y-%m-%d"
                    ),
                    "likes": _spy_digest(seed, "comment_likes", str(n)) % 3,
                    "profile_picture": _spy_instagram_image(
                        f"{seed}|commenter|{n}", "t51.2885-19", "s150x150"
                    ),
                }
            )
        tagged = None
        if author != slug:
            tagged = [
                {
                    "full_name": _SPY_INSTAGRAM_PROFILES[slug][0],
                    "id": _SPY_INSTAGRAM_PROFILES[slug][1],
                    "is_verified": True,
                    "profile_pic_url": _spy_instagram_image(
                        f"instagram_avatar|{slug}", "t51.2885-19", "s150x150"
                    ),
                    "username": slug,
                }
            ]
        posts.append(
            {
                "alt_text": alt_text,
                "audio": None,
                "audio_url": None,
                "coauthor_producers": [slug] if author != slug else None,
                "content_id": shortcode,
                "content_type": content_type,
                "date_posted": posted.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "description": text,
                "discovery_input": {
                    "url": f"https://www.instagram.com/{handle}/",
                    "start_date": "",
                    "end_date": "",
                    "post_type": "",
                },
                "followers": followers,
                "hashtags": tags or None,
                "images": images,
                "input": {"url": url},
                "is_verified": verified,
                "latest_comments": comments,
                "likes": 25 + _spy_digest(seed, "likes") % 1700,
                "location": None,
                "location_details": None,
                "num_comments": len(comments) + _spy_digest(seed, "num_comments") % 12,
                "partnership_details": None,
                "photos": photos,
                "photos_number": len(photos or []),
                "pk": str(pk),
                "post_content": post_content,
                "post_id": str(pk),
                "posts_count": posts_count,
                "product_type": product_type,
                "profile_image_link": _spy_instagram_image(
                    f"instagram_avatar|{author}", "t51.2885-19", "s150x150"
                ),
                "profile_url": f"https://www.instagram.com/{author}",
                "shortcode": shortcode,
                "tagged_users": tagged,
                "thumbnail": thumbnail,
                "thumbnail_array": thumbnail_array,
                "timestamp": f"{SPY_ANCHOR.isoformat()}T12:00:00.000Z",
                "url": url,
                "user_posted": author,
                "user_posted_id": user_id,
                "videos": videos,
                "videos_duration": videos_duration,
            }
        )
    return posts


def _spy_company_named(name: str) -> dict | None:
    needle = name.lower()
    for company in SPY_COMPETITORS:
        if needle in [n.lower() for n in [company["name"], *company["aliases"]]]:
            return company
    return None


def _spy_licdn(seed: str, salt: str, variant: str, page: int = 0) -> str:
    digest = _spy_digest(seed, salt)
    return f"https://media.licdn.com/dms/image/v2/D4E10AQ{digest % 10**12:012d}/{variant}/{page}/{1_750_000_000_000 + digest % 10**10}?e=2147483647&v=beta"


def spy_linkedin_ads(advertiser: str) -> list[dict]:
    company = _spy_company_named(advertiser)
    if company is None or "linkedin" not in company:
        return []
    slug = company["linkedin"]
    count = 5 + _spy_digest(slug, "linkedin_count") % 8
    ads = []
    for i in range(count + 1):
        seed = f"linkedin_ad|{slug}|{i}"
        ad_id = str(10**9 + _spy_digest(seed, "id") % (9 * 10**9))
        ad_type = "message" if i == 0 else _spy_pick(seed, "type", _SPY_LINKEDIN_TYPES)
        content = {"headline": spy_ad_text(ad_id)}
        if ad_type in ("image", "video"):
            content["image"] = _spy_licdn(
                seed,
                "media",
                "image-shrink_1280" if ad_type == "image" else "videocover-high",
            )
            content["cta"] = _spy_pick(seed, "cta", _SPY_AD_HEADLINES)
        elif ad_type == "document":
            content["title"] = _spy_pick(seed, "title", _SPY_AD_HEADLINES)
            content["pages"] = [
                _spy_licdn(seed, "media", "ads-document-cover-images_480", page)
                for page in range(1 + _spy_digest(seed, "pages") % 3)
            ]
        owner = {
            "name": company["name"],
            "thumbnail": _spy_licdn(slug, "logo", "company-logo_100_100"),
        }
        if i == count:
            person, role = _spy_pick(seed, "person", _SPY_LINKEDIN_PEOPLE)
            owner = {
                "name": person,
                "position": f"{role} at {company['name']}",
                "promotor": company["name"],
                "thumbnail": _spy_licdn(
                    seed, "photo", "profile-displayphoto-shrink_100_100"
                ),
            }
        link = f"https://www.linkedin.com/ad-library/detail/{ad_id}"
        if ad_type == "image":
            link += "?trk=ad_library_ad_preview_content_image"
        ads.append(
            {
                "position": i + 1,
                "advertiser": owner,
                "ad_type": ad_type,
                "content": content,
                "link": link,
                "id": ad_id,
            }
        )
    return ads


def _spy_linkedin_detail(company: dict, ad: dict) -> dict:
    seed = f"linkedin_detail|{ad['id']}"
    first_age = 1 + _spy_digest(seed, "first") % 120
    last_age = (
        1
        if _spy_digest(seed, "running") % 3 == 0
        else 1 + _spy_digest(seed, "last") % first_age
    )
    label, low, high = _spy_pick(seed, "band", _SPY_LINKEDIN_BANDS)
    countries = _spy_order(seed, list(_SPY_LINKEDIN_COUNTRIES))[
        : 2 + _spy_digest(seed, "countries") % 4
    ]
    weights = {c: 1 + _spy_digest(seed, c, "share") % 9 for c in countries}
    total = sum(weights.values())
    shares = sorted(((w * 100 // total, c) for c, w in weights.items()), reverse=True)
    company_id = 10**7 + _spy_digest(company["linkedin"], "company_id") % (9 * 10**7)
    detail = {
        "id": ad["id"],
        "link": f"https://www.linkedin.com/ad-library/detail/{ad['id']}",
        "external_link": f"{_SPY_PAGES[company['domain']][1]}?utm_source=linkedin&utm_medium=paid&hsa_ad={ad['id']}&hsa_net=linkedin",
        "ad_type": ad["ad_type"],
        "ad_format": _SPY_LINKEDIN_FORMATS[ad["ad_type"]],
        "advertiser": {
            **ad["advertiser"],
            "link": f"https://www.linkedin.com/company/{company_id}?trk=ad_library_about_ad_advertiser",
        },
        "content": {
            **ad["content"],
            "call_to_action": _spy_pick(seed, "call", _SPY_LINKEDIN_CTAS),
        },
        "paid_for_by": company["name"]
        + (", Inc." if _spy_digest(company["name"], "inc") % 2 else ""),
        "first_shown_date": (SPY_ANCHOR - timedelta(days=first_age)).isoformat(),
        "last_shown_date": (SPY_ANCHOR - timedelta(days=last_age)).isoformat(),
        "total_impressions": label,
    }
    if low:
        detail["total_impressions_min"] = low
    detail["total_impressions_max"] = high
    detail["impressions_by_country"] = [
        {"country": c, "percentage": p, "percentage_display": f"{p}%"}
        for p, c in shares
    ]
    detail["targeting"] = [
        {"name": "Language", "included": ["English"]},
        {"name": "Location", "included": countries},
    ]
    detail["targeting_parameters"] = [
        {"name": n, "is_targeted": t, "is_excluded": t}
        for n, t in _SPY_LINKEDIN_TARGETING
    ]
    if _spy_digest(seed, "published") % 3 == 0:
        return {key: detail[key] for key in _SPY_LINKEDIN_UNPUBLISHED}
    return detail


def spy_linkedin_ad_detail(ad_id: str) -> dict | None:
    for company in SPY_COMPETITORS:
        for ad in spy_linkedin_ads(company["name"]):
            if ad["id"] == ad_id:
                return _spy_linkedin_detail(company, ad)
    return None


def _spy_token(payload: dict) -> str:
    return base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()


def _spy_tiktok_token(advertiser_id: str, name: str) -> str:
    return _spy_token({"id": advertiser_id, "name": name})


def spy_tiktok_advertisers(query: str) -> list[dict]:
    needle = query.lower()
    return [
        {
            "id": advertiser_id,
            "name": company["tiktok_advertiser_name"],
            "advertiser_token": _spy_tiktok_token(
                advertiser_id, company["tiktok_advertiser_name"]
            ),
        }
        for advertiser_id, company in _SPY_TIKTOK.items()
        if needle in company["tiktok_advertiser_name"].lower()
    ]


def _spy_tiktok_image(seed: str, salt: str, folder: str) -> str:
    digest = f"{_spy_digest(seed, salt) % 16**32:032x}"
    return f"https://p16-common-sign.tiktokcdn.com/{folder}/{digest}~tplv-tiktokx-origin.jpeg?dr=14582&refresh_token={digest[:8]}&x-expires={_SPY_TIKTOK_STAMP}&x-signature={digest[8:]}%3D&t=4d5b0474&ps=13740610&shp=0c75dd76&shcp=9b759fb9&idc=sg1"


def _spy_tiktok_video(seed: str) -> str:
    digest = _spy_digest(seed, "video")
    source = base64.b64encode(
        f"https://v77.tiktokcdn.com/{digest % 16**32:032x}/video/tos/alisg/".encode()
    ).decode()
    return f"https://library.tiktok.com/api/v1/cdn/{_SPY_TIKTOK_STAMP}/video/{source}/{uuid.UUID(int=digest % 2**128)}?a=475769&bt=386&mime_type=video_mp4&vvpl=1"


def spy_tiktok_ads(advertiser_id: str) -> list[dict]:
    company = _SPY_TIKTOK.get(advertiser_id)
    if company is None:
        return []
    name = company["tiktok_advertiser_name"]
    token = _spy_tiktok_token(advertiser_id, name)
    ads = []
    for i in range(14 + _spy_digest(advertiser_id, "tiktok_count") % 7):
        seed = f"tiktok_ad|{advertiser_id}|{i}"
        fmt = "video" if _spy_digest(seed, "format") % 10 < 7 else "image"
        first_age = 1 + _spy_digest(seed, "first") % 120
        last_age = _spy_digest(seed, "last") % (first_age + 1)
        label, low, high = _spy_pick(seed, "band", _SPY_TIKTOK_BANDS)
        ad = {
            "id": str(10**15 + _spy_digest(seed, "id") % (9 * 10**15)),
            "advertiser_id": advertiser_id,
            "advertiser": name,
            "advertiser_token": token,
            "title": f"{_spy_pick(seed, 'headline', _SPY_AD_HEADLINES)}. {_spy_pick(seed, 'line', _SPY_AD_LINES)}",
            "format": fmt,
            "first_shown_datetime": (SPY_ANCHOR - timedelta(days=first_age)).isoformat()
            + "T00:00:00Z",
            "last_shown_datetime": (SPY_ANCHOR - timedelta(days=last_age)).isoformat()
            + "T00:00:00Z",
        }
        if fmt == "video":
            ad["video_link"] = _spy_tiktok_video(seed)
            ad["cover_image"] = _spy_tiktok_image(
                seed, "cover", "tos-alisg-p-0051c001-sg"
            )
            ad["image_urls"] = [ad["cover_image"]]
        else:
            ad["image_urls"] = [
                _spy_tiktok_image(seed, f"image{n}", "ad-site-i18n-sg")
                for n in range(1 + _spy_digest(seed, "images") % 3)
            ]
        ad.update(
            {
                "estimated_audience": label,
                "estimated_audience_min": low,
                "estimated_audience_max": high,
            }
        )
        ads.append(ad)
    ads.sort(key=lambda ad: ad["last_shown_datetime"], reverse=True)
    return [{"position": position, **ad} for position, ad in enumerate(ads, 1)]


def _spy_tiktok_avatar(stem: str, size: int) -> str:
    digest = f"{_spy_digest(stem, str(size)) % 16**32:032x}"
    return f"https://p19-common-sign.tiktokcdn-us.com/{stem}~tplv-tiktokx-cropcenter:{size}:{size}.jpeg?dr=9640&refresh_token={digest[:8]}&x-expires={_SPY_TIKTOK_STAMP}&x-signature={digest[8:]}%3D&t=4d5b0474&ps=13740610&shp=a5d48078&shcp=81f88b70&idc=useast5"


def _spy_tiktok_stream(seed: str, salt: str, mime: str) -> str:
    digest = _spy_digest(seed, salt)
    return f"https://v16-webapp-prime.us.tiktok.com/video/tos/useast5/tos-useast5-v-85c255-tx/o{digest % 16**33:033x}/?a=1988&bti=ODszNWYuMDE6&&bt={1000 + digest % 900}&mime_type={mime}&expire={_SPY_TIKTOK_STAMP}&ply_type=2&policy=2&signature={_spy_digest(seed, salt, 'signature') % 16**32:032x}&tk=tt_chain_token&btag=e000f0000"


def spy_tiktok_posts(handle: str) -> list[dict]:
    slug = handle.lower()
    company = _SPY_TIKTOK_HANDLES.get(slug)
    if company is None:
        return []
    username, profile_id, followers, verified, biography, avatar, secu_id = (
        _SPY_TIKTOK_PROFILES[slug]
    )
    first_age, span, least, spread = _SPY_TIKTOK_WINDOWS[slug]
    anchor = datetime(SPY_ANCHOR.year, SPY_ANCHOR.month, SPY_ANCHOR.day, tzinfo=UTC)
    count = least + _spy_digest(slug, "tiktok_count") % spread
    photo = _spy_digest(slug, "tiktok_photo") % count
    profile_url = f"https://www.tiktok.com/@{slug}"
    music_title = f"original sound - {username}"
    posts = []
    for i in range(count):
        seed = f"tiktok_post|{slug}|{i}"
        age_days = (
            first_age
            + i * span // count
            + _spy_digest(seed, "day") % max(1, span // count)
        )
        posted = anchor - timedelta(
            days=age_days,
            hours=2 + _spy_digest(seed, "hour") % 14,
            minutes=_spy_digest(seed, "minute") % 60,
            seconds=_spy_digest(seed, "second") % 60,
        )
        post_id = str(int(posted.timestamp()) << 32 | _spy_digest(seed, "id") % 2**32)
        url = f"{profile_url}/video/{post_id}"
        tags = [
            tag[1:]
            for tag in _spy_order(seed + "|tags", list(_SPY_HASHTAGS))[
                : _spy_digest(seed, "tags") % 3
            ]
        ]
        text = _spy_pick(seed, "text", _SPY_POST_TEXTS).format(
            name=company["name"],
            feature=_spy_pick(seed, "feature", _SPY_FEATURES),
            benefit=_spy_pick(seed, "benefit", _SPY_BENEFITS),
        )
        if tags:
            text += " " + " ".join("#" + tag for tag in tags)
        comments = []
        for n in range(_spy_digest(seed, "comments") % 3):
            commented = posted + timedelta(
                days=n + 1, hours=_spy_digest(seed, "comment_hour", str(n)) % 24
            )
            comment_id = str(
                int(commented.timestamp()) << 32
                | _spy_digest(seed, "comment", str(n)) % 2**32
            )
            comments.append(
                {
                    "comment": _spy_pick(
                        seed, f"comment_text_{n}", _SPY_TIKTOK_COMMENTS
                    ),
                    "comment_id": comment_id,
                    "comment_url": f"{url}?comment_id={comment_id}",
                    "date": commented.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "likes": _spy_digest(seed, "comment_likes", str(n)) % 3,
                    "num_of_replies": 0,
                    "user_handle": _spy_pick(
                        seed, f"commenter_{n}", _SPY_TIKTOK_COMMENTERS
                    ),
                    "user_id": str(
                        6 * 10**18 + _spy_digest(seed, "commenter_id", str(n)) % 10**18
                    ),
                }
            )
        subtitle_format = subtitle_url = None
        if i == photo:
            carousel = [
                _spy_tiktok_image(seed, f"photo{n}", "tos-maliva-i-photomode-us")
                for n in range(2 + _spy_digest(seed, "photos") % 4)
            ]
            preview = carousel[0]
            video = cdn_link = duration = ratio = subtitle_info = None
            width = 0
            post_type = "images"
        else:
            carousel = None
            preview = _spy_tiktok_image(seed, "preview", "tos-useast5-p-85c255-tx")
            video = _spy_tiktok_stream(seed, "video", "video_mp4")
            cdn_link = _spy_tiktok_stream(seed, "cdn", "video_mp4")
            duration = 5 + _spy_digest(seed, "duration") % 80
            ratio, width = (
                ("540p", 576) if _spy_digest(seed, "ratio") % 8 == 0 else ("720p", 720)
            )
            post_type = "video"
            subtitle_info = []
            if _spy_digest(seed, "subtitles") % 2 == 0:
                subtitle_format = "webvtt"
                subtitle_url = _spy_tiktok_stream(seed, "subtitle", "video_mp4")
                subtitle_info = [
                    {
                        "format": "webvtt",
                        "language_code_name": "eng-US",
                        "language_id": "2",
                        "size": 400 + _spy_digest(seed, "subtitle_size") % 3000,
                        "url": subtitle_url,
                        "url_expire": str(_SPY_TIKTOK_STAMP),
                        "version": "1:big_caption",
                    }
                ]
        likes = _spy_digest(seed, "likes") % 70
        shares = max(0, _spy_digest(seed, "shares") % 14 - 4)
        posts.append(
            {
                "account_id": slug,
                "carousel_images": carousel,
                "cdn_link": cdn_link,
                "cdn_url": f"https://www.tiktok.com/{uuid.UUID(int=_spy_digest(seed, 'cdn_url') % 2**128)}",
                "collect_count": _spy_digest(seed, "collects") % 12,
                "comment_count": len(comments) + _spy_digest(seed, "comment_count") % 3,
                "comments": comments,
                "commerce_info": None,
                "create_time": posted.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "description": text,
                "digg_count": likes,
                "discovery_input": {
                    "url": f"https://www.tiktok.com/@{handle}",
                    "start_date": "",
                    "end_date": "",
                    "what_to_collect": "",
                    "post_type": "",
                    "country": "",
                    "sort_by": "",
                },
                "hashtags": tags or None,
                "input": {"url": url, "discovery_input": None},
                "is_verified": verified,
                "music": {
                    "authorname": username,
                    "covermedium": _spy_tiktok_avatar(avatar, 720),
                    "id": str(int(post_id) + _spy_digest(seed, "music") % 10**9),
                    "original": True,
                    "playurl": _spy_tiktok_stream(seed, "music", "audio_mpeg"),
                    "title": music_title,
                },
                "num_share_count": shares,
                "offical_item": False,
                "original_item": False,
                "original_sound": f"{username}: {music_title}",
                "play_count": 100 + likes * 30 + _spy_digest(seed, "plays") % 900,
                "post_id": post_id,
                "post_type": post_type,
                "preview_image": preview,
                "profile_avatar": _spy_tiktok_avatar(avatar, 1080),
                "profile_biography": biography,
                "profile_followers": followers,
                "profile_id": profile_id,
                "profile_url": profile_url,
                "profile_username": username,
                "ratio": ratio,
                "region": "US",
                "secu_id": secu_id,
                "share_count": str(shares) if shares else None,
                "shortcode": post_id,
                "subtitle_format": subtitle_format,
                "subtitle_info": subtitle_info,
                "subtitle_url": subtitle_url,
                "tagged_user": None,
                "timestamp": f"{SPY_ANCHOR.isoformat()}T12:00:00.000Z",
                "tt_chain_token": base64.b64encode(
                    _spy_digest(seed, "chain").to_bytes(16, "big")
                ).decode(),
                "url": url,
                "video_duration": duration,
                "video_url": video,
                "width": width,
            }
        )
    return posts


def _spy_fbcdn(seed: str, salt: str, folder: str, sizing: str = "") -> str:
    digest = _spy_digest(seed, salt)
    query = f"stp={sizing}&" if sizing else ""
    return f"https://scontent-msp1-1.xx.fbcdn.net/v/{folder}/{digest % 10**9}_{digest // 10**9 % 10**16}_{digest // 10**25 % 10**19}_n.jpg?{query}_nc_cat={100 + digest % 12}&ccb=1-7&_nc_sid=c53f8f&oh=00_{digest:032x}&oe={digest % 16**8:08X}"


def _spy_fbcdn_video(seed: str, salt: str, folder: str) -> str:
    digest = _spy_digest(seed, salt)
    return f"https://video-msp1-1.xx.fbcdn.net/o1/v/t2/f2/{folder}/AQO{digest:032x}.mp4?_nc_cat={100 + digest % 12}&_nc_sid=b66105&oh=00_{_spy_digest(seed, salt, 'oh'):032x}&oe={digest % 16**8:08X}"


def _spy_meta_likes(page_id: str) -> int:
    return 10**4 + _spy_digest(page_id, "likes") % (3 * 10**6)


def spy_meta_pages(query: str) -> list[dict]:
    needle = query.lower()
    pages = []
    for company in _SPY_META.values():
        if not any(
            needle in name.lower() for name in [company["name"], *company["aliases"]]
        ):
            continue
        page_id = company["meta_page_id"]
        alias = company["domain"].split(".")[0]
        pages.append(
            {
                "page_id": page_id,
                "category": "Software",
                "image_uri": _spy_fbcdn(
                    page_id, "avatar", "t39.30808-1", "dst-jpg_s100x100_tt6"
                ),
                "likes": _spy_meta_likes(page_id),
                "verification": "BLUE_VERIFIED",
                "name": company["name"],
                "entity_type": "PERSON_PROFILE",
                "ig_username": alias,
                "ig_followers": 10**3 + _spy_digest(page_id, "followers") % 10**6,
                "ig_verification": True,
                "page_alias": alias,
            }
        )
    return pages


def spy_meta_ads(page_id: str) -> list[dict]:
    company = _SPY_META.get(page_id)
    if company is None:
        return []
    domain = company["domain"]
    page = {
        "page_id": page_id,
        "page_is_deleted": False,
        "page_profile_uri": f"https://www.facebook.com/{domain.split('.')[0]}/",
        "page_name": company["name"],
        "page_profile_picture_url": _spy_fbcdn(
            page_id, "avatar", "t39.35426-6", "dst-jpg_s60x60_tt6"
        ),
        "page_like_count": _spy_meta_likes(page_id),
        "page_categories": ["Software"],
    }
    ads = []
    for i in range(4 + _spy_digest(page_id, "count") % 7):
        seed = f"meta_ad|{page_id}|{i}"
        ad_id = str(10**15 + _spy_digest(seed, "id") % (9 * 10**15))
        fmt = "IMAGE" if _spy_digest(seed, "format") % 4 else "VIDEO"
        start_age = 1 + _spy_digest(seed, "start") % 120
        active = _spy_digest(seed, "active") % 5 != 0
        end_age = 0 if active else _spy_digest(seed, "end") % (start_age + 1)
        cta_text, cta_type = _spy_pick(seed, "cta", _SPY_META_CTAS)
        snapshot = {
            **page,
            "byline": None,
            "caption": domain.upper(),
            "cta_text": cta_text,
            "cards": [],
            "body": {"text": _spy_pick(seed, "line", _SPY_AD_LINES)},
            "cta_type": cta_type,
            "display_format": fmt,
            "link_description": _SPY_PAGES[domain][0],
            "link_url": f"{_SPY_PAGES[domain][1]}?utm_source=facebook&utm_medium=paid",
            "images": [],
            "title": _spy_pick(seed, "headline", _SPY_AD_HEADLINES),
            "videos": [],
            "is_reshared": False,
            "extra_links": [],
            "extra_texts": [],
            "extra_images": [],
            "extra_videos": [],
            "ec_certificates": [],
        }
        if fmt == "IMAGE":
            snapshot["images"].append(
                {
                    "image_crops": [],
                    "original_image_url": _spy_fbcdn(seed, "original", "t39.35426-6"),
                    "resized_image_url": _spy_fbcdn(
                        seed, "resized", "t39.35426-6", "dst-jpg_s600x600_tt6"
                    ),
                    "watermarked_resized_image_url": "",
                }
            )
        else:
            snapshot["videos"].append(
                {
                    "video_hd_url": _spy_fbcdn_video(seed, "hd", "m366"),
                    "video_preview_image_url": _spy_fbcdn(
                        seed, "preview", "t39.35426-6"
                    ),
                    "video_sd_url": _spy_fbcdn_video(seed, "sd", "m412"),
                }
            )
        ads.append(
            {
                "ad_archive_id": ad_id,
                "is_active": active,
                "page_id": page_id,
                "page_is_deleted": False,
                "snapshot": snapshot,
                "has_user_reported": False,
                "menu_items": [],
                "page_name": company["name"],
                "impressions_with_index": {"impressions_index": -1},
                "gated_type": "ELIGIBLE",
                "categories": ["UNKNOWN"],
                "is_aaa_eligible": _spy_digest(seed, "aaa") % 2 == 0,
                "contains_digital_created_media": False,
                "currency": "",
                "end_date": (SPY_ANCHOR - timedelta(days=end_age)).isoformat()
                + "T07:00:00Z",
                "publisher_platform": list(
                    _spy_pick(seed, "platforms", _SPY_META_PLATFORMS)
                ),
                "start_date": (SPY_ANCHOR - timedelta(days=start_age)).isoformat()
                + "T07:00:00Z",
                "contains_sensitive_content": False,
                "regional_regulation_data": _SPY_META_REGULATION,
                "hide_data_status": "NONE",
                "targeted_or_reached_countries": [],
                "ad_details_token": _spy_token(
                    {"ad_archive_id": ad_id, "page_id": page_id}
                ),
            }
        )
    ads.sort(key=lambda ad: ad["start_date"], reverse=True)
    return ads
