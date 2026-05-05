#!/usr/bin/env python3
"""md-tui — terminal markdown editor with a GUI-style menu bar.

Usage:
    python3 main.py [file.md]
"""

import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
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
# file‑browser modal
# ═══════════════════════════════════════════════════════════════════════════════

class FileManagerModal(ModalScreen[str | None]):
    """TUI file browser. Navigate with arrows/Enter/Backspace.

    In ``"open"`` mode (default): select a file to open.
    In ``"save"`` mode: select a directory, then a filename modal follows.
    """

    BINDINGS = [
        Binding("backspace", "go_up", "Parent"),
        Binding("asciitilde", "go_home", "Home"),
        Binding("escape", "dismiss_none", "Cancel"),
    ]

    CSS = """
    FileManagerModal {
        align: center middle;
    }
    #fm-container {
        width: 64;
        height: 26;
        background: $surface;
        border: thick $secondary;
        padding: 1 2;
    }
    #fm-title {
        width: 100%;
        height: 1;
        text-style: bold;
        color: $text;
        content-align: center middle;
        background: $primary-background;
        padding: 0 1;
    }
    #fm-path {
        width: 100%;
        height: 1;
        color: $text-disabled;
        padding: 0 1;
        margin-bottom: 1;
    }
    #fm-list {
        width: 100%;
        height: 1fr;
    }
    #fm-hint {
        width: 100%;
        height: 1;
        margin-top: 1;
        color: $text-disabled;
        content-align: center middle;
    }
    """

    def __init__(self, start_path: str = ".", select_dir: bool = False) -> None:
        super().__init__()
        self._current = Path(start_path).resolve()
        self._entry_map: dict[str, str | Path] = {}
        self._select_dir = select_dir

    def compose(self) -> ComposeResult:
        title = " Choose Save Location " if self._select_dir else " Open File "
        if self._select_dir:
            hint = "[~] Home  [←/→/↑/↓] Navigate  [Enter] Select  [Bksp] Parent  [Esc] Cancel"
        else:
            hint = "[~] Home  [←/→/↑/↓] Navigate  [Enter] Open  [Bksp] Parent  [Esc] Cancel"
        with Vertical(id="fm-container"):
            yield Label(title, id="fm-title")
            yield Label(self._path_display(), id="fm-path")
            yield ListView(id="fm-list")
            yield Label(hint, id="fm-hint")

    def _path_display(self) -> str:
        home = str(Path.home())
        p = str(self._current)
        if p.startswith(home):
            p = "~" + p[len(home):]
        return f" {p}"

    async def on_mount(self) -> None:
        await self._refresh()

    async def _refresh(self) -> None:
        lv = self.query_one("#fm-list", ListView)
        await lv.clear()
        self._entry_map.clear()
        self.query_one("#fm-path", Label).update(self._path_display())

        # parent directory
        if self._current.parent != self._current:
            self._entry_map["fm-parent"] = "parent"
            await lv.append(ListItem(Label(" 📁  .."), id="fm-parent"))

        # in save mode: add "select this directory" entry
        if self._select_dir:
            self._entry_map["fm-select"] = "select-dir"
            await lv.append(ListItem(Label(" 💾  Save to this directory"), id="fm-select"))

        entries: list[Path] = []
        try:
            entries = sorted(self._current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            self.notify("Permission denied", severity="error")
            self._current = self._current.parent
            await self._refresh()
            return

        for idx, p in enumerate(entries):
            if p.name.startswith("."):
                continue  # skip hidden files
            eid = f"fm-{idx}"
            self._entry_map[eid] = p
            if p.is_dir():
                await lv.append(ListItem(Label(f" 📁  {p.name}"), id=eid))
            else:
                icon = self._icon(p)
                disabled = self._select_dir  # in save mode, can't select files
                await lv.append(ListItem(Label(f" {icon}  {p.name}"), id=eid, disabled=disabled))

        lv.index = 0
        lv.focus()

    @staticmethod
    def _icon(p: Path) -> str:
        ext = p.suffix.lower()
        if ext in (".md", ".markdown", ".mdown", ".mkd"):
            return "📝"
        if ext in (".py", ".js", ".ts", ".rs", ".go", ".c", ".cpp", ".h", ".java", ".rb"):
            return "💻"
        if ext in (".txt", ".log", ".cfg", ".ini", ".toml", ".yaml", ".yml", ".json", ".xml"):
            return "📄"
        return "📄"

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        lv = event.list_view
        if lv.index is None:
            return
        item = lv.children[lv.index]
        item_id = str(item.id) if item.id else ""
        target = self._entry_map.get(item_id)
        if target is None:
            return
        if target == "parent":
            self._current = self._current.parent
            await self._refresh()
            return
        if target == "select-dir":
            self.dismiss(str(self._current))
            return
        p = Path(target)
        if p.is_dir():
            self._current = p
            await self._refresh()
        elif not self._select_dir:
            self.dismiss(str(p))

    async def action_go_up(self) -> None:
        if self._current.parent != self._current:
            self._current = self._current.parent
            await self._refresh()

    async def action_go_home(self) -> None:
        self._current = Path.home()
        await self._refresh()

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


# ═══════════════════════════════════════════════════════════════════════════════
# filename‑entry modal (for Save As)
# ═══════════════════════════════════════════════════════════════════════════════

class FileNameModal(ModalScreen[str | None]):
    """Enter a filename. Press Enter to confirm, Esc to cancel."""

    BINDINGS = [
        Binding("escape", "dismiss_none", "Cancel"),
    ]

    CSS = """
    FileNameModal {
        align: center middle;
    }
    #fn-container {
        width: 50;
        background: $surface;
        border: thick $secondary;
        padding: 1 2;
    }
    #fn-title {
        width: 100%;
        height: 1;
        text-style: bold;
        color: $text;
        content-align: center middle;
        margin-bottom: 1;
    }
    #fn-dir {
        width: 100%;
        height: 1;
        color: $text-disabled;
        padding: 0 1;
    }
    #fn-input {
        width: 100%;
        margin-top: 1;
    }
    """

    def __init__(self, directory: str) -> None:
        super().__init__()
        self._directory = directory

    def compose(self) -> ComposeResult:
        with Vertical(id="fn-container"):
            yield Label(" Save File ", id="fn-title")
            yield Label(f" {self._directory}", id="fn-dir")
            yield Input(placeholder="filename.md", id="fn-input")

    def on_mount(self) -> None:
        self.query_one("#fn-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        name = event.value.strip()
        if name:
            self.dismiss(name)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


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
        self._save_target_dir: Path | None = None
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
            start = str(Path(self._filepath).parent) if self._filepath else "."
            self.push_screen(FileManagerModal(start, select_dir=True), callback=self._on_save_dir)
            return
        editor = self.query_one("#editor", TextArea)
        try:
            Path(self._filepath).write_text(editor.text)
        except Exception as e:
            self.notify(f"Save failed: {e}", severity="error")
            return
        self._update_status()
        self.notify(f"Saved: {self._filepath}")

    def _on_save_dir(self, directory: str | None) -> None:
        if directory is None:
            return
        self._save_target_dir = Path(directory)
        self.push_screen(FileNameModal(directory), callback=self._on_save_as)

    def _on_save_as(self, filename: str | None) -> None:
        if filename is None or self._save_target_dir is None:
            return
        editor = self.query_one("#editor", TextArea)
        filepath = str(self._save_target_dir / filename)
        try:
            Path(filepath).write_text(editor.text)
        except Exception as e:
            self.notify(f"Save failed: {e}", severity="error")
            return
        self._filepath = filepath
        self._save_target_dir = None
        self._update_status()
        self.notify(f"Saved: {filepath}")

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
            start = str(Path(self._filepath).parent) if self._filepath else "."
            self.push_screen(FileManagerModal(start), callback=self._on_open)
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
        if path is None:
            return
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
