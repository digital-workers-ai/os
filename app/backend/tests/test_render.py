import base64
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.config import settings
from app.llm import paint as llm_paint
from app.render import image
from app.render.client import SIZES, Painter, Render, RenderError

PNG = b"\x89PNG\r\n\x1a\nfake"
STAT = {
    "stat": "27",
    "label": "tools, one connector each",
    "support": "Every record kept as it arrived.",
}
CAROUSEL = {
    "cover": {"title": "Where a number comes from", "kicker": "Three facts"},
    "slides": [{"title": f"Fact {n}", "body": "A body."} for n in (1, 2, 3)],
    "closing": {"title": "Open source", "cta": "Read the code"},
}


class FakeShot:
    def __init__(self, status=200, body=PNG, raises=None):
        self.status, self.body, self.raises = status, body, raises
        self.posts = []

    async def post(self, url, json):
        self.posts.append((url, json))
        if self.raises:
            raise self.raises
        return SimpleNamespace(
            status_code=self.status, content=self.body, text=self.body.decode("latin1")
        )


class FakePaint:
    def __init__(self, data=None, raises=None):
        self.data, self.raises = data, raises
        self.calls = []
        self.images = self

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return SimpleNamespace(data=self.data)


def _painted(png=PNG):
    return [SimpleNamespace(b64_json=base64.b64encode(png).decode())]


class TestRender:
    async def test_the_html_and_frame_go_to_the_render_service(self, monkeypatch):
        monkeypatch.setattr(settings, "RENDER_URL", "http://render:8200")
        shot = FakeShot()
        png = await Render(shot).shot("<html></html>", 1080, 1350)
        assert png == PNG
        assert shot.posts == [
            (
                "http://render:8200/shot",
                {"html": "<html></html>", "width": 1080, "height": 1350},
            )
        ]

    async def test_a_non_200_answer_is_a_render_error_with_the_body(self):
        shot = FakeShot(status=500, body=b"chromium crashed " + b"x" * 300)
        with pytest.raises(RenderError) as caught:
            await Render(shot).shot("<html></html>", 1080, 1080)
        assert "500" in str(caught.value)
        assert "chromium crashed" in str(caught.value)
        assert len(str(caught.value)) < 300

    async def test_a_transport_failure_is_a_render_error(self):
        shot = FakeShot(raises=httpx.ConnectError("render is down"))
        with pytest.raises(RenderError, match="render is down"):
            await Render(shot).shot("<html></html>", 1080, 1080)

    def test_the_default_client_waits_two_minutes(self):
        client = Render().client
        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout.read == 120


class TestPainter:
    def test_the_sizes_are_the_four_ratios_the_model_accepts(self):
        assert SIZES == {
            "1:1": "1024x1024",
            "4:5": "1024x1280",
            "9:16": "1024x1824",
            "16:9": "1824x1024",
        }

    async def test_the_picture_is_decoded_from_the_first_result(self, monkeypatch):
        monkeypatch.setattr(settings, "PAINT_MODEL", "gpt-image-test")
        paint = FakePaint(_painted())
        png = await Painter(paint).picture("a quiet harbour", "4:5")
        assert png == PNG
        assert paint.calls == [
            {
                "model": "gpt-image-test",
                "prompt": "a quiet harbour",
                "size": "1024x1280",
                "n": 1,
            }
        ]

    async def test_a_ratio_outside_the_sizes_is_refused_before_the_call(self):
        paint = FakePaint(_painted())
        with pytest.raises(RenderError, match="3:2"):
            await Painter(paint).picture("a harbour", "3:2")
        assert paint.calls == []

    @pytest.mark.parametrize("data", [None, [], [SimpleNamespace(b64_json=None)]])
    async def test_an_answer_with_no_picture_is_a_render_error(self, data):
        with pytest.raises(RenderError, match="no picture"):
            await Painter(FakePaint(data)).picture("a harbour", "1:1")

    async def test_an_sdk_error_is_a_render_error(self):
        paint = FakePaint(raises=openai.OpenAIError("quota"))
        with pytest.raises(RenderError, match="quota"):
            await Painter(paint).picture("a harbour", "1:1")

    async def test_a_missing_key_is_refused_by_name(self):
        with pytest.raises(RenderError, match="OPENAI_API_KEY"):
            await Painter().picture("a harbour", "1:1")

    async def test_with_a_key_and_no_client_the_llm_module_supplies_one(
        self, monkeypatch
    ):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        paint = FakePaint(_painted())
        monkeypatch.setattr(llm_paint, "client", lambda: paint)
        assert await Painter().picture("a harbour", "1:1") == PNG


class TestFit:
    def test_every_slot_within_its_max_comes_back(self):
        assert image.fit("stat-card", STAT) == STAT

    def test_a_carousel_part_is_fitted_against_its_own_slots(self):
        assert image.fit("carousel", CAROUSEL["cover"], "cover") == CAROUSEL["cover"]

    def test_an_unknown_slot_is_named(self):
        with pytest.raises(RenderError, match="'headline'"):
            image.fit("stat-card", {**STAT, "headline": "x"})

    def test_a_missing_slot_is_named(self):
        with pytest.raises(RenderError, match="'support'"):
            image.fit("stat-card", {"stat": "27", "label": "tools"})

    @pytest.mark.parametrize("value", ["", "   ", 27, None])
    def test_a_slot_without_text_is_missing(self, value):
        with pytest.raises(RenderError, match="'stat'"):
            image.fit("stat-card", {**STAT, "stat": value})

    def test_a_slot_over_its_max_names_the_count(self):
        with pytest.raises(RenderError) as caught:
            image.fit("stat-card", {**STAT, "label": "x" * 31})
        assert "'label'" in str(caught.value)
        assert "31" in str(caught.value)
        assert "28" in str(caught.value)

    def test_content_that_is_not_a_mapping_is_refused(self):
        with pytest.raises(RenderError, match="mapping"):
            image.fit("stat-card", ["27"])


