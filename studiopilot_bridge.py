# ##### BEGIN GPL LICENSE BLOCK #####
#
# StudioPilot Bridge — add-on Blender pour StudioPilot (FaciliX)
# Copyright (C) 2026 Olivier
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

"""
StudioPilot Bridge — add-on Blender (GPL-3.0).

Expose un serveur socket TCP local (127.0.0.1 UNIQUEMENT) permettant à
l'application StudioPilot (propriétaire, dépôt séparé) de piloter Blender.
Cet add-on ne communique QUE par socket : il ne contient et n'embarque
aucun code de l'application StudioPilot.

Session 1 (squelette) : panneau N, start/stop serveur, indicateur d'état.
Le protocole de commandes (ping, execute_code, ...) arrive en Session 2+.
"""

import socket
import sys
import threading

import bpy

bl_info = {
    "name": "StudioPilot Bridge",
    "author": "Olivier (StudioPilot)",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar (N) > StudioPilot",
    "description": "Serveur socket local (127.0.0.1) pour piloter Blender depuis StudioPilot",
    "category": "System",
}

# Bind loopback uniquement — ne jamais écouter sur toutes les interfaces.
_HOST = "127.0.0.1"

# État partagé entre le thread principal (UI/bpy) et le thread socket.
# Lectures/écritures de valeurs simples (bool/str/None) : sûres sous CPython
# grâce au GIL, aucun verrou nécessaire pour cet usage.
_state = {
    "running": False,
    "client_connected": False,
    "error": None,
    "thread": None,
    "stop_event": None,
}


def _accept_loop(server_socket, stop_event):
    """Tourne dans un thread séparé. N'appelle JAMAIS bpy — bpy n'est pas
    thread-safe. Se contente d'accepter une connexion et de la maintenir
    ouverte ; le protocole de commandes arrive en Session 2."""
    server_socket.settimeout(0.5)
    try:
        while not stop_event.is_set():
            try:
                conn, _addr = server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            _state["client_connected"] = True
            try:
                conn.settimeout(0.5)
                while not stop_event.is_set():
                    try:
                        chunk = conn.recv(4096)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    if not chunk:
                        break
                    # Session 1 : pas encore de protocole, les données
                    # reçues sont ignorées (voir Session 2 : queue + timers).
            finally:
                _state["client_connected"] = False
                try:
                    conn.close()
                except OSError:
                    pass
    finally:
        try:
            server_socket.close()
        except OSError:
            pass


def _redraw_timer():
    """Force le rafraîchissement du panneau N pendant que le serveur tourne.
    S'auto-désenregistre (retourne None) dès que le serveur est arrêté."""
    if not _state["running"]:
        return None
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
    return 0.3


class STUDIOPILOT_OT_start_server(bpy.types.Operator):
    bl_idname = "studiopilot.start_server"
    bl_label = "Démarrer le serveur"
    bl_description = "Démarre le serveur socket StudioPilot (127.0.0.1 uniquement)"

    def execute(self, context):
        if _state["running"]:
            return {"CANCELLED"}

        prefs = context.preferences.addons[__name__].preferences

        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if sys.platform == "win32":
                # Sur Windows, SO_REUSEADDR autorise un bind sur un port DEJA
                # occupe par un autre process (comportement different de
                # POSIX) — SO_EXCLUSIVEADDRUSE donne la vraie exclusivite
                # tout en permettant de relancer proprement apres un stop.
                server_socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1
                )
            else:
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((_HOST, prefs.port))
            server_socket.listen(1)
        except OSError as exc:
            _state["error"] = f"Port {prefs.port} indisponible : {exc}"
            self.report({"ERROR"}, _state["error"])
            return {"CANCELLED"}

        _state["error"] = None
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_accept_loop,
            args=(server_socket, stop_event),
            daemon=True,
        )
        _state["stop_event"] = stop_event
        _state["thread"] = thread
        _state["running"] = True
        thread.start()

        bpy.app.timers.register(_redraw_timer, first_interval=0.3)
        return {"FINISHED"}


class STUDIOPILOT_OT_stop_server(bpy.types.Operator):
    bl_idname = "studiopilot.stop_server"
    bl_label = "Arrêter le serveur"
    bl_description = "Arrête le serveur socket StudioPilot"

    def execute(self, context):
        if not _state["running"]:
            return {"CANCELLED"}

        _state["running"] = False
        if _state["stop_event"] is not None:
            _state["stop_event"].set()
        if _state["thread"] is not None:
            _state["thread"].join(timeout=2.0)

        _state["thread"] = None
        _state["stop_event"] = None
        _state["client_connected"] = False
        return {"FINISHED"}


class STUDIOPILOT_PT_panel(bpy.types.Panel):
    bl_label = "StudioPilot Bridge"
    bl_idname = "STUDIOPILOT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "StudioPilot"

    def draw(self, context):
        layout = self.layout
        prefs = context.preferences.addons[__name__].preferences

        if _state["client_connected"]:
            status_text = "🔵 Client connecté"
        elif _state["running"]:
            status_text = "🟢 En écoute"
        else:
            status_text = "⚫ Arrêté"

        layout.label(text=status_text)
        layout.label(text=f"Port : {prefs.port}")

        if _state["running"]:
            layout.operator("studiopilot.stop_server", icon="PAUSE")
        else:
            layout.operator("studiopilot.start_server", icon="PLAY")

        if _state["error"]:
            box = layout.box()
            box.alert = True
            box.label(text="⚠️ " + _state["error"], icon="ERROR")


class StudioPilotBridgePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    port: bpy.props.IntProperty(
        name="Port",
        description="Port TCP local du serveur StudioPilot (127.0.0.1 uniquement)",
        default=9876,
        min=1024,
        max=65535,
    )
    auto_start: bpy.props.BoolProperty(
        name="Démarrer automatiquement à l'ouverture de Blender",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "port")
        layout.prop(self, "auto_start")


def _auto_start_check():
    """Timer à usage unique exécuté juste après register() pour démarrer
    le serveur automatiquement si l'option est activée dans les préférences."""
    prefs = bpy.context.preferences.addons[__name__].preferences
    if prefs.auto_start and not _state["running"]:
        bpy.ops.studiopilot.start_server()
    return None


classes = (
    StudioPilotBridgePreferences,
    STUDIOPILOT_OT_start_server,
    STUDIOPILOT_OT_stop_server,
    STUDIOPILOT_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.timers.register(_auto_start_check, first_interval=1.0)


def unregister():
    if _state["running"]:
        _state["running"] = False
        if _state["stop_event"] is not None:
            _state["stop_event"].set()
        if _state["thread"] is not None:
            _state["thread"].join(timeout=2.0)
        _state["thread"] = None
        _state["stop_event"] = None
        _state["client_connected"] = False

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
