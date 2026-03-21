"""
Structure-aware, region-prioritized candidate extraction from opendataloader_pdf JSON.

Design principles:
  1. Rich element metadata: node_type, font_size, source_path, region label
  2. Document zoning: primary W-2 copy prioritised over duplicate copies / footers
  3. Composable confidence: label_strength × region_mult + shape/table bonuses - penalties
  4. Field-specific extractors: money (directional+column), names (heuristic-split),
     addresses (y-adjacent pair combining), EIN/SSN (regex-first, spatial fallback)
  5. Dedicated W-2 orchestrator — not a bag of generic heuristics
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class Element:
    content:    str
    x1: float; y1: float; x2: float; y2: float
    page:       int
    node_type:  str          # paragraph | header | list | table | caption | heading
    node_id:    int          # stable id from JSON (0 if absent)
    source_path: str         # root/kids[0]/kids[2] etc.
    font_size:  float        # 0.0 if not available
    parent_type: str         # parent node's type
    region:     str          # "primary" | "secondary" | "footer" | "unknown"
    is_primary: bool         # True when region == "primary"


@dataclass
class Candidate:
    value:       str
    source_text: str         # raw snippet shown to LLM
    page:        int
    bbox:        list[float] # [x1, y1, x2, y2]
    confidence:  float
    match_reason: str
    # Metadata for pre-LLM filtering and LLM context
    source_type:  str        # "regex" | "label_adjacent" | "spatial" | "heuristic" | "combined"
    region:       str
    is_primary:   bool
    is_fallback:  bool


CandidateMap = dict[str, list[Candidate]]

# ── Regex patterns ────────────────────────────────────────────────────────────

_MONEY_RE  = re.compile(r"^\$?([\d,]+\.\d+)$")          # requires decimal
# SSN: masked with * or X (ByteDance uses XXX-XX-4426), or unmasked
_SSN_RE    = re.compile(r"([X\*]{3}-[X\*]{2}-\d{4}|\d{3}-\d{2}-\d{4})", re.IGNORECASE)
_EIN_RE    = re.compile(r"(\d{2}-\d{7})")
_YEAR_RE   = re.compile(r"\b(20\d{2})\b")
_STATE_RE  = re.compile(r"^[A-Z]{2}$")
# ZIP: 5-digit NOT followed by more digits or a decimal point
_ZIP_RE    = re.compile(r"(?<!\d)\d{5}(-\d{4})?(?!\d)(?!\.)")
_STREET_RE = re.compile(r"^\d+\s+[A-Z]{3,}")            # "210 RIV…", "25 BUS…" (≥3 uppercase)

_LABEL_FONT_SIZE = 8.0   # font sizes BELOW this are presumed labels / secondary text
_DATA_FONT_SIZE  = 8.0   # font sizes AT or ABOVE this → numeric data value (strong signal)

_ROW_TOL = 20   # y-units that count as "same row"

# ── Element collection — rich metadata ────────────────────────────────────────

def _collect_elements(data: dict) -> list[Element]:
    """
    Depth-first traversal of opendataloader JSON.
    Emits one Element per leaf node that has non-trivial content.
    Preserves node_type, node_id, source_path, font_size, parent_type.
    Region is left as "unknown" here; _zone_document() fills it in.
    """
    elements: list[Element] = []

    def walk(node, parent_type: str = "root", path: str = "root"):
        if not isinstance(node, dict):
            return
        t      = node.get("type", "unknown")
        nid    = node.get("id", 0)
        page   = node.get("page number", 1)
        bbox   = node.get("bounding box") or []
        fs     = node.get("font size", 0.0) or 0.0
        content = (node.get("content") or "").strip()

        if content and len(content) > 1 and len(bbox) == 4:
            elements.append(Element(
                content=content,
                x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3],
                page=page,
                node_type=t,
                node_id=nid,
                source_path=path,
                font_size=fs,
                parent_type=parent_type,
                region="unknown",
                is_primary=False,
            ))

        # opendataloader uses "kids" for most node types but "list items" for list nodes
        children = (node.get("kids") or []) + (node.get("list items") or [])
        for i, child in enumerate(children):
            walk(child, t, f"{path}/{t}[{i}]")

    walk(data)
    return elements


# ── Document zoning ────────────────────────────────────────────────────────────

def _zone_document(elements: list[Element]) -> dict[str, tuple[float, float]]:
    """
    Identify y-ranges for each region on the primary page.

    W-2 PDFs commonly have 2 copies stacked vertically on one page.
    The top copy (higher y in PDF coords = visually higher) is the primary copy.

    Strategy:
      - Find y_max and y_min of all page-1 elements.
      - Look for a clear gap or a separator/footer pattern near the midpoint.
      - Primary region = upper portion; secondary = lower portion; footer = very low y.

    Returns:
      { "primary": (y_lo, y_hi), "secondary": (y_lo, y_hi), "footer": (y_lo, y_hi) }
    """
    page1 = [e for e in elements if e.page == 1]
    if not page1:
        return {"primary": (0, 9999), "secondary": (-1, -1), "footer": (-1, -1)}

    y_values = [e.y1 for e in page1]
    y_min, y_max = min(y_values), max(y_values)
    y_span = y_max - y_min

    # Separator heuristic: look for a paragraph containing "---" or "Copy" around midpoint
    mid = y_min + y_span * 0.45      # expected separator is ~40-50% from bottom
    sep_y = None
    _SEP_RE = re.compile(r"^[-─═=]{5,}|copy\s*[a-z]\b|department\s+of", re.I)
    candidates_near_mid = [
        e for e in page1
        if abs(e.y1 - mid) < y_span * 0.15
        and _SEP_RE.search(e.content)
    ]
    if candidates_near_mid:
        sep_y = max(e.y1 for e in candidates_near_mid)  # topmost separator line

    if sep_y is None:
        # Fallback: use midpoint
        sep_y = y_min + y_span * 0.50

    footer_threshold = y_min + y_span * 0.07   # bottom 7% = footer boilerplate

    primary   = (sep_y + 1,           y_max + 1)
    secondary = (footer_threshold,    sep_y)
    footer    = (y_min - 1,           footer_threshold)

    logger.debug(
        "zone_document: y_range=[%.0f,%.0f] sep_y=%.0f primary=%s secondary=%s",
        y_min, y_max, sep_y, primary, secondary,
    )
    return {"primary": primary, "secondary": secondary, "footer": footer}


def _assign_regions(elements: list[Element], zones: dict) -> None:
    """Mutate each element's .region and .is_primary in place."""
    p_lo, p_hi = zones.get("primary",   (9999, 9999))
    s_lo, s_hi = zones.get("secondary", (-1, -1))
    f_lo, f_hi = zones.get("footer",    (-1, -1))

    for el in elements:
        if el.page != 1:
            el.region = "secondary"; el.is_primary = False
        elif p_lo <= el.y1 <= p_hi:
            el.region = "primary";   el.is_primary = True
        elif s_lo <= el.y1 <= s_hi:
            el.region = "secondary"; el.is_primary = False
        elif f_lo <= el.y1 <= f_hi:
            el.region = "footer";    el.is_primary = False
        else:
            el.region = "unknown";   el.is_primary = False


