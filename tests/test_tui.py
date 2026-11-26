import asyncio

import pytest

pytest.importorskip("textual")

from sky.config import Config
from sky.tui import SkyTUI

def make_app(tmp_path, split=False, extra=""):
    root = tmp_path / "kok"
    (root / "adir").mkdir(parents=True)
    (root / "bdir").mkdir()
    (root / "c.txt").write_text("c")
    (root / "d.txt").write_text("d")
    conf = tmp_path / "sky.conf"
    conf.write_text(
        f"start_path : {root}\ntrash_path : {tmp_path / 'Trash'}\n"
        f"split : {'enable' if split else 'disable'}\n{extra}\n")
    return SkyTUI(Config(conf)), root

def run(coro):
    return asyncio.run(coro)

def test_tab_switches_active_panel(tmp_path):
    app, _ = make_app(tmp_path, split=True)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.active == 1 and app.focused.id == "table1"
            await pilot.press("tab")
            await pilot.pause()
            assert app.active == 2 and app.focused.id == "table2"
            await pilot.press("tab")
            await pilot.pause()
            assert app.active == 1

    run(scenario())

def test_actions_go_to_active_panel(tmp_path):
    app, root = make_app(tmp_path, split=True)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("tab")
            await pilot.press("enter")
            await pilot.pause()
            assert app.panels[2].fs.cwd == root / "adir"
            assert app.panels[1].fs.cwd == root
            await pilot.press("n", *"yeni", "enter")
            await pilot.pause()

    run(scenario())
    assert (root / "adir" / "yeni").exists()
    assert not (root / "yeni").exists()

def test_clicking_other_panel_updates_active(tmp_path):
    app, _ = make_app(tmp_path, split=True)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#table2").focus()
            await pilot.pause()
            assert app.active == 2

    run(scenario())

def test_delete_moves_to_trash_after_confirmation(tmp_path):
    app, root = make_app(tmp_path)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "down", "d")
            await pilot.pause()
            assert app.query_one("#prompt").display
            await pilot.press("h", "enter")
            await pilot.pause()
            assert (root / "c.txt").exists()
            await pilot.press("d", "e", "enter")
            await pilot.pause()

    run(scenario())
    assert not (root / "c.txt").exists()
    assert (tmp_path / "Trash" / "files" / "c.txt").exists()
    assert (tmp_path / "Trash" / "info" / "c.txt.trashinfo").exists()

def test_permanent_delete_uppercase_binding(tmp_path):
    app, root = make_app(tmp_path)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "down", "D", "e", "enter")
            await pilot.pause()

    run(scenario())
    assert not (root / "c.txt").exists()
    assert not (tmp_path / "Trash").exists()

def test_new_dir_uppercase_binding_and_rename_prefill(tmp_path):
    app, root = make_app(tmp_path)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("N", *"klasor", "enter")
            await pilot.pause()
            assert (root / "klasor").is_dir()
            await pilot.press("r")
            await pilot.pause()
            assert app.query_one("#prompt").value != ""
            await pilot.press("escape")

    run(scenario())

def test_rename_refuses_to_overwrite(tmp_path):
    app, root = make_app(tmp_path)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "down", "r")
            inp = app.query_one("#prompt")
            inp.value = "d.txt"
            await pilot.press("enter")
            await pilot.pause()

    run(scenario())
    assert (root / "c.txt").read_text() == "c" and (root / "d.txt").read_text() == "d"

def test_cursor_is_kept_on_refresh_and_up_selects_previous(tmp_path):
    app, root = make_app(tmp_path)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "down", "R")
            await pilot.pause()
            assert app._table().cursor_row == 2
            await pilot.press("down", "up", "up")
            await pilot.press("enter")
            await pilot.pause()
            assert app.panels[1].fs.cwd == root / "bdir"
            await pilot.press("backspace")
            await pilot.pause()
            assert app.selected()["name"] == "bdir"

    run(scenario())

def test_hidden_toggle_and_symlink_listing(tmp_path):
    app, root = make_app(tmp_path)
    (root / ".gizli").write_text("g")

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app._table().row_count == 4
            await pilot.press("H")
            await pilot.pause()
            assert app._table().row_count == 5
            await pilot.press("H")
            await pilot.pause()
            assert app._table().row_count == 4

    run(scenario())

def test_markup_like_names_are_shown_literally(tmp_path):
    app, root = make_app(tmp_path)
    (root / "[red]rapor").write_text("x")

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            names = [r[0].plain for r in (app._table().get_row_at(i) for i in range(app._table().row_count))]
            assert any("[red]rapor" in n for n in names)

    run(scenario())

def test_deleted_cwd_recovers(tmp_path):
    app, root = make_app(tmp_path)

    async def scenario():
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            (root / "adir").rmdir()
            await pilot.press("R")
            await pilot.pause()
            assert app.panels[1].fs.cwd == root

    run(scenario())

def test_css_variables_follow_config(tmp_path):
    app, _ = make_app(tmp_path, extra="background_color : #101010\naccent_color : #ff8800")
    variables = app.get_css_variables()
    assert variables["sky-bg"] == "#101010" and variables["sky-accent"] == "#ff8800"
