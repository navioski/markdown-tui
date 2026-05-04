#!/usr/bin/env python3
"""md-tui — terminal markdown editor with a GUI-style menu bar.

Usage:
    python3 main.py [file.md]
"""

import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    Markdown,
    TextArea,
)


# ═══════════════════════════════════════════════════════════════════════════════
# menu definition
# ═══════════════════════════════════════════════════════════════════════════════

MENU_DEF: list[tuple[str, list[tuple[str, str]]]] = [
    (" File ", [
        ("New", "new"),
        ("Open…", "open"),
        ("Save", "save"),
        ("───", ""),
        ("Quit", "quit"),
    ]),
    (" Edit ", [
        ("Undo", "undo"),
        ("Find…", "find"),
    ]),
    (" View ", [
        ("Toggle Preview", "toggle_preview"),
    ]),
    (" Theme ", [
        ("Dracula", "theme:dracula"),
        ("Nord", "theme:nord"),
        ("Gruvbox", "theme:gruvbox"),
        ("Catppuccin", "theme:catppuccin"),
        ("Solarized", "theme:solarized"),
    ]),
]


# ═══════════════════════════════════════════════════════════════════════════════
# menu bar widget
# ═══════════════════════════════════════════════════════════════════════════════

class MenuBar(Horizontal):
    """Horizontal row of menu buttons with popup ListView dropdown."""

    def __init__(self, on_action) -> None:
        super().__init__(id="menu-bar")
        self._on_action = on_action
        self._open_idx: int = -1
        self._dropdown: ListView | None = None

    def compose(self) -> ComposeResult:
        for i, (label, _) in enumerate(MENU_DEF):
            yield Button(label, id=f"menu-btn-{i}", classes="menu-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        idx = int(str(event.button.id).split("-")[-1])
        self._toggle(idx)

    def _toggle(self, idx: int) -> None:
        if self._open_idx == idx:
            self._close()
            return
        self._close()
        self._open_idx = idx

        _, items = MENU_DEF[idx]
        lv = ListView(id="menu-dropdown")
        self._dropdown = lv
        self.mount(lv)  # mount first, then add children

        for label, action in items:
            if not action:
                lv.append(ListItem(Label("─" * 16), disabled=True))
            else:
                lv.append(ListItem(Label(f" {label} ")))

        lv.styles.width = 22
        lv.styles.offset_x = self._btn_offset(idx)
        lv.styles.offset_y = 1
        lv.focus()

    def _close(self) -> None:
        self._open_idx = -1
        if self._dropdown is not None:
            self._dropdown.remove()
            self._dropdown = None

    def _btn_offset(self, idx: int) -> int:
        x = 0
        for i in range(idx):
            x += len(MENU_DEF[i][0]) + 1  # label + spacing
        return x

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self._open_idx < 0:
            return
        _, items = MENU_DEF[self._open_idx]
        lv = event.list_view
        si = lv.index
        if si is not None and si < len(items) and items[si][1]:
            self._close()
            self._on_action(items[si][1])

    def close(self) -> None:
        self._close()

    @property
    def is_open(self) -> bool:
        return self._dropdown is not None


# ═══════════════════════════════════════════════════════════════════════════════
# file‑open modal
# ═══════════════════════════════════════════════════════════════════════════════

class FileOpenModal(ModalScreen[str]):
    """Modal to type a file path. Press Enter to confirm."""

    CSS = """
    FileOpenModal {
        align: center middle;
    }
    #open-box {
        width: 50;
        background: $surface;
        border: thick $secondary;
        padding: 1 2;
    }
    #open-input {
        width: 100%;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="open-box"):
            yield Label("Open file — enter path, press Enter:")
            yield TextArea("", id="open-input")

    def on_mount(self) -> None:
        self.query_one("#open-input", TextArea).focus()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if "\n" in event.text_area.text:
            path = event.text_area.text.strip()
            if path:
                self.dismiss(path)


# ═══════════════════════════════════════════════════════════════════════════════
# main application
# ═══════════════════════════════════════════════════════════════════════════════

class MdTuiApp(App):
    """Terminal markdown editor with a clickable menu bar."""

    CSS = """
    /* ── menu bar ─────────────────────────── */
    #menu-bar {
        height: 1;
        background: $surface;
        border-bottom: solid #bd93f9;
    }
    .menu-btn {
        min-width: 9;
        background: $surface;
        color: $text;
        border: none;
        padding: 0 1;
    }
    .menu-btn:hover {
        background: #bd93f9;
        color: #282a36;
    }

    /* dropdown */
    #menu-dropdown {
        background: #3a1a5e;
        border: solid #bd93f9;
        height: auto;
        max-height: 16;
    }
    #menu-dropdown ListItem {
        padding: 0 1;
        background: #3a1a5e;
        color: $text;
        height: 1;
    }
    #menu-dropdown ListItem:hover {
        background: #bd93f9;
        color: #282a36;
    }
    #menu-dropdown ListItem:disabled {
        color: #6272a4;
    }

    /* ── main area ────────────────────────── */
    #main {
        height: 1fr;
    }
    #editor {
        width: 1fr;
        border: solid #6272a4;
        background: $background;
        color: $text;
    }
    #preview {
        width: 1fr;
        border: solid #bd93f9;
        background: $background;
        color: $text;
    }

    /* ── status bar ───────────────────────── */
    #status {
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+o", "open_file", "Open…"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("escape", "escape", "Close menu"),
    ]

    def __init__(self, filepath: str | None = None) -> None:
        super().__init__()
        self._filepath = filepath
        self._show_preview = True

    # ── compose ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        yield MenuBar(on_action=self._handle_action)
        with Horizontal(id="main"):
            yield TextArea("", id="editor", show_line_numbers=True)
            yield Markdown("", id="preview")
        yield Label("", id="status")
        yield Footer()

    # ── mount ────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.theme = "dracula"
        if self._filepath:
            self._load_file(self._filepath)
        else:
            self._update_status()
        self.query_one("#editor", TextArea).focus()

    # ── file io ──────────────────────────────────────────────────────────

    def _load_file(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            self.notify(f"Not found: {path}", severity="error")
            return
        try:
            content = p.read_text()
        except Exception as e:
            self.notify(f"Read error: {e}", severity="error")
            return
        self._filepath = path
        self.query_one("#editor", TextArea).text = content
        self._update_preview()
        self._update_status()

    def _save(self) -> None:
        if not self._filepath:
            self.notify("No file to save", severity="warning")
            return
        editor = self.query_one("#editor", TextArea)
        try:
            Path(self._filepath).write_text(editor.text)
        except Exception as e:
            self.notify(f"Save failed: {e}", severity="error")
            return
        self._update_status()
        self.notify(f"Saved: {self._filepath}")

    # ── preview ──────────────────────────────────────────────────────────

    def _update_preview(self) -> None:
        editor = self.query_one("#editor", TextArea)
        preview = self.query_one("#preview", Markdown)
        try:
            preview.update(editor.text)
        except Exception:
            preview.update("*(rendering…)*")

    def _toggle_preview(self) -> None:
        self._show_preview = not self._show_preview
        preview = self.query_one("#preview", Markdown)
        if self._show_preview:
            preview.styles.display = "block"
        else:
            preview.styles.display = "none"

    # ── status ───────────────────────────────────────────────────────────

    def _update_status(self) -> None:
        editor = self.query_one("#editor", TextArea)
        fp = self._filepath or "[new file]"
        chars = len(editor.text)
        lines = max(editor.text.count("\n") + 1, 1)
        status = self.query_one("#status", Label)
        status.update(f" {fp}  |  {lines} lines  |  {chars} chars")

    # ── actions ──────────────────────────────────────────────────────────

    def _handle_action(self, action: str) -> None:
        if action == "new":
            self._filepath = None
            self.query_one("#editor", TextArea).text = ""
            self._update_preview()
            self._update_status()
        elif action == "open":
            self.push_screen(FileOpenModal(), callback=self._on_open)
        elif action == "save":
            self._save()
        elif action == "quit":
            self.exit()
        elif action == "undo":
            self.query_one("#editor", TextArea).undo()
            self._update_preview()
        elif action == "find":
            self.notify("Use Ctrl+F to search within the editor")
        elif action == "toggle_preview":
            self._toggle_preview()
        elif action.startswith("theme:"):
            name = action.split(":", 1)[1]
            self.theme = name
            self._update_status()
            self.notify(f"Theme: {name}")

    def _on_open(self, path: str | None) -> None:
        if path:
            self._load_file(path)

    # ── events ───────────────────────────────────────────────────────────

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "editor":
            self._update_preview()
            self._update_status()

    def action_escape(self) -> None:
        menu = self.query_one(MenuBar)
        if menu.is_open:
            menu.close()
            self.query_one("#editor", TextArea).focus()

    def action_save(self) -> None:
        self._save()

    def action_open_file(self) -> None:
        self._handle_action("open")

    def action_quit(self) -> None:
        self.exit()


# ═══════════════════════════════════════════════════════════════════════════════
# entry
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    fp = sys.argv[1] if len(sys.argv) > 1 else None
    app = MdTuiApp(filepath=fp)
    app.run()
