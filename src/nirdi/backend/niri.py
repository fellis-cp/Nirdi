"""
monitor_backend.py
------------------
Parses `niri msg outputs` and wraps `wlr-randr` to control monitors.
Supports: enable/disable, resolution change, refresh rate change.
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
    def refresh_label(self) -> str:
        return f"{self.refresh:.3f} Hz"

    @property
    def label(self) -> str:
        flags = []
        if self.current:
            flags.append("current")
        if self.preferred:
            flags.append("preferred")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        return f"{self.resolution} @ {self.refresh:.3f} Hz{flag_str}"


@dataclass
class Monitor:
    connector: str          # e.g. "eDP-1", "HDMI-A-1"
    model: str              # human label from niri
    enabled: bool
    current_mode: Optional[str]  # e.g. "1920x1080 @ 100.001 Hz"
    modes: list[MonitorMode] = field(default_factory=list)
    physical_size: Optional[str] = None  # e.g. "530x290 mm"
    scale: Optional[float] = None
    transform: Optional[str] = None

    @property
    def is_builtin(self) -> bool:
        return self.connector.lower().startswith("edp")

    @property
    def display_name(self) -> str:
        """Short model name stripped of extra whitespace."""
        return " ".join(self.model.split())

    @property
    def current_resolution(self) -> Optional[str]:
        if self.current_mode and "@" in self.current_mode:
            return self.current_mode.split("@")[0].strip()
        return None

    @property
    def current_refresh(self) -> Optional[float]:
        if self.current_mode and "@" in self.current_mode:
            hz_str = self.current_mode.split("@")[1].strip()
            try:
                return float(hz_str.replace("Hz", "").strip())
            except ValueError:
                return None
        return None

    def resolutions(self) -> list[str]:
        """Unique resolutions in the order they appear (highest first)."""
        seen = []
        for m in self.modes:
            if m.resolution not in seen:
                seen.append(m.resolution)
        return seen

    def refresh_rates_for(self, resolution: str) -> list[MonitorMode]:
        """All modes that match the given resolution, ordered by refresh desc."""
        matches = [m for m in self.modes if m.resolution == resolution]
        return sorted(matches, key=lambda m: m.refresh, reverse=True)


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

    first_line = lines[0]

    # Extract connector name e.g. (eDP-1)
    connector_match = re.search(r'\(([^)]+)\)', first_line)
    if not connector_match:
        return None
    connector = connector_match.group(1).strip()

    # Extract model label from first double-quoted string
    model_match = re.search(r'Output\s+"([^"]+)"', first_line)
    model = model_match.group(1).strip() if model_match else connector

    # niri puts status on indented line 1
    disabled = False
    current_mode_str: Optional[str] = None

    if len(lines) > 1:
        second_line = lines[1].strip()
        if second_line == "Disabled":
            disabled = True
        else:
            m = re.search(
                r'Current mode:\s*([\d]+x[\d]+\s*@\s*[\d.]+(?:\s*Hz)?)',
                second_line
            )
            if m:
                current_mode_str = m.group(1).strip()

    enabled = not disabled
    full_text = "\n".join(lines)

    physical_match = re.search(r'Physical size:\s*(\S+\s*mm)', full_text)
    physical_size = physical_match.group(1) if physical_match else None

    scale_match = re.search(r'\bScale:\s*([\d.]+)', full_text)
    scale = float(scale_match.group(1)) if scale_match else None

    transform_match = re.search(r'\bTransform:\s*(\S+)', full_text)
    transform = transform_match.group(1) if transform_match else None

    # Parse available modes from "Available modes:" section only
    modes: list[MonitorMode] = []
    in_modes = False
    for line in lines:
        stripped = line.strip()
        if stripped == "Available modes:":
            in_modes = True
            continue
        if in_modes:
            m = re.match(r'([\d]+x[\d]+)@([\d.]+)\s*(.*)', stripped)
            if m:
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
            elif stripped and not stripped.startswith("#"):
                # End of modes section
                in_modes = False

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
    """Enable or disable a monitor via wlr-randr."""
    flag = "--on" if enabled else "--off"
    return _run_wlr_randr(
        ["--output", connector, flag],
        f"Monitor {connector} {'enabled' if enabled else 'disabled'} successfully."
    )


def set_monitor_mode(connector: str, resolution: str, refresh: float) -> tuple[bool, str]:
    """Change a monitor's resolution and/or refresh rate via wlr-randr."""
    mode_str = f"{resolution}@{refresh:.3f}Hz"
    return _run_wlr_randr(
        ["--output", connector, "--mode", mode_str],
        f"Mode set to {mode_str} on {connector}."
    )


def _run_wlr_randr(args: list[str], success_msg: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["wlr-randr"] + args,
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, success_msg
        err = result.stderr.strip() or result.stdout.strip()
        return False, f"wlr-randr error: {err}"
    except FileNotFoundError:
        return False, "wlr-randr not found. Install with: pacman -S wlr-randr"
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
        print(f"       Resolutions: {m.resolutions()}")
        print(f"       Modes: {len(m.modes)} available")
