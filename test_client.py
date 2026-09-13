#!/usr/bin/env python3
# ##### BEGIN GPL LICENSE BLOCK #####
#
# StudioPilot Bridge — client de test (GPL-3.0)
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
Client de test pour StudioPilot Bridge — stdlib Python pur (socket, json,
struct, base64, uuid), exécutable HORS Blender.

Mode d'emploi :
    1. Ouvrir Blender, activer l'add-on StudioPilot Bridge
       (Preferences > Add-ons).
    2. Ouvrir la sidebar du viewport (touche N) > onglet "StudioPilot",
       cliquer "Démarrer le serveur".
    3. Dans un terminal : python test_client.py

Options : --host (défaut 127.0.0.1) --port (défaut 9877).

Exécute les 6 tests de la spec Bloc 1 dans l'ordre, affiche ✅/❌ pour
chacun, et termine avec le code de sortie 0 si tout passe, 1 sinon.
"""

import argparse
import base64
import json
import socket
import struct
import sys
import uuid

# Certaines consoles Windows (cmd.exe, PowerShell selon la configuration)
# utilisent par défaut un encodage (ex. cp1252) qui ne sait pas afficher
# les emojis ✅/❌ ci-dessous, ce qui plante le script avec un
# UnicodeEncodeError avant même d'afficher un résultat de test (constaté
# en testant ce script). On force UTF-8 sur stdout/stderr pour éviter ça,
# quelle que soit la console utilisée.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # flux déjà fermé/redirigé d'une façon qui ne le permet pas

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9877

# Légèrement > le timeout serveur (30s, voir _COMMAND_TIMEOUT_S dans
# studiopilot_bridge.py) pour laisser le temps à une réponse d'erreur
# propre de revenir plutôt que de couper la connexion nous-mêmes en premier.
SOCKET_TIMEOUT_S = 35.0


class BridgeClient:
    """Implémente le protocole du bridge : JSON UTF-8 préfixé longueur
    (4 octets big-endian, voir §3 spec Bloc 1)."""

    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=SOCKET_TIMEOUT_S)
        self.sock.settimeout(SOCKET_TIMEOUT_S)

    def close(self):
        self.sock.close()

    def send(self, command, params=None):
        request = {"id": str(uuid.uuid4()), "command": command, "params": params or {}}
        payload = json.dumps(request).encode("utf-8")
        self.sock.sendall(struct.pack(">I", len(payload)) + payload)

        header = self._recv_exact(4)
        (length,) = struct.unpack(">I", header)
        body = self._recv_exact(length)
        return json.loads(body.decode("utf-8"))

    def _recv_exact(self, size):
        buf = bytearray()
        while len(buf) < size:
            chunk = self.sock.recv(size - len(buf))
            if not chunk:
                raise ConnectionError("Connexion fermée par le serveur pendant la lecture")
            buf.extend(chunk)
        return bytes(buf)


_results = []


def check(label, condition, detail=None):
    mark = "✅" if condition else "❌"
    print(f"{mark} {label}")
    if not condition and detail is not None:
        print(f"   → {detail}")
    _results.append(condition)


def run_tests(client):
    # Test 1 — ping
    resp = client.send("ping")
    result = resp.get("result", {}) or {}
    check(
        "Test 1 — ping",
        resp.get("status") == "ok" and result.get("pong") is True,
        resp,
    )
    print(f"   Blender {result.get('blender_version')} — add-on {result.get('addon_version')}")

    # Test 2 — execute_code (créer un cube), puis vérifier via get_scene_info
    resp = client.send("execute_code", {"code": "bpy.ops.mesh.primitive_cube_add(location=(2, 0, 0))"})
    check("Test 2a — execute_code crée un cube", resp.get("status") == "ok", resp)

    resp = client.send("get_scene_info")
    objects = resp.get("result", {}).get("objects", []) if resp.get("status") == "ok" else []
    mesh_names = [o["name"] for o in objects if o.get("type") == "MESH"]
    check(
        "Test 2b — get_scene_info montre le nouveau cube",
        resp.get("status") == "ok" and any(name.startswith("Cube") for name in mesh_names),
        f"objets MESH trouvés : {mesh_names}",
    )

    # Test 3 — execute_code avec une erreur volontaire
    resp = client.send("execute_code", {"code": "bpy.data.objects['Inexistant']"})
    check(
        "Test 3 — erreur volontaire → status error + traceback",
        resp.get("status") == "error" and bool(resp.get("error", {}).get("traceback")),
        resp.get("error"),
    )

    # Test 4 — liste noire (os.system)
    resp = client.send("execute_code", {"code": "import os; os.system('echo pwned')"})
    check(
        "Test 4 — liste noire bloque os.system (SecurityError)",
        resp.get("status") == "error" and resp.get("error", {}).get("type") == "SecurityError",
        resp.get("error"),
    )

    # Test 5 — get_screenshot
    resp = client.send("get_screenshot", {"max_size": 800})
    ok = resp.get("status") == "ok"
    if ok:
        image_bytes = base64.b64decode(resp["result"]["image_base64"])
        with open("test_screenshot.png", "wb") as f:
            f.write(image_bytes)
        width, height = resp["result"]["width"], resp["result"]["height"]
        ok = max(width, height) <= 800
        print(f"   Capture sauvée dans test_screenshot.png ({width}x{height}, {len(image_bytes)} octets)")
    check("Test 5 — get_screenshot ≤ 800px, sauvé dans test_screenshot.png", ok, resp)

    # Test 6 — charge légère : 20 get_scene_info d'affilée
    ok = True
    for _ in range(20):
        resp = client.send("get_scene_info")
        if resp.get("status") != "ok":
            ok = False
            break
    check("Test 6 — 20 get_scene_info d'affilée sans erreur", ok, resp if not ok else None)


def main():
    parser = argparse.ArgumentParser(description="Tests du bridge StudioPilot (Bloc 1)")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Défaut : {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Défaut : {DEFAULT_PORT}")
    args = parser.parse_args()

    print(f"Connexion à {args.host}:{args.port}...")
    try:
        client = BridgeClient(args.host, args.port)
    except OSError as exc:
        print(f"❌ Impossible de se connecter : {exc}")
        print("   Vérifiez que Blender est ouvert, l'add-on activé, et le serveur démarré (panneau N).")
        sys.exit(1)

    try:
        run_tests(client)
    finally:
        client.close()

    print()
    passed, total = sum(_results), len(_results)
    print(f"{passed}/{total} tests réussis.")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
