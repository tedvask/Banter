#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Banter — a minimal desktop client for Google Messages (messages.google.com) on WebKitGTK 6."""

import os
import sys
from urllib.parse import urlsplit

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gio, GLib, Gtk, WebKit  # noqa: E402

from tray import Tray  # noqa: E402

APP_ID = "io.github.tedvask.Banter"
NAME = "Banter"
URL = "https://messages.google.com/web/"
# Web process memory limit, MB. From ~1/3 of it WebKit starts dropping caches, from 1/2 aggressively.
MEMORY_LIMIT_MB = 1024
# Icons for running from source; the flatpak installs them into the icon theme instead.
ICON_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")

# Counts unread, non-muted conversations and reports changes to the app. Event-driven: no polling.
# -1 means the conversation list isn't rendered (window never shown yet, or not paired).
UNREAD_JS = """
(() => {
  let last = null, timer = 0;
  const report = () => {
    timer = 0;
    const n = document.querySelector('[data-e2e-is-unread]')
      ? document.querySelectorAll('[data-e2e-is-unread="true"]:not([data-e2e-is-muted="true"])').length : -1;
    if (n !== last) window.webkit.messageHandlers.unread.postMessage(last = n);
  };
  new MutationObserver(() => { timer ||= setTimeout(report, 500); }).observe(document, {
    subtree: true, childList: true, attributes: true, attributeFilter: ['data-e2e-is-unread', 'data-e2e-is-muted'],
  });
  report();
})();
"""


