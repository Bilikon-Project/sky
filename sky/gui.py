from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, Qt, QUrl
from PyQt6.QtGui import QBrush, QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSplitter,
    QVBoxLayout, QWidget,
)

from .config import Config, mix
from .fs import FileSystem, friendly_error

_MOD_NAMES = {"super": "Meta", "win": "Meta", "meta": "Meta", "alt": "Alt",
              "ctrl": "Ctrl", "control": "Ctrl", "shift": "Shift"}

def to_qt_sequence(combo: str) -> QKeySequence:
    parts = [p for p in combo.lower().split("+") if p]
    mapped = [_MOD_NAMES.get(p, p.capitalize() if len(p) > 1 else p.upper()) for p in parts]
    return QKeySequence("+".join(mapped))

class SkyGUI(QMainWindow):
    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.fs1 = FileSystem(cfg.start_path)
        self.fs2 = FileSystem(cfg.start_path)
        self.show_hidden = cfg.show_hidden
        self.active = 1
        self.split_enabled = cfg.split_enabled
        self.split_direction = cfg.split_direction
        self.filters = {1: "", 2: ""}
        self.lists: dict[int, QListWidget] = {}
        self.labels: dict[int, QLabel] = {}
        self.setWindowTitle("Sky")
        self.resize(1100, 700)
        self._apply_theme()
        self._build()
        self._setup_shortcuts()

    def _fs(self, n: int | None = None) -> FileSystem:
        return self.fs1 if (n or self.active) == 1 else self.fs2

    def _panels(self) -> list[int]:
        return [1, 2] if self.split_enabled else [1]

    def _message(self, text: str):
        self.statusBar().showMessage(text, 6000)

    def _error(self, exc: BaseException):
        QMessageBox.warning(self, "Hata", friendly_error(exc))

    def _confirm(self, title: str, text: str) -> bool:
        box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=self)
        yes = box.addButton("Evet", QMessageBox.ButtonRole.YesRole)
        no = box.addButton("Hayır", QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(no)
        box.exec()
        return box.clickedButton() is yes

    def _ask_text(self, title: str, label: str, text: str = "") -> str | None:
        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText(label)
        dlg.setTextValue(text)
        dlg.setOkButtonText("Tamam")
        dlg.setCancelButtonText("İptal")
        if dlg.exec() and dlg.textValue().strip():
            return dlg.textValue().strip()
        return None

    def _apply_theme(self):
        c = self.cfg.color
        bg, fg = c("background_color"), c("foreground_color")
        alt, border = mix(bg, fg, 0.08), mix(bg, fg, 0.20)
        accent, accent1, accent2 = c("accent_color"), c("accent_color_1"), c("accent_color_2")
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {bg}; color: {fg}; }}
            QLabel[path="true"] {{ color: {mix(bg, fg, 0.55)}; padding: 3px 6px; background: {alt}; }}
            QLabel[path="true"][active="true"] {{ color: {bg}; background: {accent}; font-weight: bold; }}
            QListWidget {{ background: {bg}; border: 1px solid {border}; outline: 0; }}
            QListWidget::item {{ padding: 3px 4px; }}
            QListWidget::item:hover {{ background: {alt}; }}
            QListWidget::item:selected {{ background: {accent}; color: {bg}; }}
            QPushButton {{ background: {alt}; border: 1px solid {border}; border-radius: 4px; padding: 4px 10px; }}
            QPushButton:hover {{ border-color: {accent}; }}
            QPushButton:checked {{ background: {accent1}; color: {bg}; }}
            QSplitter::handle {{ background: {border}; }}
            QStatusBar {{ color: {accent2}; }}
            QLineEdit {{ background: {alt}; border: 1px solid {border}; padding: 3px; }}
        """)
        families = self.cfg.font_families
        if families:
            font = QFont(self.font())
            font.setFamilies(families)
            self.setFont(font)

    def _make_panel(self, n: int) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(str(self._fs(n).cwd))
        label.setProperty("path", True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lst = QListWidget()
        lst.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        lst.installEventFilter(self)

        lst.itemActivated.connect(lambda _item, n=n: self.open_item(n))
        layout.addWidget(label)
        layout.addWidget(lst)
        self.labels[n] = label
        self.lists[n] = lst
        return w

    def _build(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        top = QHBoxLayout()
        for text, slot in [
            ("↑ Üst", self.up), ("Yenile", self.refresh),
            ("Yeni Dosya", self.new_file), ("Yeni Klasör", self.new_dir),
            ("Yeniden Adlandır", self.rename),
            ("Kopyala", self.copy), ("Taşı", self.move),
            ("Çöpe At", self.delete),
        ]:
            b = QPushButton(text)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _checked=False, s=slot: s())
            top.addWidget(b)
        self.hidden_btn = QPushButton("Gizli")
        self.hidden_btn.setCheckable(True)
        self.hidden_btn.setChecked(self.show_hidden)
        self.hidden_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.hidden_btn.toggled.connect(self.set_hidden)
        top.addWidget(self.hidden_btn)
        top.addStretch(1)
        layout.addLayout(top)

        if not self.split_enabled:
            layout.addWidget(self._make_panel(1), 1)
        else:
            horizontal = self.split_direction in ("right", "left")
            splitter = QSplitter(Qt.Orientation.Horizontal if horizontal else Qt.Orientation.Vertical)
            p1, p2 = self._make_panel(1), self._make_panel(2)

            first, second = (p1, p2) if self.split_direction in ("right", "down") else (p2, p1)
            splitter.addWidget(first)
            splitter.addWidget(second)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 1)
            layout.addWidget(splitter, 1)

        self.setCentralWidget(central)
        self.statusBar()
        self.refresh()
        self._set_active(1)
        self.lists[1].setFocus()

    def _setup_shortcuts(self):

        for seq, slot in [
            ("Backspace", self.up), ("F5", self.refresh), ("F2", self.rename),
            ("Delete", self.delete), ("Shift+Delete", self.delete_permanent),
            ("Ctrl+H", lambda: self.hidden_btn.toggle()),
            ("Ctrl+N", self.new_file), ("Ctrl+Shift+N", self.new_dir),
            ("Ctrl+F", self.search), ("Tab", self.switch_panel),
        ]:
            QShortcut(QKeySequence(seq), self, activated=slot)

        actions = {
            "exit sky": self.close,
            "delete file": self.delete,
            "search files": self.search,
        }
        if not self.cfg.shortcuts_enabled:
            return
        for combo, action in self.cfg.shortcuts.items():
            slot = actions.get(action.lower())
            seq = to_qt_sequence(combo)
            if slot is None:
                print(f"[sky] uyarı: desteklenmeyen kısayol eylemi: {action!r} ({combo})", file=sys.stderr)
            elif seq.isEmpty():
                print(f"[sky] uyarı: geçersiz tuş birleşimi: {combo!r}", file=sys.stderr)
            else:
                QShortcut(seq, self, activated=slot)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.FocusIn:
            for n, lst in self.lists.items():
                if obj is lst:
                    self._set_active(n)
                    break
        return super().eventFilter(obj, event)

    def _set_active(self, n: int):
        self.active = n
        for k, label in self.labels.items():
            label.setProperty("active", k == n)
            label.style().unpolish(label)
            label.style().polish(label)

    def switch_panel(self):
        if self.split_enabled:
            n = 2 if self.active == 1 else 1
            self._set_active(n)
            self.lists[n].setFocus()

    def refresh(self, select_name: str | None = None):
        c = self.cfg.color
        for n in self._panels():
            fs, lst = self._fs(n), self.lists[n]
            if fs.recover():
                self._message("Dizin artık yok, üst dizine çıkıldı")
            try:
                items = fs.list_dir(self.show_hidden, self.cfg.visible_file_types, self.filters[n])
            except OSError as e:
                items = []
                self._message(f"{fs.cwd}: {friendly_error(e)}")

            current = lst.currentItem()
            keep = select_name if (select_name and n == self.active) else (
                current.data(Qt.ItemDataRole.UserRole)["name"] if current else None)
            old_row = lst.currentRow()

            lst.clear()
            for item in items:
                icon = "🔗" if item["is_symlink"] else ("📁" if item["is_dir"] else "📄")
                size = "-" if item["is_dir"] else FileSystem.human_size(item["size"])
                li = QListWidgetItem(f"{icon} {item['name']}   ({size})")
                li.setData(Qt.ItemDataRole.UserRole, item)
                if item["hidden"]:
                    color = c("color_hidden")
                elif item["is_symlink"]:
                    color = c("color_symlink")
                elif item["is_dir"]:
                    color = c("color_dir")
                elif item["is_exec"]:
                    color = c("color_executable")
                else:
                    color = None
                if color:
                    li.setForeground(QBrush(QColor(color)))
                lst.addItem(li)

            row = None
            if keep:
                for i, item in enumerate(items):
                    if item["name"] == keep:
                        row = i
                        break
            if row is None and items and old_row >= 0:
                row = min(old_row, len(items) - 1)
            if row is not None:
                lst.setCurrentRow(row)

            text = str(fs.cwd)
            if self.filters[n]:
                text += f"   [filtre: {self.filters[n]}]"
            self.labels[n].setText(text)
            self.labels[n].setToolTip(str(fs.cwd))

    def selected(self) -> dict | None:
        li = self.lists[self.active].currentItem()
        return li.data(Qt.ItemDataRole.UserRole) if li else None

    def set_hidden(self, value: bool):
        self.show_hidden = value
        self.refresh()

    def up(self):
        fs = self._fs()
        left = fs.cwd
        fs.up()
        self.refresh(select_name=left.name if fs.cwd != left else None)

    def open_item(self, n: int | None = None):
        if n:
            self._set_active(n)
        item = self.selected()
        if not item:
            return
        if item["is_dir"]:
            try:
                self._fs().cd(item["path"])
            except OSError as e:
                self._error(e)
            self.refresh()
        elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(item["path"]))):
            QMessageBox.warning(self, "Açılamadı", f"{item['name']} açılamadı.")

    def new_file(self):
        name = self._ask_text("Yeni Dosya", "Ad:")
        if name:
            try:
                self.refresh(select_name=self._fs().touch(name).name)
            except Exception as e:
                self._error(e)

    def new_dir(self):
        name = self._ask_text("Yeni Klasör", "Ad:")
        if name:
            try:
                self.refresh(select_name=self._fs().mkdir(name).name)
            except Exception as e:
                self._error(e)

    def rename(self):
        item = self.selected()
        if not item:
            return
        name = self._ask_text("Yeniden Adlandır", "Yeni ad:", item["name"])
        if name:
            try:
                self.refresh(select_name=self._fs().rename(item["path"], name).name)
            except Exception as e:
                self._error(e)

    def search(self):
        text = self._ask_text("Dosya Ara", "Ada göre süz (boş bırakıp Tamam = süzmeyi kaldır):",
                              self.filters[self.active])
        self.filters[self.active] = text or ""
        self.refresh()

    def _other_cwd(self) -> str:
        if not self.split_enabled:
            return str(self._fs().cwd)
        return str(self._fs(2 if self.active == 1 else 1).cwd)

    def _ask_dest(self, action: str):
        item = self.selected()
        if not item:
            return
        etiket = "Kopyalanacak" if action == "copy" else "Taşınacak"
        dest = self._ask_text("Kopyala" if action == "copy" else "Taşı",
                              f"{etiket} hedef dizin:", self._other_cwd())
        if not dest:
            return
        dest_dir = self._fs().cwd / Path(dest).expanduser()
        try:
            if action == "copy":
                result = self._fs().copy(item["path"], dest_dir)
                self._message(f"Kopyalandı: {result}")
            else:
                result = self._fs().move(item["path"], dest_dir)
                self._message(f"Taşındı: {result}")
            self.refresh()
        except Exception as e:
            self._error(e)

    def copy(self):
        self._ask_dest("copy")

    def move(self):
        self._ask_dest("move")

    def delete(self):
        item = self.selected()
        if not item or not self._confirm("Çöpe At", f"'{item['name']}' çöpe taşınsın mı?"):
            return
        try:
            self._fs().trash(item["path"], self.cfg.trash_path)
            self._message(f"Çöpe taşındı: {item['name']}")
            self.refresh()
        except Exception as e:
            self._error(e)

    def delete_permanent(self):
        item = self.selected()
        if not item or not self._confirm(
                "Kalıcı Sil", f"'{item['name']}' KALICI olarak silinsin mi?\nBu işlem geri alınamaz."):
            return
        try:
            self._fs().delete(item["path"])
            self._message(f"Kalıcı olarak silindi: {item['name']}")
            self.refresh()
        except Exception as e:
            self._error(e)

def run(cfg: Config):
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Sky")
    QGuiApplication.setDesktopFileName("sky")
    icon_file = Path(__file__).resolve().parent / "data" / "sky.svg"
    fallback = QIcon(str(icon_file)) if icon_file.exists() else QIcon()
    app.setWindowIcon(QIcon.fromTheme("sky", fallback))
    w = SkyGUI(cfg)
    w.show()
    sys.exit(app.exec())
