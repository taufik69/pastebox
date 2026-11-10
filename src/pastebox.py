#!/usr/bin/env python3
"""PasteBox - a lightweight clipboard history manager for Ubuntu (GNOME).

Usage:
  pastebox            show / toggle the clipboard popup (starts the daemon if needed)
  pastebox --daemon   start in background (used by autostart)
  pastebox --setup    (re)assign the Super+. shortcut
  pastebox --quit     stop the running instance
"""

import os
import sys

# Restore a clean environment when launched from a snap terminal (e.g. VS Code snap),
# otherwise GTK loads the snap's incompatible schemas/modules and crashes.
for key in list(os.environ):
    if key.endswith("_VSCODE_SNAP_ORIG"):
        real = key[: -len("_VSCODE_SNAP_ORIG")]
        if os.environ[key]:
            os.environ[real] = os.environ[key]
        else:
            os.environ.pop(real, None)

# On GNOME Wayland, background apps cannot watch the clipboard. Running through
# XWayland lets us see every copy (Mutter mirrors the clipboard to X11).
if os.environ.get("XDG_SESSION_TYPE") == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
    os.environ["GDK_BACKEND"] = "x11"

import hashlib
import json
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GdkPixbuf, GdkX11, Gio, GLib, Gtk, Pango  # noqa: E402

APP_ID = "io.github.pastebox"
APP_NAME = "PasteBox"
VERSION = "1.0.1"
MAX_ITEMS = 50          # unpinned items kept in history
MAX_TEXT = 200_000      # characters stored per text item
SHORTCUT = "<Super>period"

DATA_DIR = os.path.join(GLib.get_user_data_dir(), "pastebox")
IMG_DIR = os.path.join(DATA_DIR, "images")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "pastebox")
SHORTCUT_MARKER = os.path.join(CONFIG_DIR, "shortcut-configured")

KB_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
KB_ITEM_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
KB_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/pastebox/"

CSS = b"""
window#pastebox-window { background-color: transparent; }
#pastebox-root {
  background-color: @theme_base_color;
  border: 1px solid alpha(@theme_fg_color, 0.15);
  border-radius: 4px;
  padding: 14px 14px 10px 14px;
}
#pastebox-title { font-weight: bold; font-size: 1.1em; }

/* header buttons */
button.pb-clear {
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid alpha(@theme_fg_color, 0.15);
  background: alpha(@theme_fg_color, 0.04);
  box-shadow: none;
  font-size: 0.9em;
}
button.pb-clear:hover {
  background: alpha(@error_color, 0.12);
  border-color: alpha(@error_color, 0.45);
  color: @error_color;
}
button.pb-close {
  padding: 4px;
  min-width: 26px; min-height: 26px;
  border-radius: 4px;
  border: none; background: transparent; box-shadow: none;
}
button.pb-close:hover { background: alpha(@theme_fg_color, 0.10); }

/* search */
#pastebox-search {
  border-radius: 4px;
  padding: 6px 8px;
  min-height: 30px;
}

#pastebox-list { background: transparent; }
#pastebox-list row {
  border-radius: 4px;
  margin: 3px 0;
  padding: 8px 10px;
  background-color: alpha(@theme_fg_color, 0.05);
}
#pastebox-list row:hover { background-color: alpha(@theme_selected_bg_color, 0.25); }
#pastebox-list row:selected { background-color: @theme_selected_bg_color; color: @theme_selected_fg_color; }
.pb-meta { font-size: 0.8em; opacity: 0.6; }
.pb-pinned { color: #e5a50a; }
.pb-empty { opacity: 0.6; padding: 40px; }
button.pb-icon { padding: 2px; min-width: 24px; min-height: 24px; }

/* footer shortcut hints */
.pb-footer {
  border-top: 1px solid alpha(@theme_fg_color, 0.10);
  padding-top: 8px;
}
.pb-key {
  font-size: 0.75em;
  font-weight: bold;
  padding: 1px 5px;
  border-radius: 4px;
  border: 1px solid alpha(@theme_fg_color, 0.20);
  border-bottom-width: 2px;
  background-color: alpha(@theme_fg_color, 0.05);
}
.pb-hint { font-size: 0.8em; opacity: 0.65; }
"""


