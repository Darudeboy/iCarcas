# iCarcas

Локальная настольная утилита для Windows: загрузка оригинальных App Store-пакетов, доступных вашему Apple ID, и установка на ваш iPhone.

```powershell
python -m ios_restore          # тёмная тема (или сохранённая)
python -m ios_restore --light
```

## Требования

- Windows 10/11 x64
- Python 3.12–3.13 с [python.org](https://www.python.org/downloads/) (не Microsoft Store)
- Позже (не на этапе 1): `ipatool`, инструменты libimobiledevice / `ideviceinstaller`, драйверы Apple Mobile Device Support

## Быстрый старт (mock)

```powershell
cd D:\appstore
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
pytest
python -m ios_restore --demo-cli
python -m ios_restore
```

`--demo-cli` прогоняет mock-сценарий без окна. Без флага открывается минимальный GUI.

## Что уже есть

- Доменные модели, FSM, коды ошибок
- Порты и mock-адаптеры (без сети и без iPhone)
- `ProcessRunner` с redaction секретов
- Безопасный осмотр IPA (Zip Slip / лимиты)
- Unit-тесты и демо-UI на PySide6

## Покупки и регионы

1. **Тот же Apple ID** (раньше другой регион): «Архив покупок…» → passphrase в консоли → «Подхватить архив» → «Скачать». Работает только для приложений с лицензией на этом аккаунте.
2. **Найти ID**: «Найти ID…» — локальный каталог (в т.ч. delisted) + iTunes Lookup/Search с отсечением мусора. Скачивание на текущий ID — только если лицензия уже есть; иначе `license is required`.
3. **`--purchase`**: попытка лицензии в *текущем* storefront, не обход чужого региона.

## Версии, каталог, bulk (из IPA_Downloader)

- **Версии…** → консоль `list-versions` → **Подхватить версии** → скачать конкретный `external-version-id`.
- **Каталог ID…** — локальный `data/apps_catalog.txt` (список Store ID); мультивыбор → **Массовая загрузка** (`tools/bulk-download.ps1`, один passphrase).
- Перед установкой сравнивается min iOS IPA с версией iPhone.

См. [docs/capability_matrix.md](docs/capability_matrix.md).

## Ограничения (честно)

- Установка FairPlay IPA на не-jailbroken iPhone через `ideviceinstaller` — **assumed**, не гарантия запуска.
- Обход DRM, re-sign и jailbreak не реализуются.

## Документация

- [docs/architecture.md](docs/architecture.md)
- [docs/capability_matrix.md](docs/capability_matrix.md)
- [docs/dependency_licenses.md](docs/dependency_licenses.md)

## Удаление локальных данных демо

Удалите каталог `packages/` в рабочей директории и при необходимости `.venv/`.
