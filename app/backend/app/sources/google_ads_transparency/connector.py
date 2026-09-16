from app.engine import spy
from app.sources.client import ConnectorError
from app.sources.creds import credentials_for
from app.sources.paginators import Paginator
from app.sources.util import client_for, pick_id, store_all, stored_ids

SOURCE = "google_ads_transparency"
READER = "chatgpt"

OBSERVED_AT = {"creatives": "creative.last_shown"}

MODEL = "openai/gpt-5.6-luna"
PROMPT = (
    "Read the advertisement in this image. Reply with only the words visible in "
    "the ad, headline first, in reading order. Reply NONE when there is no text."
)
PROMPT_VERSION = "2026-09-15.1"
READS_PER_PULL = 50
OPENROUTER_PATH = "/api/v1/chat/completions"
ADS_ENGINE = "google_ads_transparency_center"
PAGE_SIZE = 100
READABLE_FORMATS = ("text", "image")
KEYS_DISAGREE = (
    "OPENROUTER_API_KEY and SERPAPI_API_KEY must both be set or both unset — "
    "the ad text is read by OpenRouter"
)


class AdsPage(Paginator):
    def extract(self, data):
        creatives = data.get("ad_creatives") if isinstance(data, dict) else None
        return creatives if isinstance(creatives, list) else []

    def next_params(self, data, params):
        paging = data.get("serpapi_pagination") if isinstance(data, dict) else None
        token = paging.get("next_page_token") if isinstance(paging, dict) else None
        return {**params, "next_page_token": token} if token else None


_ADS = AdsPage()


def _creative_id(record):
    return pick_id(record["creative"], "ad_creative_id")


def _preview(creative):
    image = creative.get("image")
    if creative.get("format") in READABLE_FORMATS and isinstance(image, str):
        return image or None
    return None


def _previews(creatives):
    previews = {}
    for record in creatives:
        creative_id = _creative_id(record)
        if creative_id:
            image = _preview(record["creative"])
            if image:
                previews[creative_id] = image
    return previews


def _read_request(image):
    return {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": image}},
                ],
            }
        ],
    }


async def _read_texts(session, store, reader, creatives, notes):
    previews = _previews(creatives)
    already = await stored_ids(session, SOURCE, "creative_texts")
    fresh = [(cid, image) for cid, image in previews.items() if cid not in already]
    skipped = len(previews) - len(fresh)
    if skipped:
        notes["creative_texts_skipped"] = skipped
    if len(fresh) > READS_PER_PULL:
        notes["creative_texts_capped"] = len(fresh) - READS_PER_PULL
    reads = fresh[:READS_PER_PULL]
    for creative_id, image in reads:
        data = await reader.post(OPENROUTER_PATH, json=_read_request(image))
        await store(
            session,
            source=SOURCE,
            object_type="creative_texts",
            source_id=creative_id,
            raw_payload={
                "request": {
                    "creative_id": creative_id,
                    "image": image,
                    "model": MODEL,
                    "prompt_version": PROMPT_VERSION,
                },
                "response": data,
            },
        )
    if reads:
        notes["creative_texts_read"] = len(reads)


async def pull(session, store):
    api = client_for(SOURCE)
    reader = client_for(READER)
    if credentials_for(SOURCE).real != credentials_for(READER).real:
        raise ConnectorError(SOURCE, KEYS_DISAGREE)
    notes: dict = {}
    creatives = []
    for company in spy.definition().competitors:
        advertiser_id = company.google_advertiser_id
        if not advertiser_id:
            continue
        page = await api.get(
            "/search.json",
            params={
                "engine": ADS_ENGINE,
                "advertiser_id": advertiser_id,
                "num": PAGE_SIZE,
            },
            paginate=_ADS,
        )
        creatives += [
            {
                "request": {"company": company.name, "advertiser_id": advertiser_id},
                "creative": item,
            }
            for item in page
        ]
    await store_all(
        session,
        store,
        creatives,
        source=SOURCE,
        object_type="creatives",
        id_of=_creative_id,
        notes=notes,
    )
    await _read_texts(session, store, reader, creatives, notes)
    return notes or None
