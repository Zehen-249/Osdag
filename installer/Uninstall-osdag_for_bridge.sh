#!/usr/bin/env bash

APP_NAME="osdag_for_bridge"
PREFIX="$( cd "$( dirname "$(readlink -f "$0")" )" && pwd )"

read -p "Are you sure you want to uninstall osdag_for_bridge? [y/N]: " confirm
[[ "$confirm" == "y" || "$confirm" == "Y" ]] || exit 0

echo "Removing osdag_for_bridge shortcuts..."

rm -f "$HOME/.local/share/applications/osdag_for_bridge.desktop" 2>/dev/null
rm -f "$HOME/Desktop/osdag_for_bridge.desktop"  2>/dev/null
rm -f "$HOME/.local/share/applications/Uninstall-osdag_for_bridge.desktop" 2>/dev/null


update-desktop-database ~/.local/share/applications 2>/dev/null || true

rm -rf "$PREFIX"

echo "osdag_for_bridge cleanup complete."
read -p "Press Enter to close this window..."