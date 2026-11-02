#!/usr/bin/env bash
#
# ChooseOS installer.
#
#   sudo ./install.sh            install (and pin to the dock)
#   sudo ./install.sh --no-pin   install without touching the dock favourites
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="/usr/local/lib/chooseos"
BIN="/usr/local/bin/chooseos"
DESKTOP_ID="org.chooseos.ChooseOS.desktop"
DESKTOP_DST="/usr/share/applications/$DESKTOP_ID"
ICON_DST="/usr/local/share/icons/hicolor/scalable/apps/org.chooseos.ChooseOS.svg"
POLKIT_RULE="/etc/polkit-1/rules.d/49-chooseos.rules"

PIN=1
[ "${1:-}" = "--no-pin" ] && PIN=0

if [ "$(id -u)" -ne 0 ]; then
  echo "This installer must be run as root:  sudo ./install.sh" >&2
  exit 1
fi

# The user who invoked us (for pinning to their dock). Works for both
# `sudo ./install.sh` (SUDO_USER) and `pkexec ... install.sh` (PKEXEC_UID).
TARGET_USER="${SUDO_USER:-}"
if [ -z "$TARGET_USER" ] || [ "$TARGET_USER" = "root" ]; then
  TARGET_USER="$(logname 2>/dev/null || true)"
fi
if { [ -z "$TARGET_USER" ] || [ "$TARGET_USER" = "root" ]; } && [ -n "${PKEXEC_UID:-}" ]; then
  TARGET_USER="$(getent passwd "$PKEXEC_UID" 2>/dev/null | cut -d: -f1)"
fi

echo "==> Installing files"
install -d -m 0755 "$LIB_DIR"
install -m 0755 "$REPO_DIR/src/chooseos.py"        "$LIB_DIR/chooseos.py"
install -m 0755 "$REPO_DIR/src/chooseos-helper"    "$LIB_DIR/chooseos-helper"
install -m 0755 "$REPO_DIR/src/chooseos-launcher"  "$BIN"

# The helper runs as root via pkexec; keep it root-owned and not world-writable.
chown root:root "$LIB_DIR/chooseos-helper"
chmod 0755 "$LIB_DIR/chooseos-helper"

install -d -m 0755 "$(dirname "$DESKTOP_DST")"
install -m 0644 "$REPO_DIR/system/$DESKTOP_ID" "$DESKTOP_DST"

install -d -m 0755 "$(dirname "$ICON_DST")"
install -m 0644 "$REPO_DIR/system/icons/org.chooseos.ChooseOS.svg" "$ICON_DST"

if [ -d /etc/polkit-1/rules.d ]; then
  install -m 0644 "$REPO_DIR/system/polkit/49-chooseos.rules" "$POLKIT_RULE"
  echo "==> Installed Polkit rule (passwordless helper): $POLKIT_RULE"
else
  echo "!! /etc/polkit-1/rules.d not found; you will be prompted for a password."
fi

echo "==> Refreshing caches"
update-desktop-database -q /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -q -t -f /usr/local/share/icons/hicolor 2>/dev/null || true

# ---------------------------------------------------------------- dock pin --
if [ "$PIN" -eq 1 ] && [ -n "$TARGET_USER" ] && command -v gsettings >/dev/null; then
  UID_NUM="$(id -u "$TARGET_USER")"
  run_as_user() {
    sudo -u "$TARGET_USER" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${UID_NUM}/bus" \
      XDG_RUNTIME_DIR="/run/user/${UID_NUM}" \
      "$@"
  }
  if run_as_user gsettings get org.gnome.shell favorite-apps >/dev/null 2>&1; then
    current="$(run_as_user gsettings get org.gnome.shell favorite-apps)"
    if ! printf '%s' "$current" | grep -q "$DESKTOP_ID"; then
      if [ "$current" = "[]" ] || [ "$current" = "@as []" ]; then
        updated="['$DESKTOP_ID']"
      else
        updated="$(printf '%s' "$current" | sed "s/\]$/, '$DESKTOP_ID']/")"
      fi
      run_as_user gsettings set org.gnome.shell favorite-apps "$updated"
      echo "==> Pinned to the dock for user '$TARGET_USER'"
    else
      echo "==> Already pinned to the dock"
    fi
  else
    echo "!! Could not reach '$TARGET_USER' GNOME session; pin manually (see README)."
  fi
fi

echo
echo "Done. Launch \"Choose Next OS\" from your apps, or run:  chooseos"
