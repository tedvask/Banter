# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Minimal system tray icon (StatusNotifierItem + DBusMenu) on plain Gio, no extra libraries.

Shows up in any StatusNotifierItem host: waybar, KDE Plasma, GNOME with the AppIndicator extension.
"""

from gi.repository import Gio, GLib

ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"

ITEM_XML = """<node><interface name="org.kde.StatusNotifierItem">
  <property name="Category" type="s" access="read"/>
  <property name="Id" type="s" access="read"/>
  <property name="Title" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="IconName" type="s" access="read"/>
  <property name="IconThemePath" type="s" access="read"/>
  <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
  <property name="ItemIsMenu" type="b" access="read"/>
  <property name="Menu" type="o" access="read"/>
  <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
  <method name="ProvideXdgActivationToken"><arg type="s" direction="in"/></method>
  <signal name="NewIcon"/>
  <signal name="NewToolTip"/>
</interface></node>"""

MENU_XML = """<node><interface name="com.canonical.dbusmenu">
  <property name="Version" type="u" access="read"/>
  <property name="TextDirection" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="IconThemePath" type="as" access="read"/>
  <method name="GetLayout">
    <arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
    <arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/>
  </method>
  <method name="GetGroupProperties">
    <arg type="ai" direction="in"/><arg type="as" direction="in"/><arg type="a(ia{sv})" direction="out"/>
  </method>
  <method name="GetProperty">
    <arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/>
  </method>
  <method name="Event">
    <arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/>
  </method>
  <method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/></method>
  <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
  <method name="AboutToShowGroup">
    <arg type="ai" direction="in"/><arg type="ai" direction="out"/><arg type="ai" direction="out"/>
  </method>
  <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
</interface></node>"""


class Tray:
    """Tray icon: left click calls `activate(token)`, right click shows `menu` — a list of (label, callback).

    `token` is the Wayland activation token from the tray host (e.g. KDE Plasma) that lets the window
    take focus, or None if the host doesn't provide one (e.g. waybar).
    """

    def __init__(self, connection, app_id, title, activate, menu, icon_theme_path=""):
        self.connection = connection
        self.app_id = app_id
        self.title = title
        self.activate = activate
        self.menu = menu
        self.icon_theme_path = icon_theme_path
        self.icon_name = app_id
        self.tooltip = ""
        self.token = None
        for path, xml, on_call, on_property in (
            (ITEM_PATH, ITEM_XML, self.on_item_call, self.on_item_property),
            (MENU_PATH, MENU_XML, self.on_menu_call, self.on_menu_property),
        ):
            interface = Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0]
            connection.register_object_with_closures2(path, interface, on_call, on_property, None)
        # Registers now and again whenever the tray host restarts (e.g. waybar reload).
        Gio.bus_watch_name_on_connection(connection, "org.kde.StatusNotifierWatcher",
                                         Gio.BusNameWatcherFlags.NONE, self.on_watcher_appeared, None)

    def update(self, icon_name, tooltip):
        if (icon_name, tooltip) == (self.icon_name, self.tooltip):
            return
        self.icon_name, self.tooltip = icon_name, tooltip
        for signal in ("NewIcon", "NewToolTip"):
            self.connection.emit_signal(None, ITEM_PATH, "org.kde.StatusNotifierItem", signal, None)

    def on_watcher_appeared(self, connection, name, owner):
        connection.call(name, "/StatusNotifierWatcher", name, "RegisterStatusNotifierItem",
                        GLib.Variant("(s)", (connection.get_unique_name(),)), None,
                        Gio.DBusCallFlags.NONE, -1, None, lambda *_: None)

    def on_item_call(self, connection, sender, path, interface, method, params, invocation):
        if method == "ProvideXdgActivationToken":  # sent by the host right before Activate
            self.token = params[0]
        elif method == "Activate":
            self.activate(self.token)
            self.token = None
        invocation.return_value(None)

    def on_item_property(self, connection, sender, path, interface, name):
        return {
            "Category": GLib.Variant("s", "Communications"),
            "Id": GLib.Variant("s", self.app_id),
            "Title": GLib.Variant("s", self.title),
            "Status": GLib.Variant("s", "Active"),
            "IconName": GLib.Variant("s", self.icon_name),
            "IconThemePath": GLib.Variant("s", self.icon_theme_path),
            "ToolTip": GLib.Variant("(sa(iiay)ss)", ("", [], self.title, self.tooltip)),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", MENU_PATH),
        }[name]

    # DBusMenu: id 0 is the root, menu entries are 1..n.
    def menu_properties(self, item_id):
        if item_id == 0:
            return {"children-display": GLib.Variant("s", "submenu")}
        return {"label": GLib.Variant("s", self.menu[item_id - 1][0])}

    def on_menu_call(self, connection, sender, path, interface, method, params, invocation):
        if method == "GetLayout":
            children = [GLib.Variant("(ia{sv}av)", (i, self.menu_properties(i), []))
                        for i in range(1, len(self.menu) + 1)]
            result = GLib.Variant("(u(ia{sv}av))", (1, (0, self.menu_properties(0), children)))
        elif method == "GetGroupProperties":
            ids = [i for i in params[0] if 0 <= i <= len(self.menu)]
            result = GLib.Variant("(a(ia{sv}))", ([(i, self.menu_properties(i)) for i in ids],))
        elif method == "GetProperty":
            result = GLib.Variant("(v)", (self.menu_properties(params[0]).get(params[1], GLib.Variant("s", "")),))
        elif method in ("Event", "EventGroup"):
            events = [params.unpack()[:2]] if method == "Event" else [e[:2] for e in params[0]]
            for item_id, event in events:
                if event == "clicked" and 1 <= item_id <= len(self.menu):
                    GLib.idle_add(lambda cb=self.menu[item_id - 1][1]: cb() and False)
            result = None if method == "Event" else GLib.Variant("(ai)", ([],))
        elif method == "AboutToShow":
            result = GLib.Variant("(b)", (False,))
        else:  # AboutToShowGroup
            result = GLib.Variant("(aiai)", ([], []))
        invocation.return_value(result)

    def on_menu_property(self, connection, sender, path, interface, name):
        return {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }[name]