# ── Composable confidence ─────────────────────────────────────────────────────

def _confidence(
    label_strength: float,   # 0.5–1.0: how well the value matches what's expected
    region_mult:    float,   # 1.0 primary, 0.85 secondary, 0.65 footer / unknown
    *,
    font_bonus:     float = 0.0,   # +0.10 when font_size >= _DATA_FONT_SIZE
    shape_bonus:    float = 0.0,   # +0.05–0.15 for format matches (ZIP, name, etc.)
    table_bonus:    float = 0.0,   # +0.05 when element is a table cell
    fallback_penalty: float = 0.0, # +0.20 when from fallback/heuristic path
) -> float:
    raw = label_strength * region_mult + font_bonus + shape_bonus + table_bonus - fallback_penalty
    return round(max(0.0, min(1.0, raw)), 3)


def _region_mult(el: Element) -> float:
    return {"primary": 1.0, "secondary": 0.85, "footer": 0.65}.get(el.region, 0.70)


def _font_bonus(el: Element) -> float:
    return 0.10 if el.font_size >= _DATA_FONT_SIZE else 0.0


# ── Shared label/value helpers ────────────────────────────────────────────────

def _label_elements(
    elements: list[Element],
    patterns: list[str],
    page: int,
    primary_only: bool = True,
) -> list[Element]:
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    return [
        e for e in elements
        if e.page == page
        and (not primary_only or e.is_primary)
        and any(r.search(e.content) for r in compiled)
    ]


def _same_col(lx1: float, lx2: float, ex1: float, margin: float = 30.0) -> bool:
    return (lx1 - margin) <= ex1 <= (lx2 + margin)


def _near_elements(
    elements: list[Element],
    label: Element,
    vert_tol: int,
    *,
    direction: str = "both",     # "below" | "above" | "both"
    require_col: bool = True,
    allow_secondary: bool = True,
) -> list[tuple[Element, float]]:
    """
    Return (element, raw_confidence) pairs near a label.

    direction="below" → only elements with y1 ≤ label.y1 + 2 (on-form values)
    direction="above" → only elements with y1 ≥ label.y1 - 2
    direction="both"  → bidirectional (for addresses)

    Raw confidence comes from spatial relationship only;
    caller applies region_mult and bonuses.
    """
    col_margin = max(30.0, (label.x2 - label.x1) * 0.15)
    results: list[tuple[Element, float]] = []

    for el in elements:
        if el is label or el.page != label.page:
            continue
        if not allow_secondary and not el.is_primary:
            continue

        dy    = el.y1 - label.y1   # positive = el is above label in PDF coords
        abs_dy = abs(dy)
        in_col = _same_col(label.x1, label.x2, el.x1, col_margin)
        same_row = abs_dy <= _ROW_TOL

        # Directional filter
        if direction == "below" and dy > 2:       # element is above label → skip
            continue
        if direction == "above" and dy < -2:      # element is below label → skip
            continue

        if same_row and el.x1 > label.x2:         # to the right on the same row
            conf = 0.80
        elif in_col and abs_dy <= vert_tol:        # same column, vertically near
            conf = 0.70
        elif not require_col and not same_row and abs_dy <= vert_tol:
            conf = 0.50
        else:
            continue

        results.append((el, conf))

    return results


# ── Money parsing ─────────────────────────────────────────────────────────────

def _parse_money(text: str) -> Optional[str]:
    """Return normalised decimal string or None."""
    m = _MONEY_RE.match(text.strip())
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        val = float(raw)
    except ValueError:
        return None
    if val <= 0 or val > 9_999_999:
        return None
    return raw


def _money_tokens(text: str) -> list[str]:
    """Split combined elements like '23065.28 3033.34' into individual money tokens."""
    return [t for tok in text.split() if (t := _parse_money(tok))]


# ── Name helpers ──────────────────────────────────────────────────────────────

