"""Normalize search queries and expand common RU bank / brand aliases."""

from __future__ import annotations

import re
import unicodedata

# If the compact query contains a key, add all values as match needles.
_ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    ("альфа", "alfa", "alfabank", "alfa-bank", "alphabank"),
    ("сбер", "sber", "sberbank"),
    ("газпром", "gazprom", "gazpromneft"),
    ("автодор", "avtodor"),
    ("звук", "zvuk"),
    ("матч", "match", "matchtv"),
    ("мэш", "mesh"),
    ("рутуб", "rutube"),
    ("вк", "vk", "vkontakte"),
    # Do NOT put bare "max" alone as a broad needle source for unrelated apps;
    # known_apps pins the messenger. Keep "макс" + "oneme" for catalog names.
    ("макс", "oneme"),
    ("ржд", "rzd"),
)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value).casefold().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact_text(value: str | None) -> str:
    return normalize_text(value).replace(" ", "")


def query_needles(query: str) -> list[str]:
    """Needles used for matching names/bundles (longest first)."""
    norm = normalize_text(query)
    compact = compact_text(query)
    needles: set[str] = set()
    if norm:
        needles.add(norm)
        needles.update(t for t in norm.split() if len(t) >= 2)
    if compact:
        needles.add(compact)
    for group in _ALIAS_GROUPS:
        # Trigger only on whole-query / whole-token match, not substring of longer words.
        triggered = False
        for key in group:
            if not key:
                continue
            if compact == key or key in norm.split():
                triggered = True
                break
            # Longer keys may appear inside compact query (alfabank).
            if len(key) >= 4 and key in compact:
                triggered = True
                break
        if triggered:
            needles.update(group)
    return sorted({n for n in needles if n}, key=len, reverse=True)


def needle_in_text(needle: str, text_norm: str, text_compact: str) -> bool:
    """Match needle against text; short needles require whole-word hits."""
    if not needle:
        return False
    if len(needle) <= 3:
        if text_compact == needle:
            return True
        # Whole word in normalized text (max !∈ maxim, novelmax).
        return (
            re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", text_norm, flags=re.UNICODE)
            is not None
        )
    return needle in text_norm or needle in text_compact


def text_matches_needles(text: str | None, needles: list[str]) -> bool:
    hay = normalize_text(text)
    hay_compact = compact_text(text)
    if not hay and not hay_compact:
        return False
    for needle in needles:
        if len(needle) < 2:
            continue
        if needle_in_text(needle, hay, hay_compact):
            return True
    return False


def relevance_score(
    *,
    query: str,
    display_name: str | None,
    bundle_id: str | None = None,
    store_id: str | None = None,
    seller_name: str | None = None,
    source_boost: int = 0,
) -> int:
    """Higher is better. 0 = weak / unrelated to query tokens."""
    needles = query_needles(query)
    if not needles:
        return source_boost
    name = normalize_text(display_name)
    name_c = compact_text(display_name)
    bundle = normalize_text(bundle_id).replace(" ", ".")
    bundle_c = compact_text(bundle_id)
    seller = normalize_text(seller_name)
    q_c = compact_text(query)
    score = source_boost

    if store_id and q_c.isdigit() and store_id == q_c:
        score += 1000
    if q_c and q_c == name_c:
        score += 400
    elif q_c and len(q_c) >= 4 and name_c.startswith(q_c):
        score += 200
    elif q_c and len(q_c) < 4 and (name == q_c or name.startswith(q_c + " ")):
        # Short queries: only whole-word prefix in normalized name ("max …"),
        # never compact startswith ("maxuc").
        score += 200

    matched = 0
    for needle in needles:
        hit = False
        if needle_in_text(needle, name, name_c):
            score += 80 if len(needle) >= 4 else 50
            hit = True
        if bundle and needle_in_text(needle, bundle, bundle_c):
            # Bundle hits are strong (ru.oneme.app / oneme).
            score += 120 if len(needle) >= 4 else 60
            hit = True
        if seller and needle_in_text(needle, seller, compact_text(seller_name)):
            score += 25
            hit = True
        if hit:
            matched += 1

    if matched == 0:
        if score > 0:
            return score
        return 0 if source_boost == 0 else max(1, source_boost // 4)
    score += matched * 10
    return score
