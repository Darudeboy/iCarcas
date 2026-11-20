# Первый запуск на новом ПК

Краткий чеклист для GitHub / GitVerse: что нужно поставить вручную и какие сбои типичны.

## Зависимости (не приезжают с `git clone`)

| Что | Зачем | Как получить |
|-----|--------|--------------|
| Python **3.12–3.13** | сам iCarcas (`requires-python`) | [python.org](https://www.python.org/downloads/), не Microsoft Store |
| `tools/libimobiledevice/*.exe` | поиск устройства, Trust, установка IPA | community suite + `ipatool` (см. README) |
| **Apple Mobile Device Support** (Windows) | USB / usbmuxd для iPhone и iPad | `winget install --id Apple.AppleMobileDeviceSupport -e` |

Каталог `tools/libimobiledevice/` в `.gitignore`. Пока `.\scripts\check-tools.ps1` не пишет «Все CLI на месте», кнопки устройства и install не заработают — даже если Windows уже показывает iPad в проводнике.

## Порядок

1. Клонировать репозиторий, открыть **корень** (есть `pyproject.toml`).
2. Создать `.venv` на Python 3.12+, `pip install -e ".[dev]"`.
3. Распаковать libimobiledevice suite + положить `ipatool.exe` в `tools\libimobiledevice\`.
4. Установить Apple Mobile Device Support; служба должна быть Running.
5. Кабель → разблокировать iPhone/iPad → «Доверять» → в UI **iOS… → Найти устройство**.

## Типичные проблемы

| Симптом | Причина |
|---------|---------|
| `neither 'setup.py' nor 'pyproject.toml' found` | команды из родительской папки, не из корня репо |
| `No module named 'ios_restore'` / `PySide6` | пакет не установлен в venv (`pip install -e ".[dev]"`) |
| Python 3.9 / 3.11 | версия ниже 3.12 — поставьте 3.12+ |
| Устройство «не видно» в iCarcas, но есть в Windows | нет CLI в `tools/libimobiledevice` и/или нет Apple Mobile Device Support |
| `Password protected` / «нужно доверие» | экран заблокирован или не нажали «Доверять» |
| `idevice_id` пустой после установки драйверов | переподключить кабель, перезапустить Apple Mobile Device Service, снова «Найти устройство» |

## Что не является багом UI

- Большое пустое поле на первой странице «Знакомство» — это текст онбординга, не splash.
- Splash со слоями идёт **до** главного окна; знакомство открывается уже после него.
