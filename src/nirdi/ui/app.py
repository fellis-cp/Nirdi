#!/usr/bin/env python3
"""
main.py – Niri Monitor Manager
GTK4 GUI to view, toggle, and change resolution/refresh rate of monitors.
Uses `niri msg outputs` for info and `wlr-randr` for control.
"""

import os
import sys
import threading
import time

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, Pango

from nirdi.backend import niri as backend
from nirdi.backend.niri import Monitor


APP_ID = "io.niri.monitor-manager"
STYLE_CSS = os.path.join(os.path.dirname(__file__), "style.css")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Monitor Card Widget
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MonitorCard(Gtk.Box):
    """
    A card showing one monitor's info with:
      - power toggle
      - resolution dropdown
      - refresh rate dropdown (changes when resolution changes)
      - Apply button
    """

    def __init__(self, monitor: Monitor, on_toggle_cb, on_mode_cb):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._monitor = monitor
        self._on_toggle_cb = on_toggle_cb
        self._on_mode_cb = on_mode_cb
        self._ignore_toggle = False
        self._ignore_dropdowns = False

        self.add_css_class("monitor-card")
        if monitor.enabled:
            self.add_css_class("active")
        else:
            self.add_css_class("disabled")

        self._build_ui()

    # ── Build UI ──────────────────────────────────────────────

    def _build_ui(self):
        m = self._monitor

        # ────────────────────────────────────────────────────────
        # TOP ROW: icon + info + toggle
        # ────────────────────────────────────────────────────────
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.append(top_row)

        # Icon
        icon = Gtk.Label()
        icon.set_markup("💻" if m.is_builtin else "🖥️")
        icon.add_css_class("monitor-icon")
        icon.set_valign(Gtk.Align.CENTER)
        icon.set_margin_end(16)
        top_row.append(icon)

        # Info column (name + model + badges)
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        info_box.set_hexpand(True)
        info_box.set_valign(Gtk.Align.CENTER)

        name_lbl = Gtk.Label(label=m.connector)
        name_lbl.add_css_class("monitor-name")
        name_lbl.set_halign(Gtk.Align.START)
        info_box.append(name_lbl)

        model_lbl = Gtk.Label(label=m.display_name)
        model_lbl.add_css_class("monitor-model")
        model_lbl.set_halign(Gtk.Align.START)
        model_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        model_lbl.set_max_width_chars(38)
        info_box.append(model_lbl)

        # Badges row
        badge_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        badge_row.set_margin_top(2)

        self._status_badge = Gtk.Label()
        self._status_badge.add_css_class("badge")
        self._update_status_badge()
        badge_row.append(self._status_badge)

        if m.enabled and m.current_mode:
            mb = Gtk.Label(label=m.current_mode)
            mb.add_css_class("badge")
            mb.add_css_class("badge-mode")
            badge_row.append(mb)

        if m.physical_size:
            sb = Gtk.Label(label=m.physical_size)
            sb.add_css_class("badge")
            sb.add_css_class("badge-mode")
            badge_row.append(sb)

        info_box.append(badge_row)
        top_row.append(info_box)

        # Power toggle on the right
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        toggle_box.set_valign(Gtk.Align.CENTER)
        toggle_box.set_margin_start(18)

        pwr_lbl = Gtk.Label(label="Power")
        pwr_lbl.set_css_classes(["monitor-model"])
        pwr_lbl.set_halign(Gtk.Align.CENTER)
        toggle_box.append(pwr_lbl)

        self._switch = Gtk.Switch()
        self._switch.set_active(m.enabled)
        self._switch.set_valign(Gtk.Align.CENTER)
        self._switch.set_halign(Gtk.Align.CENTER)
        self._switch.connect("state-set", self._on_state_set)
        toggle_box.append(self._switch)

        top_row.append(toggle_box)

        # ────────────────────────────────────────────────────────
        # MODE ROW: resolution + refresh dropdowns + Apply button
        # (only shown when monitor is enabled and has modes)
        # ────────────────────────────────────────────────────────
        self._mode_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self._mode_row.set_margin_top(14)
        self._mode_row.set_visible(m.enabled and bool(m.modes))
        self.append(self._mode_row)

        mode_section_lbl = Gtk.Label(label="MODE")
        mode_section_lbl.add_css_class("section-label")
        mode_section_lbl.set_valign(Gtk.Align.CENTER)
        self._mode_row.append(mode_section_lbl)

        # Resolution dropdown
        res_lbl = Gtk.Label(label="Resolution")
        res_lbl.add_css_class("dropdown-label")
        res_lbl.set_valign(Gtk.Align.CENTER)
        self._mode_row.append(res_lbl)

        self._res_model = Gtk.StringList()
        self._res_dropdown = Gtk.DropDown(model=self._res_model)
        self._res_dropdown.add_css_class("mode-dropdown")
        self._res_dropdown.set_valign(Gtk.Align.CENTER)
        self._mode_row.append(self._res_dropdown)

        # Refresh rate dropdown
        hz_lbl = Gtk.Label(label="Refresh")
        hz_lbl.add_css_class("dropdown-label")
        hz_lbl.set_valign(Gtk.Align.CENTER)
        self._mode_row.append(hz_lbl)

        self._hz_model = Gtk.StringList()
        self._hz_dropdown = Gtk.DropDown(model=self._hz_model)
        self._hz_dropdown.add_css_class("mode-dropdown")
        self._hz_dropdown.set_valign(Gtk.Align.CENTER)
        self._mode_row.append(self._hz_dropdown)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self._mode_row.append(spacer)

        # Apply button
        self._apply_btn = Gtk.Button(label="Apply")
        self._apply_btn.add_css_class("apply-btn")
        self._apply_btn.set_valign(Gtk.Align.CENTER)
        self._apply_btn.connect("clicked", self._on_apply_clicked)
        self._mode_row.append(self._apply_btn)

        # Populate dropdowns
        self._populate_resolutions(select_current=True)

        # Connect resolution change → update Hz list
        self._res_dropdown.connect("notify::selected", self._on_resolution_changed)

    # ── Dropdown population ───────────────────────────────────

    def _populate_resolutions(self, select_current: bool = True):
        self._ignore_dropdowns = True
        while self._res_model.get_n_items() > 0:
            self._res_model.remove(0)

        resolutions = self._monitor.resolutions()
        for r in resolutions:
            self._res_model.append(r)

        # Select current resolution
        if select_current and self._monitor.current_resolution:
            try:
                idx = resolutions.index(self._monitor.current_resolution)
                self._res_dropdown.set_selected(idx)
            except ValueError:
                self._res_dropdown.set_selected(0)
        else:
            self._res_dropdown.set_selected(0)

        self._ignore_dropdowns = False
        self._populate_refresh_rates(select_current=select_current)

    def _populate_refresh_rates(self, select_current: bool = True):
        self._ignore_dropdowns = True
        while self._hz_model.get_n_items() > 0:
            self._hz_model.remove(0)

        res_idx = self._res_dropdown.get_selected()
        resolutions = self._monitor.resolutions()
        if res_idx >= len(resolutions):
            self._ignore_dropdowns = False
            return

        selected_res = resolutions[res_idx]
        hz_modes = self._monitor.refresh_rates_for(selected_res)

        for mode in hz_modes:
            self._hz_model.append(f"{mode.refresh:.3f} Hz")

        # Select current refresh
        if select_current and self._monitor.current_refresh is not None:
            current_hz = self._monitor.current_refresh
            for i, mode in enumerate(hz_modes):
                if abs(mode.refresh - current_hz) < 0.1:
                    self._hz_dropdown.set_selected(i)
                    break
        else:
            self._hz_dropdown.set_selected(0)

        self._ignore_dropdowns = False

    def _on_resolution_changed(self, dropdown, _param):
        if self._ignore_dropdowns:
            return
        self._populate_refresh_rates(select_current=False)

    # ── Helpers ───────────────────────────────────────────────

    def _update_status_badge(self):
        if self._monitor.enabled:
            self._status_badge.set_label("Active")
            self._status_badge.set_css_classes(["badge", "badge-active"])
        else:
            self._status_badge.set_label("Disabled")
            self._status_badge.set_css_classes(["badge", "badge-disabled"])

    def _get_selected_mode(self):
        """Return (resolution, refresh_float) from current dropdown state."""
        res_idx = self._res_dropdown.get_selected()
        hz_idx  = self._hz_dropdown.get_selected()
        resolutions = self._monitor.resolutions()
        if res_idx >= len(resolutions):
            return None, None
        selected_res = resolutions[res_idx]
        hz_modes = self._monitor.refresh_rates_for(selected_res)
        if hz_idx >= len(hz_modes):
            return None, None
        return selected_res, hz_modes[hz_idx].refresh

    # ── Signal handlers ───────────────────────────────────────

    def _on_state_set(self, switch, state):
        if self._ignore_toggle:
            return False
        self._on_toggle_cb(self._monitor.connector, state)
        return True  # we handle state ourselves

    def _on_apply_clicked(self, _btn):
        res, hz = self._get_selected_mode()
        if res is None or hz is None:
            return
        self._apply_btn.set_sensitive(False)
        self._apply_btn.set_label("Applying…")
        self._on_mode_cb(self._monitor.connector, res, hz)

    # ── External refresh ──────────────────────────────────────

    def refresh(self, monitor: Monitor):
        """Update visual state after a backend refresh."""
        self._ignore_toggle = True
        self._monitor = monitor

        self._switch.set_active(monitor.enabled)
        self._update_status_badge()

        if monitor.enabled:
            self.remove_css_class("disabled")
            self.add_css_class("active")
        else:
            self.remove_css_class("active")
            self.add_css_class("disabled")

        # Show/hide mode row
        self._mode_row.set_visible(monitor.enabled and bool(monitor.modes))

        # Re-populate dropdowns to reflect new state
        if monitor.enabled:
            self._populate_resolutions(select_current=True)

        # Re-enable apply button
        self._apply_btn.set_sensitive(True)
        self._apply_btn.set_label("Apply")

        self._ignore_toggle = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main Application Window
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MonitorManagerWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Monitor Manager")
        self.set_default_size(560, 520)
        self.set_resizable(True)

        self._cards: dict[str, MonitorCard] = {}
        self._monitors: list[Monitor] = []

        self._build_ui()
        self._refresh_monitors()

    def _build_ui(self):
        # Header bar
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title_box.set_valign(Gtk.Align.CENTER)
        title_lbl = Gtk.Label(label="Monitor Manager")
        title_lbl.add_css_class("title")
        sub_lbl = Gtk.Label(label="Niri Wayland")
        sub_lbl.add_css_class("monitor-model")
        title_box.append(title_lbl)
        title_box.append(sub_lbl)
        header.set_title_widget(title_box)

        self._refresh_btn = Gtk.Button(label="⟳  Refresh")
        self._refresh_btn.add_css_class("refresh-btn")
        self._refresh_btn.connect("clicked", self._on_refresh_clicked)
        header.pack_end(self._refresh_btn)
        self.set_titlebar(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._main_box.add_css_class("main-box")
        scroll.set_child(self._main_box)

        section_lbl = Gtk.Label(label="CONNECTED DISPLAYS")
        section_lbl.add_css_class("section-label")
        section_lbl.set_halign(Gtk.Align.START)
        section_lbl.set_margin_bottom(4)
        self._main_box.append(section_lbl)

        self._cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._main_box.append(self._cards_box)

        self._toast_label = Gtk.Label(label="")
        self._toast_label.add_css_class("status-bar")
        self._toast_label.set_halign(Gtk.Align.CENTER)
        self._toast_label.set_margin_top(16)
        self._main_box.append(self._toast_label)

        self.set_child(scroll)

    # ── Data refresh ─────────────────────────────────────────

    def _refresh_monitors(self):
        self._set_status("Refreshing…")
        self._refresh_btn.set_sensitive(False)

        def worker():
            monitors = backend.get_monitors()
            GLib.idle_add(self._on_monitors_loaded, monitors)

        threading.Thread(target=worker, daemon=True).start()

    def _on_monitors_loaded(self, monitors: list[Monitor]):
        self._refresh_btn.set_sensitive(True)
        self._monitors = monitors

        if not monitors:
            self._set_status("No monitors found. Is niri running?", error=True)
            return False

        existing = set(self._cards.keys())
        new = {m.connector for m in monitors}

        for connector in existing - new:
            self._cards_box.remove(self._cards.pop(connector))

        for monitor in monitors:
            if monitor.connector in self._cards:
                self._cards[monitor.connector].refresh(monitor)
            else:
                card = MonitorCard(
                    monitor,
                    on_toggle_cb=self._on_toggle,
                    on_mode_cb=self._on_mode_change,
                )
                self._cards[monitor.connector] = card
                self._cards_box.append(card)

        now = time.strftime("%H:%M:%S")
        active = sum(1 for m in monitors if m.enabled)
        self._set_status(
            f"{len(monitors)} display{'s' if len(monitors) != 1 else ''} detected  ·  "
            f"{active} active  ·  Updated {now}"
        )
        return False

    # ── Toggle handler ────────────────────────────────────────

    def _on_toggle(self, connector: str, enable: bool):
        word = "Enabling" if enable else "Disabling"
        self._set_status(f"{word} {connector}…")
        self._refresh_btn.set_sensitive(False)

        def worker():
            ok, msg = backend.set_monitor_enabled(connector, enable)
            time.sleep(0.8)
            monitors = backend.get_monitors()
            GLib.idle_add(self._on_action_done, ok, msg, monitors)

        threading.Thread(target=worker, daemon=True).start()

    # ── Mode-change handler ───────────────────────────────────

    def _on_mode_change(self, connector: str, resolution: str, refresh: float):
        self._set_status(f"Setting {connector} → {resolution} @ {refresh:.3f} Hz…")
        self._refresh_btn.set_sensitive(False)

        def worker():
            ok, msg = backend.set_monitor_mode(connector, resolution, refresh)
            time.sleep(0.8)
            monitors = backend.get_monitors()
            GLib.idle_add(self._on_action_done, ok, msg, monitors)

        threading.Thread(target=worker, daemon=True).start()

    # ── Shared post-action callback ───────────────────────────

    def _on_action_done(self, ok: bool, msg: str, monitors: list[Monitor]):
        self._on_monitors_loaded(monitors)
        if not ok:
            self._set_status(f"Error: {msg}", error=True)
        return False

    def _on_refresh_clicked(self, _btn):
        self._refresh_monitors()

    def _set_status(self, text: str, error: bool = False):
        self._toast_label.set_text(text)
        self._toast_label.set_css_classes(
            ["toast-label", "error"] if error else ["status-bar"]
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Application
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MonitorManagerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        win = MonitorManagerWindow(self)

        css_provider = Gtk.CssProvider()
        if os.path.exists(STYLE_CSS):
            css_provider.load_from_path(STYLE_CSS)
        else:
            css_provider.load_from_string(self._fallback_css())

        Gtk.StyleContext.add_provider_for_display(
            win.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        win.present()

    def _fallback_css(self) -> str:
        return """
        window { background-color: #0e0e12; color: #e2e2ef; }
        .monitor-card { border-radius: 12px; padding: 18px; margin-bottom: 14px;
                        background-color: #1a1830; border: 1px solid #444; }
        .badge { border-radius: 6px; padding: 2px 8px; font-size: 11px; }
        .badge-active { color: #58e6a0; }
        .badge-disabled { color: #7878a8; }
        .badge-mode { color: #a89fff; }
        .monitor-name { font-size: 15px; font-weight: bold; }
        .monitor-model { font-size: 12px; color: #666; }
        .section-label { font-size: 11px; color: #555; }
        .status-bar { font-size: 11px; color: #555; }
        .refresh-btn { border-radius: 8px; }
        .apply-btn { border-radius: 8px; }
        """


def main():
    app = MonitorManagerApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
