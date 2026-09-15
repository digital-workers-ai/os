import pytest

from app import media
from app.config import settings


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
    return tmp_path


class TestWhereFilesLand:
    def test_a_file_lands_under_its_kind_seq_and_version(self, store):
        written = media.write("assets", 3, 2, "v1.png", b"pixels")
        assert (store / "assets" / "3" / "2" / "v1.png").read_bytes() == b"pixels"
        assert written == {"path": "v1.png", "media_type": "image/png", "bytes": 6}

    def test_a_nested_path_stays_inside_the_run(self, store):
        media.write("runs", 1, 1, "frames/first.png", b"x")
        assert (store / "runs" / "1" / "1" / "frames" / "first.png").is_file()

    def test_text_is_written_as_utf_eight(self, store):
        written = media.write("proposals", 1, 1, "post.md", "a café opened")
        assert written["bytes"] == 14
        assert media.read("proposals", 1, 1, "post.md") == b"a caf\xc3\xa9 opened"

    def test_path_for_composes_the_absolute_path(self, store):
        assert media.path_for("assets", 1, 1, "out.mp4") == (
            store / "assets" / "1" / "1" / "out.mp4"
        ).resolve()

    def test_a_second_write_replaces_the_first(self, store):
        media.write("assets", 1, 1, "post.md", "first")
        media.write("assets", 1, 1, "post.md", "second")
        assert media.read("assets", 1, 1, "post.md") == b"second"


class TestPathsItRefuses:
    @pytest.mark.parametrize(
        "path",
        [
            "",
            "..",
            ".",
            "../escape.md",
            "a/../../b.md",
            "/etc/passwd",
            "sub//post.md",
            ".hidden.md",
            "two words.md",
            "back\\slash.md",
            "null\x00.md",
            "post.md/",
            "-leading-dash.md",
            "quote'.md",
        ],
    )
    def test_a_path_that_is_not_plain_and_relative_is_refused(self, store, path):
        with pytest.raises(media.MediaError):
            media.write("assets", 1, 1, path, "body")

    def test_a_path_longer_than_the_cap_is_refused(self, store):
        with pytest.raises(media.MediaError, match="too long"):
            media.write("assets", 1, 1, "x" * 400 + ".md", "body")

    def test_a_symlink_that_leaves_the_run_is_refused(self, store, tmp_path):
        elsewhere = tmp_path.parent / "elsewhere"
        elsewhere.mkdir(exist_ok=True)
        run = store / "assets" / "1" / "1"
        run.mkdir(parents=True)
        (run / "out").symlink_to(elsewhere)
        with pytest.raises(media.MediaError, match="outside"):
            media.write("assets", 1, 1, "out/stolen.md", "body")

    def test_an_unknown_kind_is_refused(self, store):
        with pytest.raises(media.MediaError, match="kind"):
            media.write("secrets", 1, 1, "post.md", "body")

    @pytest.mark.parametrize("seq", ["nine", None, 0, -1])
    def test_a_seq_that_is_not_a_positive_number_is_refused(self, store, seq):
        with pytest.raises(media.MediaError, match="seq"):
            media.write("assets", seq, 1, "post.md", "body")

    def test_a_version_below_one_is_refused(self, store):
        with pytest.raises(media.MediaError, match="version"):
            media.write("assets", 1, 0, "post.md", "body")

    def test_data_that_is_neither_text_nor_bytes_is_refused(self, store):
        with pytest.raises(media.MediaError, match="text or bytes"):
            media.write("assets", 1, 1, "post.md", 512)


class TestCaps:
    def test_a_file_over_the_size_cap_is_refused(self, store, monkeypatch):
        monkeypatch.setattr(media, "MAX_FILE_BYTES", 8)
        with pytest.raises(media.MediaError, match="over the"):
            media.write("assets", 1, 1, "big.md", "x" * 9)
        assert not (store / "assets" / "1" / "1" / "big.md").exists()

    def test_a_run_may_not_write_more_files_than_the_cap(self, store, monkeypatch):
        monkeypatch.setattr(media, "MAX_FILES_PER_RUN", 2)
        media.write("assets", 1, 1, "one.md", "a")
        media.write("assets", 1, 1, "two.md", "b")
        with pytest.raises(media.MediaError, match="already written"):
            media.write("assets", 1, 1, "three.md", "c")

    def test_rewriting_a_file_is_allowed_at_the_cap(self, store, monkeypatch):
        monkeypatch.setattr(media, "MAX_FILES_PER_RUN", 1)
        media.write("assets", 1, 1, "one.md", "a")
        assert media.write("assets", 1, 1, "one.md", "b")["bytes"] == 1


class TestReadingBack:
    def test_reading_a_file_that_is_not_there_is_refused(self, store):
        with pytest.raises(media.MediaError, match="no file"):
            media.read("assets", 1, 1, "missing.md")

    def test_reading_a_directory_is_refused(self, store):
        media.write("assets", 1, 1, "frames/one.png", b"x")
        with pytest.raises(media.MediaError, match="no file"):
            media.read("assets", 1, 1, "frames")

    def test_listing_a_run_that_wrote_nothing_is_empty(self, store):
        assert media.listing("assets", 9, 1) == []

    def test_listing_names_every_file_with_its_type_and_size(self, store):
        media.write("assets", 1, 1, "post.md", "hello")
        media.write("assets", 1, 1, "frames/one.png", b"xx")
        assert media.listing("assets", 1, 1) == [
            {"path": "frames/one.png", "media_type": "image/png", "bytes": 2},
            {"path": "post.md", "media_type": "text/markdown", "bytes": 5},
        ]

    def test_an_unknown_extension_falls_back_to_a_plain_type(self, store):
        assert media.write("assets", 1, 1, "thing.bin", b"x")["media_type"] == (
            "application/octet-stream"
        )
