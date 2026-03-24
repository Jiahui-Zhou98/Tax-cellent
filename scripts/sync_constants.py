#!/usr/bin/env python3
"""Sync NRA_VISA_TYPES from Python source to TypeScript.

Usage:
    python scripts/sync_constants.py

Reads backend/app/constants/tax_constants.py, extracts NRA_VISA_TYPES, and
writes the TypeScript export to frontend/app/lib/constants.ts.

Run this after ANY change to NRA_VISA_TYPES, and in CI pre-commit to prevent
Python/TypeScript drift.  See CLAUDE.md for sync maintenance instructions.

Exit codes:
    0  — success
    1  — source file not found or NRA_VISA_TYPES not parseable
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON_SOURCE = REPO_ROOT / "backend" / "app" / "constants" / "tax_constants.py"
TS_TARGET = REPO_ROOT / "frontend" / "app" / "lib" / "constants.ts"

# Marker lines used to find and replace just the NRA_VISA_TYPES block inside
# constants.ts if other exports already exist in that file.
_BEGIN_MARKER = "// BEGIN:NRA_VISA_TYPES"
_END_MARKER = "// END:NRA_VISA_TYPES"

_HEADER = """\
// AUTO-GENERATED — do not edit directly.
// Source: backend/app/constants/tax_constants.py
// Regenerate: python scripts/sync_constants.py
// See CLAUDE.md for sync maintenance instructions.
"""


def extract_nra_visa_types(source_text: str) -> list[str]:
    """Parse NRA_VISA_TYPES list literal from Python source."""
    match = re.search(
        r'NRA_VISA_TYPES\s*:\s*list\[str\]\s*=\s*\[([^\]]+)\]',
        source_text,
        re.DOTALL,
    )
    if not match:
        raise ValueError("NRA_VISA_TYPES not found in source file")
    items = re.findall(r'"([^"]+)"', match.group(1))
    if not items:
        raise ValueError("No visa type strings found inside NRA_VISA_TYPES")
    return items


def _nra_block(visa_types: list[str]) -> str:
    items_str = ", ".join(f'"{v}"' for v in visa_types)
    return (
        f"{_BEGIN_MARKER}\n"
        f"export const NRA_VISA_TYPES: string[] = [{items_str}];\n"
        f"{_END_MARKER}\n"
    )


def generate_ts_content(visa_types: list[str], existing: str | None) -> str:
    """Build the final constants.ts content.

    If the file already exists and has a marker block, replace it in place.
    If it exists without a marker block, append at the end.
    If the file is new, write a fresh file.
    """
    block = _nra_block(visa_types)

    if existing is None:
        # New file
        return f"{_HEADER}\n{block}"

    if _BEGIN_MARKER in existing:
        # Replace existing block
        begin = existing.index(_BEGIN_MARKER)
        end = existing.index(_END_MARKER) + len(_END_MARKER) + 1  # +1 for trailing \n
        return existing[:begin] + block + existing[end:]

    # Existing file without marker — append
    sep = "" if existing.endswith("\n") else "\n"
    return existing + sep + "\n" + block


def main() -> None:
    if not PYTHON_SOURCE.exists():
        print(f"ERROR: source not found: {PYTHON_SOURCE}", file=sys.stderr)
        sys.exit(1)

    source_text = PYTHON_SOURCE.read_text(encoding="utf-8")

    try:
        visa_types = extract_nra_visa_types(source_text)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    existing = TS_TARGET.read_text(encoding="utf-8") if TS_TARGET.exists() else None
    ts_content = generate_ts_content(visa_types, existing)

    TS_TARGET.parent.mkdir(parents=True, exist_ok=True)
    TS_TARGET.write_text(ts_content, encoding="utf-8")
    print(f"✓ Synced NRA_VISA_TYPES ({len(visa_types)} types) → {TS_TARGET}")


if __name__ == "__main__":
    main()
