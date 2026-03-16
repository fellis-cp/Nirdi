#!/usr/bin/env python3
"""
main.py – Niri Monitor Manager
A GTK4 GUI to view and toggle monitors in a Niri Wayland session.
Uses `niri msg outputs` for info and `wlr-randr` for control.
"""

import os
import threading
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, GObject, Pango

import monitor_backend as backend
from monitor_backend import Monitor


APP_ID = "io.niri.monitor-manager"
STYLE_CSS = os.path.join(os.path.dirname(__file__), "style.css")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Monitor Card Widget
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MonitorCard(Gtk.Box):
    """A single card representing one physical monitor."""

    def __init__(self, monitor: Monitor, on_toggle_cb):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._monitor = monitor
        self._on_toggle_cb = on_toggle_cb
        self._ignore_toggle = False

        # Card style classes
        self.add_css_class("monitor-card")
        if monitor.enabled:
            self.add_css_class("active")
        else:
            self.add_css_class("disabled")

        self._build_ui()

    def _build_ui(self):
        m = self._monitor

        # ── Left: icon ──────────────────────────────────────────
        icon_label = Gtk.Label()
        icon_label.set_markup(
            "🖥️" if not m.is_builtin else "💻"
        )
        icon_label.add_css_class("monitor-icon")
        icon_label.set_valign(Gtk.Align.CENTER)
        icon_label.set_margin_end(16)
        self.append(icon_label)

        # ── Middle: info column ──────────────────────────────────
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        info_box.set_hexpand(True)
        info_box.set_valign(Gtk.Align.CENTER)

        # Connector name
        name_label = Gtk.Label(label=m.connector)
        name_label.add_css_class("monitor-name")
        name_label.set_halign(Gtk.Align.START)
        info_box.append(name_label)

        # Model name
        model_label = Gtk.Label(label=m.display_name)
        model_label.add_css_class("monitor-model")
        model_label.set_halign(Gtk.Align.START)
        model_label.set_ellipsize(Pango.EllipsizeMode.END)
        model_label.set_max_width_chars(36)
        info_box.append(model_label)

        # Badges row
        badge_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        badge_box.set_margin_top(4)

        # Status badge
        self._status_badge = Gtk.Label()
        self._status_badge.add_css_class("badge")
        self._update_status_badge()
        badge_box.append(self._status_badge)

        # Mode badge (only when enabled)
        if m.enabled and m.current_mode:
            mode_badge = Gtk.Label(label=m.current_mode)
            mode_badge.add_css_class("badge")
            mode_badge.add_css_class("badge-mode")
            badge_box.append(mode_badge)

        # Physical size badge
        if m.physical_size:
            size_badge = Gtk.Label(label=m.physical_size)
            size_badge.add_css_class("badge")
            size_badge.add_css_class("badge-mode")
            badge_box.append(size_badge)

        info_box.append(badge_box)
        self.append(info_box)

        # ── Right: toggle switch ─────────────────────────────────
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        right_box.set_valign(Gtk.Align.CENTER)
        right_box.set_margin_start(18)

        self._switch = Gtk.Switch()
        self._switch.set_active(self._monitor.enabled)
        self._switch.set_valign(Gtk.Align.CENTER)
        self._switch.connect("state-set", self._on_state_set)
        right_box.append(self._switch)
        self.append(right_box)

    def _update_status_badge(self):
        if self._monitor.enabled:
            self._status_badge.set_label("Active")
            self._status_badge.set_css_classes(["badge", "badge-active"])
        else:
            self._status_badge.set_label("Disabled")
            self._status_badge.set_css_classes(["badge", "badge-disabled"])

    def _on_state_set(self, switch, state):
        """User flipped the toggle – call the callback."""
        if self._ignore_toggle:
            return False
        self._on_toggle_cb(self._monitor.connector, state)
        # Prevent GTK auto-toggling; let the callback decide final state
        return True  # returning True means "we handle the state"

    def refresh(self, monitor: Monitor):
        """Update this card's visual state after a monitor refresh."""
        self._ignore_toggle = True
        self._monitor = monitor
        self._switch.set_active(monitor.enabled)
        self._update_status_badge()
        # Update card style classes
        if monitor.enabled:
            self.remove_css_class("disabled")
            self.add_css_class("active")
        else:
            self.remove_css_class("active")
            self.add_css_class("disabled")
        self._ignore_toggle = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main Application Window
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MonitorManagerWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Monitor Manager")
        self.set_default_size(520, 460)
        self.set_resizable(True)

        self._cards: dict[str, MonitorCard] = {}
        self._monitors: list[Monitor] = []

        self._build_ui()
        self._refresh_monitors(initial=True)

    # ── UI construction ─────────────────────────────────────────

    def _build_ui(self):
        # Header bar
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)

        # Subtitle label inside header
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title_box.set_valign(Gtk.Align.CENTER)
        title_lbl = Gtk.Label(label="Monitor Manager")
        title_lbl.add_css_class("title")
        sub_lbl = Gtk.Label(label="Niri Wayland")
        sub_lbl.add_css_class("monitor-model")
        title_box.append(title_lbl)
        title_box.append(sub_lbl)
        header.set_title_widget(title_box)

        # Refresh button in header
        self._refresh_btn = Gtk.Button(label="⟳  Refresh")
        self._refresh_btn.add_css_class("refresh-btn")
        self._refresh_btn.connect("clicked", self._on_refresh_clicked)
        header.pack_end(self._refresh_btn)

        self.set_titlebar(header)

        # ── Scrolled container ──────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        # Main vertical box
        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._main_box.add_css_class("main-box")
        scroll.set_child(self._main_box)

        # Section label
        self._section_label = Gtk.Label(label="CONNECTED DISPLAYS")
        self._section_label.add_css_class("section-label")
        self._section_label.set_halign(Gtk.Align.START)
        self._section_label.set_margin_bottom(4)
        self._main_box.append(self._section_label)

        # Cards container
        self._cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._main_box.append(self._cards_box)

        # Toast / status area
        self._toast_label = Gtk.Label(label="")
        self._toast_label.add_css_class("status-bar")
        self._toast_label.set_halign(Gtk.Align.CENTER)
        self._toast_label.set_margin_top(16)
        self._main_box.append(self._toast_label)

        self.set_child(scroll)

    # ── Data refresh ─────────────────────────────────────────────

    def _refresh_monitors(self, initial=False):
        self._set_status("Refreshing…", error=False)
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
            return

        # Rebuild or update cards
        existing_connectors = set(self._cards.keys())
        new_connectors = {m.connector for m in monitors}

        # Remove stale cards
        for connector in existing_connectors - new_connectors:
            card = self._cards.pop(connector)
            self._cards_box.remove(card)

        # Add new / update existing
        for monitor in monitors:
            if monitor.connector in self._cards:
                self._cards[monitor.connector].refresh(monitor)
            else:
                card = MonitorCard(monitor, on_toggle_cb=self._on_toggle)
                self._cards[monitor.connector] = card
                self._cards_box.append(card)

        now = time.strftime("%H:%M:%S")
        active = sum(1 for m in monitors if m.enabled)
        self._set_status(
            f"{len(monitors)} display{'s' if len(monitors) != 1 else ''} detected  ·  {active} active  ·  Updated {now}"
        )
        return False  # required for GLib.idle_add

    # ── Toggle handler ────────────────────────────────────────────

    def _on_toggle(self, connector: str, enable: bool):
        self._set_status(
            f"{'Enabling' if enable else 'Disabling'} {connector}…", error=False
        )
        self._refresh_btn.set_sensitive(False)

        def worker():
            ok, msg = backend.set_monitor_enabled(connector, enable)
            # Small delay so niri can stabilize
            time.sleep(0.8)
            monitors = backend.get_monitors()
            GLib.idle_add(self._on_toggle_done, ok, msg, monitors)

        threading.Thread(target=worker, daemon=True).start()

    def _on_toggle_done(self, ok: bool, msg: str, monitors: list[Monitor]):
        self._on_monitors_loaded(monitors)
        if not ok:
            self._set_status(f"Error: {msg}", error=True)
        return False

    # ── Refresh button ────────────────────────────────────────────

    def _on_refresh_clicked(self, _btn):
        self._refresh_monitors()

    # ── Helpers ───────────────────────────────────────────────────

    def _set_status(self, text: str, error: bool = False):
        self._toast_label.set_text(text)
        if error:
            self._toast_label.set_css_classes(["toast-label", "error"])
        else:
            self._toast_label.set_css_classes(["status-bar"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Application entry-point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MonitorManagerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        # Load CSS
        css_provider = Gtk.CssProvider()
        if os.path.exists(STYLE_CSS):
            css_provider.load_from_path(STYLE_CSS)
        else:
            css_provider.load_from_string(self._fallback_css())

        Gtk.StyleContext.add_provider_for_display(
            self.get_windows()[0].get_display() if self.get_windows() else
            Gtk.Window().get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        win = MonitorManagerWindow(self)

        # Apply CSS after window exists
        display = win.get_display()
        Gtk.StyleContext.add_provider_for_display(
            display,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        win.present()

    def _fallback_css(self) -> str:
        return """
        window { background-color: #0e0e12; color: #e2e2ef; }
        .monitor-card { border-radius: 12px; padding: 16px; margin-bottom: 12px;
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
        """


if __name__ == "__main__":
    app = MonitorManagerApp()
    app.run()
