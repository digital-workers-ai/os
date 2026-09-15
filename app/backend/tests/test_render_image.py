import sys
import types

import pytest
import yaml

from app.render import browser, clients, image

FRAME = (1080, 1080)

MANIFEST = {
    "name": "card",
    "medium": "image",
    "ratio": "1:1",
    "slots": [{"name": "stat", "max": 6}, {"name": "label", "max": 12}],
    "limits_measured": "2026-09-01",
    "build": "one background call",
}

CARD = """<html><body>
<div class="stat">{{ slots.stat }}</div>
<div class="label">{{ slots.label }}</div>
<div class="ground" data-width="{{ width }}" data-bg="{{ background or '' }}"></div>
</body></html>"""

CONTENT = {"stat": "29", "label": "ads live"}


@pytest.fixture
def looks_dir(tmp_path):
    directory = tmp_path / "looks" / "card"
    directory.mkdir(parents=True)
    (directory / "look.yaml").write_text(yaml.safe_dump(MANIFEST))
    (directory / "card.html.j2").write_text(CARD)
    (directory / "content.yaml").write_text(yaml.safe_dump(CONTENT))
    return tmp_path / "looks"


class FakeBrowser:
    def __init__(self, findings=()):
        self.shots: list[tuple] = []
        self.measured: list[tuple] = []
        self.findings = list(findings)

    def shot(self, url, dest, *, width, height):
        self.shots.append((url, width, height))
        dest.write_bytes(b"png")
        return dest

    def measure(self, url, *, frame_width):
        self.measured.append((url, frame_width))
        return self.findings


class FakePainter:
    def __init__(self, data=b"jpeg"):
        self.data = data
        self.asked: list[tuple] = []

    async def background(self, prompt, *, width, height):
        self.asked.append((prompt, width, height))
        return self.data


class TestTheLimitsAreEnforcedFirst:
    async def test_a_slot_over_its_limit_never_reaches_the_browser(
        self, looks_dir, tmp_path
    ):
        agent = FakeBrowser()
        with pytest.raises(clients.RenderError) as caught:
            await image.render(
                "card",
                {**CONTENT, "label": "far too long for the card"},
                tmp_path / "out",
                draft=True,
                looks_dir=looks_dir,
                browser=agent,
            )
        assert "label" in str(caught.value)
        assert agent.shots == []

    async def test_a_slot_the_look_never_declared_is_refused(self, looks_dir, tmp_path):
        with pytest.raises(clients.RenderError) as caught:
            await image.render(
                "card",
                {**CONTENT, "footnote": "extra"},
                tmp_path / "out",
                draft=True,
                looks_dir=looks_dir,
                browser=FakeBrowser(),
            )
        assert "footnote" in str(caught.value)

    async def test_a_slot_the_look_needs_and_nobody_wrote_is_refused(
        self, looks_dir, tmp_path
    ):
        with pytest.raises(clients.RenderError) as caught:
            await image.render(
                "card",
                {"stat": "29"},
                tmp_path / "out",
                draft=True,
                looks_dir=looks_dir,
                browser=FakeBrowser(),
            )
        assert "label" in str(caught.value)


class TestDraftMode:
    async def test_a_draft_renders_small_and_flat(self, looks_dir, tmp_path):
        agent = FakeBrowser()
        out = tmp_path / "out"
        png = await image.render(
            "card", CONTENT, out, draft=True, looks_dir=looks_dir, browser=agent
        )
        assert png == out / image.PNG
        assert png.read_bytes() == b"png"
        _url, width, height = agent.shots[0]
        assert (width, height) == (
            int(FRAME[0] * image.DRAFT_SCALE),
            int(FRAME[1] * image.DRAFT_SCALE),
        )

    async def test_a_draft_never_asks_the_image_model_for_a_ground(
        self, looks_dir, tmp_path
    ):
        painter = FakePainter()
        await image.render(
            "card",
            {**CONTENT, "background_prompt": "a warm studio wall"},
            tmp_path / "out",
            draft=True,
            looks_dir=looks_dir,
            browser=FakeBrowser(),
            painter=painter,
        )
        assert painter.asked == []

    async def test_the_copy_is_html_and_the_markup_says_so(self, looks_dir, tmp_path):
        out = tmp_path / "out"
        await image.render(
            "card", CONTENT, out, draft=True, looks_dir=looks_dir, browser=FakeBrowser()
        )
        markup = (out / image.HTML).read_text()
        assert ">29<" in markup
        assert ">ads live<" in markup


