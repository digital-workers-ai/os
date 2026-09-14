from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from seeds.world import COMPETITOR_PAGES, COMPETITORS_BY_ID, OUR_BRAND

router = APIRouter()

_ENGINE = "google"
_CREATED_AT = "2026-09-14 05:42:11 UTC"
_DEFAULT_LOCATION = "United States"
_SNIPPET_CHARS = 155

_WORLD_PAGES = {
    (COMPETITORS_BY_ID[page.competitor_id].domain, page.path): page
    for page in COMPETITOR_PAGES
}

_OTHER_PAGES = {
    (OUR_BRAND.domain, "/"): (
        "Digital Workers — AI video ads, made by an operator not a studio",
        "We run the tool, you approve the ad. Digital Workers writes, renders and ships video ads for brands that do not want another seat to manage.",
    ),
    (OUR_BRAND.domain, "/ugc"): (
        "UGC ads without a creator roster — Digital Workers",
        "Creator-style video ads from your product page and your customer reviews, approved by you before anything runs. No casting, no usage rights, no eleven-day wait.",
    ),
    (OUR_BRAND.domain, "/ai-ads-without-a-studio"): (
        "AI ads without a studio — Digital Workers",
        "No crew, no shoot day, no edit suite. A working method for teams making video ads with AI when nobody on the team has ever cut one.",
    ),
    ("reelforge.io", "/"): (
        "ReelForge — AI video ads at agency volume",
        "Forge every ad your media buyer asked for. ReelForge drafts, voices and renders short-form video ads from a brief, a URL or a spreadsheet of products.",
    ),
    ("hookmill.co", "/"): (
        "Hookmill — a hook engine for paid social",
        "Hookmill writes two hundred hooks against your product, scores them against ads that actually ran, and hands the winners to whatever renders your video.",
    ),
    ("hookmill.co", "/ugc"): (
        "UGC hooks that survive a cold audience — Hookmill",
        "The hook library behind 40,000 creator-style ads, sorted by the objection each one answers. Free to browse, no account, scores included.",
    ),
    ("cutcraft.ai", "/"): (
        "CutCraft — automatic edits for short-form video",
        "Upload the raw file, get a feed-ready cut: hook first, captions burned in, silence trimmed, exported in every ratio. Built for teams that film more than they publish.",
    ),
    ("framewise.ai", "/"): (
        "Framewise — turn long video into short ads",
        "Framewise finds the twenty seconds worth running inside your webinars, demos and interviews, then cuts each one into an ad you can ship the same day.",
    ),
    ("promptreel.com", "/"): (
        "PromptReel — describe the ad, get the ad",
        "Type a sentence and PromptReel storyboards, voices and renders it. Two hundred presenters, thirty languages, and a first draft in about ninety seconds.",
    ),
    ("studioless.io", "/"): (
        "Studioless — ship video ads without a studio",
        "No crew, no lights, no booking. Studioless is a rendering pipeline for brands whose entire creative department is one marketer and a phone.",
    ),
    ("takeone.tools", "/"): (
        "TakeOne — one take, every format",
        "Record once and TakeOne reformats, recaptions and retimes it for every placement you buy. The 9:16 is not a crop, it is a recut.",
    ),
    ("toolwatch.io", "/best-ai-ugc-ad-tools"): (
        "The 11 best AI UGC ad tools in 2026, tested — Toolwatch",
        "We ran the same product page through eleven tools and spent $400 on each output. Scores for script quality, render time, presenter range and what it actually costs at volume.",
    ),
    ("toolwatch.io", "/ai-video-ad-makers"): (
        "AI video ad makers compared: 14 tools, one product — Toolwatch",
        "Fourteen tools, one skincare listing, the same brief. Side-by-side renders, per-ad cost, and the four that we would not pay for again.",
    ),
    ("growthletter.co", "/ai-ugc-ads-what-actually-works"): (
        "AI UGC ads: what actually works after 2,000 tests — Growthletter",
        "A paid social lead publishes the hook shapes, run times and cost-per-purchase from two thousand AI-made creator-style ads across nine consumer brands.",
    ),
    ("growthletter.co", "/thirty-ai-video-ads-teardown"): (
        "I shipped 30 AI video ads in a week. Here is the teardown — Growthletter",
        "Every ad, every number, and the two that paid for the other twenty-eight. Includes the scripts, the spend split and what broke on day four.",
    ),
    ("growthletter.co", "/no-studio-no-crew"): (
        "No studio, no crew, no excuse: a video ad process for teams of one — Growthletter",
        "A week-by-week process for making video ads without a production budget, written for the marketer who is also the analyst and the copywriter.",
    ),
    ("thecreativeindex.com", "/ugc-video-tools"): (
        "UGC video tools directory — The Creative Index",
        "Ninety-two tools that make creator-style video ads, filtered by price, presenter licensing, language support and whether they will train on your footage.",
    ),
    ("thecreativeindex.com", "/no-studio-ad-tools"): (
        "Ad tools for brands without a studio — The Creative Index",
        "Software that replaces a shoot rather than scheduling one, grouped by what you already have: a product page, an hour of footage, or nothing at all.",
    ),
}

