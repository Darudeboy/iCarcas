# Матрица возможностей

Целевая ОС: **Windows 10/11 x64**.  
Дата фиксации: 2026-11-17.

Статусы утверждений:

| Статус | Значение |
|--------|----------|
| `verified_documentation` | Подтверждено официальной документацией / README / релизами |
| `verified_locally` | Проверено запуском на этой машине |
| `assumed` | Разумно ожидается, но не подтверждено локально |
| `unsupported` | Не поддерживается или запрещено политикой проекта |

Ничего со статусом `assumed` не выдаётся за `verified_locally`.

## Стек приложения

| Возможность | Выбор | Статус | Примечание |
|-------------|--------|--------|------------|
| Язык | Python ≥ 3.12 | `verified_documentation` | На машине разработчика обнаружен 3.13.5; интерпретатор с python.org предпочтителен (не Microsoft Store) |
| UI | PySide6 ≥ 6.9.2 | `verified_documentation` | Избегать 6.9.1 из‑за известных проблем отрисовки |
| Тесты | pytest | `verified_documentation` | |
| Линт | ruff | `verified_documentation` | |
| Изоляция логики от Qt | слои domain/application | `assumed` | Соблюдается архитектурой каркаса |

## App Store: ipatool

Источник: [majd/ipatool](https://github.com/majd/ipatool), MIT.

| Возможность | Статус | Примечание |
|-------------|--------|------------|
| Бинарник Windows amd64/arm64 | `verified_documentation` | Релизы на GitHub |
| `auth login` / `auth info` / `auth revoke` | `verified_documentation` | |
| 2FA при login | `verified_documentation` | Интерактивный prompt |
| Хранение сессии на Windows | `verified_documentation` | Локальный encrypted keychain/файл + `--keychain-passphrase` |
| `search` | `verified_documentation` | Есть `--format json` |
| `download` по bundle id / app id | `verified_documentation` | `-b` / `-i`, `-o` |
| `purchase` | `verified_documentation` | Лицензия перед загрузкой |
| `list-purchases` | `verified_documentation` | |
| `list-versions` / `get-version-metadata` | `verified_documentation` | Старые версии через `external-version-id` |
| Delisted / ранее купленные приложения | `verified_documentation` | Заявлено в релизах; для РФ Apple ID — только после `verified_locally` |
| ipatool 2.8.1 Windows amd64 установлен локально | `verified_locally` | `tools/libimobiledevice/ipatool.exe` |
| Реальный login / download на этой машине | ожидает пользователя | UI открывает интерактивный `ipatool auth login`; пароль в чат не передаётся |
| Передача пароля через argv из нашего UI | `unsupported` | Политика: интерактивный механизм инструмента |
| Кросс-регион: тот же Apple ID, покупки из прошлой страны | `assumed` | `list-purchases` дамп + `download` по app-id; лицензия должна остаться на аккаунте |
| Кросс-регион: найти ID в чужой витрине (iTunes Search) | `verified_locally` | UI «Найти ID по региону»; ID ≠ лицензия |
| Скачать app без лицензии на текущем ID | `unsupported` | `license is required`; `--purchase` только для текущего storefront |
| Интерактивный полный дамп покупок | `verified_documentation` | `tools/list-purchases-dump.ps1` → `packages/purchases-dump.json` |
| UI: выбор версии (`list-versions` + `external-version-id`) | `verified_documentation` | `tools/list-versions-dump.ps1` → диалог → download |
| UI: каталог Store ID + массовая загрузка | `verified_documentation` | `data/apps_catalog.txt` + `tools/bulk-download.ps1` |
| Проверка min iOS перед install | `verified_locally` | Сравнение `MinimumOSVersion` IPA и `ProductVersion` устройства |
| DPAPI Keychain passphrase (личный ПК) | `verified_documentation` | `%LOCALAPPDATA%/iCarcas/keychain_passphrase.dpapi` |
| Download retry на HTTP 504 | `verified_documentation` | `tools/download-one.ps1` |
| ToS gate | `verified_documentation` | Первый запуск; блокирует download/install |
| Diagnostics zip (redacted) | `verified_documentation` | Без cookies / passphrase / IPA |
| Portable scripts | `verified_documentation` | `scripts/run-icarcas.ps1`, `check-tools.ps1` |

## Устройство: libimobiledevice

Источник: [libimobiledevice.org](https://libimobiledevice.org/), LGPL-2.1 (библиотека).

| Возможность | Статус | Примечание |
|-------------|--------|------------|
| Платформа Windows (сборка) | `verified_documentation` | Официально через MSYS2/MinGW |
| Официальные готовые exe | `unsupported` | Официальных prebuilt нет |
| Сторонние Windows-сборки | `assumed` | Например community suite; версия/целостность — проверить локально |
| `idevice_id` — список устройств | `verified_documentation` | |
| `ideviceinfo` — сведения об устройстве | `verified_documentation` | |
| `idevicepair` — доверие/pairing | `verified_documentation` | |
| Apple USB drivers на Windows | `verified_documentation` | Обычно Apple Mobile Device Support / iTunes |
| Локальное обнаружение iPhone | `verified_locally` | 2026-11-18: UDID виден через `idevice_id`; после re-pair — `ideviceinfo` (имя «III IV», iOS 27.2.1) |
| Apple Mobile Device Support на Windows | `verified_locally` | Установлен через winget `Apple.AppleMobileDeviceSupport` 19.4.0.10 |
| Windows-сборка libimobiledevice (L1ghtmann suite-exe-21d57a9) | `verified_locally` | Распакована в `tools/libimobiledevice` |
| Pairing / Trust | `verified_locally` | После удаления устаревшего Lockdown plist и разблокировки iPhone — `idevicepair pair` SUCCESS |

## Установка: ideviceinstaller

Источник: [libimobiledevice/ideviceinstaller](https://github.com/libimobiledevice/ideviceinstaller), GPL-2.0.  
CLI 1.2.0+: subcommands (`install`, `list`, …).

| Возможность | Статус | Примечание |
|-------------|--------|------------|
| `install PATH` | `verified_documentation` | |
| Выбор устройства `-u UDID` | `verified_documentation` | |
| Внешние sinf / iTunesMetadata | `verified_documentation` | Добавлено в 1.2.0 |
| Установка FairPlay App Store IPA на не-jailbroken iPhone | `assumed` | **Критический риск MVP**; не подменять re-sign / jailbreak |
| Успех install = приложение запускается | `unsupported` | Нужна отдельная проверка пользователем |

## Цепочка успеха (раздельные факты)

| Утверждение | Статус |
|-------------|--------|
| Успешный auth ⇒ можно скачать любое приложение | `unsupported` |
| Успешный download ⇒ можно установить | `assumed` / не доказано |
| Успешный install ⇒ приложение работает | `unsupported` без подтверждения пользователя |
| Восстановление снятого с витрины приложения | проверяемый сценарий, не гарантия |

## Лицензии (кратко)

См. [dependency_licenses.md](dependency_licenses.md).

## Непроверенные предположения

1. У пользователя удастся получить рабочий набор Windows-бинарников libimobiledevice + ideviceinstaller совместимой версии.
2. IPA, скачанный ipatool (с iTunesMetadata/sinf), установится через ideviceinstaller на доверенный iPhone того же Apple ID.
3. Регион РФ Apple ID не блокирует `download`/`list-purchases` для ранее полученных приложений.
4. PySide6 актуальный wheel совместим с установленным локально Python 3.13.5.
