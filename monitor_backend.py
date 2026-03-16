"""
monitor_backend.py
------------------
Parses `niri msg outputs` and wraps `wlr-randr` to enable/disable monitors.
"""

import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MonitorMode:
    resolution: str
    refresh: float
    preferred: bool = False
    current: bool = False

    @property
    def label(self) -> str:
        flags = []
        if self.current:
            flags.append("current")
        if self.preferred:
            flags.append("preferred")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        return f"{self.resolution} @ {self.refresh:.2f} Hz{flag_str}"


@dataclass
class Monitor:
    connector: str          # e.g. "eDP-1", "HDMI-A-1"
    model: str              # human label from niri
    enabled: bool
    current_mode: Optional[str]  # e.g. "1920x1080 @ 100.00 Hz"
    modes: list[MonitorMode] = field(default_factory=list)
    physical_size: Optional[str] = None  # e.g. "530x290 mm"
    scale: Optional[float] = None
    transform: Optional[str] = None

    @property
    def is_builtin(self) -> bool:
        return self.connector.lower().startswith("edp")

    @property
    def display_name(self) -> str:
        """Short model name stripped of newlines."""
        return " ".join(self.model.split())

    @property
    def resolution(self) -> Optional[str]:
        if self.current_mode:
            parts = self.current_mode.split("@")
            return parts[0].strip() if parts else None
        return None

    @property
    def refresh_rate(self) -> Optional[str]:
        if self.current_mode and "@" in self.current_mode:
            return self.current_mode.split("@")[1].strip()
        return None


def get_monitors() -> list[Monitor]:
    """Run `niri msg outputs` and return parsed Monitor objects."""
    try:
        result = subprocess.run(
            ["niri", "msg", "outputs"],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"Error running niri msg outputs: {e}")
        return []

    return _parse_niri_outputs(output)


def _parse_niri_outputs(text: str) -> list[Monitor]:
    monitors: list[Monitor] = []

    # Split by double-newlines to get per-output blocks, but niri separates
    # outputs with a blank line after the last field, so we split on the
    # Output header lines which always start at column 0.
    output_blocks = re.split(r'\n(?=Output ")', text.strip())

    for block in output_blocks:
        if not block.strip():
            continue

        monitor = _parse_output_block(block)
        if monitor:
            monitors.append(monitor)

    return monitors


def _parse_output_block(block: str) -> Optional[Monitor]:
    lines = block.strip().splitlines()
    if not lines:
        return None

    # First line: Output "Model\nvariant" (CONNECTOR)    [Disabled | Current mode: ...]
    first_line = lines[0]

    # Extract connector name
    connector_match = re.search(r'\(([^)]+)\)', first_line)
    if not connector_match:
        return None
    connector = connector_match.group(1).strip()

    # Extract model – everything in the first double-quotes
    model_match = re.search(r'Output\s+"([^"]+)"', first_line)
    model = model_match.group(1).strip() if model_match else connector

    # niri puts state on an indented line 1 — either "Disabled" or "Current mode: ..."
    disabled = False
    current_mode_str: Optional[str] = None

    if len(lines) > 1:
        second_line = lines[1].strip()
        if second_line == "Disabled":
            disabled = True
        else:
            current_mode_match = re.search(
                r'Current mode:\s*([\d]+x[\d]+\s*@\s*[\d.]+(?:\s*Hz)?)',
                second_line
            )
            if current_mode_match:
                current_mode_str = current_mode_match.group(1).strip()

    enabled = not disabled

    # Parse remaining fields
    full_text = "\n".join(lines)

    physical_match = re.search(r'Physical size:\s*(\S+\s*mm)', full_text)
    physical_size = physical_match.group(1) if physical_match else None

    scale_match = re.search(r'\bScale:\s*([\d.]+)', full_text)
    scale = float(scale_match.group(1)) if scale_match else None

    transform_match = re.search(r'\bTransform:\s*(\S+)', full_text)
    transform = transform_match.group(1) if transform_match else None

    # Parse available modes
    modes: list[MonitorMode] = []
    for m in re.finditer(
        r'([\d]+x[\d]+)@([\d.]+)\s*((?:\([^)]*\)\s*)*)',
        full_text
    ):
        res = m.group(1)
        refresh = float(m.group(2))
        flags_str = m.group(3).lower()
        preferred = "preferred" in flags_str
        current = "current" in flags_str
        modes.append(MonitorMode(
            resolution=res,
            refresh=refresh,
            preferred=preferred,
            current=current,
        ))

    return Monitor(
        connector=connector,
        model=model,
        enabled=enabled,
        current_mode=current_mode_str,
        modes=modes,
        physical_size=physical_size,
        scale=scale,
        transform=transform,
    )


def set_monitor_enabled(connector: str, enabled: bool) -> tuple[bool, str]:
    """
    Enable or disable a monitor via wlr-randr.
    Returns (success, message).
    """
    flag = "--on" if enabled else "--off"
    try:
        result = subprocess.run(
            ["wlr-randr", "--output", connector, flag],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, f"Monitor {connector} {'enabled' if enabled else 'disabled'} successfully."
        else:
            err = result.stderr.strip() or result.stdout.strip()
            return False, f"wlr-randr error: {err}"
    except FileNotFoundError:
        return False, "wlr-randr not found. Please install it (pacman -S wlr-randr)."
    except subprocess.TimeoutExpired:
        return False, "Timed out waiting for wlr-randr."
    except subprocess.SubprocessError as e:
        return False, str(e)


if __name__ == "__main__":
    monitors = get_monitors()
    for m in monitors:
        print(f"[{'ON ' if m.enabled else 'OFF'}] {m.connector:12s}  {m.display_name}")
        if m.current_mode:
            print(f"       Mode : {m.current_mode}")
        if m.physical_size:
            print(f"       Size : {m.physical_size}")
        print(f"       Modes: {len(m.modes)} available")
