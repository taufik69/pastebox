# Installing PasteBox

This guide walks you through installing PasteBox on your own Ubuntu computer.

## Before you start

- **Ubuntu with the default GNOME desktop.** Other GNOME-based distributions may work, but the keyboard shortcut is set up for GNOME.
- An internet connection.
- Your user password (for `sudo`).

Open a terminal with **Ctrl + Alt + T**. Every command below goes there.

---

## Option A — Download only the installer (quickest)

```bash
cd ~/Downloads
wget https://github.com/taufik69/pastebox/raw/main/dist/pastebox_1.0.1_all.deb
sudo apt install ./pastebox_1.0.1_all.deb
pastebox --setup
pastebox --daemon &
```

You can also download the `.deb` from the GitHub page in your browser and double-click it to install with the **App Center**, then run the last two commands.

## Option B — Clone the whole project with Git

Use this if you also want the helper scripts, or want to update with `git pull` later.

```bash
sudo apt install git
git clone https://github.com/taufik69/pastebox.git
cd pastebox
sudo apt install ./dist/pastebox_1.0.1_all.deb
pastebox --setup
pastebox --daemon &
```

### Optional: remove other clipboard managers

If you already use Diodon, GPaste, CopyQ, Parcellite or ClipIt, they can clash with PasteBox. From the `pastebox` folder, run:

```bash
./remove-old-clipboards.sh
```

> **Warning:** this uninstalls those apps **and deletes their saved clipboard history**. Skip it if you want to keep them.

---

## Try it

1. Copy some text (Ctrl + C).
2. Press **Super (Windows key) + .** (period).
3. The PasteBox window opens. Click an item or press **Enter** to copy it again, then paste with **Ctrl + V**.

From now on PasteBox starts automatically every time you log in.

| Key | Action |
|---|---|
| `↑` `↓` | Move through the list |
| `Enter` | Copy the selected item |
| `Alt + 1…9` | Copy item 1–9 directly |
| `Del` | Remove the selected item |
| Type anything | Search |
| `Esc` | Close |

---

## Troubleshooting

**Super + . does nothing**
1. Log out and log back in once.
2. Run `pastebox --setup` again.
3. Check **Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts** for an entry called **PasteBox Clipboard**.

**Super + . opens the emoji picker instead**
Run `pastebox --setup`, then log out and back in. The emoji picker moves to **Super + ;**.

**Nothing appears in the list**
PasteBox only records what you copy while it's running. Make sure it's running:
```bash
pgrep -af pastebox
```
If nothing is shown, start it with `pastebox --daemon &`.

**`sudo apt install` says the package is already installed**
You already have this version. To reinstall it anyway:
```bash
sudo apt install --reinstall ./pastebox_1.0.1_all.deb
```

---

## Updating to a new version

With Option B:
```bash
cd pastebox
git pull
ls dist/                                          # see the newest .deb file name
sudo apt install ./dist/pastebox_<version>_all.deb
pastebox --quit; pastebox --daemon &
```

With Option A, download the new `.deb` from GitHub and install it the same way.

## Uninstalling

```bash
pastebox --quit
sudo apt purge pastebox
rm -rf ~/.local/share/pastebox ~/.config/pastebox    # also deletes your clipboard history
```

The `Super + .` shortcut entry may stay in Keyboard settings; you can delete it there.