def setup_shortcut():
    """Bind Super+. to `pastebox` and free it from the IBus emoji picker."""
    src = Gio.SettingsSchemaSource.get_default()
    if src.lookup(KB_SCHEMA, True) is None:
        print("GNOME media-keys schema not found; set the shortcut manually.", file=sys.stderr)
        return False

    exe = "pastebox" if GLib.find_program_in_path("pastebox") else \
        f"{sys.executable} {os.path.abspath(__file__)}"

    media = Gio.Settings.new(KB_SCHEMA)
    paths = list(media.get_strv("custom-keybindings"))
    # Drop any other custom shortcut already using Super+.
    for p in list(paths):
        if p == KB_PATH:
            continue
        item = Gio.Settings.new_with_path(KB_ITEM_SCHEMA, p)
        if item.get_string("binding").lower() == SHORTCUT.lower():
            paths.remove(p)
    if KB_PATH not in paths:
        paths.append(KB_PATH)
    item = Gio.Settings.new_with_path(KB_ITEM_SCHEMA, KB_PATH)
    item.set_string("name", "PasteBox Clipboard")
    item.set_string("command", exe)
    item.set_string("binding", SHORTCUT)
    media.set_strv("custom-keybindings", paths)

    # IBus binds Super+. to its emoji picker by default; that would swallow the key.
    if src.lookup("org.freedesktop.ibus.panel.emoji", True):
        emoji = Gio.Settings.new("org.freedesktop.ibus.panel.emoji")
        keys = [k for k in emoji.get_strv("hotkey") if k.lower() != SHORTCUT.lower()]
        emoji.set_strv("hotkey", keys)

    Gio.Settings.sync()
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(SHORTCUT_MARKER, "w") as f:
        f.write(SHORTCUT + "\n")
    return True


class History:
    def __init__(self):
        os.makedirs(IMG_DIR, exist_ok=True)
        self.items = []
        try:
            with open(HISTORY_FILE) as f:
                self.items = json.load(f)
        except (OSError, ValueError):
            self.items = []

    def save(self):
        tmp = HISTORY_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.items, f, ensure_ascii=False)
        os.replace(tmp, HISTORY_FILE)

    def _find(self, kind, key):
        for i, it in enumerate(self.items):
            if it["type"] == kind and it["key"] == key:
                return i
        return -1

    def add_text(self, text):
        if not text or not text.strip():
            return False
        text = text[:MAX_TEXT]
        key = hashlib.sha1(text.encode()).hexdigest()
        return self._add({"type": "text", "key": key, "text": text})

    def add_image(self, pixbuf):
        ok, data = pixbuf.save_to_bufferv("png", [], [])
        if not ok:
            return False
        key = hashlib.sha1(data).hexdigest()
        path = os.path.join(IMG_DIR, key + ".png")
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(data)
        return self._add({"type": "image", "key": key, "path": path,
                          "w": pixbuf.get_width(), "h": pixbuf.get_height()})

    def _add(self, item):
        idx = self._find(item["type"], item["key"])
        if idx == 0:
            return False  # already newest
        if idx > 0:
            old = self.items.pop(idx)
            item["pinned"] = old.get("pinned", False)
        item.setdefault("pinned", False)
        item["time"] = time.time()
        self.items.insert(0, item)
        self._trim()
        self.save()
        return True

    def _trim(self):
        unpinned = [it for it in self.items if not it.get("pinned")]
        for it in unpinned[MAX_ITEMS:]:
            self.remove(it, save=False)

    def remove(self, item, save=True):
        if item in self.items:
            self.items.remove(item)
            if item["type"] == "image" and not any(
                    i["type"] == "image" and i["key"] == item["key"] for i in self.items):
                try:
                    os.remove(item["path"])
                except OSError:
                    pass
        if save:
            self.save()

    def clear(self):
        for it in [i for i in self.items if not i.get("pinned")]:
            self.remove(it, save=False)
        self.save()

    def toggle_pin(self, item):
        item["pinned"] = not item.get("pinned", False)
        self.save()

    def bump(self, item):
        if item in self.items:
            self.items.remove(item)
            self.items.insert(0, item)
            item["time"] = time.time()
            self.save()


