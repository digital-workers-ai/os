import uuid

import pytest

from app import media
from app.config import settings

RECORD = uuid.UUID("5b1f3c2a-7d4e-4f60-9a8b-1c2d3e4f5a6b")
OTHER_RECORD = uuid.UUID("0c7a9e10-1d2b-4c3d-8e4f-5a6b7c8d9e0f")
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"


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

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("photo.jpeg", "image/jpeg"),
            ("image.webp", "image/webp"),
            ("invoice.pdf", "application/pdf"),
            ("clip-1.webm", "audio/webm"),
            ("clip-1.m4a", "audio/mp4"),
            ("clip-1.wav", "audio/wav"),
        ],
    )
    def test_a_record_file_suffix_names_its_type(self, path, expected):
        assert media.media_type(path) == expected

    @pytest.mark.parametrize("path", ["photo.heic", "Makefile", "a.tar.gz"])
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


class TestWriteRecord:
    def test_a_record_file_is_stored_under_custom_and_the_record_id(self, media_root):
        media.write_record(RECORD, "photo-1.jpg", JPEG)
        stored = media_root / "custom" / str(RECORD) / "photo-1.jpg"
        assert stored.read_bytes() == JPEG

    def test_writing_says_the_path_the_type_and_the_size(self):
        assert media.write_record(RECORD, "photo-1.jpg", JPEG) == {
            "path": "photo-1.jpg",
            "media_type": "image/jpeg",
            "bytes": 16,
        }

    def test_writing_a_record_path_again_replaces_it(self):
        media.write_record(RECORD, "signature.png", b"first")
        media.write_record(RECORD, "signature.png", b"second")
        assert media.read_record(RECORD, "signature.png") == b"second"

    def test_each_record_keeps_its_own_files(self):
        media.write_record(RECORD, "photo-1.jpg", b"first")
        media.write_record(OTHER_RECORD, "photo-1.jpg", b"second")
        assert (
            media.read_record(RECORD, "photo-1.jpg"),
            media.read_record(OTHER_RECORD, "photo-1.jpg"),
        ) == (b"first", b"second")

    def test_a_climbing_path_is_refused_before_anything_touches_the_disk(
        self, media_root
    ):
        with pytest.raises(media.MediaError, match="climbs"):
            media.write_record(RECORD, "../photo-1.jpg", JPEG)
        assert not (media_root / "custom").exists()

    def test_a_segment_outside_the_alphabet_is_refused(self, media_root):
        with pytest.raises(media.MediaError, match="segment"):
            media.write_record(RECORD, "photo 1.jpg", JPEG)
        assert not (media_root / "custom").exists()

    def test_a_path_over_120_characters_is_refused(self):
        with pytest.raises(media.MediaError, match="121 characters"):
            media.write_record(RECORD, "a" * 121, JPEG)

    def test_a_record_file_over_the_cap_is_refused(self, monkeypatch, media_root):
        monkeypatch.setattr(media, "MAX_FILE_BYTES", 8)
        media.write_record(RECORD, "ok.jpg", b"x" * 8)
        with pytest.raises(media.MediaError, match="9 bytes"):
            media.write_record(RECORD, "big.jpg", b"x" * 9)
        assert not (media_root / "custom" / str(RECORD) / "big.jpg").exists()

    def test_a_record_is_not_held_to_the_assets_file_count(self, monkeypatch):
        monkeypatch.setattr(media, "MAX_FILES_PER_VERSION", 1)
        media.write_record(RECORD, "clip-1.webm", b"a")
        media.write_record(RECORD, "clip-2.webm", b"b")
        assert media.read_record(RECORD, "clip-2.webm") == b"b"


class TestReadRecord:
    def test_a_stored_record_file_comes_back_as_bytes(self):
        media.write_record(RECORD, "photo-1.jpg", JPEG)
        assert media.read_record(RECORD, "photo-1.jpg") == JPEG

    def test_the_record_id_may_be_given_as_text(self):
        media.write_record(RECORD, "photo-1.jpg", JPEG)
        assert media.read_record(str(RECORD), "photo-1.jpg") == JPEG

    def test_a_missing_record_file_is_refused(self):
        with pytest.raises(media.MediaError, match="no file 'photo-1.jpg'"):
            media.read_record(RECORD, "photo-1.jpg")

    def test_a_climbing_record_path_is_refused(self, media_root):
        (media_root / "secret").write_text("x")
        with pytest.raises(media.MediaError, match="climbs"):
            media.read_record(RECORD, "../../secret")


class TestSniff:
    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            (JPEG, "image/jpeg"),
            (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", "image/png"),
            (b"RIFF\x24\x00\x00\x00WEBPVP8 ", "image/webp"),
            (b"%PDF-1.7\n%\xe2\xe3\xcf\xd3", "application/pdf"),
            (b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01", "audio/webm"),
            (b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00", "audio/mp4"),
            (b"RIFF\x24\x00\x00\x00WAVEfmt ", "audio/wav"),
        ],
    )
    def test_a_known_signature_names_its_type(self, data, expected):
        assert media.sniff(data) == expected

    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            (b"\xff\xd8\xff", "image/jpeg"),
            (b"\x89PNG\r\n\x1a\n", "image/png"),
            (b"RIFF\x00\x00\x00\x00WEBP", "image/webp"),
            (b"%PDF-", "application/pdf"),
            (b"\x1a\x45\xdf\xa3", "audio/webm"),
            (b"\x00\x00\x00\x00ftyp", "audio/mp4"),
            (b"RIFF\x00\x00\x00\x00WAVE", "audio/wav"),
        ],
    )
    def test_the_signature_alone_is_enough(self, data, expected):
        assert media.sniff(data) == expected

    @pytest.mark.parametrize(
        "data",
        [
            b"",
            b"\xff\xd8",
            b"\x89PNG\r\n\x1a",
            b"RIFF\x00\x00\x00\x00WEB",
            b"RIFF\x00\x00\x00\x00WAV",
            b"%PDF",
            b"\x1a\x45\xdf",
            b"\x00\x00\x00\x00fty",
        ],
    )
    def test_a_signature_cut_short_names_nothing(self, data):
        assert media.sniff(data) is None

    @pytest.mark.parametrize(
        "data",
        [
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00",
            b"hello, world",
            b"\x00" * 16,
            b"PK\x03\x04\x14\x00\x00\x00",
            b"RIFF\x24\x00\x00\x00AVI LIST",
            b"\x00\x00\x00\x00\x00\x00\x00\x00WEBP",
            b"ftypM4A \x00\x00\x00\x00",
            b"%pdf-1.7\n",
        ],
    )
    def test_unknown_bytes_name_nothing(self, data):
        assert media.sniff(data) is None
