from ios_restore.domain.search_query import (
    query_needles,
    relevance_score,
    text_matches_needles,
)


def test_alfabank_needles_include_cyrillic() -> None:
    needles = query_needles("Alfabank")
    assert any(n == "альфа" or n == "alfabank" for n in needles)
    assert text_matches_needles("Альфа-Банк (Оригинал)", needles)


def test_max_needles_are_strict() -> None:
    needles = query_needles("MAX")
    assert "max" in needles
    # bare max must not pull in "maxim" via substring
    assert not text_matches_needles("Такси Maxim", needles)
    assert text_matches_needles("Макс (Max)", needles)


def test_relevance_filters_noise() -> None:
    good = relevance_score(
        query="Alfabank",
        display_name="Альфа-Банк (Kluch)",
        bundle_id=None,
        store_id="6746730236",
    )
    noise = relevance_score(
        query="Alfabank",
        display_name="Instagram",
        bundle_id="com.burbn.instagram",
        store_id="389801252",
    )
    assert good > 0
    assert noise == 0


def test_numeric_store_id_boost() -> None:
    score = relevance_score(
        query="353127685",
        display_name="Альфа-Банк",
        store_id="353127685",
    )
    assert score >= 1000
