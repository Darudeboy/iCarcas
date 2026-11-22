# Если что-то не работает

## Чеклист нового ПК

1. Python **3.12+** (не 3.9 / не Store)
2. Команды из **корня** репозитория (`pyproject.toml` рядом)
3. `pip install -e ".[dev]"`
4. Файлы в `tools\libimobiledevice\` + `ipatool.exe`
5. `winget install --id Apple.AppleMobileDeviceSupport -e`
6. `.\scripts\check-tools.ps1` — всё OK
7. Кабель, экран разблокирован, нажали **«Доверять»**

## Частые проблемы

| Что видите | Что сделать |
|------------|-------------|
| Нет `pyproject.toml` / `ios_restore` | Открыть папку iCarcas, заново `pip install -e ".[dev]"` |
| Устройство в Windows есть, в iCarcas нет | Шаги 4–5 выше (CLI + драйверы Apple) |
| «Нужно доверие» / Password protected | Разблокировать экран, «Доверять», снова **Найти устройство** |
| `license is required` | Приложения нет на этом Apple ID — поиск ID сам по себе не даёт скачать |

Ссылки на файлы: README → разделы «Инструменты для телефона» и «Запуск».