def _looks_like_person_name(text: str) -> bool:
    words = text.split()
    if len(words) < 2 or len(words) > 5:
        return False
    return all(len(w) >= 2 and re.match(r"^[A-Za-z'\-\.]+$", w) for w in words)


def _looks_like_org_name(text: str) -> bool:
    """Org names: multi-word, may contain OF/THE/&, typically all-caps."""
    if len(text) < 5:
        return False
    words = text.split()
    if len(words) < 2:
        return False
    # Form labels start with a box number ("3 Social security wages...") — reject
    if re.match(r"^\d+$", words[0]):
        return False
    return all(re.match(r"^[A-Za-z0-9'\-\.\,&]+$", w) for w in words)


# ── Field extractors ──────────────────────────────────────────────────────────

def _extract_regex_field(
    elements: list[Element],
    pattern: re.Pattern,
    source_type: str,
    base_strength: float = 0.90,
) -> list[Candidate]:
    """Generic regex scan — region-aware, deduplicates by matched value."""
    seen: dict[str, Candidate] = {}
    for el in elements:
        m = pattern.search(el.content)
        if not m:
            continue
        val = m.group(1)
        rm  = _region_mult(el)
        conf = _confidence(base_strength, rm, font_bonus=_font_bonus(el))
        if val not in seen or conf > seen[val].confidence:
            seen[val] = Candidate(
                value=val, source_text=el.content[:80],
                page=el.page, bbox=[el.x1, el.y1, el.x2, el.y2],
                confidence=conf, match_reason=f"regex:{source_type}",
                source_type="regex", region=el.region,
                is_primary=el.is_primary, is_fallback=False,
            )
    return sorted(seen.values(), key=lambda c: -c.confidence)[:4]


def _extract_money_field(
    elements: list[Element],
    label_patterns: list[str],
    page: int,
    x_range: Optional[tuple[float, float]] = None,
) -> list[Candidate]:
    """
    Extract money candidates for a single box.

    Strategy A (label-adjacent, directional):
      Find the label in the primary region. Look for money values BELOW the label
      (direction="below"), in the same column when no x_range, or within x_range column.
      Handles combined '23065.28 3033.34' elements by splitting into tokens.

    Strategy B (x-range per-label scan, for state boxes):
      For each label element, scan elements within the x-column and within 60 y-units.
    """
    candidates: list[Candidate] = []
    seen_vals: set[str] = set()

    labels = _label_elements(elements, label_patterns, page, primary_only=True)
    allow_sec = False
    if not labels:
        # fallback: try non-primary labels; when we do, also allow secondary values
        labels = _label_elements(elements, label_patterns, page, primary_only=False)
        allow_sec = True

    # Strategy A: label-adjacent with directional filter.
    # When labels are in secondary region (multi-copy side-by-side, e.g. ADP/ByteDance):
    #   • Skip x_range column filter — column offsets differ between layouts.
    #   • Tighten vert_tol to 15: same-row values are ≈7–8 units away, next row ≈25+,
    #     so 15 keeps only the correct row and avoids cross-row contamination.
    eff_x_range  = None if allow_sec else x_range
    eff_vert_tol = 15   if allow_sec else 40
    for label in labels:
        near = _near_elements(
            elements, label, vert_tol=eff_vert_tol,
            direction="below",
            require_col=(eff_x_range is None),
            allow_secondary=allow_sec,
        )
        near.sort(key=lambda t: -t[1])
        for val_el, spatial_conf in near[:8]:
            if eff_x_range and not (eff_x_range[0] <= val_el.x1 <= eff_x_range[1]):
                continue
            tokens = _money_tokens(val_el.content)
            if not tokens:
                continue
            n = len(tokens)
            for pos, tok in enumerate(tokens):
                if tok in seen_vals:
                    continue
                seen_vals.add(tok)
                pos_note = f"token {pos+1}/{n}" if n > 1 else "only value"
                strength = 0.78 if spatial_conf >= 0.79 else 0.70
                conf = _confidence(
                    strength, _region_mult(val_el),
                    font_bonus=_font_bonus(val_el),
                )
                candidates.append(Candidate(
                    value=tok,
                    source_text=f"{label.content[:50]} → {val_el.content[:60]}",
                    page=val_el.page,
                    bbox=[val_el.x1, val_el.y1, val_el.x2, val_el.y2],
                    confidence=conf,
                    match_reason=f"label-adj[{pos_note}] near '{label.content[:35]}'",
                    source_type="label_adjacent",
                    region=val_el.region, is_primary=val_el.is_primary,
                    is_fallback=False,
                ))

    # Strategy B: x-range per-label scan (state boxes)
    if x_range:
        x_lo, x_hi = x_range
        for label in labels:
            ref_y = label.y1
            for el in elements:
                if el.page != page:
                    continue
                if not el.is_primary and not allow_sec:
                    continue
                if not (x_lo <= el.x1 <= x_hi):
                    continue
                if abs(el.y1 - ref_y) > 60:
                    continue
                for tok in _money_tokens(el.content):
                    if tok not in seen_vals:
                        seen_vals.add(tok)
                        conf = _confidence(
                            0.80, _region_mult(el),
                            font_bonus=_font_bonus(el),
                        )
                        candidates.append(Candidate(
                            value=tok, source_text=el.content[:80],
                            page=el.page, bbox=[el.x1, el.y1, el.x2, el.y2],
                            confidence=conf,
                            match_reason=f"x-range[{x_lo:.0f},{x_hi:.0f}] y≈{ref_y:.0f}",
                            source_type="spatial",
                            region=el.region, is_primary=el.is_primary,
                            is_fallback=False,
                        ))

    candidates.sort(key=lambda c: (-c.confidence, -float(c.value or 0)))
    return candidates[:6]


