# Sky

A file manager for Linux with both a terminal (TUI) and a graphical (GUI) interface.

## Features

- TUI (Textual) and GUI (PyQt6) modes, or both at once (`tui+gui`)
- Create, rename, copy, move, delete (to trash, recoverable)
- Dual-pane mode (`split : enable`)
- Never overwrites files silently: copies get a `(kopya)` suffix, move/rename refuse on conflict
- Colors, fonts and shortcuts configurable in one plain-text file

## Install

Pick one. All of them add Sky to your application menu (launcher).

**1. From GitHub with pipx (recommended)**

```bash
pipx install git+https://github.com/<your-user>/Sky
sky --install-desktop      # adds the menu entry + icon
```

**2. Clone and run the installer**

```bash
git clone https://github.com/<your-user>/Sky && cd Sky
./install.sh               # own venv, dependencies, menu entry, `sky` command
```

**3. Without installing**

```bash
pip install -r requirements.txt
python -m sky tui          # or: gui | tui+gui
```

Then open **Sky** from your launcher, or run `sky` in a terminal.
Without an argument, `default_mode` from `sky.conf` is used.
Your config (`~/.config/sky/sky.conf`) is never overwritten by re-installing.

Remove: `sky --uninstall-desktop` and `pipx uninstall sky-fm`, or `./uninstall.sh`.

## Configuration

`~/.config/sky/sky.conf`, format `key : value`. Colors are `#rrggbb`/`#rgb`; `#` alone means "use default".
See the commented `sky.conf` for every option (colors, fonts, `trash_path`, `start_path`,
`show_hidden`, `file_types`, `split`, `split_direction`, `default_mode`, `sky.shortcuts`).
Invalid values print a warning at startup and fall back to defaults.

Fonts and `sky.shortcuts` apply to the GUI only (terminals cannot receive `super+...`).
Supported shortcut actions: `exit sky`, `delete file`, `search files`.

## Keys

| TUI | Action | GUI | Action |
|---|---|---|---|
| Enter | open | Enter / double-click | open |
| Backspace | parent dir | Backspace | parent dir |
| Tab | switch panel | Tab | switch panel |
| n / N | new file / dir | Ctrl+N / Ctrl+Shift+N | new file / dir |
| r | rename (prefilled) | F2 | rename |
| c / m | copy / move (asks target dir) | buttons | copy / move |
| d | move to trash (asks) | Delete | move to trash (asks) |
| D | delete permanently (asks) | Shift+Delete | delete permanently |
| H | toggle hidden | Ctrl+H | toggle hidden |
| R | refresh | F5 | refresh |
| q | quit | Ctrl+F | filter by name |

## Development

```bash
pip install pytest -r requirements.txt
pytest
```

## License

MIT
