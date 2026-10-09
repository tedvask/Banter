#!/bin/sh
# SPDX-License-Identifier: MPL-2.0
# Builds the flatpak on top of the installed org.gnome.Platform (no SDK, no flatpak-builder)
# and installs it for the current user. Running it again updates the app.
set -eu
cd "$(dirname "$0")"

APP_ID=io.github.tedvask.Banter
RUNTIME_VERSION=50
BUILD=build/app
REPO="$PWD/build/repo"
ICONS="$BUILD/files/share/icons/hicolor/scalable/apps"

rm -rf "$BUILD"
# Nothing to compile, so the runtime doubles as the SDK.
flatpak build-init "$BUILD" "$APP_ID" org.gnome.Platform org.gnome.Platform "$RUNTIME_VERSION"
install -Dm644 -t "$BUILD/files/share/banter" banter.py tray.py
chmod +x "$BUILD/files/share/banter/banter.py"
mkdir -p "$BUILD/files/bin"
ln -s ../share/banter/banter.py "$BUILD/files/bin/banter"
install -Dm644 "data/$APP_ID.desktop" "$BUILD/files/share/applications/$APP_ID.desktop"
install -Dm644 -t "$ICONS" "data/$APP_ID.svg" "data/$APP_ID-unread.svg"
install -Dm644 LICENSE "$BUILD/files/share/licenses/$APP_ID/LICENSE"
flatpak build-finish "$BUILD" \
    --command=banter \
    --share=network \
    --share=ipc \
    --socket=wayland \
    --socket=fallback-x11 \
    --socket=pulseaudio \
    --device=dri \
    --filesystem=xdg-download \
    --talk-name=org.kde.StatusNotifierWatcher
flatpak build-export "$REPO" "$BUILD"

flatpak --user remote-add --if-not-exists --no-gpg-verify banter-local "$REPO"
flatpak --user install -y --or-update banter-local "$APP_ID"
