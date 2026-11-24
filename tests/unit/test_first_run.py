from ios_restore.ui import first_run


def test_what_you_need_mentions_cable_and_apple_id() -> None:
    text = first_run.what_you_need()
    assert "кабель" in text.casefold() or "USB" in text
    assert "Apple ID" in text


def test_first_connection_has_ordered_steps() -> None:
    text = first_run.first_connection_steps()
    assert "Шаг A" in text
    assert "Шаг B" in text
    assert "Телефон" in text
    assert "Apple ID" in text


def test_help_html_includes_platform() -> None:
    html = first_run.help_html()
    assert first_run.platform_label() in html
