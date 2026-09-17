import pytest

from app import media
from app.config import settings


@pytest.fixture(autouse=True)
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
    return tmp_path


class TestRelative:
    @pytest.mark.parametrize(
        "path", ["post.md", "slides/slide-01.png", "a.b_c-d/e", "9", "a..b"]
    )
    def test_a_plain_path_comes_back_as_given(self, path):
        assert media.relative(path) == path

    @pytest.mark.parametrize(
        "path",
        [
            "",
            "/post.md",
            "post.md/",
            "a//b",
            ".hidden",
            "-dash",
            "_under",
            "a b",
            "a\\b",
            "post.md\x00",
            "post.md\n",
            "café.md",
        ],
    )
    def test_a_segment_outside_the_alphabet_is_refused(self, path):
        with pytest.raises(media.MediaError, match="segment"):
            media.relative(path)

    @pytest.mark.parametrize("path", ["..", "../post.md", "a/../b", "a/.."])
    def test_a_climb_is_refused(self, path):
        with pytest.raises(media.MediaError, match="climbs"):
            media.relative(path)

    def test_a_path_may_carry_120_characters_and_not_121(self):
        assert media.relative("a" * 120) == "a" * 120
        with pytest.raises(media.MediaError, match="121 characters"):
            media.relative("a" * 121)

    def test_the_length_is_checked_before_the_segments(self):
        with pytest.raises(media.MediaError, match="characters"):
            media.relative("../" * 41)


class TestMediaType:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("post.md", "text/markdown"),
            ("notes.txt", "text/plain"),
            ("newsletter.html", "text/html"),
            ("content.yaml", "text/yaml"),
            ("build.json", "application/json"),
            ("image.png", "image/png"),
            ("photo.jpg", "image/jpeg"),
            ("slides/slide-01.png", "image/png"),
        ],
    )
    def test_a_known_suffix_names_its_type(self, path, expected):
        assert media.media_type(path) == expected

    @pytest.mark.parametrize("path", ["image.webp", "Makefile", "a.tar.gz"])
    def test_anything_else_is_a_byte_stream(self, path):
        assert media.media_type(path) == "application/octet-stream"


class TestReadable:
    @pytest.mark.parametrize(
        "media_type", ["text/markdown", "text/plain", "text/html", "application/json"]
    )
    def test_text_and_json_read_as_text(self, media_type):
        assert media.readable(media_type) is True

    @pytest.mark.parametrize("media_type", ["image/png", "application/octet-stream"])
    def test_bytes_do_not(self, media_type):
        assert media.readable(media_type) is False


