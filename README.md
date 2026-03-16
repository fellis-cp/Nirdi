# Nirdi — Niri Monitor Manager

Nirdi is a modern, lightweight GTK4 GUI for managing monitors in the [niri](https://github.com/YaLTeR/niri) Wayland compositor. It allows you to view connected displays, toggle them on/off, and change resolutions or refresh rates with a user-friendly interface.

![Nirdi Screenshot](https://raw.githubusercontent.com/username/nirdi/main/screenshot.png) *(Placeholder: Add your own screenshot here!)*

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

### Running Locally
You can run the application directly from the repository:

```bash
python3 main.py
```

### Desktop Integration
To make Nirdi appear in your application launcher (wofi, rofi, etc.), copy the `.desktop` file to your local applications directory:

```bash
cp niri-monitor-manager.desktop ~/.local/share/applications/
```

> [!NOTE]  
> If you move the project directory, you will need to update the `Exec` path in the `.desktop` file.

## Development

The project is structured into two main components:
- `main.py`: The GTK4 application and UI layout.
- `monitor_backend.py`: Logic for parsing `niri` output and executing `wlr-randr` commands.
- `style.css`: Custom styling tokens for the premium dark-mode look.

## License
MIT
