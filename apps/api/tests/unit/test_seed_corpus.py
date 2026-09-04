from __future__ import annotations

import sys
import time
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_corpus import _multipart_body, already_seeded, wait_for_health


def test_multipart_body_includes_each_file_and_its_content(tmp_path):
    f1 = tmp_path / "a.md"
    f1.write_text("content of a")
    f2 = tmp_path / "b.md"
    f2.write_text("content of b")

    body, content_type = _multipart_body([f1, f2])

    assert b"content of a" in body
    assert b"content of b" in body
    assert b'filename="a.md"' in body
    assert b'filename="b.md"' in body
    assert "multipart/form-data; boundary=" in content_type


def test_multipart_body_boundary_appears_in_both_header_and_body(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("hello")

    body, content_type = _multipart_body([f])
    boundary = content_type.split("boundary=")[1]

    assert boundary.encode() in body


def test_wait_for_health_returns_once_a_200_is_seen():
    fake_response = MagicMock()
    fake_response.status = 200
    fake_response.__enter__ = lambda self: fake_response
    fake_response.__exit__ = lambda self, *a: None

    with patch("urllib.request.urlopen", return_value=fake_response):
        wait_for_health("http://fake", timeout=5)  # should return without raising


def test_wait_for_health_raises_systemexit_after_timeout():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
        start = time.time()
        try:
            wait_for_health("http://fake", timeout=0.5)
            assert False, "expected SystemExit"
        except SystemExit as exc:
            assert "did not become healthy" in str(exc)
        assert time.time() - start < 5  # didn't hang well past the timeout


def test_already_seeded_true_when_chunks_present():
    fake_response = MagicMock()
    fake_response.read.return_value = b'{"source_documents": ["a.md"], "total_chunks": 4}'
    fake_response.__enter__ = lambda self: fake_response
    fake_response.__exit__ = lambda self, *a: None

    with patch("urllib.request.urlopen", return_value=fake_response):
        assert already_seeded("http://fake") is True


def test_already_seeded_false_when_index_is_empty():
    fake_response = MagicMock()
    fake_response.read.return_value = b'{"source_documents": [], "total_chunks": 0}'
    fake_response.__enter__ = lambda self: fake_response
    fake_response.__exit__ = lambda self, *a: None

    with patch("urllib.request.urlopen", return_value=fake_response):
        assert already_seeded("http://fake") is False


def test_already_seeded_false_and_not_fatal_when_the_check_itself_fails():
    with patch("urllib.request.urlopen", side_effect=OSError("network error")):
        assert already_seeded("http://fake") is False
