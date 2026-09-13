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
bpy.app.timers, commande `ping`.
Session 3 : commande `execute_code`. + deux correctifs confirmés
manuellement par Olivier sur le round-trip Session 2 (ping fonctionne en
conditions réelles, confirmé) :
  1. bpy.app.timers ne se déclenche pas de façon fiable sans interaction
     Blender (le bpy.app.timers registré en Session 2 dépendait du cycle
     de redraw) → remplacé par un opérateur modal avec un timer de
     window_manager (event_timer_add), qui reçoit des événements TIMER
     même sans interaction utilisateur.
  2. Un processus tiers (probablement BlenderMCP) se connecte
     automatiquement au port dès le démarrage sans jamais envoyer de
     requête → le serveur accepte maintenant chaque connexion dans son
     propre thread, refuse proprement (JSON BusyError) toute connexion
     supplémentaire pendant qu'un client est actif, et abandonne une
     connexion silencieuse au bout de quelques secondes pour libérer
     la place pour un vrai client.
Session 4 : commande `get_scene_info`.
Session 5 : commande `get_screenshot`.
Session 6 (dernière du Bloc 1) : liste noire de sécurité (défense en
profondeur sur `execute_code` — voir SecurityError plus bas), test_client.py
et README dans le dépôt. La validation principale du code généré reste
côté app StudioPilot (Bloc 4) : cette liste noire ne protège que contre les
appels les plus évidents, elle n'est PAS une sandbox.
"""

import base64
import contextlib
import glob
import io
import json
import math
import os
import queue
import random
import re
import socket
import struct
import sys
import threading
import time
import traceback
import uuid

import bpy
import mathutils

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

# Délai laissé à une connexion pour envoyer son premier message valide.
# Passé ce délai sans un seul octet reçu, on considère que ce n'est pas
# un vrai client StudioPilot (ex. sonde/health-check d'un autre outil local
# type BlenderMCP) et on libère la place. Ne s'applique plus une fois le
# premier message reçu — un client légitime peut ensuite rester inactif
# arbitrairement longtemps entre deux requêtes utilisateur.
_FIRST_MESSAGE_TIMEOUT_S = 5.0

# Taille max d'un message (garde-fou mémoire si le préfixe de longueur est
# corrompu ou envoyé par un pair qui ne parle pas notre protocole).
_MAX_MESSAGE_SIZE = 20 * 1024 * 1024

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


class SecurityError(Exception):
    """Levée par la liste noire de `execute_code` (§6 spec Bloc 1).

    ⚠️ Défense en profondeur UNIQUEMENT — PAS la sandbox principale. La
    validation réelle du code généré par le LLM est côté app StudioPilot
    (Bloc 4). Un contournement de cette liste noire (ex. espace entre
    `eval` et `(`, alias d'import) n'est ni surprenant ni à corriger ici :
    c'est le rôle du Bloc 4, pas de ce garde-fou minimal.
    """


# Motifs interdits (§6 spec Bloc 1) — recherche insensible à la casse, mot
# entier (\b) pour éviter les faux positifs du type "subprocessing_lib".
# "socket." et "eval("/"exec(" n'ont pas de \b final : on veut bloquer
# TOUT usage (n'importe quel attribut de socket, tout appel eval/exec),
# pas seulement le token isolé.
_BLACKLIST_PATTERNS = [
    (r"\bos\.system\b", "os.system"),
    (r"\bsubprocess\b", "subprocess"),
    (r"\bshutil\.rmtree\b", "shutil.rmtree"),
    (r"\bsocket\.", "socket."),
    (r"\burllib\b", "urllib"),
    (r"\brequests\b", "requests"),
    (r"\beval\(", "eval("),
    (r"\b__import__\b", "__import__"),
    (r"\bctypes\b", "ctypes"),
    (r"\bsys\.exit\b", "sys.exit"),
    (r"\bexec\(", "exec("),
]
_BLACKLIST_REGEX = [(re.compile(pattern, re.IGNORECASE), label) for pattern, label in _BLACKLIST_PATTERNS]


def _find_blacklisted_pattern(code):
    """Retourne le libellé du premier motif interdit trouvé dans `code`,
    ou None si aucun ne matche."""
    for regex, label in _BLACKLIST_REGEX:
        if regex.search(code):
            return label
    return None


def _cmd_execute_code(params):
    """Exécute du code bpy arbitraire sur le thread principal, après
    passage par la liste noire de secours (voir SecurityError).

    ⚠️ La liste noire est une défense en profondeur, PAS une sandbox — un
    code malveillant suffisamment habile peut la contourner. La validation
    principale reste côté app StudioPilot (Bloc 4)."""
    code = params.get("code", "")
    if not isinstance(code, str):
        raise TypeError("params.code doit être une chaîne de caractères")

    blocked_pattern = _find_blacklisted_pattern(code)
    if blocked_pattern is not None:
        raise SecurityError(f"Motif interdit détecté dans le code : {blocked_pattern!r}")

    namespace = {"bpy": bpy, "math": math, "mathutils": mathutils, "random": random}
    stdout_capture = io.StringIO()
    with contextlib.redirect_stdout(stdout_capture):
        exec(code, namespace)  # noqa: S102 - c'est la fonctionnalité même du bridge

    return {"stdout": stdout_capture.getvalue(), "executed": True}


def _round_vec(vec, ndigits=4):
    return [round(float(v), ndigits) for v in vec]


def _material_info(material):
    """Base_color/metallic/roughness : priorité au node Principled BSDF
    (reflète ce qui est réellement rendu — voir skill bpy-blender), repli sur
    les propriétés "affichage viewport" du matériau (toujours présentes,
    jamais de KeyError même sans nodes ou avec un shader personnalisé)."""
    info = {
        "name": material.name,
        "base_color": _round_vec(material.diffuse_color),
        "metallic": round(material.metallic, 4),
        "roughness": round(material.roughness, 4),
    }

    if material.use_nodes and material.node_tree is not None:
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is not None:
            base_color_input = principled.inputs.get("Base Color")
            metallic_input = principled.inputs.get("Metallic")
            roughness_input = principled.inputs.get("Roughness")
            if base_color_input is not None:
                info["base_color"] = _round_vec(base_color_input.default_value)
            if metallic_input is not None:
                info["metallic"] = round(metallic_input.default_value, 4)
            if roughness_input is not None:
                info["roughness"] = round(roughness_input.default_value, 4)

    return info


def _cmd_get_scene_info(params):
    """État compact de la scène active — destiné au contexte LLM (Bloc 3),
    chaque token compte (§4 spec Bloc 1). `objects` est tronqué à
    `max_objects` (défaut 100) ; `lights`/`materials`/`camera` couvrent
    toute la scène (généralement peu nombreux, utiles même si les objets
    sont tronqués)."""
    max_objects = params.get("max_objects", 100)
    if not isinstance(max_objects, int) or isinstance(max_objects, bool) or max_objects < 0:
        raise TypeError("params.max_objects doit être un entier >= 0")

    scene = bpy.context.scene
    all_objects = list(scene.objects)
    object_count_total = len(all_objects)
    truncated = object_count_total > max_objects

    objects_info = []
    material_names_seen = set()
    for obj in all_objects[:max_objects]:
        slot_material_names = [slot.material.name for slot in obj.material_slots if slot.material is not None]
        material_names_seen.update(slot_material_names)
        objects_info.append(
            {
                "name": obj.name,
                "type": obj.type,
                "location": _round_vec(obj.location),
                "rotation_euler": _round_vec(obj.rotation_euler),
                "scale": _round_vec(obj.scale),
                "dimensions": _round_vec(obj.dimensions),
                "materials": slot_material_names,
                "visible": obj.visible_get(),
            }
        )

    camera_obj = scene.camera
    camera_info = None
    if camera_obj is not None:
        camera_info = {
            "name": camera_obj.name,
            "location": _round_vec(camera_obj.location),
            "rotation_euler": _round_vec(camera_obj.rotation_euler),
            "lens_mm": round(camera_obj.data.lens, 4) if camera_obj.data is not None else None,
        }

    lights_info = [
        {
            "name": obj.name,
            "type": obj.data.type,
            "energy": round(obj.data.energy, 4),
            "location": _round_vec(obj.location),
        }
        for obj in all_objects
        if obj.type == "LIGHT" and obj.data is not None
    ]

    materials_info = [
        _material_info(bpy.data.materials[name])
        for name in sorted(material_names_seen)
        if name in bpy.data.materials
    ]

    fps_base = scene.render.fps_base or 1.0

    return {
        "scene_name": scene.name,
        "frame_current": scene.frame_current,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "objects": objects_info,
        "object_count_total": object_count_total,
        "truncated": truncated,
        "camera": camera_info,
        "lights": lights_info,
        "materials": materials_info,
        "render": {
            "engine": scene.render.engine,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "fps": round(scene.render.fps / fps_base, 4),
        },
    }


_SCREENSHOT_FORMATS = {"png": "PNG", "jpeg": "JPEG", "jpg": "JPEG"}


def _find_view3d_context():
    """Cherche une zone VIEW_3D avec une région WINDOW, dans n'importe
    quelle fenêtre ouverte. Retourne (window, area, region), ou None si
    aucune n'est utilisable.

    ⚠️ En mode `--background`, Blender conserve la mise en page
    fenêtre/écran/zone du fichier de démarrage par défaut MÊME SANS aucun
    contexte OpenGL réel — `window_manager.windows` n'est donc PAS vide et
    une zone VIEW_3D "fantôme" y est trouvée, ce qui ferait planter
    `bpy.ops.render.opengl` avec "Cannot use OpenGL render in background
    mode". `bpy.app.background` est le signal fiable pour détecter ce cas
    et basculer directement sur le repli rendu complet (découvert en testant
    cette commande en headless)."""
    if bpy.app.background:
        return None
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                for region in area.regions:
                    if region.type == "WINDOW":
                        return window, area, region
    return None


def _cmd_get_screenshot(params):
    """Capture le viewport actif (§ get_screenshot spec Bloc 1). Modifie
    temporairement les réglages de rendu de la scène active (filepath,
    format, résolution %) puis les restaure toujours (try/finally) — cette
    commande ne doit jamais altérer les réglages de rendu réels de
    l'utilisateur."""
    max_size = params.get("max_size", 800)
    if not isinstance(max_size, int) or isinstance(max_size, bool) or max_size <= 0:
        raise TypeError("params.max_size doit être un entier > 0")

    format_key = str(params.get("format", "png")).lower()
    if format_key not in _SCREENSHOT_FORMATS:
        raise ValueError(f"format non supporté : {format_key!r} (attendu : {sorted(_SCREENSHOT_FORMATS)})")
    file_format = _SCREENSHOT_FORMATS[format_key]

    scene = bpy.context.scene
    render = scene.render
    view3d_ctx = _find_view3d_context()

    temp_path = os.path.join(bpy.app.tempdir, f"studiopilot_screenshot_{uuid.uuid4().hex}")

    original_filepath = render.filepath
    original_file_format = render.image_settings.file_format
    original_percentage = render.resolution_percentage

    largest_side = max(render.resolution_x, render.resolution_y, 1)
    target_percentage = min(100.0, 100.0 * max_size / largest_side)

    try:
        render.filepath = temp_path
        render.image_settings.file_format = file_format
        # floor (pas round) : garantit que la sortie ne dépasse JAMAIS
        # max_size — un arrondi au plus proche peut pousser un pixel au-delà
        # (constaté : 41.67% arrondi à 42% donnait 806px pour max_size=800).
        render.resolution_percentage = max(1, math.floor(target_percentage))

        if view3d_ctx is not None:
            window, area, region = view3d_ctx
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.render.opengl(write_still=True, view_context=True)
        else:
            # Aucun viewport disponible (ex. mode --background) : repli sur
            # un rendu complet depuis la caméra active. Moins fidèle à "ce
            # que voit l'utilisateur" qu'un rendu viewport, mais évite de
            # réimplémenter un rendu offscreen GPU complet pour un cas qui
            # ne se présente jamais en usage réel (app StudioPilot = GUI
            # Blender toujours ouverte avec un viewport).
            bpy.ops.render.render(write_still=True)
    finally:
        render.filepath = original_filepath
        render.image_settings.file_format = original_file_format
        render.resolution_percentage = original_percentage

    # Le nom de fichier réellement écrit par Blender pour un rendu "still"
    # ne correspond pas toujours à render.frame_path() (celui-ci ajoute un
    # suffixe de numéro de frame que write_still=True n'utilise pas
    # toujours — constaté en testant cette commande). Le préfixe étant unique
    # (UUID), un glob retrouve le fichier réel sans avoir à deviner le
    # suffixe/extension exacts.
    matches = glob.glob(temp_path + "*")
    if not matches:
        raise RuntimeError(f"Le rendu n'a produit aucun fichier (préfixe attendu : {temp_path})")
    output_path = matches[0]

    try:
        image_datablock = bpy.data.images.load(output_path, check_existing=False)
        try:
            width, height = image_datablock.size[0], image_datablock.size[1]
        finally:
            bpy.data.images.remove(image_datablock)

        with open(output_path, "rb") as image_file:
            image_bytes = image_file.read()
    finally:
        try:
            os.remove(output_path)
        except OSError:
            pass

    return {
        "image_base64": base64.b64encode(image_bytes).decode("ascii"),
        "width": width,
        "height": height,
    }


# Registre des commandes supportées. Ajouter une commande = ajouter une
# fonction ci-dessus + une entrée ici, zéro modification de la boucle.
_COMMAND_HANDLERS = {
    "ping": _cmd_ping,
    "execute_code": _cmd_execute_code,
    "get_scene_info": _cmd_get_scene_info,
    "get_screenshot": _cmd_get_screenshot,
}


def _process_queue():
    """Appelé sur le thread principal à chaque tick TIMER de l'opérateur
    modal (STUDIOPILOT_OT_modal_server) — SEUL point d'exécution des
    commandes bpy. Dépile tout ce qui est disponible sans bloquer."""
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


def _error_response(request_id, error_type, message):
    return {
        "id": request_id,
        "status": "error",
        "result": None,
        "error": {"type": error_type, "message": message, "traceback": None},
    }


def _recv_exact(conn, size, stop_event, deadline=None):
    """Lit exactement `size` octets. Retourne None si le client se
    déconnecte, si l'arrêt du serveur est demandé, ou si `deadline`
    (time.monotonic()) est dépassée pendant l'attente."""
    buf = bytearray()
    while len(buf) < size:
        if stop_event.is_set():
            return None
        if deadline is not None and time.monotonic() > deadline:
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


def _recv_message(conn, stop_event, deadline=None):
    """Lit un message JSON préfixé longueur (4 octets big-endian). Retourne
    None sur déconnexion/arrêt/deadline dépassée. Peut lever ValueError si
    le JSON est invalide ou si le préfixe de longueur dépasse
    _MAX_MESSAGE_SIZE — géré par l'appelant."""
    header = _recv_exact(conn, 4, stop_event, deadline)
    if header is None:
        return None
    (length,) = struct.unpack(">I", header)
    if length > _MAX_MESSAGE_SIZE:
        raise ValueError(f"message de {length} octets > limite {_MAX_MESSAGE_SIZE}")
    payload = _recv_exact(conn, length, stop_event, deadline)
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
    """Boucle de traitement d'UN client déjà accepté. Tant qu'aucun message
    valide n'a été reçu, une deadline courte (_FIRST_MESSAGE_TIMEOUT_S)
    s'applique — voir le commentaire sur cette constante. Une fois un
    premier message reçu (même invalide), le client est traité comme
    légitime et peut rester inactif indéfiniment."""
    conn.settimeout(0.5)
    got_first_message = False

    while not stop_event.is_set():
        deadline = None if got_first_message else time.monotonic() + _FIRST_MESSAGE_TIMEOUT_S
        try:
            request = _recv_message(conn, stop_event, deadline)
        except (ValueError, UnicodeDecodeError) as exc:
            got_first_message = True
            try:
                _send_message(conn, _error_response(None, "ProtocolError", f"JSON invalide : {exc}"))
            except OSError:
                break
            continue

        if request is None:
            break  # client déconnecté, arrêt demandé, ou premier message jamais reçu

        got_first_message = True
        response = _dispatch(request)
        try:
            _send_message(conn, response)
        except OSError:
            break


def _refuse_extra_client(conn):
    """Un client est déjà actif : refus propre avec une erreur JSON plutôt
    que de laisser la connexion en attente indéfiniment (§1 spec Bloc 1)."""
    try:
        conn.settimeout(1.0)
        _send_message(conn, _error_response(None, "BusyError", "Un client StudioPilot est déjà connecté."))
    except OSError:
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass


def _serve_client(conn, stop_event):
    """Tourne dans son propre thread (un par client actif). N'appelle
    JAMAIS bpy — voir _handle_client. Libère `client_connected` en sortie,
    quelle que soit la cause (déconnexion, erreur, arrêt du serveur)."""
    try:
        _handle_client(conn, stop_event)
    finally:
        _state["client_connected"] = False
        try:
            conn.close()
        except OSError:
            pass


def _accept_loop(server_socket, stop_event):
    """Tourne dans un thread séparé. N'appelle JAMAIS bpy — bpy n'est pas
    thread-safe. Accepte les connexions en continu (jamais bloqué par un
    client en cours de traitement, qui vit dans son propre thread) : un
    seul client actif à la fois, toute connexion supplémentaire reçoit un
    refus JSON propre puis est fermée."""
    server_socket.settimeout(0.5)
    active_client_thread = None
    try:
        while not stop_event.is_set():
            try:
                conn, _addr = server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            if active_client_thread is not None and not active_client_thread.is_alive():
                active_client_thread = None

            if active_client_thread is not None or _state["client_connected"]:
                _refuse_extra_client(conn)
                continue

            _state["client_connected"] = True
            active_client_thread = threading.Thread(
                target=_serve_client,
                args=(conn, stop_event),
                daemon=True,
            )
            active_client_thread.start()

        if active_client_thread is not None:
            active_client_thread.join(timeout=2.0)
    finally:
        try:
            server_socket.close()
        except OSError:
            pass


def _tag_redraw_viewports(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


class STUDIOPILOT_OT_modal_server(bpy.types.Operator):
    """Boucle interne du bridge — invisible pour l'utilisateur.

    Remplace le bpy.app.timers utilisé en Session 2 : celui-ci ne se
    déclenche pas de façon fiable sans interaction Blender (confirmé
    manuellement). Un opérateur modal avec un timer de window_manager
    (event_timer_add) reçoit des événements TIMER dispatchés par Blender
    indépendamment de toute interaction souris/clavier — c'est le
    mécanisme recommandé pour du travail périodique sans UI.
    """

    bl_idname = "studiopilot.modal_server"
    bl_label = "StudioPilot Bridge — boucle interne"
    bl_options = {"INTERNAL"}

    _timer = None

    def modal(self, context, event):
        if not _state["running"]:
            self._stop_timer(context)
            return {"FINISHED"}

        if event.type == "TIMER":
            _process_queue()
            _tag_redraw_viewports(context)

        return {"PASS_THROUGH"}

    def execute(self, context):
        window_manager = context.window_manager
        window = context.window or (window_manager.windows[0] if window_manager.windows else None)
        if window is None:
            return {"CANCELLED"}  # aucune fenêtre disponible (ex. mode --background)
        self._timer = window_manager.event_timer_add(0.05, window=window)
        window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _stop_timer(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None


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

        try:
            modal_result = bpy.ops.studiopilot.modal_server("INVOKE_DEFAULT")
        except RuntimeError as exc:
            modal_result = None
            _state["error"] = f"Boucle interne non démarrée : {exc}"

        if modal_result is None or "RUNNING_MODAL" not in modal_result:
            # Pas de fenêtre disponible (ex. démarrage auto trop tôt, ou
            # mode --background) : le serveur socket tourne quand même,
            # mais aucune commande ne pourra être exécutée tant que la
            # boucle modale n'aura pas pu démarrer (relancer depuis le
            # panneau une fois une fenêtre Blender ouverte).
            if _state["error"] is None:
                _state["error"] = "Boucle interne non démarrée (aucune fenêtre Blender disponible)."
            self.report({"WARNING"}, _state["error"])

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
    STUDIOPILOT_OT_modal_server,
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