def human_time(ts):
    d = time.time() - ts
    if d < 60:
        return "just now"
    if d < 3600:
        return f"{int(d // 60)} min ago"
    if d < 86400:
        return f"{int(d // 3600)} h ago"
    return time.strftime("%d %b %H:%M", time.localtime(ts))


class PopupWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(title=APP_NAME, application=app)
        self.app = app
        self.set_default_size(400, 540)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_icon_name("pastebox")

        # Transparent window so the root box's rounded corners show.
        self.set_name("pastebox-window")
        visual = self.get_screen().get_rgba_visual()
        if visual is not None and self.get_screen().is_composited():
            self.set_visual(visual)
            self.set_app_paintable(True)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.set_name("pastebox-root")
        self.add(root)

        header = Gtk.Box(spacing=6)
        title = Gtk.Label(label="📋  Clipboard", xalign=0)
        title.set_name("pastebox-title")
        header.pack_start(title, True, True, 0)
        clear_btn = Gtk.Button()
        clear_box = Gtk.Box(spacing=5)
        clear_box.pack_start(Gtk.Image.new_from_icon_name("edit-clear-all-symbolic", Gtk.IconSize.MENU),
                             False, False, 0)
        clear_box.pack_start(Gtk.Label(label="Clear all"), False, False, 0)
        clear_btn.add(clear_box)
        clear_btn.get_style_context().add_class("pb-clear")
        clear_btn.set_valign(Gtk.Align.CENTER)
        clear_btn.set_tooltip_text("Remove all unpinned items")
        clear_btn.connect("clicked", self._on_clear)
        header.pack_start(clear_btn, False, False, 0)
        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        close_btn.get_style_context().add_class("pb-close")
        close_btn.set_valign(Gtk.Align.CENTER)
        close_btn.set_tooltip_text("Close (Esc)")
        close_btn.connect("clicked", lambda *_: self.hide())
        header.pack_start(close_btn, False, False, 0)
        root.pack_start(header, False, False, 0)

        self.search = Gtk.SearchEntry(placeholder_text="Search clipboard…")
        self.search.set_name("pastebox-search")
        self.search.connect("search-changed", lambda *_: self.listbox.invalidate_filter())
        self.search.connect("activate", self._on_search_activate)
        self.search.connect("key-press-event", self._on_search_key)
        root.pack_start(self.search, False, False, 0)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.listbox = Gtk.ListBox()
        self.listbox.set_name("pastebox-list")
        self.listbox.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect("row-activated", self._on_row_activated)
        self.listbox.set_filter_func(self._filter)
        empty = Gtk.Label(label="Nothing copied yet.\nCopy something with Ctrl+C.")
        empty.set_justify(Gtk.Justification.CENTER)
        empty.get_style_context().add_class("pb-empty")
        empty.show()
        self.listbox.set_placeholder(empty)
        scroller.add(self.listbox)
        root.pack_start(scroller, True, True, 0)

        footer = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        footer.get_style_context().add_class("pb-footer")
        for key, action in (("Enter", "copy"), ("Del", "remove"),
                            ("Alt+1…9", "quick pick"), ("Esc", "close")):
            pair = Gtk.Box(spacing=4)
            k = Gtk.Label(label=key, valign=Gtk.Align.CENTER)
            k.get_style_context().add_class("pb-key")
            a = Gtk.Label(label=action, valign=Gtk.Align.CENTER)
            a.get_style_context().add_class("pb-hint")
            pair.pack_start(k, False, False, 0)
            pair.pack_start(a, False, False, 0)
            footer.pack_start(pair, False, False, 0)
        root.pack_start(footer, False, False, 0)

        self.connect("key-press-event", self._on_key)
        self.connect("focus-out-event", self._on_focus_out)
        self.connect("delete-event", lambda *_: self.hide() or True)

    # ---------- list ----------
    def rebuild(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        items = self.app.history.items
        ordered = [i for i in items if i.get("pinned")] + [i for i in items if not i.get("pinned")]
        for n, item in enumerate(ordered):
            self.listbox.add(self._make_row(item, n))
        self.listbox.show_all()
        first = self.listbox.get_row_at_index(0)
        if first:
            self.listbox.select_row(first)

    def _make_row(self, item, index):
        row = Gtk.ListBoxRow()
        row.item = item
        box = Gtk.Box(spacing=8)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        if item["type"] == "text":
            preview = item["text"].strip()
            lines = preview.splitlines()
            preview = "\n".join(lines[:4])[:400]
            lbl = Gtk.Label(label=preview, xalign=0)
            lbl.set_line_wrap(True)
            lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            lbl.set_lines(4)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            lbl.set_max_width_chars(40)
            content.pack_start(lbl, False, False, 0)
            meta = f"{len(item['text'])} chars"
        else:
            try:
                w, h = item.get("w") or 300, item.get("h") or 110
                scale = min(1.0, 300 / w, 110 / h)
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    item["path"], max(1, int(w * scale)), max(1, int(h * scale)), True)
                content.pack_start(Gtk.Image.new_from_pixbuf(pb), False, False, 0)
            except GLib.Error:
                content.pack_start(Gtk.Label(label="[image missing]", xalign=0), False, False, 0)
            meta = f"Image {item.get('w')}×{item.get('h')}"

        prefix = f"Alt+{index + 1}  ·  " if index < 9 else ""
        m = Gtk.Label(label=f"{prefix}{meta}  ·  {human_time(item.get('time', 0))}", xalign=0)
        m.get_style_context().add_class("pb-meta")
        content.pack_start(m, False, False, 0)
        box.pack_start(content, True, True, 0)

        btns = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        pin = Gtk.Button(label="★" if item.get("pinned") else "☆")
        pin.set_relief(Gtk.ReliefStyle.NONE)
        pin.get_style_context().add_class("pb-icon")
        if item.get("pinned"):
            pin.get_style_context().add_class("pb-pinned")
        pin.set_tooltip_text("Unpin" if item.get("pinned") else "Pin (keep forever)")
        pin.connect("clicked", self._on_pin, item)
        btns.pack_start(pin, False, False, 0)
        rm = Gtk.Button.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.MENU)
        rm.set_relief(Gtk.ReliefStyle.NONE)
        rm.get_style_context().add_class("pb-icon")
        rm.set_tooltip_text("Remove")
        rm.connect("clicked", self._on_remove, item)
        btns.pack_start(rm, False, False, 0)
        box.pack_start(btns, False, False, 0)

        row.add(box)
        return row

    def _filter(self, row):
        q = self.search.get_text().strip().lower()
        if not q:
            return True
        it = row.item
        return it["type"] == "text" and q in it["text"].lower()

    def _visible_rows(self):
        return [r for r in self.listbox.get_children() if self._filter(r)]

    # ---------- actions ----------
    def _on_row_activated(self, _lb, row):
        self.app.paste_item(row.item)

    def _on_search_activate(self, _e):
        row = self.listbox.get_selected_row()
        if row is None or not self._filter(row):
            rows = self._visible_rows()
            row = rows[0] if rows else None
        if row:
            self.app.paste_item(row.item)

    def _on_search_key(self, _e, event):
        if event.keyval in (Gdk.KEY_Down, Gdk.KEY_Up):
            rows = self._visible_rows()
            if rows:
                target = rows[0] if event.keyval == Gdk.KEY_Down else rows[-1]
                self.listbox.select_row(target)
                target.grab_focus()
            return True
        return False

    def _on_key(self, _w, event):
        kv = event.keyval
        if kv == Gdk.KEY_Escape:
            self.hide()
            return True
        if event.state & Gdk.ModifierType.MOD1_MASK and Gdk.KEY_1 <= kv <= Gdk.KEY_9:
            idx = kv - Gdk.KEY_1
            rows = self._visible_rows()
            if idx < len(rows):
                self.app.paste_item(rows[idx].item)
            return True
        focus = self.get_focus()
        if focus is not self.search:
            if kv == Gdk.KEY_Delete:
                row = self.listbox.get_selected_row()
                if row:
                    self._on_remove(None, row.item)
                return True
            ch = Gdk.keyval_to_unicode(kv)
            if ch and chr(ch).isprintable() and not (event.state & Gdk.ModifierType.CONTROL_MASK):
                self.search.grab_focus_without_selecting()
                return self.search.event(event)
        return False

    def _on_focus_out(self, *_):
        GLib.timeout_add(150, self._hide_if_unfocused)
        return False

    def _hide_if_unfocused(self):
        if not self.is_active():
            self.hide()
        return False

    def _on_pin(self, _b, item):
        self.app.history.toggle_pin(item)
        self.rebuild()

    def _on_remove(self, _b, item):
        self.app.history.remove(item)
        self.rebuild()
        self.search.grab_focus()

    def _on_clear(self, _b):
        self.app.history.clear()
        self.rebuild()

    def popup(self):
        self.search.set_text("")
        self.rebuild()
        self.show_all()
        gdk_win = self.get_window()
        ts = GdkX11.x11_get_server_time(gdk_win) if isinstance(gdk_win, GdkX11.X11Window) \
            else Gtk.get_current_event_time()
        self.present_with_time(ts)
        self.search.grab_focus()


class PasteBoxApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.history = None
        self.window = None
        self.clipboard = None
        self._started = False

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.history = History()
        self.window = PopupWindow(self)
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.clipboard.connect("owner-change", self._on_owner_change)
        self.hold()  # keep running in the background while the window is hidden
        if not os.path.exists(SHORTCUT_MARKER):
            try:
                setup_shortcut()
            except Exception as e:  # never block startup on settings errors
                print(f"Shortcut setup failed: {e}", file=sys.stderr)
        # Capture whatever is on the clipboard right now.
        GLib.idle_add(self._on_owner_change)

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        first = not self._started
        self._started = True
        if "--quit" in args:
            self.quit()
        elif "--setup" in args:
            ok = setup_shortcut()
            cmdline.print_literal("Shortcut Super+. configured.\n" if ok else "Shortcut setup failed.\n")
            if first:
                self.quit()
        elif "--version" in args:
            cmdline.print_literal(f"{APP_NAME} {VERSION}\n")
            if first:
                self.quit()
        elif "--daemon" in args:
            pass
        elif self.window.get_visible() and not first:
            self.window.hide()
        else:
            self.window.popup()
        return 0

    # ---------- clipboard ----------
    def _on_owner_change(self, *_):
        self.clipboard.request_targets(self._on_targets)
        return False

    def _on_targets(self, clipboard, atoms, *_):
        names = [a.name() for a in (atoms or [])]
        # Respect password managers that mark secrets as sensitive.
        if "x-kde-passwordManagerHint" in names:
            return
        if any(n.startswith("image/") for n in names) and not any(
                n in ("UTF8_STRING", "text/plain", "text/plain;charset=utf-8", "STRING") for n in names):
            clipboard.request_image(self._on_image)
        elif names:
            clipboard.request_text(self._on_text)

    def _on_text(self, _cb, text):
        if text and self.history.add_text(text) and self.window.get_visible():
            self.window.rebuild()

    def _on_image(self, _cb, pixbuf):
        if pixbuf and self.history.add_image(pixbuf) and self.window.get_visible():
            self.window.rebuild()

    def paste_item(self, item):
        if item["type"] == "text":
            self.clipboard.set_text(item["text"], -1)
        else:
            try:
                self.clipboard.set_image(GdkPixbuf.Pixbuf.new_from_file(item["path"]))
            except GLib.Error:
                return
        self.clipboard.store()
        self.history.bump(item)
        self.window.hide()


def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return 0
    return PasteBoxApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
