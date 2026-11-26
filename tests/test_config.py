from sky.config import Config, mix

def make(tmp_path, text):
    p = tmp_path / "sky.conf"
    p.write_text(text, encoding="utf-8")
    return Config(p)

def test_hex_colors_survive_comment_stripping(tmp_path):
    cfg = make(tmp_path, "background_color : #112233\naccent_color : #abc  # kısa renk\n")
    assert cfg.color("background_color") == "#112233"
    assert cfg.color("accent_color") == "#aabbcc"

def test_placeholder_hash_means_default(tmp_path):
    cfg = make(tmp_path, "background_color : #\n")
    assert cfg.get("background_color") is None
    assert cfg.color("background_color") == "#1a1b26"
    assert cfg.warnings == []

def test_invalid_color_warns_and_falls_back(tmp_path):
    cfg = make(tmp_path, "accent_color : #zzzzzz\n")
    assert cfg.color("accent_color") == "#7aa2f7"
    assert any("accent_color" in w for w in cfg.warnings)

def test_blank_colors_derive_from_accent(tmp_path):
    cfg = make(tmp_path, "accent_color : #ff0000\naccent_color_1 : #00ff00\ncolor_dir : #\n")
    assert cfg.color("color_dir") == "#ff0000"
    assert cfg.color("color_symlink") == "#00ff00"

def test_values_may_contain_colons(tmp_path):
    cfg = make(tmp_path, 'start_path : C:/x\nsky.shortcuts : super+x : get "https://a.b/c"\n')
    assert cfg.get("start_path") == "C:/x"
    assert cfg.shortcuts["super+x"] == 'get "https://a.b/c"'

def test_split_flag_from_sky_conf(tmp_path):
    assert make(tmp_path, "split : enable\n").split_enabled is True
    assert make(tmp_path, "split : disable\n").split_enabled is False
    assert make(tmp_path, "split_mode : on\n").split_enabled is True
    assert make(tmp_path, "").split_enabled is False

def test_split_direction_validation(tmp_path):
    assert make(tmp_path, "split_direction : TOP\n").split_direction == "top"
    cfg = make(tmp_path, "split_direction : diagonal\n")
    assert cfg.split_direction == "right" and cfg.warnings

def test_shortcuts_toggle(tmp_path):
    assert make(tmp_path, "sky.shortcuts : disable\n").shortcuts_enabled is False
    assert make(tmp_path, "sky.shortcuts : enable\n").shortcuts_enabled is True

def test_file_types(tmp_path):
    cfg = make(tmp_path, "file_types_all : false\nfile_types : .TXT , md, .tar.gz ,\n")
    assert cfg.visible_file_types == (".txt", ".md", ".tar.gz")
    assert make(tmp_path, "file_types_all : true\nfile_types : .txt\n").visible_file_types is None
    assert make(tmp_path, "file_types_all : false\n").visible_file_types is None

def test_default_mode(tmp_path):
    assert make(tmp_path, "default_mode : tui+gui\n").default_mode == "tui+gui"
    assert make(tmp_path, "default_mode : bogus\n").default_mode == "tui"

def test_trash_path_expands_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = make(tmp_path, "trash_path : ~/cop\n")
    assert cfg.trash_path == tmp_path / "cop"

def test_missing_file_uses_defaults(tmp_path):
    cfg = Config(tmp_path / "yok.conf")
    assert cfg.warnings == [] and cfg.default_mode == "tui"

def test_mix_endpoints():
    assert mix("#000000", "#ffffff", 0) == "#000000"
    assert mix("#000000", "#ffffff", 1) == "#ffffff"
    assert mix("#000000", "#ffffff", 0.5) == "#808080"