class TestAssetsUri:
    def test_fonts_and_logo_are_data_uris(self):
        assets = image.assets_uri()
        assert set(assets) == {"fonts", "logo"}
        assert set(assets["fonts"]) == {"sans", "display"}
        for uri in assets["fonts"].values():
            assert uri.startswith("data:font/woff2;base64,")
        assert assets["logo"].startswith("data:image/svg+xml;base64,")
        encoded = assets["logo"].split(",", 1)[1]
        assert base64.b64decode(encoded).startswith(b"<")


class TestHtml:
    def test_the_card_carries_the_slots_the_frame_and_the_tokens(self):
        html = image.html("stat-card", STAT, "4:5", None)
        assert "tools, one connector each" in html
        assert "width: 1080px" in html and "height: 1350px" in html
        assert "#FD4E00" in html
        assert "data:font/woff2;base64," in html
        assert "data:image/svg+xml;base64," in html
        assert "data:image/png" not in html

    def test_a_picture_becomes_a_png_data_uri(self):
        html = image.html("stat-card", STAT, "1:1", PNG)
        assert f"data:image/png;base64,{base64.b64encode(PNG).decode()}" in html

    def test_slot_text_is_escaped(self):
        html = image.html("stat-card", {**STAT, "label": "<b>bold</b>"}, "1:1", None)
        assert "<b>bold</b>" not in html
        assert "&lt;b&gt;bold&lt;/b&gt;" in html

    def test_a_carousel_part_renders_its_own_template_with_its_page(self):
        html = image.html("carousel", CAROUSEL["slides"][0], "4:5", None, "slide", 2, 5)
        assert "carousel slide" in html
        assert "2 / 5" in html
        assert "Fact 1" in html

    def test_a_missing_variable_is_an_error_not_an_empty_string(self):
        with pytest.raises(Exception, match="undefined"):
            image.html("carousel", CAROUSEL["cover"], "4:5", None, "cover")


class TestRenderImage:
    async def test_the_card_is_shot_at_the_ratio_frame(self):
        shot = FakeShot()
        png = await image.render("stat-card", STAT, "16:9", None, Render(shot))
        assert png == PNG
        [(_url, body)] = shot.posts
        assert (body["width"], body["height"]) == (1920, 1080)
        assert "tools, one connector each" in body["html"]

    async def test_the_picture_goes_under_the_card(self):
        shot = FakeShot()
        await image.render("stat-card", STAT, "1:1", PNG, Render(shot))
        assert "data:image/png;base64," in shot.posts[0][1]["html"]

    async def test_a_ratio_the_look_does_not_render_is_refused(self):
        shot = FakeShot()
        with pytest.raises(RenderError, match="16:9"):
            await image.render_slides("carousel", CAROUSEL, "16:9", Render(shot))
        assert shot.posts == []

    async def test_a_bad_slot_is_refused_before_anything_is_shot(self):
        shot = FakeShot()
        with pytest.raises(RenderError, match="'label'"):
            await image.render(
                "stat-card", {**STAT, "label": "x" * 40}, "1:1", None, Render(shot)
            )
        assert shot.posts == []


class TestRenderSlides:
    async def test_every_page_is_shot_in_order_and_numbered(self):
        shot = FakeShot()
        pages = await image.render_slides("carousel", CAROUSEL, "4:5", Render(shot))
        assert pages == [PNG] * 5
        bodies = [body["html"] for _url, body in shot.posts]
        assert "carousel cover" in bodies[0]
        assert "carousel closing" in bodies[-1]
        assert all("carousel slide" in body for body in bodies[1:-1])
        assert "2 / 5" in bodies[1]
        assert "5 / 5" in bodies[4]
        assert all(body["width"] == 1080 for _url, body in shot.posts)
        assert all(body["height"] == 1350 for _url, body in shot.posts)

    @pytest.mark.parametrize("count", [2, 11])
    async def test_a_slide_count_outside_the_look_is_refused(self, count):
        content = {**CAROUSEL, "slides": [CAROUSEL["slides"][0]] * count}
        with pytest.raises(RenderError) as caught:
            await image.render_slides("carousel", content, "4:5", Render(FakeShot()))
        assert str(count) in str(caught.value)
        assert "3" in str(caught.value) and "10" in str(caught.value)

    async def test_slides_that_are_not_a_list_are_refused(self):
        content = {**CAROUSEL, "slides": "three"}
        with pytest.raises(RenderError, match="slides"):
            await image.render_slides("carousel", content, "4:5", Render(FakeShot()))

    async def test_content_that_is_not_a_mapping_is_refused(self):
        with pytest.raises(RenderError, match="mapping"):
            await image.render_slides("carousel", [], "4:5", Render(FakeShot()))

    async def test_an_image_look_has_no_slides(self):
        with pytest.raises(RenderError, match="carousel"):
            await image.render_slides("stat-card", CAROUSEL, "1:1", Render(FakeShot()))

    async def test_a_bad_slot_names_the_part(self):
        content = {**CAROUSEL, "closing": {"title": "Open source", "cta": "x" * 41}}
        with pytest.raises(RenderError) as caught:
            await image.render_slides("carousel", content, "4:5", Render(FakeShot()))
        assert "closing" in str(caught.value)
        assert "'cta'" in str(caught.value)