class TestWrite:
    def test_text_is_stored_as_utf8_under_the_version(self, media_root):
        written = media.write(7, 2, "post.md", "café")
        assert written == {"path": "post.md", "media_type": "text/markdown", "bytes": 5}
        stored = media_root / "assets" / "7" / "2" / "post.md"
        assert stored.read_bytes() == "café".encode()

    def test_bytes_are_stored_as_given(self, media_root):
        png = b"\x89PNG\r\n\x1a\n"
        written = media.write(1, 1, "image.png", png)
        assert written == {"path": "image.png", "media_type": "image/png", "bytes": 8}
        assert (media_root / "assets" / "1" / "1" / "image.png").read_bytes() == png

    def test_a_nested_path_creates_its_directories(self, media_root):
        media.write(1, 1, "slides/slide-01.png", b"x")
        assert (media_root / "assets" / "1" / "1" / "slides" / "slide-01.png").is_file()

    def test_writing_a_path_again_replaces_it(self):
        media.write(1, 1, "post.md", "first")
        assert media.write(1, 1, "post.md", "second")["bytes"] == 6
        assert media.read(1, 1, "post.md") == b"second"
        assert len(media.listing(1, 1)) == 1

    def test_a_bad_path_is_refused_before_anything_touches_the_disk(self, media_root):
        with pytest.raises(media.MediaError, match="climbs"):
            media.write(1, 1, "../post.md", "x")
        assert not (media_root / "assets").exists()

    def test_a_file_over_the_cap_is_refused(self, monkeypatch, media_root):
        monkeypatch.setattr(media, "MAX_FILE_BYTES", 8)
        media.write(1, 1, "ok.bin", b"x" * 8)
        with pytest.raises(media.MediaError, match="9 bytes"):
            media.write(1, 1, "big.bin", b"x" * 9)
        assert not (media_root / "assets" / "1" / "1" / "big.bin").exists()

    def test_the_cap_counts_the_encoded_text(self, monkeypatch):
        monkeypatch.setattr(media, "MAX_FILE_BYTES", 4)
        with pytest.raises(media.MediaError, match="5 bytes"):
            media.write(1, 1, "post.md", "café")

    def test_the_cap_is_32_mebibytes(self):
        assert media.MAX_FILE_BYTES == 32 * 1024 * 1024

    def test_a_version_holds_at_most_the_file_cap(self, monkeypatch):
        monkeypatch.setattr(media, "MAX_FILES_PER_VERSION", 2)
        media.write(1, 1, "a.md", "a")
        media.write(1, 1, "sub/b.md", "b")
        with pytest.raises(media.MediaError, match="2 files"):
            media.write(1, 1, "c.md", "c")
        assert [entry["path"] for entry in media.listing(1, 1)] == ["a.md", "sub/b.md"]

    def test_the_file_cap_still_allows_replacing_a_file(self, monkeypatch):
        monkeypatch.setattr(media, "MAX_FILES_PER_VERSION", 1)
        media.write(1, 1, "a.md", "a")
        assert media.write(1, 1, "a.md", "aa")["bytes"] == 2

    def test_the_file_cap_is_per_version(self, monkeypatch):
        monkeypatch.setattr(media, "MAX_FILES_PER_VERSION", 1)
        media.write(1, 1, "a.md", "a")
        media.write(1, 2, "a.md", "a")
        media.write(2, 1, "a.md", "a")
        assert [entry["path"] for entry in media.listing(1, 2)] == ["a.md"]
        assert [entry["path"] for entry in media.listing(2, 1)] == ["a.md"]

    def test_the_file_cap_is_24(self):
        assert media.MAX_FILES_PER_VERSION == 24


class TestRead:
    def test_a_stored_file_comes_back_as_bytes(self):
        media.write(3, 1, "post.md", "hello")
        assert media.read(3, 1, "post.md") == b"hello"

    def test_a_missing_file_is_refused(self):
        with pytest.raises(media.MediaError, match="no file 'post.md'"):
            media.read(3, 1, "post.md")

    def test_a_directory_is_not_a_file(self):
        media.write(3, 1, "slides/slide-01.png", b"x")
        with pytest.raises(media.MediaError, match="no file 'slides'"):
            media.read(3, 1, "slides")

    def test_a_climbing_path_is_refused(self, media_root):
        (media_root / "secret").write_text("x")
        with pytest.raises(media.MediaError, match="climbs"):
            media.read(3, 1, "../../../secret")


class TestListing:
    def test_an_unknown_version_lists_nothing(self):
        assert media.listing(9, 9) == []

    def test_every_file_is_listed_by_path_in_order(self):
        media.write(1, 1, "slides/slide-02.png", b"xx")
        media.write(1, 1, "post.md", "hello")
        media.write(1, 1, "slides/slide-01.png", b"x")
        media.write(1, 2, "post.md", "other version")
        assert media.listing(1, 1) == [
            {"path": "post.md", "media_type": "text/markdown", "bytes": 5},
            {"path": "slides/slide-01.png", "media_type": "image/png", "bytes": 1},
            {"path": "slides/slide-02.png", "media_type": "image/png", "bytes": 2},
        ]

    def test_the_root_is_read_from_settings_at_call_time(self, tmp_path, monkeypatch):
        media.write(1, 1, "post.md", "x")
        other = tmp_path / "other"
        monkeypatch.setattr(settings, "MEDIA_DIR", str(other))
        assert media.listing(1, 1) == []
        media.write(1, 1, "post.md", "y")
        assert (other / "assets" / "1" / "1" / "post.md").read_text() == "y"