def _extract_name_field(
    elements: list[Element],
    label_patterns: list[str],
    page: int,
    *,
    name_test,          # callable(str) → bool
    heuristic_scan: bool = True,
    vert_tol: int = 60,
) -> list[Candidate]:
    """
    Generic name extractor with pluggable name_test.
    Searches ABOVE the label (in PDF coords = visually below the label on the page,
    since y increases upward — but for W-2 names the value IS below the label visually).
    Actually uses bidirectional within vert_tol with col constraint.
    """
    candidates: list[Candidate] = []
    seen: set[str] = set()

    labels = _label_elements(elements, label_patterns, page, primary_only=True)
    allow_sec = False
    if not labels:
        labels = _label_elements(elements, label_patterns, page, primary_only=False)
        allow_sec = True

    for label in labels:
        near = _near_elements(
            elements, label, vert_tol=vert_tol,
            direction="below",   # W-2 name values appear below their labels
            require_col=True, allow_secondary=allow_sec,
        )
        near.sort(key=lambda t: -t[1])
        for val_el, spatial_conf in near[:8]:
            txt = val_el.content.strip()
            if len(txt) < 2 or txt in seen:
                continue
            seen.add(txt)
            name_ok = name_test(txt)
            shape_bonus = 0.12 if name_ok else 0.0
            strength = 0.78 if spatial_conf >= 0.79 else 0.70
            conf = _confidence(
                strength, _region_mult(val_el),
                shape_bonus=shape_bonus,
                font_bonus=_font_bonus(val_el),
            )
            candidates.append(Candidate(
                value=txt,
                source_text=f"{label.content[:50]} → {txt[:70]}",
                page=val_el.page, bbox=[val_el.x1, val_el.y1, val_el.x2, val_el.y2],
                confidence=conf,
                match_reason=(
                    f"label-adj near '{label.content[:35]}'"
                    + (" +name-shaped" if name_ok else "")
                ),
                source_type="label_adjacent",
                region=val_el.region, is_primary=val_el.is_primary,
                is_fallback=False,
            ))

    # Heuristic fallback: scan primary (or secondary when allow_sec) for name-shaped elements
    if heuristic_scan:
        for el in elements:
            if el.page != page or el.content in seen:
                continue
            if not el.is_primary and not allow_sec:
                continue
            if name_test(el.content):
                seen.add(el.content)
                conf = _confidence(
                    0.45, _region_mult(el),
                    fallback_penalty=0.10,
                )
                candidates.append(Candidate(
                    value=el.content, source_text=el.content[:80],
                    page=el.page, bbox=[el.x1, el.y1, el.x2, el.y2],
                    confidence=conf,
                    match_reason="heuristic:name-scan",
                    source_type="heuristic",
                    region=el.region, is_primary=el.is_primary,
                    is_fallback=True,
                ))

    candidates.sort(key=lambda c: -c.confidence)
    return candidates[:8]


def _extract_address_field(
    elements: list[Element],
    label_patterns: list[str],
    page: int,
) -> list[Candidate]:
    """
    Address extractor:
      1. Collect spatially-near elements (bidirectional, large vert_tol).
      2. Boost elements containing a ZIP code.
      3. Build a combined "street, city/state/zip" candidate when a y-adjacent pair exists.
    """
    candidates: list[Candidate] = []
    seen: set[str] = set()

    _ADDR_FILTER = re.compile(
        r"employee|employer|first\s+name|last\s+name|address\s+and\s+zip|"
        r"^\d+\s+of\s+\d+$|social\s+security|wages|federal|import\s+code|"
        r"copy\s+[a-z2]|department\s+of|form\s+w|^\-{3,}|^\d+\.\d{2}|"
        r"^\d+$|"                                    # bare numbers (control codes like "16678")
        r"^\d{7,}|"                                  # long digit-starting strings (control numbers)
        r"^[X\*]{3}-[X\*]{2}-\d{4}",               # masked SSN (XXX-XX-4426 or ***-**-4426)
        re.IGNORECASE,
    )

    labels = _label_elements(elements, label_patterns, page, primary_only=True)
    allow_sec = False
    if not labels:
        labels = _label_elements(elements, label_patterns, page, primary_only=False)
        allow_sec = True

    for label in labels:
        near = _near_elements(
            elements, label, vert_tol=100,
            direction="both", require_col=True, allow_secondary=allow_sec,
        )
        near.sort(key=lambda t: -t[1])
        count = 0
        for val_el, spatial_conf in near:
            if count >= 10:
                break
            txt = val_el.content.strip()
            if len(txt) <= 5 or txt in seen:
                continue
            if _ADDR_FILTER.search(txt):
                continue
            seen.add(txt)
            has_zip = bool(_ZIP_RE.search(txt))
            shape_bonus = 0.12 if has_zip else 0.0
            strength = 0.78 if spatial_conf >= 0.79 else 0.70
            conf = _confidence(
                strength, _region_mult(val_el),
                shape_bonus=shape_bonus,
                font_bonus=_font_bonus(val_el),
            )
            candidates.append(Candidate(
                value=txt,
                source_text=f"{label.content[:50]} → {txt[:70]}",
                page=val_el.page, bbox=[val_el.x1, val_el.y1, val_el.x2, val_el.y2],
                confidence=conf,
                match_reason=(
                    f"addr-adj near '{label.content[:35]}'"
                    + (" +ZIP" if has_zip else "")
                ),
                source_type="label_adjacent",
                region=val_el.region, is_primary=val_el.is_primary,
                is_fallback=False,
            ))
            count += 1

    # Combine street + city/state/ZIP when y-adjacent (within 30 units, same region)
    candidates.sort(key=lambda c: -c.confidence)
    zip_cands    = [c for c in candidates if _ZIP_RE.search(c.value)]
    if zip_cands:
        city = zip_cands[0]
        adjacent_streets = [
            c for c in candidates
            if c is not city
            and abs(c.bbox[1] - city.bbox[1]) <= 30
            and c.region == city.region
            and _STREET_RE.match(c.value)
        ]
        if adjacent_streets:
            street = min(adjacent_streets, key=lambda c: abs(c.bbox[1] - city.bbox[1]))
            combined_val = f"{street.value}, {city.value}"
            if combined_val not in seen:
                candidates.insert(0, Candidate(
                    value=combined_val,
                    source_text=f"{street.value} + {city.value}",
                    page=street.page, bbox=street.bbox,
                    confidence=min(city.confidence + 0.05, 0.95),
                    match_reason="combined:street+city/ZIP",
                    source_type="combined",
                    region=street.region, is_primary=street.is_primary,
                    is_fallback=False,
                ))

    return candidates[:6]


