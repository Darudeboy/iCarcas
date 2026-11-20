from ios_restore.ui.brand_icon import _paint_stack, _render_static_mark, load_app_icon, icon_png_path


def test_load_app_icon_not_null(qapp) -> None:
    icon = load_app_icon()
    assert not icon.isNull()


def test_render_static_mark(qapp) -> None:
    pix = _render_static_mark(64, progress=1.0)
    assert not pix.isNull()
    assert pix.width() == 64


def test_icon_png_exists() -> None:
    path = icon_png_path()
    assert path.is_file(), f"missing brand png: {path}"
