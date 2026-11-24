# iCarcas

Скачать **свои** приложения из App Store и поставить на **iPhone / iPad**.  
Локально: пароли и ключ сессии никуда не уходят.  
Клиентам без Python:
- **Windows:** [iCarcas-exe Releases](https://github.com/Darudeboy/iCarcas-exe/releases) (ZIP)
- **Mac:** `.app` / `.dmg` — [iCarcas Releases](https://github.com/Darudeboy/iCarcas/releases) или `./scripts/build-macos-app.sh` на Mac / Actions **Build macOS**

**Первое подключение:** [docs/client-first-run.md](docs/client-first-run.md) · **macOS:** [docs/macos.md](docs/macos.md)

## Быстрый старт — Windows

Работайте из папки репозитория (там, где `pyproject.toml`).

### 1. Python

Нужен **Python 3.12 или 3.13** с [python.org](https://www.python.org/downloads/) (не из Microsoft Store).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e ".[dev]"
```

Или: `.\scripts\run-icarcas.ps1`

### 2. Инструменты для телефона

1. [libimobiledevice (Windows)](https://github.com/L1ghtmann/libimobiledevice/releases/tag/suite-exe-21d57a9) → `tools\libimobiledevice\`
2. [ipatool](https://github.com/majd/ipatool/releases) → `tools\libimobiledevice\ipatool.exe`
3. Драйверы: `winget install --id Apple.AppleMobileDeviceSupport -e`
4. Проверка: `.\scripts\check-tools.ps1`

В приложении то же делает **«Впервые здесь?»**.

### 3. Запуск

```powershell
.\scripts\run-icarcas.ps1
```

## Быстрый старт — macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
brew install libimobiledevice ideviceinstaller
./scripts/fetch-tools-macos.sh
./scripts/run-icarcas.sh
```

Подробности: [docs/macos.md](docs/macos.md).

## Как пользоваться (оба ОС)

1. **Впервые здесь?** — подготовка компьютера  
2. Кабель → «Доверять» → **Телефон… → Найти телефон**  
3. **Apple ID… → Войти** (пароль и код в отдельном окне)  
4. Найти ID → **Скачать** → **Установить на устройство**

Скачивается только то, что уже было на этом Apple ID.

## Важно

- Обход чужого региона, пиратские IPA и jailbreak — **не поддерживаются**.
- Ключ сессии (passphrase) — не пароль Apple ID; хранится только локально.

## Документация

- [docs/client-first-run.md](docs/client-first-run.md) — путь для клиента  
- [docs/macos.md](docs/macos.md) — Mac  
- [docs/setup.md](docs/setup.md) — сбои на Windows  
- [docs/architecture.md](docs/architecture.md) · [docs/capability_matrix.md](docs/capability_matrix.md)