def _extract_ssn(elements: list[Element]) -> list[Candidate]:
    return _extract_regex_field(elements, _SSN_RE, "SSN", base_strength=0.92)


def _extract_ein(elements: list[Element]) -> list[Candidate]:
    return _extract_regex_field(elements, _EIN_RE, "EIN", base_strength=0.92)


def _extract_state_id(
    elements: list[Element], page: int, exclude_ein: str | None = None
) -> list[Candidate]:
    """
    Extract Box 15 employer state ID (XX-XXXXXXX format, state-specific number).

    Three strategies, in order:
      A. EIN embedded within a box-15 label element itself
         (handles "15 State CA 12-3456789" as a single combined element)
      B. EIN in elements spatially adjacent to the box-15 label
      C. Global EIN fallback — all EINs except the known federal EIN
         (ensures the field is populated even when the label text doesn't match)
    """
    label_patterns = [
        r"15\s+state",
        r"employer.{0,20}state\s+id",
        r"state\s+id\s+no",
    ]
    labels = _label_elements(elements, label_patterns, page, primary_only=True)
    allow_sec = False
    if not labels:
        labels = _label_elements(elements, label_patterns, page, primary_only=False)
        allow_sec = True

    candidates: list[Candidate] = []
    seen: set[str] = set()
    eff_vert_tol = 15 if allow_sec else 30

    def _add(val: str, el: Element, conf: float, reason: str) -> None:
        if val in seen or val == exclude_ein:
            return
        seen.add(val)
        candidates.append(Candidate(
            value=val, source_text=el.content[:80],
            page=el.page, bbox=[el.x1, el.y1, el.x2, el.y2],
            confidence=conf, match_reason=reason,
            source_type="regex", region=el.region,
            is_primary=el.is_primary, is_fallback=allow_sec,
        ))

    # Strategy A: EIN embedded in the label element itself
    for label in labels:
        for m in _EIN_RE.finditer(label.content):
            _add(m.group(1), label,
                 _confidence(0.80, _region_mult(label)),
                 "embedded:box15-state-id")

    # Strategy B: EIN in adjacent elements below the label
    for label in labels:
        near = _near_elements(elements, label, vert_tol=eff_vert_tol, direction="below",
                              require_col=False, allow_secondary=allow_sec)
        for val_el, spatial_conf in near[:6]:
            m = _EIN_RE.search(val_el.content)
            if not m:
                continue
            conf = _confidence(0.82, _region_mult(val_el), font_bonus=_font_bonus(val_el))
            _add(m.group(1), val_el, min(conf * spatial_conf, 0.98), "label:box15-state-id")

    # Strategy C: global EIN scan — exclude the federal EIN, lower confidence
    if not candidates:
        for c in _extract_ein(elements):
            if c.value != exclude_ein and c.value not in seen:
                seen.add(c.value)
                candidates.append(Candidate(
                    value=c.value, source_text=c.source_text,
                    page=c.page, bbox=c.bbox,
                    confidence=min(c.confidence * 0.70, 0.60),
                    match_reason="fallback:global-ein",
                    source_type="regex", region=c.region,
                    is_primary=c.is_primary, is_fallback=True,
                ))

    return sorted(candidates, key=lambda c: -c.confidence)[:4]


def _extract_year(elements: list[Element]) -> list[Candidate]:
    """Year: regex scan, prefer page 1 primary region, most-recent year first."""
    seen: dict[str, Candidate] = {}
    for el in elements:
        for m in _YEAR_RE.finditer(el.content):
            yr = m.group(1)
            rm = _region_mult(el) if el.page == 1 else 0.60
            conf = _confidence(0.88, rm)
            if yr not in seen or conf > seen[yr].confidence:
                seen[yr] = Candidate(
                    value=yr, source_text=el.content[:80],
                    page=el.page, bbox=[el.x1, el.y1, el.x2, el.y2],
                    confidence=conf, match_reason="regex:year",
                    source_type="regex", region=el.region,
                    is_primary=el.is_primary, is_fallback=False,
                )
    return sorted(seen.values(), key=lambda c: (-c.confidence, -int(c.value)))[:3]


_VALID_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN",
    "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV",
    "NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN",
    "TX","UT","VT","VA","WA","WV","WI","WY","DC",
}
_EMBEDDED_STATE_RE = re.compile(r"\b([A-Z]{2})\b")


