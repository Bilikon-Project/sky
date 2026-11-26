from sky import cli

def test_install_and_uninstall_desktop(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(cli, "CONFIG_DIR", tmp_path / "cfg")
    assert cli.main(["--install-desktop"]) == 0
    desktop = tmp_path / "data" / "applications" / "sky.desktop"
    text = desktop.read_text()
    assert any(l.startswith("Exec=") and l.endswith(" gui") for l in text.splitlines())
    assert (tmp_path / "data/icons/hicolor/scalable/apps/sky.svg").exists()
    conf = tmp_path / "cfg" / "sky.conf"
    conf.write_text("show_hidden : true\n")
    cli.main(["--install-desktop"])
    assert conf.read_text() == "show_hidden : true\n"
    assert cli.main(["--uninstall-desktop"]) == 0
    assert not desktop.exists() and conf.exists()

def test_version_help_and_bad_mode(capsys):
    assert cli.main(["--version"]) == 0 and "sky " in capsys.readouterr().out
    assert cli.main(["--help"]) == 0
    assert cli.main(["bogus"]) == 2
