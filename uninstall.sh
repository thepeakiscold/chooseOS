#!/usr/bin/env bash
#
# ChooseOS uninstaller:  sudo ./uninstall.sh
#
set -euo pipefail

LIB_DIR="/usr/local/lib/chooseos"
BIN="/usr/local/bin/chooseos"
DESKTOP_ID="org.chooseos.ChooseOS.desktop"
DESKTOP_DST="/usr/share/applications/$DESKTOP_ID"
ICON_DST="/usr/local/share/icons/hicolor/scalable/apps/org.chooseos.ChooseOS.svg"
POLKIT_RULE="/etc/polkit-1/rules.d/49-chooseos.rules"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root:  sudo ./uninstall.sh" >&2
  exit 1
fi

TARGET_USER="${SUDO_USER:-}"

echo "==> Removing files"
rm -rf "$LIB_DIR" "$BIN" "$DESKTOP_DST" "$ICON_DST" "$POLKIT_RULE"

update-desktop-database -q /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache -q -t -f /usr/local/share/icons/hicolor 2>/dev/null || true

if [ -n "$TARGET_USER" ] && [ "$TARGET_USER" != "root" ] && command -v gsettings >/dev/null; then
  UID_NUM="$(id -u "$TARGET_USER")"
  if sudo -u "$TARGET_USER" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${UID_NUM}/bus" \
      XDG_RUNTIME_DIR="/run/user/${UID_NUM}" \
      gsettings get org.gnome.shell favorite-apps >/dev/null 2>&1; then
    current="$(sudo -u "$TARGET_USER" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${UID_NUM}/bus" \
      XDG_RUNTIME_DIR="/run/user/${UID_NUM}" \
      gsettings get org.gnome.shell favorite-apps)"
    updated="$(printf '%s' "$current" \
      | sed "s/, '$DESKTOP_ID'//; s/'$DESKTOP_ID', //; s/'$DESKTOP_ID'//")"
    sudo -u "$TARGET_USER" \
      DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${UID_NUM}/bus" \
      XDG_RUNTIME_DIR="/run/user/${UID_NUM}" \
      gsettings set org.gnome.shell favorite-apps "$updated"
    echo "==> Removed dock pin"
  fi
fi

echo "Done."
