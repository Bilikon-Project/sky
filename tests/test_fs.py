import os
from pathlib import Path

import pytest

from sky.fs import FileSystem, friendly_error

@pytest.fixture
def fs(tmp_path):
    return FileSystem(str(tmp_path))

def write(p: Path, text="x"):
    p.write_text(text)
    return p

def test_rename_never_overwrites(tmp_path, fs):
    write(tmp_path / "a.txt", "ESKI")
    write(tmp_path / "b.txt", "YENI")
    with pytest.raises(FileExistsError):
        fs.rename(tmp_path / "b.txt", "a.txt")
    assert (tmp_path / "a.txt").read_text() == "ESKI"

def test_rename_rejects_path_components(tmp_path, fs):
    write(tmp_path / "a.txt")
    for bad in ("../x", "sub/x", "", "  ", ".", ".."):
        with pytest.raises(ValueError):
            fs.rename(tmp_path / "a.txt", bad)

def test_mkdir_and_touch_validate_and_refuse_existing(tmp_path, fs):
    with pytest.raises(ValueError):
        fs.mkdir("../kacis")
    assert not (tmp_path.parent / "kacis").exists()
    write(tmp_path / "var.txt", "ICERIK")
    with pytest.raises(FileExistsError):
        fs.touch("var.txt")
    assert (tmp_path / "var.txt").read_text() == "ICERIK"
    fs.mkdir("yeni")
    with pytest.raises(FileExistsError):
        fs.mkdir("yeni")

def test_copy_never_overwrites(tmp_path, fs):
    dest = tmp_path / "hedef"
    dest.mkdir()
    write(dest / "x.txt", "HEDEF")
    src = write(tmp_path / "x.txt", "KAYNAK")
    result = fs.copy(src, dest)
    assert (dest / "x.txt").read_text() == "HEDEF"
    assert result.name == "x (kopya).txt" and result.read_text() == "KAYNAK"
    assert fs.copy(src, dest).name == "x (kopya 2).txt"

def test_copy_into_same_dir_and_archive_names(tmp_path, fs):
    src = write(tmp_path / "a.tar.gz")
    assert fs.copy(src, tmp_path).name == "a (kopya).tar.gz"

def test_copy_dir_into_itself_rejected(tmp_path, fs):
    d = tmp_path / "d"
    (d / "alt").mkdir(parents=True)
    with pytest.raises(ValueError):
        fs.copy(d, d / "alt")

def test_move_conflict_and_into_self(tmp_path, fs):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    write(a / "f.txt", "A")
    write(b / "f.txt", "B")
    with pytest.raises(FileExistsError):
        fs.move(a / "f.txt", b)
    assert (b / "f.txt").read_text() == "B"
    (a / "icerde").mkdir()
    with pytest.raises(ValueError):
        fs.move(a, a / "icerde")
    with pytest.raises(ValueError):
        fs.move(a / "f.txt", a)
    (b / "f.txt").unlink()
    assert fs.move(a / "f.txt", b) == b / "f.txt"

def test_broken_symlink_is_listed(tmp_path, fs):
    os.symlink(tmp_path / "yok", tmp_path / "kirik")
    items = {i["name"]: i for i in fs.list_dir()}
    assert "kirik" in items and items["kirik"]["is_symlink"] and not items["kirik"]["is_dir"]

def test_delete_symlink_to_dir_keeps_target(tmp_path, fs):
    target = tmp_path / "t"
    target.mkdir()
    write(target / "f.txt")
    os.symlink(target, tmp_path / "link")
    fs.delete(tmp_path / "link")
    assert not (tmp_path / "link").exists() and (target / "f.txt").exists()

