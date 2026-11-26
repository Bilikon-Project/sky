from __future__ import annotations

import os
import shutil
import stat
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

_DOUBLE_EXTS = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst")

def friendly_error(exc: BaseException) -> str:

    if isinstance(exc, (ValueError, OSError)) and not getattr(exc, "errno", None):
        return str(exc)
    if isinstance(exc, FileExistsError):
        return "Bu adda bir öğe zaten var"
    if isinstance(exc, PermissionError):
        return "İzin yok"
    if isinstance(exc, FileNotFoundError):
        return "Bulunamadı (başka bir program tarafından silinmiş olabilir)"
    if isinstance(exc, NotADirectoryError):
        return "Dizin değil"
    if isinstance(exc, OSError):
        return exc.strerror or str(exc)
    return str(exc)

def open_default(path: Path | str) -> None:
    subprocess.Popen(
        ["xdg-open", str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

def _validate_name(name: str) -> str:
    name = name.strip()
    if not name or name in (".", ".."):
        raise ValueError("Geçersiz ad")
    if "/" in name or "\0" in name:
        raise ValueError("Ad '/' içeremez")
    if len(name.encode("utf-8", "surrogateescape")) > 255:
        raise ValueError("Ad çok uzun (en fazla 255 bayt)")
    return name

def _split_ext(name: str, is_dir: bool) -> tuple[str, str]:
    if is_dir:
        return name, ""
    low = name.lower()
    for ext in _DOUBLE_EXTS:
        if low.endswith(ext) and len(name) > len(ext):
            return name[:-len(ext)], name[-len(ext):]
    p = Path(name)
    if p.suffix and p.stem:
        return p.stem, p.suffix
    return name, ""

def _unique_path(target: Path, is_dir: bool) -> Path:
    if not os.path.lexists(target):
        return target
    stem, ext = _split_ext(target.name, is_dir)
    n = 1
    while True:
        tag = "(kopya)" if n == 1 else f"(kopya {n})"
        candidate = target.with_name(f"{stem} {tag}{ext}")
        if not os.path.lexists(candidate):
            return candidate
        n += 1

def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False

class FileSystem:
    def __init__(self, start: str = "~"):
        try:
            p = Path(start).expanduser().resolve()
        except (OSError, RuntimeError):
            p = Path.home()
        self.cwd = p if p.is_dir() else Path.home()

    def list_dir(self, show_hidden: bool = False,
                 file_types: tuple[str, ...] | None = None,
                 name_filter: str = "") -> list[dict]:
        items = []
        needle = name_filter.lower()
        with os.scandir(self.cwd) as it:
            for entry in it:
                name = entry.name
                hidden = name.startswith(".")
                if hidden and not show_hidden:
                    continue
                if needle and needle not in name.lower():
                    continue

                is_symlink = entry.is_symlink()
                try:
                    st = entry.stat()
                    is_dir = stat.S_ISDIR(st.st_mode)
                except OSError:

                    try:
                        st = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    is_dir = False

                if file_types and not is_dir and not name.lower().endswith(tuple(file_types)):
                    continue

                items.append({
                    "name": name,
                    "path": Path(entry.path),
                    "is_dir": is_dir,
                    "is_symlink": is_symlink,
                    "is_exec": (not is_dir) and bool(st.st_mode & 0o111) and stat.S_ISREG(st.st_mode),
                    "hidden": hidden,
                    "size": 0 if is_dir else st.st_size,
                })
        items.sort(key=lambda x: (not x["is_dir"], x["name"].casefold()))
        return items

    def cd(self, path) -> Path:
        target = (self.cwd / Path(path).expanduser()).resolve()
        if not target.is_dir():
            raise NotADirectoryError(f"Dizin değil: {target}")
        if not os.access(target, os.R_OK | os.X_OK):
            raise PermissionError(f"İzin yok: {target}")
        self.cwd = target
        return self.cwd

    def up(self) -> Path:
        self.cwd = self.cwd.parent
        return self.cwd

    def recover(self) -> bool:
        changed = False
        while not self.cwd.is_dir() and self.cwd != self.cwd.parent:
            self.cwd = self.cwd.parent
            changed = True
        return changed

    def mkdir(self, name: str) -> Path:
        target = self.cwd / _validate_name(name)
        target.mkdir()
        return target

    def touch(self, name: str) -> Path:
        target = self.cwd / _validate_name(name)
        target.touch(exist_ok=False)
        return target

    def delete(self, path) -> None:
        path = Path(path)
        if path.is_symlink() or not path.is_dir():
            path.unlink()
        else:
            shutil.rmtree(path)

    def trash(self, path, trash_root=None) -> Path:
        path = Path(path)
        if trash_root is None:
            base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
            trash_root = Path(base) / "Trash"
        root = Path(trash_root).expanduser()
        files_dir, info_dir = root / "files", root / "info"
        files_dir.mkdir(parents=True, exist_ok=True)
        info_dir.mkdir(parents=True, exist_ok=True)

        original = Path(os.path.abspath(path))
        n = 0
        while True:
            name = path.name if n == 0 else f"{path.name}.{n}"
            info = info_dir / f"{name}.trashinfo"
            try:
                fd = os.open(info, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                n += 1
                continue
            if os.path.lexists(files_dir / name):
                os.close(fd)
                info.unlink()
                n += 1
                continue
            break

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(
                    "[Trash Info]\n"
                    f"Path={quote(os.fsencode(original))}\n"
                    f"DeletionDate={datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n"
                )
            dest = files_dir / name
            shutil.move(str(path), str(dest))
        except BaseException:
            info.unlink(missing_ok=True)
            raise
        return dest

    def copy(self, src, dest_dir) -> Path:
        src, dest_dir = Path(src), Path(dest_dir)
        if not dest_dir.is_dir():
            raise NotADirectoryError(f"Hedef dizin değil: {dest_dir}")
        real_dir = src.is_dir() and not src.is_symlink()
        if real_dir and _is_inside(dest_dir, src):
            raise ValueError("Bir klasör kendi içine kopyalanamaz")
        dest = _unique_path(dest_dir / src.name, real_dir)
        if src.is_symlink():
            shutil.copy2(src, dest, follow_symlinks=False)
        elif real_dir:
            shutil.copytree(src, dest, symlinks=True)
        else:
            shutil.copy2(src, dest)
        return dest

    def move(self, src, dest_dir) -> Path:
        src, dest_dir = Path(src), Path(dest_dir)
        if not dest_dir.is_dir():
            raise NotADirectoryError(f"Hedef dizin değil: {dest_dir}")
        target = dest_dir / src.name
        if src.parent.resolve() == dest_dir.resolve():
            raise ValueError("Öğe zaten bu dizinde")
        if src.is_dir() and not src.is_symlink() and _is_inside(dest_dir, src):
            raise ValueError("Bir klasör kendi içine taşınamaz")
        if os.path.lexists(target):
            raise FileExistsError(f"Hedefte '{src.name}' adında bir öğe zaten var")
        shutil.move(str(src), str(target))
        return target

    def rename(self, path, new_name: str) -> Path:
        path = Path(path)
        new_name = _validate_name(new_name)
        target = path.with_name(new_name)
        if new_name == path.name:
            return path
        if os.path.lexists(target):
            raise FileExistsError(f"'{new_name}' adında bir öğe zaten var")
        path.rename(target)
        return target

    @staticmethod
    def human_size(n: int) -> str:
        size = float(n)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
