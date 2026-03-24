#!/usr/bin/env bash
# fetch_irs_forms.sh — Download IRS Form 8843 PDFs for one or more tax years.
#
# Usage:
#   scripts/fetch_irs_forms.sh [YEAR...]
#
# Examples:
#   scripts/fetch_irs_forms.sh              # current year (2025)
#   scripts/fetch_irs_forms.sh 2024 2025    # two specific years
#   scripts/fetch_irs_forms.sh 2023 2024 2025
#
# What it does for each year:
#   1. Downloads f8843.pdf from irs.gov (or the prior-year archive URL).
#   2. Computes SHA-256 checksum.
#   3. Saves the PDF to backend/static/forms/f8843_{year}.pdf.
#   4. Appends or updates a checksum entry in backend/static/forms/checksums.sha256.
#
# Run this every January when IRS publishes the new Form 8843 for the prior year.
# See CLAUDE.md "Form 8843 — Annual Maintenance" for the full checklist.
#
# Requirements:
#   - curl (macOS/Linux built-in)
#   - shasum (macOS) or sha256sum (Linux) — detected automatically
#   - write access to backend/static/forms/
#
# Exit codes:
#   0  — all downloads succeeded
#   1  — one or more downloads failed (partial downloads removed)
#   2  — precondition failure (missing tool, bad argument)

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMS_DIR="$REPO_ROOT/backend/static/forms"
CHECKSUM_FILE="$FORMS_DIR/checksums.sha256"
CURRENT_YEAR=2025

# IRS URL patterns:
#   Current year: https://www.irs.gov/pub/irs-pdf/f8843.pdf
#   Prior year:   https://www.irs.gov/pub/irs-prior/f8843--{year}.pdf
IRS_CURRENT_URL="https://www.irs.gov/pub/irs-pdf/f8843.pdf"
IRS_PRIOR_URL_TEMPLATE="https://www.irs.gov/pub/irs-prior/f8843--{YEAR}.pdf"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*" >&2; }
error() { echo "[ERROR] $*" >&2; }

# Detect SHA-256 tool (macOS vs Linux)
if command -v sha256sum &>/dev/null; then
    sha256() { sha256sum "$1" | awk '{print $1}'; }
elif command -v shasum &>/dev/null; then
    sha256() { shasum -a 256 "$1" | awk '{print $1}'; }
else
    error "Neither sha256sum nor shasum found. Install one and retry."
    exit 2
fi

# Update or append a checksum line for a given filename in CHECKSUM_FILE.
# Format: <sha256>  <filename>
upsert_checksum() {
    local hash="$1"
    local filename="$2"
    if grep -q "  ${filename}$" "$CHECKSUM_FILE" 2>/dev/null; then
        # Replace existing line (portable sed: -i '' on macOS, -i on Linux)
        if sed --version 2>&1 | grep -q GNU; then
            sed -i "s|^.*  ${filename}$|${hash}  ${filename}|" "$CHECKSUM_FILE"
        else
            sed -i '' "s|^.*  ${filename}$|${hash}  ${filename}|" "$CHECKSUM_FILE"
        fi
        info "Updated checksum for ${filename}"
    else
        echo "${hash}  ${filename}" >> "$CHECKSUM_FILE"
        info "Added checksum for ${filename}"
    fi
}

download_form() {
    local year="$1"
    local dest="$FORMS_DIR/f8843_${year}.pdf"
    local tmp="${dest}.tmp"

    # Pick the right URL
    local url
    if [[ "$year" -eq "$CURRENT_YEAR" ]]; then
        url="$IRS_CURRENT_URL"
    else
        url="${IRS_PRIOR_URL_TEMPLATE/\{YEAR\}/$year}"
    fi

    info "Fetching f8843_${year}.pdf from $url ..."

    # Download with curl; -f makes curl return non-zero on HTTP errors
    if ! curl -fsSL --retry 3 --retry-delay 5 -o "$tmp" "$url"; then
        error "Download failed for year $year (URL: $url)"
        rm -f "$tmp"
        return 1
    fi

    # Sanity-check: IRS PDFs start with %PDF
    if ! head -c 4 "$tmp" | grep -q '%PDF'; then
        error "Downloaded file for year $year does not appear to be a PDF."
        error "IRS may have returned an error page. Check: $url"
        rm -f "$tmp"
        return 1
    fi

    mv "$tmp" "$dest"
    info "Saved → $dest"

    # Compute and record checksum
    local hash
    hash="$(sha256 "$dest")"
    local filename="f8843_${year}.pdf"
    upsert_checksum "$hash" "$filename"
    info "SHA-256: $hash"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

mkdir -p "$FORMS_DIR"
touch "$CHECKSUM_FILE"

# Default to current year if no args
years=("${@:-$CURRENT_YEAR}")

failures=0
for year in "${years[@]}"; do
    # Validate: must be a 4-digit year between 2018 and current year
    if ! [[ "$year" =~ ^[0-9]{4}$ ]] || (( year < 2018 || year > CURRENT_YEAR )); then
        error "Invalid year: $year (must be 2018–$CURRENT_YEAR)"
        (( failures++ )) || true
        continue
    fi
    download_form "$year" || (( failures++ )) || true
done

# Sort the checksum file for stable diffs
sort -k2 "$CHECKSUM_FILE" -o "$CHECKSUM_FILE"

if (( failures > 0 )); then
    error "$failures download(s) failed."
    exit 1
fi

info "Done. Verify AcroForm fields with:"
for year in "${years[@]}"; do
    echo "  python -c \"import pypdf; print(pypdf.PdfReader('$FORMS_DIR/f8843_${year}.pdf').get_fields())\""
done
info "Then update backend/app/constants/form_8843_fields.py if field names changed."
info "Finally, run: python -m pytest backend/tests/test_form_8843.py"
