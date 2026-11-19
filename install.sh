#!/usr/bin/env bash
# Install Scanero IP scanner for the current user (no root required).
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"

if dpkg-query -W -f='${Status}' scanero-ip-scanner 2>/dev/null | grep -q "install ok installed"; then
  if [ "${SCANERO_ALLOW_USER_INSTALL:-0}" != "1" ]; then
    echo "Scanero IP Сканер уже установлен системным пакетом (.deb)."
    echo "Пользовательская установка создаст ~/.local/bin/scanero, который"
    echo "перекроет /usr/bin/scanero. Обновите пакет или удалите его:"
    echo "  sudo apt install --reinstall ./scanero-ip-scanner_*.deb"
    echo "  sudo apt remove scanero-ip-scanner"
    echo "Для намеренной установки поверх пакета: SCANERO_ALLOW_USER_INSTALL=1 ./install.sh"
    exit 1
  fi
fi

DEST="${XDG_DATA_HOME:-$HOME/.local/share}/scanero"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
BIN="${HOME}/.local/bin"

echo "Установка Scanero IP Сканер в $DEST"
mkdir -p "$DEST" "$APPS" "$ICONS" "$BIN"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' \
    "$SRC/app.py" "$SRC/scanero" "$SRC/run.sh" "$SRC/requirements.txt" \
    "$SRC/README.md" "$SRC/LICENSE" "$DEST/"
else
  tar -C "$SRC" --exclude='__pycache__' --exclude='*.pyc' -cf - \
    app.py scanero run.sh requirements.txt README.md LICENSE | tar -C "$DEST" -xf -
fi
chmod +x "$DEST/run.sh"
install -m 644 "$SRC/scanero/assets/scanero.png" "$ICONS/scanero.png"
sed -e "s|@EXEC@|\"$DEST/run.sh\"|" "$SRC/scanero.desktop.in" > "$APPS/scanero.desktop"
chmod 644 "$APPS/scanero.desktop"
ln -sf "$DEST/run.sh" "$BIN/scanero"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true

if ! command -v xdotool >/dev/null 2>&1; then
  echo "Подсказка: для автоматического фокуса внешних окон установите xdotool:"
  echo "  sudo apt install xdotool"
fi
echo "Готово. Запускайте: scanero   (или через меню приложений — Scanero IP Сканер)"