class TestBuildMode:
    async def test_a_build_renders_at_the_looks_own_size(self, looks_dir, tmp_path):
        agent = FakeBrowser()
        await image.render(
            "card", CONTENT, tmp_path / "out", draft=False, looks_dir=looks_dir,
            browser=agent,
        )
        assert agent.shots[0][1:] == FRAME

    async def test_a_named_ground_is_generated_and_referenced(self, looks_dir, tmp_path):
        painter = FakePainter()
        out = tmp_path / "out"
        await image.render(
            "card",
            {**CONTENT, "background_prompt": "a warm studio wall"},
            out,
            draft=False,
            looks_dir=looks_dir,
            browser=FakeBrowser(),
            painter=painter,
        )
        assert painter.asked == [("a warm studio wall", *FRAME)]
        assert (out / image.BACKGROUND).read_bytes() == b"jpeg"
        assert image.BACKGROUND in (out / image.HTML).read_text()

    async def test_a_build_with_no_prompt_keeps_the_flat_ground(
        self, looks_dir, tmp_path
    ):
        painter = FakePainter()
        out = tmp_path / "out"
        await image.render(
            "card", CONTENT, out, draft=False, looks_dir=looks_dir,
            browser=FakeBrowser(), painter=painter,
        )
        assert painter.asked == []
        assert 'data-bg=""' in (out / image.HTML).read_text()

    async def test_each_stage_is_reported_as_it_runs(self, looks_dir, tmp_path):
        seen: list[str] = []
        await image.render(
            "card",
            {**CONTENT, "background_prompt": "a wall"},
            tmp_path / "out",
            draft=False,
            looks_dir=looks_dir,
            browser=FakeBrowser(),
            painter=FakePainter(),
            progress=seen.append,
        )
        assert seen == list(image.STAGES)


class TestTheOverflowMeasurement:
    def test_copy_that_fits_measures_clean(self, tmp_path):
        page = tmp_path / "card.html"
        page.write_text("<p>short</p>")
        assert browser.overflow(page, frame_width=1080, client=FakeBrowser()) == []

    def test_copy_that_does_not_fit_comes_back_as_findings(self, tmp_path):
        page = tmp_path / "card.html"
        page.write_text("<p>long</p>")
        finding = {
            "scene": "card",
            "cls": "label",
            "text": "far too long",
            "chars": 12,
            "width": 980,
            "available": 800,
            "over": 180,
        }
        agent = FakeBrowser([finding])
        assert browser.overflow(page, frame_width=1080, client=agent) == [finding]
        assert agent.measured[0][1] == 1080

    def test_findings_are_described_one_line_each(self):
        finding = {
            "scene": "card",
            "cls": "label",
            "text": "far too long",
            "chars": 12,
            "width": 980,
            "available": 800,
            "over": 180,
        }
        described = browser.describe([finding])
        assert "label" in described
        assert "180px over" in described

    def test_an_overflow_refusal_carries_its_findings(self, tmp_path):
        page = tmp_path / "card.html"
        page.write_text("<p>long</p>")
        finding = {
            "scene": "card",
            "cls": "label",
            "text": "far too long",
            "chars": 12,
            "width": 980,
            "available": 800,
            "over": 180,
        }
        with pytest.raises(browser.OverflowError) as caught:
            browser.refuse_overflow(page, frame_width=1080, client=FakeBrowser([finding]))
        assert caught.value.findings == [finding]
        assert "label" in str(caught.value)

    def test_copy_that_fits_is_not_refused(self, tmp_path):
        page = tmp_path / "card.html"
        page.write_text("<p>short</p>")
        assert (
            browser.refuse_overflow(page, frame_width=1080, client=FakeBrowser())
            is None
        )

    def test_a_screenshot_writes_the_file_the_caller_named(self, tmp_path):
        page = tmp_path / "card.html"
        page.write_text("<p>short</p>")
        dest = tmp_path / "card.png"
        assert (
            browser.screenshot(page, dest, width=10, height=10, client=FakeBrowser())
            == dest
        )
        assert dest.read_bytes() == b"png"


class FakePage:
    def __init__(self, recorder):
        self.recorder = recorder

    def goto(self, url, **kw):
        self.recorder["url"] = url

    def wait_for_timeout(self, ms):
        self.recorder["settled"] = ms

    def screenshot(self, path):
        self.recorder["shot"] = path
        open(path, "wb").write(b"png")

    def evaluate(self, expression, arg):
        self.recorder["evaluated"] = (expression, arg)
        return self.recorder["findings"]


