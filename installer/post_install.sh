#!/usr/bin/env bash

set -e

APP_NAME="osdag_for_bridge"
INSTALL_DIR="$PREFIX"

launch_shortcut="$HOME/.local/share/applications/osdag_for_bridge.desktop"
uninstall_shortcut="$HOME/.local/share/applications/Uninstall-osdag_for_bridge.desktop"
ICON_FILE="$INSTALL_DIR/Osdag.ico"
LAUNCHER="$INSTALL_DIR/bin/osdag_for_bridge"
UNINSTALLER="$INSTALL_DIR/Uninstall-osdag_for_bridge.sh"

echo "Creating application launcher..."

mkdir -p "$HOME/.local/share/applications"

cat <<EOF > "$launch_shortcut"
[Desktop Entry]
Name=osdag_for_bridge
Exec=$LAUNCHER
Icon=$ICON_FILE
Type=Application
Categories=Engineering;
Terminal=false
EOF

chmod +x "$launch_shortcut"

echo "Launcher created at:"
echo "$launch_shortcut"

echo "Creating application Uninstaller..."

cat <<EOF > "$uninstall_shortcut"
[Desktop Entry]
Name=Uninstall osdag_for_bridge
Exec=$UNINSTALLER
Icon=$ICON_FILE
Type=Application
Categories=Engineering;
Terminal=true
EOF

chmod +x "$UNINSTALLER"
chmod +x "$uninstall_shortcut"

update-desktop-database ~/.local/share/applications 2>/dev/null || true
echo "Uninstaller created at:"
echo "$uninstall_shortcut"