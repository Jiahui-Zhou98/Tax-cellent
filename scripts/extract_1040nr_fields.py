#!/usr/bin/env python3
"""
scripts/extract_1040nr_fields.py
IRS Form 1040-NR AcroForm field extraction and mapping diff tool.

Run this script every January when the IRS publishes the new 1040-NR PDF to
detect field-name changes before they silently corrupt the generated return.

Annual maintenance steps:
  1. Download the new 1040-NR PDF:
       https://www.irs.gov/forms-pubs/about-form-1040-nr
  2. Run the diff:
       python scripts/extract_1040nr_fields.py /path/to/f1040nr_{year}.pdf --diff
  3. Review the ADDED / REMOVED sections in the output.
  4. Update FIELD_MAP in backend/app/services/generate_1040nr_pdf.py to match.
  5. Re-run the accuracy tests:
       cd backend && python -m pytest tests/test_accuracy.py -v
  6. Commit: "chore: update 1040-NR field mapping for {year}"

Usage:
  # Print all AcroForm field names in the PDF:
  python scripts/extract_1040nr_fields.py f1040nr_2025.pdf

  # Diff against current FIELD_MAP in generate_1040nr_pdf.py:
  python scripts/extract_1040nr_fields.py f1040nr_2025.pdf --diff

  # Machine-readable JSON output:
  python scripts/extract_1040nr_fields.py f1040nr_2025.pdf --json

  # Diff with JSON output:
  python scripts/extract_1040nr_fields.py f1040nr_2025.pdf --diff --json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

# Path to generate_1040nr_pdf.py relative to this script's location (repo root).
_GENERATE_PDF_PATH = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "app"
    / "services"
    / "generate_1040nr_pdf.py"
)


# ---------------------------------------------------------------------------
# Core extraction logic
# ---------------------------------------------------------------------------

def extract_fields(pdf_path: str | Path) -> dict[str, str]:
    """Extract all AcroForm widget field names from *pdf_path*.

    Returns a ``{field_name: field_type}`` mapping where *field_type* is one of
    ``/Tx`` (text), ``/Btn`` (checkbox/radio), ``/Ch`` (choice/dropdown), etc.

    Raises ``SystemExit`` with a helpful message if pypdf is not installed.
    """
    try:
        from pypdf import PdfReader  # type: ignore[import]
    except ImportError:
        print(
            "ERROR: pypdf is not installed.\n"
            "       Run: pip install pypdf==4.3.1",
            file=sys.stderr,
        )
        sys.exit(1)

    reader = PdfReader(str(pdf_path))
    raw = reader.get_fields()
    if not raw:
        return {}

    result: dict[str, str] = {}
    for name, field in raw.items():
        # /FT may be an IndirectObject; coerce to str so it's JSON-serialisable.
        ft = field.get("/FT", "/Tx")
        result[name] = str(ft)
    return result


def load_field_map() -> dict[str, str] | None:
    """Import ``FIELD_MAP`` from ``generate_1040nr_pdf.py`` if it exists.

    Returns ``None`` when the module is absent (i.e., Exp 3 has not shipped yet).
    """
    if not _GENERATE_PDF_PATH.exists():
        return None

    spec = importlib.util.spec_from_file_location("generate_1040nr_pdf", _GENERATE_PDF_PATH)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: could not import generate_1040nr_pdf.py — {exc}", file=sys.stderr)
        return None
    return getattr(mod, "FIELD_MAP", None)


# ---------------------------------------------------------------------------
# Diff / display helpers
# ---------------------------------------------------------------------------

def build_diff(extracted: dict[str, str], current: dict[str, str]) -> dict:
    """Return a structured diff between *extracted* PDF fields and *current* FIELD_MAP.

    Structure::

        {
            "added":   {"field_name": "/Tx", ...},   # in PDF, not in map
            "removed": {"field_name": "/Tx", ...},   # in map, not in PDF
            "unchanged_count": int,
        }
    """
    return {
        "added": {k: v for k, v in extracted.items() if k not in current},
        "removed": {k: v for k, v in current.items() if k not in extracted},
        "unchanged_count": sum(1 for k in extracted if k in current),
    }


def print_diff(diff: dict) -> None:
    """Print a human-readable diff summary."""
    added = diff["added"]
    removed = diff["removed"]
    unchanged = diff["unchanged_count"]

    if not added and not removed:
        print("✓  No changes — FIELD_MAP is current.")
        return

    if added:
        print(f"\n[ADDED]  {len(added)} field(s) new in PDF (add to FIELD_MAP):")
        for name in sorted(added):
            print(f"    +  {name!r}  ({added[name]})")

    if removed:
        print(f"\n[REMOVED]  {len(removed)} field(s) missing from PDF (remove from FIELD_MAP):")
        for name in sorted(removed):
            print(f"    -  {name!r}  ({removed[name]})")

    print(f"\n   Unchanged: {unchanged} field(s) match.")
    print(
        "\nAction required: update FIELD_MAP in "
        "backend/app/services/generate_1040nr_pdf.py, then re-run:\n"
        "  cd backend && python -m pytest tests/test_accuracy.py -v"
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract IRS 1040-NR AcroForm field names from a PDF and "
            "optionally diff against the current FIELD_MAP mapping table."
        ),
        epilog="See the module docstring for the full annual maintenance checklist.",
    )
    parser.add_argument("pdf_path", help="Path to the IRS 1040-NR PDF file.")
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Compare extracted fields against FIELD_MAP in generate_1040nr_pdf.py.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Emit machine-readable JSON instead of human-readable text.",
    )
    args = parser.parse_args(argv)

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"ERROR: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # In JSON mode, status lines go to stderr so stdout is pure JSON.
    _status = sys.stderr if args.output_json else sys.stdout
    print(f"Extracting AcroForm fields from: {pdf_path}", file=_status)
    fields = extract_fields(pdf_path)

    if not fields:
        print("WARNING: No AcroForm fields found in this PDF.", file=sys.stderr)
        sys.exit(0)

    print(f"Found {len(fields)} field(s).", file=_status)

    if args.diff:
        current_map = load_field_map()
        if current_map is None:
            print(
                f"\nNOTE: generate_1040nr_pdf.py not found at:\n  {_GENERATE_PDF_PATH}\n"
                "      (Exp 3 has not shipped yet — no FIELD_MAP to diff against.)\n"
                "      Listing all extracted fields instead:\n",
                file=sys.stderr,
            )
            if args.output_json:
                print(json.dumps({"fields": fields}, indent=2))
            else:
                for name in sorted(fields):
                    print(f"  {name!r}  ({fields[name]})")
            return

        diff = build_diff(fields, current_map)
        if args.output_json:
            print(json.dumps(diff, indent=2))
        else:
            print(f"\nDiffing against FIELD_MAP ({len(current_map)} entries in generate_1040nr_pdf.py):")
            print_diff(diff)
        return

    # No --diff: just list the fields.
    if args.output_json:
        print(json.dumps({"fields": fields}, indent=2))
    else:
        print("\nExtracted fields:")
        for name in sorted(fields):
            print(f"  {name!r}  ({fields[name]})")


if __name__ == "__main__":
    main()
