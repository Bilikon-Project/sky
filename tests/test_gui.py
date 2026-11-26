import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut
from PyQt6.QtWidgets import QApplication

from sky.config import Config
from sky.gui import SkyGUI, to_qt_sequence

@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])

def make(tmp_path, qapp, split=True, extra=""):
    root = tmp_path / "kok"
    (root / "adir").mkdir(parents=True, exist_ok=True)
    (root / "c.txt").write_text("c")
    (root / "d.txt").write_text("d")
    (root / ".gizli").write_text("g")
    conf = tmp_path / "sky.conf"
    conf.write_text(
        f"start_path : {root}\ntrash_path : {tmp_path / 'Trash'}\n"
        f"split : {'enable' if split else 'disable'}\n{extra}\n")
    return SkyGUI(Config(conf)), root

def names(w, n=1):
    lst = w.lists[n]
    return [lst.item(i).data(Qt.ItemDataRole.UserRole)["name"] for i in range(lst.count())]

def test_active_panel_survives_refresh(tmp_path, qapp):
    w, _ = make(tmp_path, qapp)
    w.lists[2].setCurrentRow(0)
    w._set_active(2)
    w.lists[1].setCurrentRow(1)
    w._set_active(1)
    w.refresh()
    assert w.active == 1

def test_active_follows_focus_event(tmp_path, qapp):
    w, _ = make(tmp_path, qapp)
    w.show()
    w.lists[2].setFocus()
    qapp.processEvents()
    assert w.active == 2
    w.lists[1].setFocus()
    qapp.processEvents()
    assert w.active == 1

def test_open_dir_up_and_selection_restore(tmp_path, qapp):
    w, root = make(tmp_path, qapp, split=False)
    w.lists[1].setCurrentRow(0)
    w.open_item(1)
    assert w.fs1.cwd == root / "adir"
    w.up()
    assert w.fs1.cwd == root
    assert w.selected()["name"] == "adir"

def test_hidden_toggle(tmp_path, qapp):
    w, _ = make(tmp_path, qapp, split=False)
    assert ".gizli" not in names(w)
    w.hidden_btn.setChecked(True)
    assert ".gizli" in names(w)

def test_rename_and_refusal_to_overwrite(tmp_path, qapp, monkeypatch):
    w, root = make(tmp_path, qapp, split=False)
    warnings = []
    monkeypatch.setattr(w, "_error", lambda e: warnings.append(e))
    w.lists[1].setCurrentRow(names(w).index("c.txt"))
    monkeypatch.setattr(w, "_ask_text", lambda *a, **k: "d.txt")
    w.rename()
    assert warnings and (root / "c.txt").exists() and (root / "d.txt").read_text() == "d"
    monkeypatch.setattr(w, "_ask_text", lambda *a, **k: "yeni.txt")
    w.rename()
    assert (root / "yeni.txt").exists() and w.selected()["name"] == "yeni.txt"

def test_delete_asks_then_trashes(tmp_path, qapp, monkeypatch):
    w, root = make(tmp_path, qapp, split=False)
    w.lists[1].setCurrentRow(names(w).index("c.txt"))
    monkeypatch.setattr(w, "_confirm", lambda *a: False)
    w.delete()
    assert (root / "c.txt").exists()
    monkeypatch.setattr(w, "_confirm", lambda *a: True)
    w.delete()
    assert not (root / "c.txt").exists()
    assert (tmp_path / "Trash" / "files" / "c.txt").exists()

def test_copy_prefills_other_panel_and_never_overwrites(tmp_path, qapp, monkeypatch):
    w, root = make(tmp_path, qapp)
    w.fs2.cd(root / "adir")
    w.refresh()
    (root / "adir" / "c.txt").write_text("HEDEF")
    seen = {}

    def fake_ask(title, label, text=""):
        seen["prefill"] = text
        return text

    monkeypatch.setattr(w, "_ask_text", fake_ask)
    w.lists[1].setCurrentRow(names(w).index("c.txt"))
    w._set_active(1)
    w.copy()
    assert seen["prefill"] == str(root / "adir")
    assert (root / "adir" / "c.txt").read_text() == "HEDEF"
    assert (root / "adir" / "c (kopya).txt").read_text() == "c"

def test_search_filters_active_panel_only(tmp_path, qapp, monkeypatch):
    w, _ = make(tmp_path, qapp)
    monkeypatch.setattr(w, "_ask_text", lambda *a, **k: "d.t")
    w._set_active(1)
    w.search()
    assert names(w, 1) == ["d.txt"] and "adir" in names(w, 2)
    monkeypatch.setattr(w, "_ask_text", lambda *a, **k: None)
    w.search()
    assert "c.txt" in names(w, 1)

def test_shortcut_translation():
    assert to_qt_sequence("super+alt+f").toString() == "Meta+Alt+F"
    assert to_qt_sequence("ctrl+shift+e").toString() == "Ctrl+Shift+E"
    assert to_qt_sequence("super+x").toString() == "Meta+X"

def test_config_shortcuts_registered_and_unknown_warned(tmp_path, qapp, capsys):
    base, _ = make(tmp_path, qapp, split=False)
    n_builtin = len(base.findChildren(QShortcut))
    w, _ = make(tmp_path, qapp, split=False, extra=(
        "sky.shortcuts : enable\n"
        "sky.shortcuts : super+alt+q : delete file\n"
        "sky.shortcuts : super+shift+e : exit sky\n"
        "sky.shortcuts : super+x : download file to nowhere\n"))
    assert len(w.findChildren(QShortcut)) == n_builtin + 2
    assert "desteklenmeyen" in capsys.readouterr().err
    off, _ = make(tmp_path, qapp, split=False, extra="sky.shortcuts : disable\nsky.shortcuts : super+x : exit sky\n")
    assert len(off.findChildren(QShortcut)) == n_builtin

def test_theme_uses_configured_colors(tmp_path, qapp):
    w, _ = make(tmp_path, qapp, extra="background_color : #101010\naccent_color : #ff8800\n"
                                      "global_font : DejaVu Sans\nglobal_other_font : Noto Color Emoji\n")
    css = w.styleSheet()
    assert "#101010" in css and "#ff8800" in css
    assert w.font().families()[:2] == ["DejaVu Sans", "Noto Color Emoji"]

def test_item_colors_follow_config(tmp_path, qapp):
    w, _ = make(tmp_path, qapp, split=False, extra="color_dir : #123456\nshow_hidden : true\n")
    lst = w.lists[1]
    row = names(w).index("adir")
    assert lst.item(row).foreground().color().name() == "#123456"
    hidden_row = names(w).index(".gizli")
    assert lst.item(hidden_row).foreground().color().name() == "#565f89"
