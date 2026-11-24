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

## Ограничения сейчас

- Готовый `.app` / DMG в Releases ещё не публикуется (Windows ZIP есть в iCarcas-exe).
- `idevice*` ожидаются из Homebrew (PATH) или из `tools/libimobiledevice/`.
- Ярлык на рабочий стол — пока в основном Windows; на Mac удобнее Dock / скрипт запуска.

## Проверка

1. «Впервые здесь?» — ipatool OK, idevice_* OK (или подсказка brew).
2. Кабель → «Телефон…» → «Найти телефон».
3. «Apple ID…» → «Войти» в Terminal.
4. Скачать → установить.
