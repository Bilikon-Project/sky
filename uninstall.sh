#!/usr/bin/env bash
set -u
PREFIX="${PREFIX:-$HOME/.local}"
rm -rf "$PREFIX/share/sky"
rm -f  "$PREFIX/bin/sky"
rm -f  "$PREFIX/share/applications/sky.desktop"
rm -f  "$PREFIX/share/icons/hicolor/scalable/apps/sky.svg"
update-desktop-database "$PREFIX/share/applications" 2>/dev/null || true
echo "🗑️ Sky kaldırıldı. (Ayarlar korundu: ${XDG_CONFIG_HOME:-$HOME/.config}/sky/)"
