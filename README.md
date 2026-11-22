# iCarcas

Скачать **свои** приложения из App Store и поставить на **iPhone / iPad**.  
Всё локально: пароли и ключ сессии никуда не уходят.

## Быстрый старт (Windows)

Работайте из папки репозитория (там, где `pyproject.toml`).

### 1. Python

Нужен **Python 3.12 или 3.13** с [python.org](https://www.python.org/downloads/) (не из Microsoft Store).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e ".[dev]"
```

Или одной командой: `.\scripts\run-icarcas.ps1`

### 2. Инструменты для телефона (обязательно)

После `git clone` их **ещё нет** — без них iCarcas не увидит устройство.

1. Скачайте [libimobiledevice (Windows)](https://github.com/L1ghtmann/libimobiledevice/releases/tag/suite-exe-21d57a9) и распакуйте файлы в `tools\libimobiledevice\`
2. Скачайте [ipatool](https://github.com/majd/ipatool/releases) (Windows) → сохраните как `tools\libimobiledevice\ipatool.exe`
3. Установите драйверы Apple:

```powershell
winget install --id Apple.AppleMobileDeviceSupport -e
```

4. Проверьте: `.\scripts\check-tools.ps1` — должно быть OK по всем пунктам.

### 3. Запуск

```powershell
.\scripts\run-icarcas.ps1
```

Подключите кабель → разблокируйте iPhone/iPad → нажмите **«Доверять»** → в углу **iOS… → Найти устройство**.

### 4. Как пользоваться

1. **iOS…** — найти устройство  
2. **Войти…** — свой Apple ID (пароль и код в консоли)  
3. Найти ID → **Скачать IPA** → **Установить на устройство**

Скачивается только то, что уже было на этом Apple ID (покупки / прошлые установки).

Подробнее при сбоях: [docs/setup.md](docs/setup.md). В приложении сверху: **Впервые здесь?** и **Справка**.

## Важно знать

- Обход чужого региона, пиратские IPA и jailbreak — **не поддерживаются**.
- Установка на устройство без джейлбрейка — «как получится»; запуск приложения iCarcas не гарантирует.
- Ключ сессии (passphrase) — не пароль Apple ID; на Windows можно сохранить локально (DPAPI).

## Документация

- [docs/setup.md](docs/setup.md) — если устройство не видно / ошибки установки  
- [docs/capability_matrix.md](docs/capability_matrix.md) — что проверено  
- [docs/architecture.md](docs/architecture.md) · [docs/dependency_licenses.md](docs/dependency_licenses.md)