def _extract_state(elements: list[Element], page: int) -> list[Candidate]:
    """Extract Box 15 state abbreviation.

    Strategy A: standalone 2-letter elements (most W-2s).
    Strategy B: state code embedded within a box-15 label element
                (handles combined elements like '15 State CA 12-3456789').
    """
    seen: set[str] = set()
    results = []
    page_els = [el for el in elements if el.page == page]

    # Strategy A: standalone 2-letter element
    # Tight adjacency: word-spacing within a split label is typically < 15 PDF pts.
    # A real state-value cell is always separated from "no." by at least one full
    # sub-column (60-100+ pts), so this safely distinguishes label fragments.
    _NO_ADJ = 15
    for el in page_els:
        val = el.content.strip()
        if not (_STATE_RE.match(val) and val in _VALID_STATES and val not in seen):
            continue

        # Reject if "no." appears at word-spacing distance immediately to the right.
        # This exclusively matches the "Employer's state ID no." label fragment
        # where pdfplumber splits the label into "...state", "ID", "no." pieces.
        # A real state-abbreviation cell ("PA", "CA", etc.) is separated from any
        # "no." text by the entire width of the employer-state-ID sub-column.
        has_no_right = any(
            abs(other.y1 - el.y1) <= 8
            and 0 <= other.x1 - el.x2 <= _NO_ADJ
            and re.search(r'^\s*no\.?\b', other.content.strip(), re.I)
            for other in page_els if other is not el
        )
        if has_no_right:
            continue  # label fragment "state [XX] no." — not a real state value

        seen.add(val)
        conf = _confidence(0.80, _region_mult(el))
        results.append(Candidate(
            value=val, source_text=val, page=el.page,
            bbox=[el.x1, el.y1, el.x2, el.y2],
            confidence=conf, match_reason="regex:state-code",
            source_type="regex", region=el.region,
            is_primary=el.is_primary, is_fallback=False,
        ))

    # Strategy B: embedded state code near box-15 label
    if not results:
        label_patterns = [r"15\s+state", r"employer.{0,20}state\s+id"]
        labels = _label_elements(elements, label_patterns, page, primary_only=True)
        if not labels:
            labels = _label_elements(elements, label_patterns, page, primary_only=False)
        for label in labels:
            for m in _EMBEDDED_STATE_RE.finditer(label.content):
                val = m.group(1)
                if val not in _VALID_STATES or val in seen:
                    continue
                # Skip "ID" when it appears as part of "state ID no." label text
                ctx_before = label.content[max(0, m.start() - 8):m.start()].lower()
                ctx_after  = label.content[m.end():m.end() + 8].lower()
                if re.search(r'state\s*$', ctx_before) or re.search(r'^\s*no', ctx_after):
                    continue
                seen.add(val)
                conf = _confidence(0.70, _region_mult(label))
                results.append(Candidate(
                    value=val, source_text=label.content[:80], page=label.page,
                    bbox=[label.x1, label.y1, label.x2, label.y2],
                    confidence=conf, match_reason="embedded:box15-state",
                    source_type="regex", region=label.region,
                    is_primary=label.is_primary, is_fallback=False,
                ))

    # Strategy C: label-proximity search (covers "PA 15985369" combined elements
    # or any layout where the state code isn't a standalone 2-letter text run).
    if not results:
        lbl_patterns = [r"15\s+state\b", r"\bstate\b"]
        lbls = _label_elements(elements, lbl_patterns, page, primary_only=True)
        if not lbls:
            lbls = _label_elements(elements, lbl_patterns, page, primary_only=False)
        for label in lbls:
            near = _near_elements(
                elements, label, vert_tol=40,
                direction="below", require_col=True, allow_secondary=True,
            )
            near.sort(key=lambda t: -t[1])
            for val_el, spatial_conf in near[:6]:
                for m in _EMBEDDED_STATE_RE.finditer(val_el.content):
                    code = m.group(1)
                    if code not in _VALID_STATES or code in seen:
                        continue
                    # Skip label-fragment matches
                    ctx_before = val_el.content[max(0, m.start() - 8):m.start()].lower()
                    ctx_after  = val_el.content[m.end():m.end() + 8].lower()
                    if re.search(r'state\s*$', ctx_before) or re.search(r'^\s*no', ctx_after):
                        continue
                    seen.add(code)
                    conf = _confidence(0.68, _region_mult(val_el))
                    results.append(Candidate(
                        value=code, source_text=val_el.content[:80], page=val_el.page,
                        bbox=[val_el.x1, val_el.y1, val_el.x2, val_el.y2],
                        confidence=conf, match_reason="near-label:box15-state",
                        source_type="regex", region=val_el.region,
                        is_primary=val_el.is_primary, is_fallback=False,
                    ))

    return sorted(results, key=lambda c: -c.confidence)[:4]


