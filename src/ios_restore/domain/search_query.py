"""Normalize search queries, aliases, and relevance ranking."""

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
    # Не путать с английским Mesh*: только школа / mes.
    ("мэш", "mes", "дневникмэш", "журналмэш", "библиотекамэш"),
    ("рутуб", "rutube"),
    ("вк", "vk", "vkontakte"),
    # Do NOT put bare "max" alone as a broad needle source for unrelated apps;
    # known_apps pins the messenger. Keep "макс" + "oneme" for catalog names.
    ("макс", "oneme"),
    ("ржд", "rzd"),
)

# Extra App Store search strings when the user types a short brand.
_SEARCH_EXPAND: dict[str, tuple[str, ...]] = {
    "мэш": ("Дневник МЭШ", "Журнал МЭШ", "Библиотека МЭШ", "Колледж МЭШ", "МЭШ школа"),
    "mes": ("Дневник МЭШ", "Журнал МЭШ", "Библиотека МЭШ"),
    "сбер": ("Сбербанк", "Sberbank"),
    "альфа": ("Альфа-Банк", "Alfa-Bank"),
    "матч": ("Матч ТВ", "Match TV"),
    "звук": ("Звук", "Zvuk"),
    "ржд": ("РЖД Пассажирам", "RZD"),
    "вк": ("ВКонтакте", "VK"),
    "рутуб": ("Rutube", "RuTube"),
}

_CYR_TO_LAT = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
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


def has_cyrillic(value: str | None) -> bool:
    return bool(re.search(r"[а-яё]", (value or "").casefold()))


def transliterate_cyr_to_lat(value: str) -> str:
    """Rough RU→LAT for alternate iTunes queries (not for loose scoring)."""
    raw = normalize_text(value)
    if not raw:
        return ""
    return raw.translate(_CYR_TO_LAT)


def is_local_bundle(bundle_id: str | None) -> bool:
    b = (bundle_id or "").casefold().replace(" ", "")
    if not b:
        return False
    return bool(
        re.match(r"^(ru|by|kz|ua|su)\.", b)
        or ".ru." in b
        or b.startswith("com.yandex")
        or b.startswith("com.vk")
        or b.startswith("com.sber")
    )


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


def search_query_variants(term: str) -> list[str]:
    """Queries to send to iTunes: original + brand expansions + transliteration."""
    cleaned = (term or "").strip()
    if not cleaned:
        return []
    variants: list[str] = [cleaned]
    q = compact_text(cleaned)
    for key, extras in _SEARCH_EXPAND.items():
        if q == key or key in normalize_text(cleaned).split():
            variants.extend(extras)
    lat = transliterate_cyr_to_lat(cleaned)
    if lat and lat not in {v.casefold() for v in variants}:
        # Only add if it still looks like a brand (not empty / too short noise).
        if len(compact_text(lat)) >= 2:
            variants.append(lat)

    seen: set[str] = set()
    out: list[str] = []
    for item in variants:
        key = item.casefold().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


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
    seller_c = compact_text(seller_name)
    q_c = compact_text(query)
    q_norm = normalize_text(query)
    score = source_boost

    if store_id and q_c.isdigit() and store_id == q_c:
        return source_boost + 1000

    if q_c and q_c == name_c:
        score += 400
    elif q_c and len(q_c) >= 4 and name_c.startswith(q_c):
        score += 200
    elif q_c and len(q_c) < 4 and (name == q_c or name.startswith(q_c + " ")):
        score += 200

    name_hits = 0
    bundle_hits = 0
    seller_hits = 0
    matched_needles = 0
    for needle in needles:
        hit = False
        if needle_in_text(needle, name, name_c):
            score += 100 if len(needle) >= 4 else 55
            name_hits += 1
            hit = True
        if bundle and needle_in_text(needle, bundle, bundle_c):
            score += 130 if len(needle) >= 4 else 70
            bundle_hits += 1
            hit = True
        if seller and needle_in_text(needle, seller, seller_c):
            score += 20
            seller_hits += 1
            hit = True
        if hit:
            matched_needles += 1

    # Seller-only = noise (random studio name contains a token).
    if name_hits == 0 and bundle_hits == 0 and seller_hits > 0:
        return 0

    # Short query: must touch title or a meaningful bundle.
    if len(q_c) <= 4 and name_hits == 0 and bundle_hits == 0:
        return 0

    # Multi-word query: prefer titles that cover more tokens.
    tokens = [t for t in q_norm.split() if len(t) >= 2]
    if len(tokens) >= 2:
        covered = sum(1 for t in tokens if needle_in_text(t, name, name_c))
        if covered == 0 and bundle_hits == 0:
            return 0
        score += covered * 40
        if covered == len(tokens):
            score += 80

    # Script affinity: Cyrillic query → Cyrillic or local-bundle apps first.
    if has_cyrillic(query):
        local = is_local_bundle(bundle_id)
        if not has_cyrillic(display_name) and not local:
            # Latin-only foreign apps matching via alias (mesh←мэш, match←матч).
            return 0
        if has_cyrillic(display_name):
            score += 60
        if local:
            score += 40

    # «МЭШ» school boost (after latin Mesh already zeroed by script rule).
    if q_c in {"мэш", "mes"} or "мэш" in needles:
        if "мэш" in name or "мэш" in name_c or is_local_bundle(bundle_id):
            score += 200

    if matched_needles == 0:
        if score > source_boost:
            return score
        return 0 if source_boost == 0 else max(1, source_boost // 4)

    score += matched_needles * 12
    return score


def trim_by_relevance[T](
    scored: list[tuple[int, T]],
    *,
    keep_sources: tuple[str, ...] = ("known", "catalog"),
) -> list[tuple[int, T]]:
    """Drop long tail far below the best hit (keeps lists scannable)."""
    if not scored:
        return []
    best = max(s for s, _ in scored)
    floor = max(50, int(best * 0.18))
    kept: list[tuple[int, T]] = []
    for score, item in scored:
        source = getattr(item, "source", "") or ""
        if source.startswith(keep_sources) or score >= floor:
            kept.append((score, item))
    return kept