def test_list_dir_filters_and_sorting(tmp_path, fs):
    (tmp_path / "Zdir").mkdir()
    (tmp_path / "adir").mkdir()
    write(tmp_path / "b.TXT")
    write(tmp_path / "c.md")
    write(tmp_path / "d.tar.gz")
    write(tmp_path / ".gizli")
    names = [i["name"] for i in fs.list_dir()]
    assert names == ["adir", "Zdir", "b.TXT", "c.md", "d.tar.gz"]
    assert ".gizli" in [i["name"] for i in fs.list_dir(show_hidden=True)]
    only = [i["name"] for i in fs.list_dir(file_types=(".txt", ".tar.gz"))]
    assert only == ["adir", "Zdir", "b.TXT", "d.tar.gz"]
    assert [i["name"] for i in fs.list_dir(name_filter="MD")] == ["c.md"]

def test_cd_errors_leave_cwd_untouched(tmp_path, fs):
    write(tmp_path / "dosya")
    before = fs.cwd
    with pytest.raises(NotADirectoryError):
        fs.cd(tmp_path / "dosya")
    with pytest.raises(NotADirectoryError):
        fs.cd(tmp_path / "yok")
    assert fs.cwd == before
    (tmp_path / "alt").mkdir()
    fs.cd("alt")
    assert fs.cwd == tmp_path / "alt"

@pytest.mark.skipif(os.geteuid() == 0, reason="root izin kısıtlamasına takılmaz")
def test_cd_permission_denied(tmp_path, fs):
    d = tmp_path / "kilitli"
    d.mkdir()
    d.chmod(0)
    try:
        with pytest.raises(PermissionError):
            fs.cd(d)
    finally:
        d.chmod(0o700)

def test_recover_climbs_to_existing_parent(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    fs = FileSystem(str(tmp_path / "a" / "b"))
    (tmp_path / "a" / "b").rmdir()
    assert fs.recover() is True and fs.cwd == tmp_path / "a"
    assert fs.recover() is False

def test_trash_roundtrip(tmp_path, fs):
    trash = tmp_path / "Trash"
    f = write(tmp_path / "rapor 1.txt", "ICERIK")
    dest = fs.trash(f, trash)
    assert not f.exists() and dest.read_text() == "ICERIK"
    info = (trash / "info" / "rapor 1.txt.trashinfo").read_text()
    assert info.startswith("[Trash Info]\n")
    assert f"Path={str(f).replace(' ', '%20')}" in info and "DeletionDate=" in info

def test_trash_name_collisions_and_dirs(tmp_path, fs):
    trash = tmp_path / "Trash"
    for i in range(3):
        d = tmp_path / "ayni"
        d.mkdir()
        write(d / "i.txt", str(i))
        fs.trash(d, trash)
    assert sorted(p.name for p in (trash / "files").iterdir()) == ["ayni", "ayni.1", "ayni.2"]
    assert len(list((trash / "info").iterdir())) == 3

def test_trash_symlink_does_not_touch_target(tmp_path, fs):
    target = tmp_path / "t"
    target.mkdir()
    write(target / "f")
    os.symlink(target, tmp_path / "ln")
    fs.trash(tmp_path / "ln", tmp_path / "Trash")
    assert (target / "f").exists() and not os.path.lexists(tmp_path / "ln")

def test_trash_failure_cleans_info(tmp_path, fs):
    trash = tmp_path / "Trash"
    with pytest.raises(FileNotFoundError):
        fs.trash(tmp_path / "yok", trash)
    assert list((trash / "info").iterdir()) == []

def test_human_size():
    assert FileSystem.human_size(0) == "0 B"
    assert FileSystem.human_size(1023) == "1023 B"
    assert FileSystem.human_size(1024) == "1.0 KB"
    assert FileSystem.human_size(5 * 1024 ** 2) == "5.0 MB"
    assert FileSystem.human_size(3 * 1024 ** 4) == "3.0 TB"

def test_friendly_error_messages(tmp_path, fs):
    write(tmp_path / "a")
    write(tmp_path / "b")
    with pytest.raises(FileExistsError) as e:
        fs.rename(tmp_path / "a", "b")
    assert "zaten var" in friendly_error(e.value)
    assert friendly_error(PermissionError(13, "Permission denied")) == "İzin yok"
    assert friendly_error(ValueError("Geçersiz ad")) == "Geçersiz ad"
