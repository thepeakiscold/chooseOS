# ChooseOS

Pick which operating system boots **after the next restart** — Windows or
Ubuntu — from a small app you can pin to the dock/taskbar.

It works by setting the UEFI `BootNext` variable via `efibootmgr`. That is a
**one-time** choice: the firmware boots the selected OS once and then falls
back to your normal default order. Nothing about your installed systems or
the default boot order is modified.

```
┌──────────────────────────────────────────┐
│  Choose Next OS                          │
│                                          │
│  Which OS should boot next?              │
│  Applies to the next restart only…       │
│                                          │
│  Next restart → Ubuntu (default order)   │
│  Default: Ubuntu                         │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │            🪟                      │  │
│  │          Windows                   │  │
│  │      Restart into Windows          │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │            🐧                      │  │
│  │          Ubuntu                    │  │
│  │      Restart into Ubuntu           │  │
│  └────────────────────────────────────┘  │
│          Use default boot order          │
└──────────────────────────────────────────┘
```

## Requirements

* A UEFI system with a Linux (`efibootmgr`) boot entry for each OS.
* Ubuntu/Debian with GTK4 + libadwaita and Python's `gi` bindings
  (all preinstalled on Ubuntu desktop).
* `efibootmgr` (`sudo apt install efibootmgr` if missing).

This app runs **on Linux**. It changes which OS the firmware boots next, so
from Ubuntu you can say "boot Windows next" (and vice-versa, if you install an
equivalent tool on Windows — not shipped here).

## Install

```bash
cd ChooseOS
sudo ./install.sh
```

This will:

1. Install the app to `/usr/local/lib/chooseos/` and a launcher at
   `/usr/local/bin/chooseos`.
2. Install the desktop entry and icon.
3. Install a Polkit rule so the privileged helper runs **without a password
   prompt** from the desktop.
4. **Pin the app to your dock** (GNOME favourites).

Then open **Choose Next OS** from your apps, or run `chooseos`.

If the automatic dock pin did not work (e.g. no active GNOME session at install
time), pin it manually:

* Open the app once so it appears in the dash, then right-click its icon →
  **Pin to Dash**; or
* run `gsettings set org.gnome.shell favorite-apps "$(gsettings get org.gnome.shell favorite-apps | sed "s/\]$/, 'org.chooseos.ChooseOS.desktop']/")"`.

Install without touching the dock:

```bash
sudo ./install.sh --no-pin
```

## Uninstall

```bash
sudo ./uninstall.sh
```

## How it works

| Piece | Location |
|------|----------|
| GUI (GTK4/libadwaita) | `/usr/local/lib/chooseos/chooseos.py` |
| Privileged helper | `/usr/local/lib/chooseos/chooseos-helper` |
| Launcher | `/usr/local/bin/chooseos` |
| Desktop entry | `/usr/share/applications/org.chooseos.ChooseOS.desktop` |
| Polkit rule | `/etc/polkit-1/rules.d/49-chooseos.rules` |

The GUI reads `efibootmgr` (no root needed) to show your entries and the
current one-time choice. When you click a button it runs
`pkexec /usr/local/lib/chooseos/chooseos-helper <windows|ubuntu|default>`,
which sets or clears `BootNext`.

### Non-standard entry names

The helper matches the Windows entry by the label `Windows Boot Manager` and
Ubuntu by `ubuntu`. Override with environment variables, e.g.:

```bash
sudo CHOOSEOS_WINDOWS_PATTERN='Windows Boot Manager' \
     CHOOSEOS_UBUNTU_PATTERN='ubuntu' ./install.sh
```

(Environment overrides must be set in the helper's environment; the easiest
way is to edit the two `*_PATTERN` defaults at the top of
`src/chooseos-helper` before installing.)

## Manual / CLI use

```bash
chooseos                                   # open the app
sudo /usr/local/lib/chooseos/chooseos-helper windows   # boot Windows next
sudo /usr/local/lib/chooseos/chooseos-helper ubuntu    # boot Ubuntu next
sudo /usr/local/lib/chooseos/chooseos-helper default   # clear the choice
efibootmgr                                 # inspect BootNext / BootOrder
```

## Safety notes

* Only `BootNext` is written. Your `BootOrder` and firmware entries are left
  untouched, so a mistake can never make a system unbootable — worst case you
  boot the "wrong" one once.
* The Polkit rule grants passwordless execution **only** for the installed
  helper path, for the local active user; the helper itself accepts only the
  four fixed sub-commands.
