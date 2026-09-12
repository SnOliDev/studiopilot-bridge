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

Session 1 : panneau N, start/stop serveur, indicateur d'état.
Session 2 : protocole JSON préfixé longueur, boucle queue.Queue +
bpy.app.timers, commande `ping`. execute_code/get_scene_info/get_screenshot
arrivent en Sessions 3-5.
"""

import json
import queue
import socket
import struct
import sys
import threading
import traceback

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

# Timeout d'exécution d'une commande (§5 spec Bloc 1). Au-delà, le thread
# socket répond TimeoutError au client ; la commande peut néanmoins finir
# de s'exécuter plus tard sur le thread principal (résultat alors ignoré).
_COMMAND_TIMEOUT_S = 30.0

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

# Requêtes en attente d'exécution sur le thread principal. Chaque item :
# (request: dict, response_box: dict, response_event: threading.Event).
# bpy n'étant pas thread-safe, c'est le SEUL canal par lequel le thread
# socket déclenche du travail lié à bpy.
_request_queue = queue.Queue()


def _cmd_ping(params):
    """Exécuté sur le thread principal (bpy.app.version_string lit l'état
    Blender). Ne fait aucune supposition sur `params`."""
    return {
        "pong": True,
        "blender_version": bpy.app.version_string,
        "addon_version": ".".join(str(part) for part in bl_info["version"]),
    }


# Registre des commandes supportées. Ajouter une commande = ajouter une
# fonction ci-dessus + une entrée ici, zéro modification de la boucle.
_COMMAND_HANDLERS = {
    "ping": _cmd_ping,
}


def _process_queue():
    """Timer bpy.app.timers — SEUL point d'exécution des commandes bpy.
    Dépile tout ce qui est disponible sans bloquer, puis se réenregistre
    tant que le serveur tourne."""
    if not _state["running"]:
        return None

    while True:
        try:
            request, response_box, response_event = _request_queue.get_nowait()
        except queue.Empty:
            break

        request_id = request.get("id")
        command = request.get("command")
        params = request.get("params") or {}
        handler = _COMMAND_HANDLERS.get(command)

        try:
            if handler is None:
                raise KeyError(f"Commande inconnue : {command}")
            result = handler(params)
            response = {"id": request_id, "status": "ok", "result": result, "error": None}
        except Exception as exc:  # noqa: BLE001 - renvoyé au client, jamais avalé
            response = {
                "id": request_id,
                "status": "error",
                "result": None,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            }

        response_box["response"] = response
        response_event.set()

    return 0.05


def _error_response(request_id, error_type, message):
    return {
        "id": request_id,
        "status": "error",
        "result": None,
        "error": {"type": error_type, "message": message, "traceback": None},
    }


def _recv_exact(conn, size, stop_event):
    """Lit exactement `size` octets. Retourne None si le client se
    déconnecte ou si l'arrêt du serveur est demandé pendant l'attente."""
    buf = bytearray()
    while len(buf) < size:
        if stop_event.is_set():
            return None
        try:
            chunk = conn.recv(size - len(buf))
        except socket.timeout:
            continue
        except OSError:
            return None
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def _recv_message(conn, stop_event):
    """Lit un message JSON préfixé longueur (4 octets big-endian). Retourne
    None sur déconnexion/arrêt. Peut lever ValueError si le JSON est
    invalide — géré par l'appelant."""
    header = _recv_exact(conn, 4, stop_event)
    if header is None:
        return None
    (length,) = struct.unpack(">I", header)
    payload = _recv_exact(conn, length, stop_event)
    if payload is None:
        return None
    return json.loads(payload.decode("utf-8"))


def _send_message(conn, obj):
    payload = json.dumps(obj).encode("utf-8")
    conn.sendall(struct.pack(">I", len(payload)) + payload)


def _dispatch(request):
    """Appelé depuis le thread socket. Pousse la requête dans la queue et
    attend la réponse produite par _process_queue sur le thread principal —
    ne touche jamais bpy directement."""
    request_id = request.get("id") if isinstance(request, dict) else None

    if not isinstance(request, dict) or "command" not in request:
        return _error_response(request_id, "ProtocolError", "Requête invalide : champ 'command' manquant")

    command = request["command"]
    if command not in _COMMAND_HANDLERS:
        return _error_response(request_id, "UnknownCommand", f"Commande inconnue : {command}")

    response_box = {}
    response_event = threading.Event()
    _request_queue.put((request, response_box, response_event))

    if not response_event.wait(timeout=_COMMAND_TIMEOUT_S):
        return _error_response(
            request_id, "TimeoutError", f"Commande '{command}' : délai de {_COMMAND_TIMEOUT_S}s dépassé"
        )
    return response_box["response"]


def _handle_client(conn, stop_event):
    conn.settimeout(0.5)
    while not stop_event.is_set():
        try:
            request = _recv_message(conn, stop_event)
        except (ValueError, UnicodeDecodeError) as exc:
            try:
                _send_message(conn, _error_response(None, "ProtocolError", f"JSON invalide : {exc}"))
            except OSError:
                break
            continue

        if request is None:
            break  # client déconnecté ou arrêt demandé

        response = _dispatch(request)
        try:
            _send_message(conn, response)
        except OSError:
            break


def _accept_loop(server_socket, stop_event):
    """Tourne dans un thread séparé. N'appelle JAMAIS bpy — bpy n'est pas
    thread-safe. Accepte une connexion, délègue à _handle_client (protocole
    JSON préfixé longueur), qui pousse les commandes dans _request_queue
    pour exécution sur le thread principal via bpy.app.timers."""
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
                _handle_client(conn, stop_event)
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
        bpy.app.timers.register(_process_queue, first_interval=0.05)
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

        # Purge les requêtes non traitées (ex. client déconnecté avant
        # réponse) pour ne pas les faire réapparaître au prochain démarrage.
        while True:
            try:
                _request_queue.get_nowait()
            except queue.Empty:
                break

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
        default=9877,
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