def _extract_import_code(elements: list[Element], page: int) -> list[Candidate]:
    results = []
    _IC_VAL = re.compile(r"^[A-Z0-9]{4,12}$")
    labels = _label_elements(elements, [r"import\s*code"], page, primary_only=True)
    for label in labels:
        near = _near_elements(elements, label, vert_tol=30, direction="both",
                              require_col=False, allow_secondary=False)
        for val_el, spatial_conf in near[:4]:
            val = val_el.content.strip()
            # Try to extract the code portion if it's embedded
            m = re.search(r"import\s*code[:\s]+([A-Z0-9]{4,12})", val_el.content, re.I)
            code = m.group(1) if m else (val if _IC_VAL.match(val) else None)
            if code:
                conf = _confidence(0.80, _region_mult(val_el))
                results.append(Candidate(
                    value=code, source_text=val_el.content[:80],
                    page=val_el.page, bbox=[val_el.x1, val_el.y1, val_el.x2, val_el.y2],
                    confidence=conf, match_reason="label-adj:import_code",
                    source_type="label_adjacent", region=val_el.region,
                    is_primary=val_el.is_primary, is_fallback=False,
                ))
    # Also try regex scan on "Import Code: XXXXX" style elements
    _IC_RE = re.compile(r"import\s*code[:\s]+([A-Z0-9]{4,12})", re.I)
    for el in elements:
        if el.page != page:
            continue
        m = _IC_RE.search(el.content)
        if m:
            code = m.group(1)
            if not any(c.value == code for c in results):
                conf = _confidence(0.85, _region_mult(el))
                results.append(Candidate(
                    value=code, source_text=el.content[:80],
                    page=el.page, bbox=[el.x1, el.y1, el.x2, el.y2],
                    confidence=conf, match_reason="regex:import_code",
                    source_type="regex", region=el.region,
                    is_primary=el.is_primary, is_fallback=False,
                ))
    results.sort(key=lambda c: -c.confidence)
    return results[:3]


# ── Form-type detection ───────────────────────────────────────────────────────

def _detect_form_type(elements: list[Element]) -> list[Candidate]:
    seen: dict[str, Candidate] = {}
    for el in elements:
        cu = el.content.upper()
        for form, keywords in [
            ("W-2",      ["W-2", "WAGE AND TAX STATEMENT"]),
            ("1099-NEC", ["1099-NEC", "NONEMPLOYEE COMPENSATION"]),
            ("1099-INT", ["1099-INT", "INTEREST INCOME"]),
        ]:
            if any(kw in cu for kw in keywords):
                conf = _confidence(0.99, 1.0)
                if form not in seen or conf > seen[form].confidence:
                    seen[form] = Candidate(
                        value=form, source_text=el.content[:80],
                        page=el.page, bbox=[el.x1, el.y1, el.x2, el.y2],
                        confidence=conf, match_reason=f"keyword:{form}",
                        source_type="regex", region=el.region,
                        is_primary=el.is_primary, is_fallback=False,
                    )
    return sorted(seen.values(), key=lambda c: -c.confidence)


# ── W-2 orchestrator ──────────────────────────────────────────────────────────

def _extract_w2_fields(elements: list[Element]) -> CandidateMap:
    """
    Dedicated W-2 field extraction.
    Operates entirely on Element objects (already region-zoned).

    Field groupings:
      Identity:     employee_name, employee_ssn, employee_address
                    employer_name, employer_ein, employer_address
      Federal:      box_1_wages … box_8_allocated_tips
      State:        box_15_state, box_15_employer_state_id,
                    box_16_state_wages, box_17_state_income_tax
    """
    P = 1   # primary page

    result: CandidateMap = {}

    # ── Employee identity ────────────────────────────────────────────────────
    result["employee_name"] = _extract_name_field(
        elements,
        [
            r"e\s+employee.{0,20}first\s+name",   # "e Employee's first name..."
            r"e/?f\s+employee.{0,20}name",         # "e/f Employee's name, address..."
            r"first\s+name.{0,15}initial",
        ],
        P,
        name_test=_looks_like_person_name,
        vert_tol=60,
    )
    result["employee_ssn"] = _extract_ssn(elements)

    result["employee_address"] = _extract_address_field(
        elements,
        [
            r"f\s+employee.{0,15}address",
            r"e/?f\s+employee.{0,20}name.{0,20}address",  # "e/f Employee's name, address..."
            r"employee.{0,15}address\s+and\s+zip",
        ],
        P,
    )

    # ── Employer identity ────────────────────────────────────────────────────
    result["employer_name"] = _extract_name_field(
        elements,
        [r"c\s+employer.{0,15}name", r"employer.{0,15}name.*address"],
        P,
        name_test=_looks_like_org_name,   # employer names are org names
        vert_tol=60,
    )
    _all_eins = _extract_ein(elements)
    result["employer_ein"] = _all_eins
    _fed_ein = _all_eins[0].value if _all_eins else None

    result["employer_address"] = _extract_address_field(
        elements,
        [r"c\s+employer.{0,15}name", r"employer.{0,15}name.*address"],
        P,
    )

    # ── Federal boxes ────────────────────────────────────────────────────────
    # Box 1 + 2 share the same combined element — token 1/2 = wages, 2/2 = withheld.
    # Boxes 3-8 may be absent (blank on many W-2s).
    _BOX12_PATS = [
        r"1\s+wages.*tips.*other\s+comp",
        r"wages.*tips.*other.*2\s+federal",
    ]
    result["box_1_wages"]              = _extract_money_field(elements, _BOX12_PATS, P)
    result["box_2_federal_tax_withheld"] = _extract_money_field(elements, [
        r"2\s+federal\s+income\s+tax\s+withheld",
    ] + _BOX12_PATS, P)

    result["box_3_social_security_wages"] = _extract_money_field(elements, [
        r"3\s+social\s+security\s+wages",
        r"social\s+security\s+wages.*4\s+social",
    ], P)
    result["box_4_social_security_tax"] = _extract_money_field(elements, [
        r"4\s+social\s+security\s+tax",
        r"social\s+security\s+wages.*4\s+social",
    ], P)
    result["box_5_medicare_wages"] = _extract_money_field(elements, [
        r"5\s+medicare\s+wages",
        r"medicare\s+wages.*6\s+medicare",
    ], P)
    result["box_6_medicare_tax"] = _extract_money_field(elements, [
        r"6\s+medicare\s+tax\s+withheld",
        r"medicare\s+wages.*6\s+medicare",
    ], P)
    result["box_7_social_security_tips"] = _extract_money_field(elements, [
        r"7\s+social\s+security\s+tips",
        r"social\s+security\s+tips.*8\s+allocated",
    ], P)
    result["box_8_allocated_tips"] = _extract_money_field(elements, [
        r"8\s+allocated\s+tips",
        r"social\s+security\s+tips.*8\s+allocated",
    ], P)

    # ── State boxes ──────────────────────────────────────────────────────────
    # W-2 state row: MA(x≈39) | EIN(x≈68) | wages(x≈195) | tax(x≈284)
    result["box_15_state"]              = _extract_state(elements, P)
    result["box_15_employer_state_id"]  = _extract_state_id(elements, P, exclude_ein=_fed_ein)

    result["box_16_state_wages"] = _extract_money_field(elements, [
        r"16\s+state\s+wages",
        r"state\s+wages.*tips.*17\s+state",
        r"15\s+state.*employer.{0,20}state\s+id",
    ], P, x_range=(150.0, 270.0))

    result["box_17_state_income_tax"] = _extract_money_field(elements, [
        r"17\s+state\s+income\s+tax",
        r"state\s+wages.*tips.*17\s+state",
        r"15\s+state.*employer.{0,20}state\s+id",
    ], P, x_range=(270.0, 360.0))

    # ── Local boxes ───────────────────────────────────────────────────────────
    # Box 18 local wages and box 19 local income tax share the same row label.
    # x_range estimates for standard W-2 layout (right of the state columns).
    result["box_18_local_wages"] = _extract_money_field(elements, [
        r"18\s+local\s+wages",
        r"local\s+wages.*tips.*19\s+local",
    ], P, x_range=(360.0, 470.0))

    result["box_19_local_income_tax"] = _extract_money_field(elements, [
        r"19\s+local\s+income\s+tax",
        r"local\s+wages.*tips.*19\s+local",
    ], P, x_range=(470.0, 570.0))

    # Drop fields with no candidates
    return {k: v for k, v in result.items() if v}


