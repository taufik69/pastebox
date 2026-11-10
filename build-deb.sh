#!/bin/bash
# Builds dist/pastebox_<version>_all.deb
set -euo pipefail
cd "$(dirname "$0")"
VERSION=$(grep -oP '^VERSION = "\K[^"]+' src/pastebox.py)
PKG=build/pastebox_${VERSION}_all
rm -rf build && mkdir -p "$PKG/DEBIAN" dist

install -Dm755 src/pastebox.py                 "$PKG/usr/bin/pastebox"
install -Dm644 packaging/pastebox.desktop      "$PKG/usr/share/applications/pastebox.desktop"
install -Dm644 packaging/pastebox-autostart.desktop "$PKG/etc/xdg/autostart/pastebox.desktop"
install -Dm644 packaging/pastebox.svg          "$PKG/usr/share/icons/hicolor/scalable/apps/pastebox.svg"

cat > "$PKG/DEBIAN/control" <<CTRL
Package: pastebox
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-gi, gir1.2-gtk-3.0
Conflicts: diodon, gpaste-2, copyq, parcellite, clipit
Maintainer: PasteBox <itizaraa@gmail.com>
Description: Clipboard history manager for GNOME
 Keeps a history of copied text and images. Press Super+. to open it,
 search, pin favourites and paste any earlier item.
CTRL
echo "/etc/xdg/autostart/pastebox.desktop" > "$PKG/DEBIAN/conffiles"

cat > "$PKG/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
command -v update-desktop-database >/dev/null && update-desktop-database -q || true
POST
chmod 755 "$PKG/DEBIAN/postinst"

dpkg-deb --root-owner-group --build "$PKG" dist/ >/dev/null
echo "Built: dist/pastebox_${VERSION}_all.deb"
