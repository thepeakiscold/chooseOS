#!/usr/bin/env python3
"""ChooseOS — pick which OS (Windows or Ubuntu) boots after the next restart.

A small GTK4 / libadwaita front-end for efibootmgr's one-time BootNext setting.
The privileged work is done by /usr/local/lib/chooseos/chooseos-helper, invoked
through pkexec (passwordless when the shipped Polkit rule is installed).
"""

import re
import shutil
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

APP_ID = "org.chooseos.ChooseOS"
HELPER = "/usr/local/lib/chooseos/chooseos-helper"
EFIBOOTMGR = shutil.which("efibootmgr") or "/usr/bin/efibootmgr"

CSS = """
.os-icon   { font-size: 2.6em; }
.os-title  { font-size: 1.3em; font-weight: 700; }
.os-sub    { font-size: 0.9em; opacity: 0.65; }
button.big { padding: 20px 16px; border-radius: 16px; }
.status    { font-size: 1.0em; }
.dim       { opacity: 0.7; }
"""


def read_boot_state():
    """Parse efibootmgr output.

    Returns (entries, bootnext, bootorder) where entries maps e.g. "0000" to
    the entry label, bootnext is the one-time choice (or None), and bootorder
    is the list of entry numbers in default order.
    """
    try:
        out = subprocess.run(
            [EFIBOOTMGR], capture_output=True, text=True, check=True
        ).stdout
    except FileNotFoundError:
        raise RuntimeError("efibootmgr is not installed.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"efibootmgr failed: {exc.stderr.strip() or exc}")

    entries, bootnext, bootorder = {}, None, []
    for line in out.splitlines():
        m = re.match(r"^Boot([0-9A-Fa-f]{4})\*?[ \t]+(.*)$", line)
        if m:
            # The label is everything up to the first tab (then device path).
            label = m.group(2).split("\t", 1)[0].strip()
            entries[m.group(1).upper()] = label
            continue
        m = re.match(r"^BootNext:\s*([0-9A-Fa-f]{4})", line)
        if m:
            bootnext = m.group(1).upper()
            continue
        m = re.match(r"^BootOrder:\s*(.*)$", line)
        if m:
            bootorder = [n.strip().upper() for n in m.group(1).split(",") if n.strip()]
    return entries, bootnext, bootorder


def find_num(entries, needle):
    """Return the entry number whose label contains `needle` (case-insensitive)."""
    for num, label in entries.items():
        if needle.lower() in label.lower():
            return num
    return None


class AppWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Choose Next OS")
        self.set_default_size(440, 560)

        self._install_css()

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(toolbar)
        self.set_content(self.toast_overlay)

        clamp = Adw.Clamp(maximum_size=480)
        for m in ("top", "bottom"):
            getattr(clamp, f"set_margin_{m}")(20)
        clamp.set_margin_start(18)
        clamp.set_margin_end(18)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        title = Gtk.Label(label="Which OS should boot next?", xalign=0)
        title.add_css_class("title-1")
        subtitle = Gtk.Label(
            label="Applies to the next restart only. Your default boot order stays the same.",
            xalign=0, wrap=True,
        )
        subtitle.add_css_class("dim")
        box.append(title)
        box.append(subtitle)

        self.status_label = Gtk.Label(xalign=0, use_markup=True)
        self.status_label.add_css_class("status")
        self.status_label.set_margin_top(4)
        box.append(self.status_label)

        self.windows_btn = self._make_button(
            "🪟", "Windows", "Restart into Windows", "windows"
        )
        self.ubuntu_btn = self._make_button(
            "🐧", "Ubuntu", "Restart into Ubuntu", "ubuntu"
        )
        box.append(self.windows_btn)
        box.append(self.ubuntu_btn)

        reset = Gtk.Button(label="Use default boot order")
        reset.add_css_class("flat")
        reset.set_halign(Gtk.Align.CENTER)
        reset.connect("clicked", lambda _b: self.apply("default"))
        box.append(reset)

        self.notice = Gtk.Label(xalign=0, wrap=True)
        self.notice.add_css_class("dim")
        box.append(self.notice)

        toolbar.set_content(clamp)
        clamp.set_child(box)

        self.refresh()

    # -- UI helpers ---------------------------------------------------------
    def _install_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _make_button(self, icon, osname, subtitle, target):
        btn = Gtk.Button()
        btn.add_css_class("big")
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        inner.set_halign(Gtk.Align.CENTER)

        icon_label = Gtk.Label(label=icon)
        icon_label.add_css_class("os-icon")

        title = Gtk.Label(label=osname)
        title.add_css_class("os-title")

        sub = Gtk.Label(label=subtitle)
        sub.add_css_class("os-sub")

        for w in (icon_label, title, sub):
            inner.append(w)
        btn.set_child(inner)
        btn.connect("clicked", lambda _b, t=target: self.apply(t))
        return btn

    def toast(self, text):
        self.toast_overlay.add_toast(Adw.Toast(title=text, timeout=3))

    # -- actions ------------------------------------------------------------
    def apply(self, target):
        try:
            proc = subprocess.run(
                ["pkexec", HELPER, target], capture_output=True, text=True
            )
        except FileNotFoundError:
            self.toast("pkexec not found — is PolicyKit installed?")
            return

        if proc.returncode == 0:
            self.toast(proc.stdout.strip() or "Done.")
        elif proc.returncode in (126, 127):
            self.toast("Authorization cancelled.")
        else:
            msg = (proc.stderr or proc.stdout or "Operation failed.").strip()
            last = msg.splitlines()[-1] if msg else "Operation failed."
            self.toast(last)
        self.refresh()

    def refresh(self):
        try:
            entries, bootnext, bootorder = read_boot_state()
        except RuntimeError as exc:
            self.status_label.set_markup(f"<b>Unavailable</b>\n{exc}")
            for b in (self.windows_btn, self.ubuntu_btn):
                b.set_sensitive(False)
            return

        win_num = find_num(entries, "windows")
        ubu_num = find_num(entries, "ubuntu")
        self.windows_btn.set_sensitive(win_num is not None)
        self.ubuntu_btn.set_sensitive(ubu_num is not None)

        def name(num):
            return entries.get(num, f"entry {num}") if num else "—"

        default_num = bootorder[0] if bootorder else None
        if bootnext:
            next_txt = f"<b>{name(bootnext)}</b> (one time)"
        else:
            next_txt = f"<b>{name(default_num)}</b> (default order)"

        self.status_label.set_markup(
            "Next restart → " + next_txt
            + f"\nDefault: {name(default_num)}"
        )

        missing = []
        if win_num is None:
            missing.append("Windows")
        if ubu_num is None:
            missing.append("Ubuntu")
        self.notice.set_text(
            "Not detected in the UEFI boot entries: " + ", ".join(missing)
            if missing else ""
        )


class ChooseOSApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        window = self.props.active_window or AppWindow(application=self)
        window.present()


def main():
    return ChooseOSApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