# ── 1099-NEC / 1099-INT orchestrators ────────────────────────────────────────

def _extract_1099_nec_fields(elements: list[Element]) -> CandidateMap:
    P = 1
    return {k: v for k, v in {
        "payer_name": _extract_name_field(elements, [r"payer.{0,15}name"], P,
                                          name_test=_looks_like_org_name),
        "payer_tin":  _extract_ein(elements),
        "payer_address": _extract_address_field(elements, [r"payer.{0,15}address"], P),
        "recipient_name": _extract_name_field(elements, [r"recipient.{0,15}name"], P,
                                              name_test=_looks_like_person_name),
        "recipient_tin":  _extract_ssn(elements),
        "recipient_address": _extract_address_field(elements, [r"recipient.{0,15}address"], P),
        "box_1_nonemployee_compensation": _extract_money_field(elements, [
            r"1\s+nonemployee\s+compensation", r"nonemployee\s+comp"], P),
        "box_4_federal_tax_withheld": _extract_money_field(elements, [
            r"4\s+federal.*tax.*withheld", r"federal\s+income\s+tax\s+withheld"], P),
    }.items() if v}


def _extract_1099_int_fields(elements: list[Element]) -> CandidateMap:
    P = 1
    return {k: v for k, v in {
        "payer_name":  _extract_name_field(elements, [r"payer.{0,15}name"], P,
                                           name_test=_looks_like_org_name),
        "recipient_name": _extract_name_field(elements, [r"recipient.{0,15}name"], P,
                                              name_test=_looks_like_person_name),
        "box_1_interest_income": _extract_money_field(elements, [
            r"1\s+interest\s+income", r"interest\s+income"], P),
        "box_2_early_withdrawal_penalty": _extract_money_field(elements, [
            r"2\s+early\s+withdrawal", r"early\s+withdrawal\s+penalty"], P),
        "box_4_federal_tax_withheld": _extract_money_field(elements, [
            r"4\s+federal.*tax.*withheld"], P),
    }.items() if v}


# ── Main entry point ──────────────────────────────────────────────────────────

def extract_candidates(parsed_json: dict) -> CandidateMap:
    """
    Traverse opendataloader JSON → zone document → extract field candidates.

    Returns CandidateMap (field_name → list[Candidate]).
    All retrieval is deterministic; LLM resolves the final value from these candidates.
    """
    elements = _collect_elements(parsed_json)

    zones = _zone_document(elements)
    _assign_regions(elements, zones)

    page1 = [e for e in elements if e.page == 1]
    primary = [e for e in page1 if e.is_primary]
    logger.info(
        "candidate_extractor: %d total elements, %d page-1, %d primary-region",
        len(elements), len(page1), len(primary),
    )

    # Detect form type
    form_cands = _detect_form_type(elements)
    form_type  = form_cands[0].value if form_cands else "UNKNOWN"
    logger.info("candidate_extractor: form_type=%s", form_type)

    result: CandidateMap = {
        "form_type":   form_cands,
        "tax_year":    _extract_year(elements),
        "import_code": _extract_import_code(elements, 1),
    }

    if form_type == "W-2":
        result.update(_extract_w2_fields(elements))
    elif form_type == "1099-NEC":
        result.update(_extract_1099_nec_fields(elements))
    elif form_type == "1099-INT":
        result.update(_extract_1099_int_fields(elements))

    result = {k: v for k, v in result.items() if v}
    logger.info(
        "candidate_extractor: %d fields with candidates: %s",
        len(result), list(result.keys()),
    )
    return result