def is_internal(uri):
    """Google links (sign-in, pairing) stay in the app, everything else opens in the browser."""
    host = urlsplit(uri).hostname or ""
    return host == "google.com" or host.endswith(".google.com")


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option("background", ord("b"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Start without a window (for autostart)", None)
        self.notifications = {}  # GNotification id -> WebKit.Notification
        self.unread = -1

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.view = self.create_view()
        # Closing the window only hides it: the page keeps running and sending notifications.
        self.win = Gtk.Window(application=self, title=NAME,
                              default_width=1100, default_height=750, hide_on_close=True)
        # Tiling compositors like sway draw their own borders; a GTK title bar would be redundant.
        self.win.set_decorated("GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", ""))
        self.win.set_child(self.view)
        self.view.connect("notify::title", lambda *_: self.update_unread())
        self.tray = Tray(self.get_dbus_connection(), APP_ID, NAME, self.toggle_window,
                         [(f"Show {NAME}", self.win.present), ("Quit", self.quit)],
                         ICON_DIR if os.path.isdir(ICON_DIR) else "")
        self.setup_actions()
        self.view.load_uri(URL)

    def do_command_line(self, command_line):
        if not command_line.get_options_dict().contains("background"):
            self.win.present()
        return 0

    def do_activate(self):
        self.win.present()

    def create_view(self):
        data_dir = os.path.join(GLib.get_user_data_dir(), APP_ID)
        session = WebKit.NetworkSession.new(data_dir, os.path.join(GLib.get_user_cache_dir(), APP_ID))
        session.get_cookie_manager().set_persistent_storage(
            os.path.join(data_dir, "cookies.sqlite"), WebKit.CookiePersistentStorage.SQLITE)

        memory = WebKit.MemoryPressureSettings.new()
        memory.set_memory_limit(MEMORY_LIMIT_MB)
        context = WebKit.WebContext(memory_pressure_settings=memory)
        # Minimal in-memory caching but keeps the HTTP disk cache (DOCUMENT_VIEWER would drop it too).
        context.set_cache_model(WebKit.CacheModel.DOCUMENT_BROWSER)
        # Notification permission is granted at startup, so it never has to be re-enabled per session.
        context.connect("initialize-notification-permissions", lambda ctx: ctx.initialize_notification_permissions(
            [WebKit.SecurityOrigin.new_for_uri(URL)], []))

        content = WebKit.UserContentManager()
        content.add_script(WebKit.UserScript.new(UNREAD_JS, WebKit.UserContentInjectedFrames.TOP_FRAME,
                                                 WebKit.UserScriptInjectionTime.END, None, None))
        content.register_script_message_handler("unread", None)
        content.connect("script-message-received::unread", self.on_unread_message)

        settings = WebKit.Settings(enable_webgl=False, enable_page_cache=False,
                                   enable_developer_extras=bool(os.environ.get("BANTER_DEBUG")))
        view = WebKit.WebView(network_session=session, web_context=context, settings=settings,
                              user_content_manager=content)
        # Page and its service worker share one web process instead of two: ~35 MB less.
        # Must be set after the WebView is created — the constructor resets this flag.
        features = WebKit.Settings.get_all_features()
        for i in range(features.get_length()):
            if features.get(i).get_identifier() == "UsesSingleWebProcess":
                settings.set_feature_enabled(features.get(i), True)
        view.connect("decide-policy", self.on_decide_policy)
        view.connect("create", self.on_create)
        view.connect("permission-request", self.on_permission_request)
        view.connect("show-notification", self.on_show_notification)
        view.connect("web-process-terminated", self.on_web_process_terminated)
        return view

    def setup_actions(self):
        action = Gio.SimpleAction.new("open-notification", GLib.VariantType.new("s"))
        action.connect("activate", self.on_open_notification)
        self.add_action(action)
        for name, accels, callback in (
            ("quit", ["<Ctrl>q"], self.quit),
            ("close", ["<Ctrl>w"], self.win.close),
            ("reload", ["<Ctrl>r", "F5"], self.view.reload),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_, cb=callback: cb())
            self.add_action(action)
            self.set_accels_for_action(f"app.{name}", accels)

    def toggle_window(self, token=None):
        if self.win.is_visible() and self.win.is_active():
            self.win.close()
            return
        if token:
            self.win.set_startup_id(token)  # lets the compositor give the window focus
        self.win.present()

    def on_unread_message(self, manager, value):
        self.unread = value.to_int32()
        self.update_unread()

    def update_unread(self):
        # Until the list is rendered, conversations with pending notifications are the best estimate.
        count = self.unread if self.unread >= 0 else len(self.notifications)
        title = self.view.get_title() or NAME
        self.win.set_title(f"({count}) {title}" if count else title)
        self.tray.update(f"{APP_ID}-unread" if count else APP_ID,
                         f"{count} unread chat{'s' if count > 1 else ''}" if count else "")

    def open_external(self, uri):
        Gtk.UriLauncher.new(uri).launch(self.win, None, lambda *_: None)

    def on_decide_policy(self, view, decision, decision_type):
        new_window = decision_type == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION
        if not new_window and decision_type != WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            return False
        action = decision.get_navigation_action()
        uri = action.get_request().get_uri()
        if new_window or (action.get_navigation_type() == WebKit.NavigationType.LINK_CLICKED
                          and not is_internal(uri)):
            decision.ignore()
            self.open_external(uri)
            return True
        return False

    def on_create(self, view, action):
        # window.open(): the app never opens new windows, the link goes to the browser.
        uri = action.get_request().get_uri()
        if uri.startswith("http"):
            self.open_external(uri)
        return None

    def on_permission_request(self, view, request):
        if isinstance(request, WebKit.NotificationPermissionRequest):
            request.allow()
            return True
        return False

    def on_show_notification(self, view, notification):
        # Google Messages tags notifications per conversation: one chat, one notification, newest wins.
        key = notification.get_tag() or str(notification.get_id())
        self.notifications[key] = notification
        notification.connect("closed", self.on_notification_closed, key)
        n = Gio.Notification.new(notification.get_title())
        n.set_body(notification.get_body())
        n.set_default_action_and_target("app.open-notification", GLib.Variant.new_string(key))
        self.send_notification(key, n)
        self.update_unread()
        return True

    def on_notification_closed(self, notification, key):
        if self.notifications.get(key) is notification:
            del self.notifications[key]
            self.withdraw_notification(key)
            self.update_unread()

    def on_open_notification(self, action, key):
        self.win.present()
        notification = self.notifications.pop(key.get_string(), None)
        if notification:
            notification.clicked()  # the page opens the conversation itself
        self.update_unread()

    def on_web_process_terminated(self, view, reason):
        if reason != WebKit.WebProcessTerminationReason.TERMINATED_BY_API:
            view.reload()


if __name__ == "__main__":
    sys.exit(App().run(sys.argv))
