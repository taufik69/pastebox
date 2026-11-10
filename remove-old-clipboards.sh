#!/bin/bash
# Removes every other clipboard manager so it doesn't fight with PasteBox.
set -u
echo ">> Stopping running clipboard managers..."
pkill -x diodon copyq gpaste-daemon parcellite clipit 2>/dev/null || true

echo ">> Purging packages (needs your password)..."
PKGS=$(dpkg -l | awk '{print $2}' | sed 's/:.*//' | grep -E '^(diodon|gpaste-2|libgpaste-2-common|libgpaste-2t64|gir1.2-gpaste-2|copyq|copyq-plugins|parcellite|clipit|glipper|xfce4-clipman)$' | sort -u)
if [ -n "$PKGS" ]; then
  sudo apt purge -y $PKGS && sudo apt autoremove -y
else
  echo "   nothing to purge"
fi
sudo rm -f /etc/xdg/autostart/diodon-autostart.desktop

echo ">> Removing leftover user data..."
rm -rf ~/.config/copyq ~/.local/share/gpaste ~/.config/gpaste ~/.config/diodon ~/.local/share/diodon
echo "Done."
