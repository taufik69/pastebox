# PasteBox — Clipboard Manager for Ubuntu

Press **Super (Win) + .** to see a list of all the text and images you've copied. Click any item (or press Enter) to copy it again, then paste it with **Ctrl+V**.

## Features
- Keeps a history of both text and images (the last 50 unpinned items)
- Search by typing in the box at the top
- ☆ Pin: pinned items are never deleted and always stay at the top of the list
- Remove one item with 🗑, or everything except pinned items with **Clear all**
- Keyboard: `↑ ↓` select, `Enter` copy, `Alt+1…9` quick pick, `Del` remove, `Esc` close
- Starts automatically when you log in (runs in the background)
- Does not save text that a password manager marks as secret
- History is stored in `~/.local/share/pastebox/`

## Installation

Open a terminal (`Ctrl+Alt+T`), go to the project folder and run:

```bash
# 1) Fully remove any old clipboard apps (Diodon, GPaste, CopyQ...)
./remove-old-clipboards.sh

# 2) Install PasteBox
sudo apt install ./dist/pastebox_1.0.1_all.deb

# 3) Start it now (it will start automatically on every login after this)
pastebox --setup
pastebox --daemon &
```

Now copy something, then press **Win + .** 🎉

> If the shortcut doesn't work, log out and log back in once.
> If it still doesn't work, go to **Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts** and check that "PasteBox Clipboard" is listed.
> The emoji picker now opens with **Win + ;**, because **Win + .** is assigned to PasteBox.

## Installing on another computer
Copy the `dist/pastebox_1.0.1_all.deb` file over, then run:
```bash
sudo apt install ./pastebox_1.0.1_all.deb
pastebox --daemon &
```
You can also double-click the file and install it through the **App Center**.

## Building a new .deb after changing the code
```bash
./build-deb.sh          # creates a new .deb in the dist/ folder
```
To release a new version, change `VERSION` in `src/pastebox.py` first. If the version stays the same, `apt` will think it's already installed and skip it.

## Uninstall
```bash
pastebox --quit
sudo apt purge pastebox
rm -rf ~/.local/share/pastebox ~/.config/pastebox     # if you also want to delete your history
```

## Commands
| Command | What it does |
|---|---|
| `pastebox` | Open or close the popup |
| `pastebox --daemon` | Start in the background |
| `pastebox --setup` | Set the Win+. shortcut again |
| `pastebox --quit` | Stop PasteBox |
