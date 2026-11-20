# iCarcas

Локальная настольная утилита (Windows / macOS) **для iOS**: загрузка оригинальных App Store-пакетов, доступных вашему Apple ID, и установка на **iPhone / iPad**. Учётные данные и ключ сессии хранятся только на этом компьютере.

```powershell
.\scripts\run-icarcas.ps1          # venv + проверки CLI + запуск
.\scripts\run-icarcas.ps1 -Light
# или:
python -m ios_restore              # тёмная тема (или сохранённая)
python -m ios_restore --light
python -m ios_restore --no-splash  # без анимации слоёв
```

Иконка: `assets/icarcas-icon.png` (окно/taskbar), `assets/favicon.ico` / `favicon.png`. При старте — splash «Загрузка…» с анимацией слоёв.

Личный portable: `.\scripts\check-tools.ps1` проверяет `tools\libimobiledevice\*.exe`.  
Откат к бэкапу перед prod-срезом: `git checkout backup/pre-prod-2026-11-20`.

## Требования

- Windows 10/11 x64 или macOS (Apple Silicon / Intel)
- **Python 3.12–3.13** с [python.org](https://www.python.org/downloads/) (на Windows — не Microsoft Store; 3.9/3.11 не подойдут)
- Каталог **`tools/libimobiledevice`** с CLI (в git **не** входит — см. ниже)
- На Windows: **Apple Mobile Device Support** (драйверы USB для iPhone/iPad)

## Установка на новый ПК (Windows)

После клонирования работайте **из корня репозитория** (там, где `pyproject.toml`), не из родительской папки.

### 1. Python и пакет

```powershell
cd путь\к\iCarcas
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
pytest
```

### 2. iOS CLI (обязательно для устройства)

Папка `tools/libimobiledevice/` в `.gitignore`: после `git clone` её **нет**. Без неё приложение не увидит iPhone/iPad (`idevice_id`) и не установит IPA.

1. Скачайте Windows-suite libimobiledevice (community):  
   [L1ghtmann suite-exe (tar.xz)](https://github.com/L1ghtmann/libimobiledevice/releases/tag/suite-exe-21d57a9)  
   Распакуйте **содержимое** в `tools\libimobiledevice\`  
   (нужны как минимум `idevice_id.exe`, `ideviceinfo.exe`, `idevicepair.exe`, `ideviceinstaller.exe` и DLL рядом).
2. Скачайте [ipatool](https://github.com/majd/ipatool/releases) (Windows amd64), положите как `tools\libimobiledevice\ipatool.exe`.
3. Проверьте:

```powershell
.\scripts\check-tools.ps1
```

### 3. Apple Mobile Device Support

Windows может показать «Apple iPad» в проводнике, но без службы **Apple Mobile Device Support** CLI обычно не работает.

```powershell
winget install --id Apple.AppleMobileDeviceSupport -e
```

Либо установите компонент вместе с iTunes / Apple Devices. Служба `Apple Mobile Device Service` должна быть **Running**.

### 4. Кабель, доверие, запуск

1. Подключите устройство USB-кабелем, **разблокируйте** экран.
2. При запросе на устройстве — **«Доверять этому компьютеру»**.
3. Запуск: `.\scripts\run-icarcas.ps1` или `python -m ios_restore`.
4. В углу **«iOS…» → Найти устройство**. Если видите UDID / «нужно доверие» — нажмите «Установить доверие» при разблокированном экране.

Краткий сценарий в UI: **iOS…** и **Войти…** → найти ID → скачать IPA → **Установить на устройство**.

## Быстрый старт (mock, без устройства)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev]"
pytest
python -m ios_restore --demo-cli
python -m ios_restore
```

`--demo-cli` прогоняет mock-сценарий без окна. Без флага открывается GUI (для реального устройства всё равно нужны CLI и драйверы выше).

## Что уже есть

- Доменные модели, FSM, коды ошибок
- Порты и mock-адаптеры (без сети и без устройства)
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
- Перед установкой сравнивается min iOS IPA с версией устройства.

См. [docs/capability_matrix.md](docs/capability_matrix.md).

## Personal / portable

- **ToS** при первом запуске — без принятия download/install закрыты.
- **Сохранить passphrase** (DPAPI) → фоновый download с ретраями на HTTP 504.
- **Диагностика…** → zip без паролей/IPA/cookies.
- Откат к тегу: `git checkout backup/pre-prod-2026-11-20` (или актуальный `backup/…`).

## Ограничения (честно)

- Установка FairPlay IPA на не-jailbroken устройство через `ideviceinstaller` — **assumed**, не гарантия запуска.
- Обход DRM, re-sign и jailbreak не реализуются.
- Сохранённый passphrase живёт только на этом Windows-пользователе (DPAPI).

## Документация

- [docs/setup.md](docs/setup.md) — первый запуск на новом ПК, зависимости, типичные ошибки
- [docs/architecture.md](docs/architecture.md)
- [docs/capability_matrix.md](docs/capability_matrix.md)
- [docs/dependency_licenses.md](docs/dependency_licenses.md)

## Удаление локальных данных демо

Удалите каталог `packages/` в рабочей директории и при необходимости `.venv/`.
