import asyncio
import base64
import json
import os
import subprocess
from importlib import import_module
from pathlib import Path

import httpx

from app.config import (
    DEEPGRAM_CREDENTIAL_ENV,
    HEYGEN_CREDENTIAL_ENV,
    PAINT_CREDENTIAL_ENV,
    settings,
)

HEYGEN_BASE = "https://api.heygen.com"
DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"
DEEPGRAM_PARAMS = {
    "model": "nova-2",
    "smart_format": "true",
    "punctuate": "true",
    "utterances": "false",
}
POLL_INTERVAL = 10.0
POLL_TIMEOUT = 600.0
DONE = ("completed", "success")
BROKEN = ("failed", "error")
PLAYWRIGHT_MODULE = "playwright.sync_api"
SETTLE_MS = 2500
FRAMES_PACKAGE = "hyperframes@0.6.6"
FRAMES_CONFIG = "hyperframes.json"
FRAMES_SETTINGS = {
    "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
    "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
    "paths": {
        "blocks": "compositions",
        "components": "compositions/components",
        "assets": "assets",
    },
}
FRAMES_TIMEOUT = 1800
RENDERS = "renders"

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


def _refuse(response) -> None:
    if response.status_code >= 400:
        raise RenderError(f"{response.status_code}: {response.text[:300]}")


class HeyGen:
    def __init__(self, key=None, transport=None):
        self.key = key or credential(HEYGEN_CREDENTIAL_ENV)
        self._transport = transport

    def _session(self, read=600.0):
        return httpx.AsyncClient(
            transport=self._transport,
            timeout=httpx.Timeout(30, read=read),
            headers={"X-Api-Key": self.key, "Content-Type": "application/json"},
        )

    async def slots(self, template_id: str) -> list[tuple[str, str]]:
        async with self._session() as session:
            response = await session.get(f"{HEYGEN_BASE}/v3/templates/{template_id}")
        _refuse(response)
        found: list[tuple[str, str]] = []
        for position, scene in enumerate(response.json()["data"].get("scenes", [])):
            named = [
                variable["name"]
                for variable in scene.get("variables", [])
                if variable.get("variable_type") == "text"
            ]
            if not named:
                continue
            preferred = f"script_{position + 1}"
            found.append(
                (scene["scene_id"], preferred if preferred in named else named[0])
            )
        return found

    async def start(
        self, template_id: str, scene_id: str, script: str, variable: str
    ) -> str:
        async with self._session() as session:
            response = await session.post(
                f"{HEYGEN_BASE}/v3/templates/{template_id}",
                json={
                    "variables": {variable: {"type": "text", "content": script}},
                    "scene_ids": [scene_id],
                },
            )
        _refuse(response)
        return response.json()["data"]["id"]

    async def wait(
        self, video_id: str, *, interval=POLL_INTERVAL, timeout=POLL_TIMEOUT
    ) -> dict:
        elapsed = 0.0
        while True:
            async with self._session() as session:
                response = await session.get(f"{HEYGEN_BASE}/v3/videos/{video_id}")
            _refuse(response)
            data = response.json()["data"]
            status = data.get("status")
            if status in DONE:
                return data
            if status in BROKEN:
                raise RenderError(
                    f"HeyGen refused {video_id}: {data.get('error') or status}"
                )
            if elapsed >= timeout:
                raise RenderError(f"HeyGen timed out on {video_id} after {timeout}s")
            await asyncio.sleep(interval)
            elapsed += interval

    async def speak(self, voice_id: str, script: str) -> dict:
        async with self._session() as session:
            response = await session.post(
                f"{HEYGEN_BASE}/v3/voices/speech",
                json={"text": script, "voice_id": voice_id},
            )
        _refuse(response)
        return response.json()["data"]

    async def fetch(self, url: str, dest: Path) -> Path:
        async with self._session() as session:
            response = await session.get(url)
        _refuse(response)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return dest


class Deepgram:
    def __init__(self, key=None, transport=None):
        self.key = key or credential(DEEPGRAM_CREDENTIAL_ENV)
        self._transport = transport

    async def listen(self, audio: bytes) -> dict:
        async with httpx.AsyncClient(transport=self._transport, timeout=120) as session:
            response = await session.post(
                DEEPGRAM_URL,
                headers={
                    "Authorization": f"Token {self.key}",
                    "Content-Type": "audio/mp4",
                },
                params=DEEPGRAM_PARAMS,
                content=audio,
            )
        _refuse(response)
        heard = response.json()["results"]["channels"][0]["alternatives"][0]
        return {
            "words": [
                {
                    "word": word["word"],
                    "start": round(word["start"], 3),
                    "end": round(word["end"], 3),
                }
                for word in heard.get("words", [])
            ],
            "text": heard.get("transcript", "").strip(),
        }


class Frames:
    def __init__(self, runner=None):
        self._run = runner or subprocess.run

    def export(self, project_dir: Path, name: str) -> Path:
        config = project_dir / FRAMES_CONFIG
        if not config.exists():
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(json.dumps(FRAMES_SETTINGS, indent=2))
        dest = project_dir / RENDERS / name
        result = self._run(
            [
                "npx",
                "--yes",
                FRAMES_PACKAGE,
                "render",
                ".",
                "-o",
                str(Path(RENDERS) / name),
                "--quiet",
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=FRAMES_TIMEOUT,
        )
        if result.returncode != 0:
            raise RenderError(f"the frame exporter failed: {result.stderr[-600:]}")
        if not dest.exists():
            raise RenderError(
                f"the frame exporter reported success and wrote no {name}"
            )
        return dest


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
