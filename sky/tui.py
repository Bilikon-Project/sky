from __future__ import annotations

from pathlib import Path

from rich.markup import escape
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Input, Static

from .config import Config, mix
from .fs import FileSystem, friendly_error, open_default

YES = {"e", "evet", "y", "yes"}

class Panel:

    def __init__(self, n: int, fs: FileSystem):
        self.n = n
        self.fs = fs
        self.rows: list[dict] = []

class SkyTUI(App):
    TITLE = "Sky"

    CSS = """
    Screen { background: $sky-bg; color: $sky-fg; }
    Header { background: $sky-bg-alt; color: $sky-accent; text-style: bold; }
    #split { height: 1fr; }
    .panel { width: 1fr; height: 1fr; }
    .path { dock: top; height: 1; padding: 0 1; background: $sky-bg-alt; color: $sky-dim; }
    .path.active { background: $sky-accent; color: $sky-bg; text-style: bold; }
    DataTable { height: 1fr; background: $sky-bg; color: $sky-fg; }
    DataTable > .datatable--header { background: $sky-bg-alt; color: $sky-accent2; text-style: bold; }
    DataTable > .datatable--cursor { background: $sky-accent; color: $sky-bg; text-style: bold; }
    DataTable > .datatable--hover { background: $sky-bg-alt; }
    #prompt { display: none; dock: bottom; height: 3; background: $sky-bg; color: $sky-fg; border: tall $sky-accent; }
    """

    BINDINGS = [
        Binding("q", "quit", "Çıkış"),
        Binding("backspace", "up", "Üst"),
        Binding("n", "new_file", "Yeni dosya"),
        Binding("N", "new_dir", "Yeni klasör"),
        Binding("d", "delete", "Çöpe at"),
        Binding("D", "delete_permanent", "Kalıcı sil"),
        Binding("r", "rename", "Yeniden adlandır"),
        Binding("c", "copy", "Kopyala"),
        Binding("m", "move", "Taşı"),
        Binding("R", "refresh", "Yenile"),
        Binding("H", "toggle_hidden", "Gizli"),

        Binding("tab", "switch_panel", "Panel", priority=True),
        Binding("shift+tab", "switch_panel", show=False, priority=True),
        Binding("escape", "cancel_input", "İptal"),
    ]

    def __init__(self, cfg: Config):

        self.cfg = cfg
        super().__init__()
        self.panels: dict[int, Panel] = {1: Panel(1, FileSystem(cfg.start_path))}
        if cfg.split_enabled:
            self.panels[2] = Panel(2, FileSystem(cfg.start_path))
        self.split_enabled = len(self.panels) == 2
        self.split_direction = cfg.split_direction
        self.show_hidden = cfg.show_hidden
        self.active = 1
        self._pending: str | None = None
        self._pending_src: dict | None = None

    def get_css_variables(self) -> dict[str, str]:
        variables = super().get_css_variables()
        c = self.cfg.color
        bg, fg = c("background_color"), c("foreground_color")
        variables.update({
            "sky-bg": bg,
            "sky-bg-alt": mix(bg, fg, 0.10),
            "sky-fg": fg,
            "sky-dim": mix(bg, fg, 0.55),
            "sky-accent": c("accent_color"),
            "sky-accent1": c("accent_color_1"),
            "sky-accent2": c("accent_color_2"),
        })
        return variables

    def _make_panel(self, n: int):
        with Vertical(id=f"panel{n}", classes="panel"):
            yield Static(Text(str(self.panels[n].fs.cwd)), id=f"path{n}", classes="path")
            yield DataTable(id=f"table{n}", cursor_type="row")

    def compose(self) -> ComposeResult:
        yield Header()
        if self.split_enabled:
            order = [2, 1] if self.split_direction in ("left", "top") else [1, 2]
            container = Horizontal if self.split_direction in ("left", "right") else Vertical
            with container(id="split"):
                for n in order:
                    yield from self._make_panel(n)
        else:
            yield from self._make_panel(1)
        yield Input(placeholder="isim gir...", id="prompt")
        yield Footer()

    def on_mount(self):
        for n in self.panels:
            self.query_one(f"#table{n}", DataTable).add_columns("Ad", "Boyut", "Tür")
        self.refresh_all()
        self._set_active(1)
        self.query_one("#table1", DataTable).focus()

    def _notify(self, message: str, severity: str = "information"):

        try:
            self.notify(message, severity=severity, markup=False)
        except TypeError:
            self.notify(escape(message), severity=severity)

    def _panel(self) -> Panel:
        return self.panels[self.active]

    def _fs(self) -> FileSystem:
        return self._panel().fs

    def _table(self, n: int | None = None) -> DataTable:
        return self.query_one(f"#table{n or self.active}", DataTable)

    def _other_cwd(self) -> str:
        other = self.panels.get(2 if self.active == 1 else 1)
        return str(other.fs.cwd) if other else ""

    def _set_active(self, n: int):
        self.active = n
        for k in self.panels:
            self.query_one(f"#path{k}", Static).set_class(k == n, "active")

    def _label(self, item: dict) -> Text:
        c = self.cfg.color
        if item["hidden"]:
            color = c("color_hidden")
        elif item["is_symlink"]:
            color = c("color_symlink")
        elif item["is_dir"]:
            color = c("color_dir")
        elif item["is_exec"]:
            color = c("color_executable")
        else:
            color = c("foreground_color")
        icon = "🔗" if item["is_symlink"] else ("📁" if item["is_dir"] else "📄")
        style = f"bold {color}" if item["is_dir"] else color
        return Text(f"{icon} {item['name']}", style=style)

    def refresh_panel(self, n: int, select_name: str | None = None):
        panel = self.panels[n]
        table = self._table(n)
        if panel.fs.recover():
            self._notify("Dizin artık yok, üst dizine çıkıldı", "warning")

        try:
            items = panel.fs.list_dir(self.show_hidden, self.cfg.visible_file_types)
        except OSError as e:
            items = []
            self._notify(f"{panel.fs.cwd}: {friendly_error(e)}", "error")

        old_row = table.cursor_row
        table.clear()
        panel.rows = items
        for item in items:
            size = "-" if item["is_dir"] else FileSystem.human_size(item["size"])
            kind = "Bağlantı" if item["is_symlink"] else ("Dizin" if item["is_dir"] else "Dosya")
            table.add_row(self._label(item), size, kind)

        if items:
            row = min(old_row, len(items) - 1)
            if select_name is not None:
                for i, item in enumerate(items):
                    if item["name"] == select_name:
                        row = i
                        break
            table.move_cursor(row=max(row, 0))

        self.query_one(f"#path{n}", Static).update(Text(str(panel.fs.cwd)))

    def refresh_all(self, select_name: str | None = None):
        for n in self.panels:
            self.refresh_panel(n, select_name if n == self.active else None)

    def refresh_tables(self):
        self.refresh_all()

    def selected(self) -> dict | None:
        rows = self._panel().rows
        idx = self._table().cursor_row
        return rows[idx] if 0 <= idx < len(rows) else None

    def on_descendant_focus(self, event):
        widget = event.widget
        if isinstance(widget, DataTable) and widget.id and widget.id.startswith("table"):
            self._set_active(int(widget.id[len("table"):]))

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        self._set_active(int(event.data_table.id[len("table"):]))
        self.action_open()

    def ask(self, action: str, placeholder: str, value: str = "", src: dict | None = None):
        self._pending = action
        self._pending_src = src
        inp = self.query_one("#prompt", Input)
        inp.placeholder = placeholder
        inp.value = value
        inp.display = True
        inp.focus()

    def _ask_dest(self, action: str):
        item = self.selected()
        if not item:
            return
        etiket = "Kopyalanacak" if action == "copy" else "Taşınacak"
        self.ask(action, f"{etiket} hedef dizin", value=self._other_cwd(), src=item)

    def _close_prompt(self):
        self.query_one("#prompt", Input).display = False
        self._pending = None
        self._pending_src = None
        self._table().focus()

    def on_input_submitted(self, event: Input.Submitted):
        value = event.value.strip()
        action, src = self._pending, self._pending_src
        self._close_prompt()
        if not value or not action:
            return

        select = None
        try:
            if action == "new_file":
                select = self._fs().touch(value).name
            elif action == "new_dir":
                select = self._fs().mkdir(value).name
            elif action == "rename" and src:
                select = self._fs().rename(src["path"], value).name
            elif action in ("copy", "move") and src:

                dest_dir = self._fs().cwd / Path(value).expanduser()
                if action == "copy":
                    result = self._fs().copy(src["path"], dest_dir)
                    self._notify(f"Kopyalandı: {src['name']} → {result}")
                else:
                    result = self._fs().move(src["path"], dest_dir)
                    self._notify(f"Taşındı: {src['name']} → {result}")
            elif action in ("delete", "delete_permanent") and src:
                if value.lower() not in YES:
                    self._notify("İptal edildi")
                    return
                if action == "delete":
                    self._fs().trash(src["path"], self.cfg.trash_path)
                    self._notify(f"Çöpe taşındı: {src['name']}")
                else:
                    self._fs().delete(src["path"])
                    self._notify(f"Kalıcı olarak silindi: {src['name']}")
        except Exception as e:
            self._notify(friendly_error(e), "error")
        self.refresh_all(select_name=select)

    def action_cancel_input(self):
        self._close_prompt()

    def action_up(self):
        fs = self._fs()
        left = fs.cwd
        fs.up()
        self.refresh_all(select_name=left.name if fs.cwd != left else None)

    def action_refresh(self):
        self.refresh_all()

    def action_toggle_hidden(self):
        self.show_hidden = not self.show_hidden
        self.refresh_all()
        self._notify("Gizli dosyalar: " + ("görünür" if self.show_hidden else "gizli"))

    def action_open(self):
        item = self.selected()
        if not item:
            return
        if item["is_dir"]:
            try:
                self._fs().cd(item["path"])
            except OSError as e:
                self._notify(friendly_error(e), "error")
            self.refresh_all()
        else:
            try:
                open_default(item["path"])
                self._notify(f"Açılıyor: {item['name']}")
            except Exception as e:
                self._notify(f"Açılamadı: {friendly_error(e)}", "error")

    def action_new_file(self):
        self.ask("new_file", "Yeni dosya adı")

    def action_new_dir(self):
        self.ask("new_dir", "Yeni klasör adı")

    def action_rename(self):
        item = self.selected()
        if item:
            self.ask("rename", "Yeni ad", value=item["name"], src=item)

    def action_delete(self):
        item = self.selected()
        if item:
            self.ask("delete", f"'{item['name']}' çöpe taşınsın mı? (e/h)", src=item)

    def action_delete_permanent(self):
        item = self.selected()
        if item:
            self.ask("delete_permanent",
                     f"'{item['name']}' KALICI olarak silinsin mi? (e/h)", src=item)

    def action_copy(self):
        self._ask_dest("copy")

    def action_move(self):
        self._ask_dest("move")

    def action_switch_panel(self):
        if not self.split_enabled or self._pending:
            return
        self._set_active(2 if self.active == 1 else 1)
        self._table().focus()

def run(cfg: Config):
    SkyTUI(cfg).run()
