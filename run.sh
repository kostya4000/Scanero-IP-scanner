#!/usr/bin/env bash
# Scanero launcher (works from a symlink as well)
set -e
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  case "$SOURCE" in
    /*) ;;
    *) SOURCE="$DIR/$SOURCE" ;;
  esac
done
cd "$(dirname "$SOURCE")"

if ! python3 -c "import PyQt6" >/dev/null 2>&1; then
  echo "Scanero IP Сканер: не найден PyQt6."
  echo "Установите его командой:  sudo apt install python3-pyqt6"
  echo "или в виртуальном окружении:  pip install -r requirements.txt"
  exit 1
fi
exec python3 app.py "$@"
