"""Tests for scripts/extract_1040nr_fields.py — AcroForm field extraction utility.

These tests are pure unit tests with no network access and no real PDF required.
They mock PdfReader so the extraction logic can be verified in isolation.

Run: pytest backend/tests/test_extract_fields.py -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import the script under test (lives in scripts/, not a package).
# We load it directly by file path so it works regardless of PYTHONPATH.
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "extract_1040nr_fields.py"
)


def _load_script():
    spec = importlib.util.spec_from_file_location("extract_1040nr_fields", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


script = _load_script()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_reader(fields: dict[str, str] | None):
    """Return a mock PdfReader whose get_fields() returns *fields*."""
    mock_field_objs = {}
    if fields:
        for name, ft in fields.items():
            obj = MagicMock()
            obj.get.return_value = ft
            mock_field_objs[name] = obj

    reader = MagicMock()
    reader.get_fields.return_value = mock_field_objs if fields is not None else None
    return reader


# ---------------------------------------------------------------------------
# extract_fields
# ---------------------------------------------------------------------------

class TestExtractFields:
    def test_returns_field_name_and_type(self, tmp_path):
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")
        fields = {"f1[0]": "/Tx", "f2[0]": "/Btn"}
        with patch("pypdf.PdfReader", return_value=_make_mock_reader(fields)):
            result = script.extract_fields(str(fake_pdf))
        assert result == {"f1[0]": "/Tx", "f2[0]": "/Btn"}

    def test_returns_empty_dict_when_no_acroform(self, tmp_path):
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")
        with patch("pypdf.PdfReader", return_value=_make_mock_reader(None)):
            result = script.extract_fields(str(fake_pdf))
        assert result == {}

    def test_exits_if_pypdf_missing(self, tmp_path, monkeypatch):
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")
        # Simulate pypdf not installed by patching the import inside extract_fields.
        import builtins
        real_import = builtins.__import__

        def broken_import(name, *args, **kwargs):
            if name == "pypdf":
                raise ImportError("No module named 'pypdf'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", broken_import)
        with pytest.raises(SystemExit) as exc:
            script.extract_fields(str(fake_pdf))
        assert exc.value.code == 1


# ---------------------------------------------------------------------------
# build_diff
# ---------------------------------------------------------------------------

class TestBuildDiff:
    def test_no_changes(self):
        fields = {"a": "/Tx", "b": "/Btn"}
        diff = script.build_diff(fields, fields.copy())
        assert diff["added"] == {}
        assert diff["removed"] == {}
        assert diff["unchanged_count"] == 2

    def test_added_field(self):
        extracted = {"a": "/Tx", "b": "/Btn"}
        current = {"a": "/Tx"}
        diff = script.build_diff(extracted, current)
        assert diff["added"] == {"b": "/Btn"}
        assert diff["removed"] == {}
        assert diff["unchanged_count"] == 1

    def test_removed_field(self):
        extracted = {"a": "/Tx"}
        current = {"a": "/Tx", "old_field": "/Ch"}
        diff = script.build_diff(extracted, current)
        assert diff["added"] == {}
        assert diff["removed"] == {"old_field": "/Ch"}
        assert diff["unchanged_count"] == 1

    def test_added_and_removed(self):
        extracted = {"a": "/Tx", "new_field": "/Btn"}
        current = {"a": "/Tx", "old_field": "/Ch"}
        diff = script.build_diff(extracted, current)
        assert diff["added"] == {"new_field": "/Btn"}
        assert diff["removed"] == {"old_field": "/Ch"}
        assert diff["unchanged_count"] == 1


# ---------------------------------------------------------------------------
# print_diff (smoke — verifies no crash and key phrases appear)
# ---------------------------------------------------------------------------

class TestPrintDiff:
    def test_no_changes_message(self, capsys):
        script.print_diff({"added": {}, "removed": {}, "unchanged_count": 5})
        out = capsys.readouterr().out
        assert "No changes" in out

    def test_added_shows_field_name(self, capsys):
        script.print_diff({"added": {"new_f": "/Tx"}, "removed": {}, "unchanged_count": 3})
        out = capsys.readouterr().out
        assert "new_f" in out
        assert "ADDED" in out

    def test_removed_shows_field_name(self, capsys):
        script.print_diff({"added": {}, "removed": {"old_f": "/Ch"}, "unchanged_count": 3})
        out = capsys.readouterr().out
        assert "old_f" in out
        assert "REMOVED" in out


# ---------------------------------------------------------------------------
# load_field_map — returns None when generate_1040nr_pdf.py is absent
# ---------------------------------------------------------------------------

class TestLoadFieldMap:
    def test_returns_none_when_module_missing(self, monkeypatch):
        # Point the script at a path that doesn't exist.
        monkeypatch.setattr(script, "_GENERATE_PDF_PATH", Path("/nonexistent/generate_1040nr_pdf.py"))
        result = script.load_field_map()
        assert result is None


# ---------------------------------------------------------------------------
# CLI integration (main) — no-diff path
# ---------------------------------------------------------------------------

class TestMainCLI:
    def test_list_fields_human_readable(self, tmp_path, capsys):
        fake_pdf = tmp_path / "f1040nr.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")
        with patch("pypdf.PdfReader", return_value=_make_mock_reader({"topmostSubform[0]": "/Tx"})):
            script.main([str(fake_pdf)])
        out = capsys.readouterr().out
        assert "topmostSubform[0]" in out

    def test_json_output(self, tmp_path, capsys):
        fake_pdf = tmp_path / "f1040nr.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")
        with patch("pypdf.PdfReader", return_value=_make_mock_reader({"f1": "/Tx"})):
            script.main([str(fake_pdf), "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["fields"]["f1"] == "/Tx"

    def test_exits_nonzero_for_missing_pdf(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            script.main([str(tmp_path / "nonexistent.pdf")])
        assert exc.value.code == 1

    def test_diff_without_generate_module(self, tmp_path, monkeypatch, capsys):
        fake_pdf = tmp_path / "f1040nr.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")
        monkeypatch.setattr(script, "_GENERATE_PDF_PATH", Path("/nonexistent/generate_1040nr_pdf.py"))
        with patch("pypdf.PdfReader", return_value=_make_mock_reader({"f1": "/Tx"})):
            script.main([str(fake_pdf), "--diff"])
        # Should fall back to listing all fields with a NOTE message.
        err = capsys.readouterr().err
        assert "generate_1040nr_pdf.py not found" in err
