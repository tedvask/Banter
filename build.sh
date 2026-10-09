#!/bin/sh
# Собирает flatpak поверх уже установленного org.gnome.Platform (без SDK и flatpak-builder)
# и ставит его в пользовательскую установку. Повторный запуск обновляет приложение.
set -eu
cd "$(dirname "$0")"

APP_ID=io.github.favask.GoogleMessages
RUNTIME_VERSION=50
BUILD=build/app
REPO="$PWD/build/repo"

rm -rf "$BUILD"
# Приложению нечего компилировать, поэтому в роли SDK выступает сам рантайм.
flatpak build-init "$BUILD" "$APP_ID" org.gnome.Platform org.gnome.Platform "$RUNTIME_VERSION"
install -Dm755 googlemessages.py "$BUILD/files/bin/googlemessages"
install -Dm644 "data/$APP_ID.desktop" "$BUILD/files/share/applications/$APP_ID.desktop"
install -Dm644 "data/$APP_ID.svg" "$BUILD/files/share/icons/hicolor/scalable/apps/$APP_ID.svg"
flatpak build-finish "$BUILD" \
    --command=googlemessages \
    --share=network \
    --share=ipc \
    --socket=wayland \
    --socket=fallback-x11 \
    --socket=pulseaudio \
    --device=dri \
    --filesystem=xdg-download
flatpak build-export "$REPO" "$BUILD"

flatpak --user remote-add --if-not-exists --no-gpg-verify googlemessages-local "$REPO"
flatpak --user install -y --or-update googlemessages-local "$APP_ID"
