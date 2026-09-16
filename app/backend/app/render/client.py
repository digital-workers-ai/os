import base64
import os

import httpx
import openai

from app.config import settings

SIZES = {
    "1:1": "1024x1024",
    "4:5": "1024x1280",
    "9:16": "1024x1824",
    "16:9": "1824x1024",
}
TIMEOUT = 120
KEY_ENV = "OPENAI_API_KEY"
BODY_CHARS = 200


class RenderError(RuntimeError):
    pass


class Render:
    def __init__(self, client=None):
        self.client = client or httpx.AsyncClient(timeout=TIMEOUT)

    async def shot(self, html: str, width: int, height: int) -> bytes:
        try:
            response = await self.client.post(
                f"{settings.RENDER_URL}/shot",
                json={"html": html, "width": width, "height": height},
            )
        except httpx.HTTPError as exc:
            raise RenderError(f"render service: {type(exc).__name__}: {exc}") from exc
        if response.status_code != 200:
            raise RenderError(
                f"render service answered {response.status_code}: "
                f"{response.text[:BODY_CHARS]}"
            )
        return response.content


def _painter_client():
    if not os.environ.get(KEY_ENV):
        raise RenderError(
            f"{KEY_ENV} is not set, and image.paint calls the painter with it"
        )
    return openai.AsyncOpenAI()


class Painter:
    def __init__(self, client=None):
        self.client = client

    async def picture(self, prompt: str, ratio: str) -> bytes:
        if ratio not in SIZES:
            raise RenderError(f"ratio {ratio!r} is not one of {list(SIZES)}")
        client = self.client or _painter_client()
        try:
            response = await client.images.generate(
                model=settings.PAINT_MODEL, prompt=prompt, size=SIZES[ratio], n=1
            )
        except openai.OpenAIError as exc:
            raise RenderError(f"painter: {type(exc).__name__}: {exc}") from exc
        data = response.data or []
        if not data or not data[0].b64_json:
            raise RenderError("the painter answered with no picture")
        return base64.b64decode(data[0].b64_json)
