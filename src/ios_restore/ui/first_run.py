"""Client-facing first-connection checklist (Windows / macOS)."""

from __future__ import annotations

import sys


def platform_label() -> str:
    if sys.platform == "darwin":
        return "macOS"
    if sys.platform == "win32":
        return "Windows"
    return "Linux"


def what_you_need() -> str:
    """What the client must have before the first successful install."""
    lines = [
        "Что понадобится от вас",
        "",
        "1. Компьютер — Windows или Mac.",
        f"   Сейчас запущена сборка для: {platform_label()}.",
        "2. iPhone или iPad и обычный кабель USB "
        "(тот, которым заряжаете устройство).",
        "3. Ваш Apple ID (почта) и пароль — только свой аккаунт.",
        "4. Телефон под рукой: разблокировать экран и нажать «Доверять».",
        "5. Код подтверждения из SMS или с другого устройства Apple "
        "(если включена двухфакторная защита).",
        "",
        "Пароль и ключ сессии остаются на этом компьютере и никуда не отправляются.",
    ]
    if sys.platform == "win32":
        lines.extend(
            [
                "",
                "Эта сборка — Windows (ZIP iCarcas-exe из Releases).",
                "На Windows один раз нужны драйверы Apple "
                "(кнопка «Впервые здесь?» поставит их сама, если можно).",
                "",
                "На Mac ставят .app / .dmg из Releases iCarcas "
                "(не этот ZIP) — см. docs/macos.md.",
            ]
        )
    elif sys.platform == "darwin":
        lines.extend(
            [
                "",
                "Вы на Mac: .app / .dmg (не Windows ZIP).",
                "Отдельные драйверы Apple не ставятся.",
                "Если телефон не находится — «Впервые здесь?» докачает ipatool; "
                "утилиты для телефона: brew install libimobiledevice ideviceinstaller "
                "(программа покажет команду).",
            ]
        )
    return "\n".join(lines)


def first_connection_steps() -> str:
    """Ordered path for the first successful session."""
    return "\n".join(
        [
            "Первое подключение — по шагам",
            "",
            "Шаг A. Подготовка компьютера",
            "• Откройте «Впервые здесь?» (вверху окна).",
            "• Нажмите «Установить недостающее» и дождитесь OK.",
            "",
            "Шаг B. Телефон",
            "• Кабель USB → разблокируйте экран.",
            "• На телефоне: «Доверять этому компьютеру».",
            "• В углу iCarcas: «Телефон…» → «Найти телефон» (кнопка станет зелёной).",
            "",
            "Шаг C. Apple ID",
            "• «Apple ID…» → «Войти».",
            "• В отдельном окне: почта, пароль, код из SMS — так и должно быть.",
            "• Когда вход успешен, кнопка станет зелёной.",
            "",
            "Шаг D. Приложение",
            "• Найдите нужное → «Скачать» → «Установить на устройство».",
            "",
            "Скачивается только то, что уже было на этом Apple ID "
            "(покупки или прошлые установки).",
        ]
    )


def help_html() -> str:
    need = what_you_need().replace("\n", "<br/>")
    steps = first_connection_steps().replace("\n", "<br/>")
    return f"""
<p><b>iCarcas</b> ставит на ваш iPhone или iPad приложения, которые уже были
на <b>вашем</b> Apple ID. Работает на <b>{platform_label()}</b>.
Пароли никуда не отправляются.</p>

<h3>Что понадобится</h3>
<p>{need}</p>

<h3>Первое подключение</h3>
<p>{steps}</p>

<p>Если телефон не находится — снова «Впервые здесь?».
Просто найти название в поиске — ещё не значит, что можно скачать.</p>
"""
