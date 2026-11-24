# iCarcas на macOS

Цель: тот же сценарий, что на Windows — свои IPA с Apple ID на свой iPhone/iPad.

## Требования

- macOS (Apple Silicon или Intel)
- Python 3.12–3.13
- [Homebrew](https://brew.sh) для утилит телефона
- Кабель USB, «Доверять» на устройстве

## Установка

```bash
git clone https://github.com/Darudeboy/iCarcas.git
cd iCarcas
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

Утилиты для телефона:

```bash
brew install libimobiledevice ideviceinstaller
# или по подсказке из «Впервые здесь?»
```

ipatool:

```bash
./scripts/fetch-tools-macos.sh
# либо кнопка «Установить недостающее» в приложении
```

Запуск:

```bash
./scripts/run-icarcas.sh
# или: python -m ios_restore
```

## Что уже кроссплатформенно

- UI (PySide6), онбординг и справка с учётом ОС
- Ключ сессии в `~/Library/Application Support/iCarcas/` (файл 0600)
- Интерактивный вход через Terminal.app
- Фоновая загрузка через `tools/download_one.py`
- Дампы покупок/версий через Python-скрипты

## Дистрибутив `.app` / `.dmg`

Сборка **только на Mac** (или GitHub Actions `macos-14`):

```bash
./scripts/build-macos-app.sh
# → dist/iCarcas.app
# → dist/iCarcas-macos.dmg
```

CI: Actions → **Build macOS** (workflow_dispatch) или тег `v*`.

На Windows эту сборку сделать нельзя — нужен Mac/CI.

После установки DMG:
1. Перетащить `iCarcas.app` в Applications (или открыть из образа).
2. Один раз: `brew install libimobiledevice ideviceinstaller`

### Gatekeeper: «приложение повреждено»

Так macOS часто пишет про **неподписанный** скачанный `.app`/`.dmg` (не обязательно реальная порча файла).

В Terminal:

```bash
xattr -cr /Applications/iCarcas.app
open /Applications/iCarcas.app
```

Или: ПКМ по приложению → Open → Open.

Полное лечение — Apple Developer ID + notarization (пока нет). В сборке CI есть ad-hoc `codesign`.

Windows ZIP: [iCarcas-exe Releases](https://github.com/Darudeboy/iCarcas-exe/releases).

## Ограничения сейчас

- `idevice*` на машине пользователя — из Homebrew (PATH).
- Нет notarization Apple — возможен диалог Gatekeeper / «повреждено».

## Проверка

1. «Впервые здесь?» — ipatool OK, idevice_* OK (или подсказка brew).
2. Кабель → «Устройство…» → «Найти устройство».
3. «Apple ID…» → «Войти» в Terminal.
4. Скачать → установить.
