# Архитектура

Целевая ОС: Windows 10/11. Приложение локальное: UI на ПК, операции с App Store и устройством (iPhone/iPad) через внешние CLI.

## Слои

```
UI (PySide6)
  → Application Services
    → Domain (models, ports, FSM)
    → Infrastructure (ProcessRunner, adapters, logging)
```

Бизнес-логика и FSM не импортируют PySide6.

## Модули

| Пакет | Назначение |
|-------|------------|
| `ios_restore.domain` | Модели, коды ошибок, порты, переходы состояний |
| `ios_restore.application` | Сервисы: окружение, устройство, auth, download, install; оркестрация сценария |
| `ios_restore.infrastructure` | ProcessRunner, registry инструментов, mock/реальные адаптеры, inspector IPA, логирование |
| `ios_restore.ui` | Окно, view-model, фоновые workers |

## Поток MVP (mock на этапе 1)

1. Проверка окружения (mock: инструменты «найдены»).
2. Обнаружение устройства (mock: одно устройство).
3. Auth (mock: успех без секретов).
4. Download (mock: путь к фиктивному пакету + PackageInfo).
5. Подтверждение установки пользователем.
6. Install (mock: успех инструмента установки).
7. Показ результата без формулировки «приложение работает».

## Внешние инструменты (позже)

| Роль | Инструмент |
|------|------------|
| App Store | `ipatool` |
| Устройство | `idevice_id`, `ideviceinfo`, `idevicepair` |
| Установка | `ideviceinstaller` |

Все вызовы — через `ProcessRunner` (`shell=False`, allowlist env, redaction, timeout, cancel).

## Безопасность

- Секреты не в моделях `repr`, логах, fixtures, diagnostic archive.
- Пароль Apple ID не передаётся через argv нашего кода.
- IPA считается недоверенным входом (Zip Slip, лимиты распаковки).
