#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PREFIX="${PREFIX:-$HOME/.local}"
APP_DIR="$PREFIX/share/sky"
BIN_DIR="$PREFIX/bin"
DESKTOP_DIR="$PREFIX/share/applications"
ICON_DIR="$PREFIX/share/icons/hicolor/scalable/apps"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/sky"

echo "→ Sky kuruluyor: $PREFIX"

command -v python3 >/dev/null 2>&1 || { echo "HATA: python3 bulunamadı." >&2; exit 1; }

mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR" "$CONFIG_DIR"
rm -rf "$APP_DIR/sky"
cp -r sky "$APP_DIR/sky"
find "$APP_DIR/sky" -name __pycache__ -type d -prune -exec rm -rf {} +
cp sky/data/sky.svg "$ICON_DIR/sky.svg"

if [ -e "$CONFIG_DIR/sky.conf" ]; then
    echo "  Mevcut ayar dosyası korundu: $CONFIG_DIR/sky.conf"
else
    cp sky/data/sky.conf "$CONFIG_DIR/sky.conf"
fi

if [ "${SKY_NO_VENV:-0}" = "1" ]; then
    PYTHON="python3"
    echo "  SKY_NO_VENV=1: bağımlılıkları kendin kurmalısın (pip install -r requirements.txt)"
else
    echo "  Sanal ortam hazırlanıyor ve bağımlılıklar kuruluyor..."
    python3 -m venv "$APP_DIR/venv" || {
        echo "HATA: venv oluşturulamadı. Debian/Ubuntu için: sudo apt install python3-venv" >&2
        exit 1
    }
    "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
    "$APP_DIR/venv/bin/pip" install --quiet -r requirements.txt
    PYTHON="$APP_DIR/venv/bin/python"
fi

cat > "$BIN_DIR/sky" <<LAUNCHER
PYTHONPATH="$APP_DIR" exec "$PYTHON" -m sky "\$@"
LAUNCHER
chmod +x "$BIN_DIR/sky"

sed "s|^Exec=.*|Exec=\"$BIN_DIR/sky\" gui|" sky/data/sky.desktop > "$DESKTOP_DIR/sky.desktop"

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f -t "$PREFIX/share/icons/hicolor" 2>/dev/null || true

echo "✅ Kuruldu! Menüden 'Sky' veya terminalden 'sky' yazarak açabilirsin."
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "⚠️  $BIN_DIR PATH içinde değil; 'sky' komutu için PATH'e ekle." ;;
esac
