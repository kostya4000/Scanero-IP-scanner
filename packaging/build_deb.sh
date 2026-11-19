#!/usr/bin/env bash
# Build a self-contained Debian package for Scanero IP Scanner.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PKG="scanero-ip-scanner"
VERSION="$(python3 - <<'PY'
import re
from pathlib import Path
text = Path("scanero/__init__.py").read_text(encoding="utf-8")
print(re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1))
PY
)"
BUILD="$ROOT/build/deb"
DIST="$ROOT/dist"
DEB="$DIST/${PKG}_${VERSION}_all.deb"

rm -rf "$BUILD"
mkdir -p \
  "$BUILD/DEBIAN" \
  "$BUILD/usr/bin" \
  "$BUILD/usr/lib/scanero" \
  "$BUILD/usr/share/applications" \
  "$BUILD/usr/share/icons/hicolor/256x256/apps" \
  "$BUILD/usr/share/man/man1" \
  "$BUILD/usr/share/doc/$PKG"

cp -a "$ROOT/app.py" "$ROOT/scanero" "$BUILD/usr/lib/scanero/"
find "$BUILD/usr/lib/scanero" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$BUILD/usr/lib/scanero" -name '*.pyc' -delete
cp "$ROOT/README.md" "$ROOT/CHANGELOG.md" "$ROOT/LICENSE" "$BUILD/usr/share/doc/$PKG/"
cp "$ROOT/LICENSE" "$BUILD/usr/share/doc/$PKG/copyright"
gzip -9n -c "$ROOT/packaging/changelog" > "$BUILD/usr/share/doc/$PKG/changelog.gz"
gzip -9n -c "$ROOT/packaging/scanero.1" > "$BUILD/usr/share/man/man1/scanero.1.gz"
cp "$ROOT/scanero/assets/scanero.png" "$BUILD/usr/share/icons/hicolor/256x256/apps/scanero.png"
python3 - <<'PY'
import gzip
from pathlib import Path
source = Path("scanero/assets/oui.json.gz")
target = Path("build/deb/usr/lib/scanero/scanero/assets/oui.json.gz")
with gzip.open(source, "rb") as src:
    data = src.read()
with gzip.GzipFile(filename="", mode="wb", fileobj=open(target, "wb"), mtime=0, compresslevel=9) as dst:
    dst.write(data)
PY
cp "$ROOT/packaging/scanero.desktop" "$BUILD/usr/share/applications/scanero.desktop"

cat > "$BUILD/usr/bin/scanero" <<'LAUNCHER'
#!/bin/sh
exec python3 /usr/lib/scanero/app.py "$@"
LAUNCHER
chmod 0755 "$BUILD/usr/bin/scanero"
find "$BUILD/usr" -type d -exec chmod 0755 {} +
find "$BUILD/usr" -type f -exec chmod 0644 {} +
chmod 0755 "$BUILD/usr/bin/scanero"

cat > "$BUILD/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VERSION
Section: net
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-pyqt6, iputils-ping, iproute2, xdg-utils
Recommends: xdotool, avahi-utils, gvfs-backends
Suggests: samba-common-bin, remmina, freerdp2-x11, vlc
Installed-Size: $(du -sk "$BUILD/usr" | cut -f1)
Maintainer: kostya4000 <2225821+kostya4000@users.noreply.github.com>
Homepage: https://github.com/kostya4000/Scanero-IP-scanner
Description: Modern local network scanner for Ubuntu
 Scanero IP scanner discovers computers, phones, printers, routers,
 NAS and IoT devices in a local network. It shows IP and MAC addresses,
 vendors, hostnames, operating systems and open services, and can open
 SMB, FTP, HTTP and RDP resources, send Wake-on-LAN packets and shut
 down Windows computers remotely. Includes favorites, history, export
 to CSV/JSON/HTML, light/dark themes and adjustable font size.
CONTROL

cat > "$BUILD/DEBIAN/postinst" <<'SCRIPT'
#!/bin/sh
set -e

# Older source installs created ~/.local/bin/scanero, which shadows
# /usr/bin/scanero in PATH. Remove only links/shortcuts that point to that
# previous per-user installation.
for home in /home/* /root; do
  [ -d "$home" ] || continue
  link="$home/.local/bin/scanero"
  if [ -L "$link" ]; then
    target="$(readlink "$link" 2>/dev/null || true)"
    case "$target" in
      */.local/share/scanero/run.sh|*/.local/share/scanero/run.sh/)
        rm -f "$link"
        echo "Scanero: removed stale user launcher $link"
        ;;
    esac
  fi
  desktop="$home/.local/share/applications/scanero.desktop"
  if [ -f "$desktop" ] && grep -q '\.local/share/scanero/run\.sh' "$desktop" 2>/dev/null; then
    rm -f "$desktop"
    echo "Scanero: removed stale user desktop shortcut $desktop"
  fi
done

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
SCRIPT

cat > "$BUILD/DEBIAN/postrm" <<'SCRIPT'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
SCRIPT
chmod 0755 "$BUILD/DEBIAN/postinst" "$BUILD/DEBIAN/postrm"

(cd "$BUILD" && find usr -type f -print0 | sort -z | xargs -0 md5sum) > "$BUILD/DEBIAN/md5sums"

mkdir -p "$DIST"
rm -f "$DEB"
dpkg-deb --build --root-owner-group "$BUILD" "$DEB"

echo
dpkg-deb --info "$DEB" | sed -n '1,18p'
echo
echo "Package: $DEB"
echo "Size:    $(du -h "$DEB" | cut -f1)"
