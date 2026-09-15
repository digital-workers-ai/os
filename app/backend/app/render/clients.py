import base64
import os
from importlib import import_module
from pathlib import Path

from app.config import PAINT_CREDENTIAL_ENV, settings

PLAYWRIGHT_MODULE = "playwright.sync_api"
SETTLE_MS = 2500

OVERFLOW_SCAN = """(FRAME) => {
  const findings = [];
  document.querySelectorAll('.preview-card, .clip, body').forEach(root => {
    const card = root.closest('.preview-card');
    const scale = card ? FRAME / card.getBoundingClientRect().width : 1;
    const label = card
      ? card.querySelector('.preview-label')?.textContent.trim()
      : root.id || 'frame';
    root.querySelectorAll('*').forEach(el => {
      if (el.children.length) return;
      const text = el.textContent.trim();
      if (!text) return;
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return;
      const rng = document.createRange();
      rng.selectNodeContents(el);
      const rects = [...rng.getClientRects()];
      if (!rects.length) return;
      const textW = Math.max(...rects.map(x => x.width)) * scale;
      let box = el.parentElement, avail = 0, inset = 0;
      while (box && box !== root) {
        const bs = getComputedStyle(box);
        if (['block', 'flex', 'grid', 'inline-block'].includes(bs.display)) {
          const padX = parseFloat(bs.paddingLeft) + parseFloat(bs.paddingRight);
          const w = box.getBoundingClientRect().width - padX;
          let widest = 0;
          for (const kid of box.children) {
            widest = Math.max(widest, kid.getBoundingClientRect().width);
          }
          if (widest && w <= widest + 1) {
            inset += padX; box = box.parentElement; continue;
          }
          if ((w - inset) * scale > 40) { avail = (w - inset) * scale; break; }
        }
        box = box.parentElement;
      }
      if (!avail) avail = FRAME;
      if (textW > avail + 1) {
        findings.push({
          scene: label, cls: el.className || el.tagName.toLowerCase(),
          text: text.slice(0, 60), chars: text.length,
          width: Math.round(textW), available: Math.round(avail),
          over: Math.round(textW - avail),
        });
      }
    });
  });
  return findings;
}"""


class RenderError(RuntimeError):
    pass


def credential(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RenderError(
            f"{name} is not set — a render that quietly skipped the call would "
            "hand back a file nobody could tell from a finished one"
        )
    return value


class Painter:
    def __init__(self, client=None):
        self._client = client or self._openai()

    def _openai(self):
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=credential(PAINT_CREDENTIAL_ENV))

    async def background(self, prompt: str, *, width: int, height: int) -> bytes:
        try:
            response = await self._client.images.generate(
                model=settings.IMAGE_MODEL,
                prompt=prompt,
                size=f"{width}x{height}",
                n=1,
            )
        except Exception as exc:
            raise RenderError(f"{type(exc).__name__}: {exc}") from exc
        if not response.data:
            raise RenderError(
                f"{settings.IMAGE_MODEL} returned no image for {prompt!r}"
            )
        return base64.b64decode(response.data[0].b64_json)


def _sync_playwright():
    try:
        return import_module(PLAYWRIGHT_MODULE).sync_playwright
    except ImportError as exc:
        raise RenderError(
            "this image carries no headless browser, so nothing can be "
            f"screenshotted or measured here ({PLAYWRIGHT_MODULE})"
        ) from exc


class Browser:
    def __init__(self, playwright=None):
        self._playwright = playwright or _sync_playwright()

    def _page(self, driver, url, width, height):
        engine = driver.chromium.launch()
        page = engine.new_page(viewport={"width": width, "height": height})
        page.goto(url)
        page.wait_for_timeout(SETTLE_MS)
        return engine, page

    def shot(self, url: str, dest: Path, *, width: int, height: int) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._playwright() as driver:
                engine, page = self._page(driver, url, width, height)
                page.screenshot(path=str(dest))
                engine.close()
        except Exception as exc:
            raise RenderError(f"{type(exc).__name__}: {exc}") from exc
        return dest

    def measure(self, url: str, *, frame_width: int) -> list[dict]:
        try:
            with self._playwright() as driver:
                engine, page = self._page(driver, url, frame_width, frame_width)
                findings = page.evaluate(OVERFLOW_SCAN, frame_width)
                engine.close()
        except Exception as exc:
            raise RenderError(f"{type(exc).__name__}: {exc}") from exc
        return findings
