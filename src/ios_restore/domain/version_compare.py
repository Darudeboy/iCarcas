"""Compare dotted OS / app version strings (e.g. 17.5.1 vs 15.0)."""

from __future__ import annotations

import re


def parse_version_tuple(value: str | None) -> tuple[int, ...] | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    # Take leading dotted numeric segment (ignore suffixes like "17.5.1 (a)").
    match = re.match(r"^(\d+(?:\.\d+)*)", text)
    if not match:
        return None
    parts = match.group(1).split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def compare_versions(left: str | None, right: str | None) -> int | None:
    """Return -1 / 0 / 1 if left < / == / > right; None if either unparsable."""
    a = parse_version_tuple(left)
    b = parse_version_tuple(right)
    if a is None or b is None:
        return None
    # Pad to same length.
    width = max(len(a), len(b))
    a_pad = a + (0,) * (width - len(a))
    b_pad = b + (0,) * (width - len(b))
    if a_pad < b_pad:
        return -1
    if a_pad > b_pad:
        return 1
    return 0


def device_meets_minimum(device_os: str | None, minimum_os: str | None) -> bool | None:
    """True if device >= minimum; None if comparison impossible."""
    cmp = compare_versions(device_os, minimum_os)
    if cmp is None:
        return None
    return cmp >= 0