class FakeChromium:
    def __init__(self, recorder):
        self.recorder = recorder

    def launch(self, **kw):
        self.recorder["launched"] = True
        return self

    def new_page(self, **kw):
        self.recorder["viewport"] = kw.get("viewport")
        return FakePage(self.recorder)

    def close(self):
        self.recorder["closed"] = True


class FakePlaywright:
    def __init__(self, recorder):
        self.chromium = FakeChromium(recorder)
        self.recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def playwright(monkeypatch):
    recorder: dict = {"findings": []}
    module = types.ModuleType("fake_playwright")
    module.sync_playwright = lambda: FakePlaywright(recorder)
    monkeypatch.setitem(sys.modules, "fake_playwright", module)
    monkeypatch.setattr(clients, "PLAYWRIGHT_MODULE", "fake_playwright")
    return recorder


class TestTheBrowserSeam:
    def test_an_image_with_no_browser_in_it_refuses_rather_than_passes(
        self, monkeypatch
    ):
        monkeypatch.setattr(clients, "PLAYWRIGHT_MODULE", "no_browser_here")
        with pytest.raises(clients.RenderError) as caught:
            clients.Browser()
        assert "browser" in str(caught.value)

    def test_a_shot_opens_the_page_at_the_size_it_was_given(self, playwright, tmp_path):
        page = tmp_path / "card.html"
        page.write_text("<p>hi</p>")
        dest = tmp_path / "card.png"
        assert clients.Browser().shot(page.as_uri(), dest, width=800, height=600) == dest
        assert playwright["viewport"] == {"width": 800, "height": 600}
        assert playwright["url"] == page.as_uri()
        assert playwright["closed"] is True

    def test_a_measurement_runs_the_scan_in_the_page(self, playwright, tmp_path):
        playwright["findings"] = [{"cls": "label", "over": 12}]
        page = tmp_path / "card.html"
        page.write_text("<p>hi</p>")
        found = clients.Browser().measure(page.as_uri(), frame_width=1080)
        assert found == [{"cls": "label", "over": 12}]
        assert playwright["evaluated"][1] == 1080

    def test_a_browser_that_falls_over_is_one_render_error(self, tmp_path):
        def explode():
            raise RuntimeError("chromium died")

        agent = clients.Browser(playwright=explode)
        with pytest.raises(clients.RenderError) as caught:
            agent.shot("about:blank", tmp_path / "card.png", width=10, height=10)
        assert "chromium died" in str(caught.value)

    def test_a_measurement_that_falls_over_is_one_render_error(self):
        def explode():
            raise RuntimeError("chromium died")

        with pytest.raises(clients.RenderError):
            clients.Browser(playwright=explode).measure("about:blank", frame_width=1080)


class FakeImageResponse:
    def __init__(self, encoded):
        self.data = [types.SimpleNamespace(b64_json=encoded)] if encoded else []


class FakeOpenAI:
    def __init__(self, encoded, error=None):
        self.encoded = encoded
        self.error = error
        self.asked: list[dict] = []
        self.images = types.SimpleNamespace(generate=self._generate)

    async def _generate(self, **kw):
        self.asked.append(kw)
        if self.error:
            raise self.error
        return FakeImageResponse(self.encoded)


class TestTheImageModelSeam:
    async def test_a_ground_comes_back_as_bytes(self, monkeypatch):
        import base64

        encoded = base64.b64encode(b"pixels").decode()
        fake = FakeOpenAI(encoded)
        painter = clients.Painter(client=fake)
        assert await painter.background("a wall", width=1080, height=1080) == b"pixels"
        assert fake.asked[0]["size"] == "1080x1080"

    async def test_a_model_that_refuses_is_one_render_error(self):
        painter = clients.Painter(client=FakeOpenAI("", error=RuntimeError("over quota")))
        with pytest.raises(clients.RenderError) as caught:
            await painter.background("a wall", width=1080, height=1080)
        assert "over quota" in str(caught.value)

    async def test_an_empty_answer_is_one_render_error(self):
        fake = FakeOpenAI(None)
        painter = clients.Painter(client=fake)
        with pytest.raises(clients.RenderError) as caught:
            await painter.background("a wall", width=1080, height=1080)
        assert "no image" in str(caught.value)

    def test_no_key_is_a_refusal_rather_than_a_silent_skip(self, monkeypatch):
        monkeypatch.delenv(clients.PAINT_CREDENTIAL_ENV, raising=False)
        with pytest.raises(clients.RenderError) as caught:
            clients.Painter()
        assert clients.PAINT_CREDENTIAL_ENV in str(caught.value)
