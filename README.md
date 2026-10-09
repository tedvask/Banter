# Banter

A lightweight desktop client for [Google Messages](https://messages.google.com/web/) on Linux:
your phone's SMS and RCS chats in a native window, with system notifications, an unread counter and a tray icon.

Banter is two small Python files on GTK 4 and WebKitGTK 6, packaged as a flatpak on top of the GNOME runtime.
The app itself is a few kilobytes; at runtime it uses about 300 MB of RAM (almost all of it WebKit
running the Google Messages page) and no CPU while idle.

> Banter is an unofficial project and is not affiliated with or endorsed by Google.
> Google Messages is a trademark of Google LLC.

## Features

- **Runs in the background.** Closing the window only hides it, so notifications keep arriving.
- **Native notifications** through the desktop notification service, one per conversation.
  Clicking one opens that conversation. Notifications are allowed from the first launch.
- **Unread counter** in the window title (`(3) Google Messages…`) and on the tray icon.
  Muted conversations are not counted.
- **Tray icon** for waybar, KDE Plasma, or GNOME with the AppIndicator extension:
  left click shows or hides the window, right click opens a menu.
- **Links open in your default browser**; only Google sign-in and pairing pages stay in the app.
- **Tuned for low resource use**: a single web process, no WebGL, minimal in-memory caching.

## Install

You need `flatpak` and the GNOME 50 runtime from Flathub:

```sh
flatpak install flathub org.gnome.Platform//50
git clone https://github.com/tedvask/Banter.git
cd Banter
./build.sh
```

`build.sh` builds the flatpak without an SDK or flatpak-builder and installs it for the current user.
Run it again to update after pulling changes.

On first launch, pair your phone: in the Messages app on Android, tap your profile picture →
**Device pairing** → **QR code scanner**, and scan the code shown in Banter.

## Usage

| Action | How |
| --- | --- |
| Hide the window (keeps running) | `Ctrl+W` or close the window |
| Show the window again | Launch Banter again, or click the tray icon |
| Quit | `Ctrl+Q`, or **Quit** in the tray menu |
| Reload the page | `Ctrl+R` or `F5` |
| Start hidden (for autostart) | `flatpak run io.github.tedvask.Banter --background` |

Downloads go to `~/Downloads`. App data lives in `~/.var/app/io.github.tedvask.Banter/`.

With `--background`, the conversation list isn't rendered until the window has been shown once.
Until then the unread counter shows the number of conversations with pending notifications.

### Sway and other tiling compositors

Banter draws no title bar outside GNOME, so your compositor's borders are the only decoration.
Example sway config:

```text
assign [app_id="io.github.tedvask.Banter"] workspace number 2
exec flatpak run io.github.tedvask.Banter
```

waybar's tray doesn't pass apps the activation token that Wayland requires for taking focus,
so under sway a tray click shows a hidden window but can't switch you to another workspace.
With an `assign` rule like the one above, switch to that workspace yourself. Tray hosts that do pass
the token, such as KDE Plasma, bring the window to the front.

## Development

- Run from source without building: `python3 banter.py`. Your system needs GTK 4, WebKitGTK 6.0
  and PyGObject (on Fedora: `webkitgtk6.0 python3-gobject`). Quit the flatpak first: both use the same
  app ID, so a second instance would just show the first one's window. From source, data is stored in
  `~/.local/share/io.github.tedvask.Banter/`, separate from the flatpak.
- `BANTER_DEBUG=1` adds **Inspect Element** to the context menu:
  `flatpak run --env=BANTER_DEBUG=1 io.github.tedvask.Banter`.
- Settings such as the URL and the memory limit are constants at the top of `banter.py`.
- `tray.py` is a self-contained StatusNotifierItem + DBusMenu implementation on plain Gio,
  reusable in other GTK 4 apps.

## Uninstall

```sh
flatpak --user uninstall --delete-data io.github.tedvask.Banter
flatpak --user remote-delete banter-local
```

## License

Copyright © 2026 tedvask. Licensed under the [Mozilla Public License 2.0](LICENSE).