_RANKINGS = {
    "ai ugc ads": [
        ("vidora.ai", "/"),
        ("toolwatch.io", "/best-ai-ugc-ad-tools"),
        ("avatarly.com", "/"),
        ("reelforge.io", "/"),
        ("clipwise.io", "/"),
        ("hookmill.co", "/ugc"),
        ("growthletter.co", "/ai-ugc-ads-what-actually-works"),
        ("cutcraft.ai", "/"),
        (OUR_BRAND.domain, "/"),
        ("promptreel.com", "/"),
    ],
    "ugc video tool": [
        ("clipwise.io", "/"),
        ("vidora.ai", "/"),
        ("thecreativeindex.com", "/ugc-video-tools"),
        ("framewise.ai", "/"),
        ("reelforge.io", "/"),
        ("takeone.tools", "/"),
        ("avatarly.com", "/"),
        (OUR_BRAND.domain, "/ugc"),
        ("studioless.io", "/"),
        ("cutcraft.ai", "/"),
    ],
    "ai video ads": [
        ("reelforge.io", "/"),
        ("vidora.ai", "/"),
        ("toolwatch.io", "/ai-video-ad-makers"),
        ("clipwise.io", "/"),
        ("promptreel.com", "/"),
        ("avatarly.com", "/"),
        ("framewise.ai", "/"),
        ("growthletter.co", "/thirty-ai-video-ads-teardown"),
        ("studioless.io", "/"),
        (OUR_BRAND.domain, "/"),
    ],
    "ai ads without a studio": [
        ("studioless.io", "/"),
        (OUR_BRAND.domain, "/ai-ads-without-a-studio"),
        ("growthletter.co", "/no-studio-no-crew"),
        ("vidora.ai", "/how-it-works"),
        ("avatarly.com", "/how-it-works"),
        ("takeone.tools", "/"),
        ("hookmill.co", "/"),
        ("thecreativeindex.com", "/no-studio-ad-tools"),
        ("clipwise.io", "/how-it-works"),
        ("cutcraft.ai", "/"),
    ],
}


def _clip(text):
    if len(text) <= _SNIPPET_CHARS:
        return text
    return text[:_SNIPPET_CHARS].rsplit(" ", 1)[0] + " ..."


def _listing(domain, path):
    page = _WORLD_PAGES.get((domain, path))
    if page is not None:
        return page.title, _clip(page.paragraphs[0])
    return _OTHER_PAGES[(domain, path)]


def _displayed(domain, path):
    if path == "/":
        return f"https://{domain}"
    return f"https://{domain} › " + " › ".join(path.strip("/").split("/"))


def _organic(position, domain, path):
    title, snippet = _listing(domain, path)
    return {
        "position": position,
        "title": title,
        "link": f"https://{domain}{path}",
        "displayed_link": _displayed(domain, path),
        "snippet": snippet,
    }


def _parameters(engine, q, location, num):
    params = {
        "engine": engine,
        "q": q,
        "location_requested": location,
        "location_used": location,
        "google_domain": "google.com",
        "device": "desktop",
    }
    if num is not None:
        params["num"] = num
    return params


@router.get("/search")
async def search(
    request: Request,
    engine: str = Query(...),
    q: str = Query(...),
    location: str = Query(_DEFAULT_LOCATION),
    num: int = Query(None, ge=1, le=100),
):
    if not request.query_params.get("api_key"):
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"},
        )
    if engine != _ENGINE:
        return JSONResponse(status_code=400, content={"error": f"Unsupported `{engine}` engine."})
    ranked = _RANKINGS.get(q)
    if ranked is None:
        return {"error": "Google hasn't returned any results for this query."}
    results = [_organic(i + 1, domain, path) for i, (domain, path) in enumerate(ranked)]
    return {
        "search_metadata": {"status": "Success", "created_at": _CREATED_AT},
        "search_parameters": _parameters(engine, q, location, num),
        "organic_results": results[:num] if num else results,
    }
