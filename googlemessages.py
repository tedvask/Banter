#!/usr/bin/env python3
"""Google Messages — минимальная обёртка над messages.google.com на WebKitGTK 6."""

import os
import sys
from urllib.parse import urlsplit

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gio, GLib, Gtk, WebKit  # noqa: E402

APP_ID = "io.github.favask.GoogleMessages"
URL = "https://messages.google.com/web/"
# Лимит памяти веб-процесса, МБ. С ~1/3 лимита WebKit начинает чистить кэши, с 1/2 — агрессивно.
MEMORY_LIMIT_MB = 1024


def is_internal(uri):
    """Ссылки Google (вход, сопряжение) открываем в приложении, остальные — в браузере."""
    host = urlsplit(uri).hostname or ""
    return host == "google.com" or host.endswith(".google.com")


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option("background", ord("b"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Запуститься без окна (для автозапуска)", None)
        self.notifications = {}  # ключ GNotification -> WebKit.Notification

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.view = self.create_view()
        # Закрытие окна только прячет его: страница живёт в фоне и продолжает присылать уведомления.
        self.win = Gtk.Window(application=self, title="Google Messages",
                              default_width=1100, default_height=750, hide_on_close=True)
        # В sway рамку рисует композитор, GTK-шный заголовок не нужен.
        self.win.set_decorated("GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", ""))
        self.win.set_child(self.view)
        self.view.connect("notify::title", lambda v, _: self.win.set_title(v.get_title() or "Google Messages"))
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
        # Минимальный кэш в памяти, но с дисковым HTTP-кэшем (DOCUMENT_VIEWER отключает и его).
        context.set_cache_model(WebKit.CacheModel.DOCUMENT_BROWSER)
        # Разрешение на уведомления выдаётся сразу при старте, его не нужно включать заново каждую сессию.
        context.connect("initialize-notification-permissions", lambda ctx: ctx.initialize_notification_permissions(
            [WebKit.SecurityOrigin.new_for_uri(URL)], []))

        settings = WebKit.Settings(enable_webgl=False, enable_page_cache=False,
                                   enable_developer_extras=bool(os.environ.get("GOOGLEMESSAGES_DEBUG")))
        view = WebKit.WebView(network_session=session, web_context=context, settings=settings)
        # Страница и её service worker в одном веб-процессе вместо двух: минус ~35 МБ.
        # Только после создания WebView — конструктор этот флаг сбрасывает.
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
        # window.open() — новые окна приложение не открывает, ссылка уходит в браузер.
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
        # Google Messages ставит tag на беседу: одна беседа — одно уведомление, новое заменяет старое.
        key = notification.get_tag() or str(notification.get_id())
        self.notifications[key] = notification
        notification.connect("closed", self.on_notification_closed, key)
        n = Gio.Notification.new(notification.get_title())
        n.set_body(notification.get_body())
        n.set_default_action_and_target("app.open-notification", GLib.Variant.new_string(key))
        self.send_notification(key, n)
        return True

    def on_notification_closed(self, notification, key):
        if self.notifications.get(key) is notification:
            del self.notifications[key]
            self.withdraw_notification(key)

    def on_open_notification(self, action, key):
        self.win.present()
        notification = self.notifications.pop(key.get_string(), None)
        if notification:
            notification.clicked()  # страница сама откроет нужную беседу

    def on_web_process_terminated(self, view, reason):
        if reason != WebKit.WebProcessTerminationReason.TERMINATED_BY_API:
            view.reload()


if __name__ == "__main__":
    sys.exit(App().run(sys.argv))
