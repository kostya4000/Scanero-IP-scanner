#!/usr/bin/env bash
set -euo pipefail
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/scanero"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
rm -rf "$DEST"
rm -f "$APPS/scanero.desktop" "$ICONS/scanero.png" "$HOME/.local/bin/scanero"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" || true
echo "Scanero IP Сканер удалён. Настройки в ~/.config/scanero сохранены."
