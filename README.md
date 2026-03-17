# Nirdi — Niri Monitor Manager

Nirdi is a modern, lightweight GTK4 GUI for managing monitors in the [niri](https://github.com/YaLTeR/niri) Wayland compositor. It allows you to view connected displays, toggle them on/off, and change resolutions or refresh rates with a user-friendly interface.

<img width="1900" height="807" alt="image" src="https://github.com/user-attachments/assets/9f1ffa26-c883-4417-8d1f-cd8d86bf2d43" />


## Features

- **Monitor Status**: Real-time view of all connected displays.
- **Power Control**: Easily enable or disable monitors with a single toggle.
- **Mode Switching**: Change resolution and refresh rate via intuitive dropdowns.
- **Smart Refresh**: Syncs with the current system state using `niri msg outputs`.
- **Modern UI**: Styled with a clean, dark-themed GTK4 interface.

## Prerequisites

Nirdi depends on the following tools:

- **niri**: The Wayland compositor (used for querying output information).
- **wlr-randr**: Used for applying display configurations.
- **GTK4**: The GUI toolkit.
- **PyGObject**: Python bindings for GTK4.

### Installation on Arch Linux

```bash
sudo pacman -S niri wlr-randr gtk4 python-gobject
```

## Installation & Usage

To install Nirdi on your local user account (`~/.local/share/nirdi` and `~/.local/bin/nirdi`), simply clone this repository and run the install script:

```bash
git clone https://github.com/username/nirdi.git
cd nirdi
./install.sh
```

This will check dependencies, structure the Python files, install the executable script to `~/.local/bin`, and register the `.desktop` file for your application launcher.
Make sure `~/.local/bin` is in your `$PATH`.

### Running Locally without installation

If you prefer to run from source without installing:

```bash
PYTHONPATH=src python3 -m nirdi
```

## Development

The project is structured into a standard python package under `src/`:
- `src/nirdi/ui/app.py`: The GTK4 application and UI layout.
- `src/nirdi/ui/style.css`: Custom styling tokens for the premium dark-mode look.
- `src/nirdi/backend/niri.py`: Logic for parsing `niri` output and executing `wlr-randr` commands.

## License
MIT
