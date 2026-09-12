# BLOC 1 — Bridge Blender (StudioPilot / FaciliX)

> Document d'exécution pour Claude Code. Respecter les règles de code du projet :
> [OBJECTIF]→[FICHIERS]→[CODE]→[TESTS]→[VÉRIFICATION], diffs ciblés, questions avant ambiguïté.

---

## [OBJECTIF]

Créer un add-on Blender (GPL, dépôt séparé) qui expose un serveur socket TCP local
permettant à l'app StudioPilot de :
1. exécuter du code Python `bpy` dans Blender,
2. lire l'état de la scène (objets, matériaux, caméra, lumières),
3. capturer une image du viewport (retour visuel pour le LLM),
4. vérifier que le pont est vivant (ping).

Cible : **Blender 4.2 LTS**, Windows d'abord. Aucune dépendance externe
(uniquement la stdlib Python embarquée dans Blender).

**Hors périmètre Bloc 1** : l'app Tauri (Bloc 2), la boucle LLM (Bloc 3),
la validation/sandbox côté app (Bloc 4). L'add-on inclut seulement un
garde-fou minimal (voir Sécurité).

---

## [FICHIERS]

Dépôt séparé `studiopilot-bridge/` (licence GPL-3.0, comme Blender) :

```
studiopilot-bridge/
├── LICENSE                  # GPL-3.0
├── README.md                # installation en 3 étapes + captures
├── studiopilot_bridge.py    # add-on mono-fichier (tout dedans)
└── test_client.py           # client de test hors Blender (stdlib only)
```

Un add-on **mono-fichier** suffit et simplifie l'installation
(Edit → Preferences → Add-ons → Install → sélectionner le .py).

---

## SPÉCIFICATION TECHNIQUE

### 1. Serveur socket

- TCP, **bind 127.0.0.1 uniquement** (jamais 0.0.0.0), port **9877**
  (configurable dans les préférences de l'add-on).
- Un seul client à la fois (l'app StudioPilot). Refuser proprement les connexions
  supplémentaires avec une erreur JSON.
- Le serveur tourne dans un **thread séparé** ; démarrage/arrêt via un panneau
  dans la sidebar du viewport (touche N, onglet "StudioPilot") avec indicateur
  d'état : ⚫ arrêté / 🟢 en écoute / 🔵 client connecté.
- Option "Démarrer automatiquement à l'ouverture de Blender" dans les préférences.

### 2. ⚠️ Contrainte critique : thread principal

`bpy` n'est **pas thread-safe**. Le thread socket ne doit JAMAIS appeler `bpy`
directement. Architecture obligatoire :

- Le thread socket reçoit la requête et la pousse dans une `queue.Queue`.
- Un callback enregistré via `bpy.app.timers.register(...)` (exécuté sur le
  thread principal) dépile la queue, exécute la commande, pousse le résultat
  dans une queue de réponse.
- Le thread socket attend la réponse (avec timeout, voir §5) puis répond au client.

C'est le point le plus délicat du bloc — le traiter en premier et le tester isolément.

### 3. Protocole de messages

JSON encodé UTF-8, **délimité par un préfixe de longueur** : 4 octets big-endian
(uint32) donnant la taille du payload JSON qui suit. (Plus robuste que le
délimiteur newline pour les screenshots base64 volumineux.)

**Requête :**
```json
{ "id": "uuid-généré-par-le-client", "command": "execute_code", "params": { ... } }
```

**Réponse :**
```json
{ "id": "même-uuid", "status": "ok" | "error", "result": { ... }, "error": null | { "type": "...", "message": "...", "traceback": "..." } }
```

### 4. Commandes

| command | params | result |
|---|---|---|
| `ping` | — | `{ "pong": true, "blender_version": "4.2.x", "addon_version": "0.1.0" }` |
| `execute_code` | `{ "code": "<python bpy>" }` | `{ "stdout": "...", "executed": true }` |
| `get_scene_info` | `{ "max_objects": 100 }` (défaut 100) | voir schéma ci-dessous |
| `get_screenshot` | `{ "max_size": 800, "format": "png" }` | `{ "image_base64": "...", "width": w, "height": h }` |

**Schéma `get_scene_info`** (compact — il part dans le contexte LLM, chaque token compte) :
```json
{
  "scene_name": "Scene",
  "frame_current": 1, "frame_start": 1, "frame_end": 250,
  "objects": [
    { "name": "Cube", "type": "MESH",
      "location": [0,0,0], "rotation_euler": [0,0,0], "scale": [1,1,1],
      "dimensions": [2,2,2],
      "materials": ["Material.001"],
      "visible": true }
  ],
  "object_count_total": 3,
  "truncated": false,
  "camera": { "name": "Camera", "location": [...], "rotation_euler": [...], "lens_mm": 50 },
  "lights": [ { "name": "Light", "type": "POINT", "energy": 1000, "location": [...] } ],
  "materials": [ { "name": "Material.001", "base_color": [0.8,0.1,0.1,1.0], "metallic": 0.0, "roughness": 0.5 } ],
  "render": { "engine": "BLENDER_EEVEE_NEXT", "resolution": [1920,1080], "fps": 24 }
}
```
Arrondir les floats à 4 décimales. Si > `max_objects`, tronquer et mettre
`"truncated": true`.

**`execute_code`** :
- Exécuter via `exec(code, namespace)` avec un namespace contenant `bpy`,
  `math`, `mathutils`, `random`.
- Capturer stdout (redirection `io.StringIO`) pour le renvoyer — le LLM
  pourra faire des `print()` de diagnostic.
- En cas d'exception : `status: "error"` avec type, message et traceback
  complet (le Bloc 3 renverra ce traceback au LLM pour auto-correction).

**`get_screenshot`** :
- Rendu OpenGL du viewport (`bpy.ops.render.opengl` sur le viewport actif,
  ou rendu offscreen `gpu` si aucun viewport n'est disponible).
- Redimensionner pour que le plus grand côté ≤ `max_size` px (défaut 800),
  PNG, retourner en base64. Objectif : réponse < 500 Ko.
- Fichier temporaire dans le dossier temp de Blender, supprimé après lecture.

### 5. Timeouts et robustesse

- Timeout d'exécution d'une commande : **30 s** ; au-delà, répondre
  `status: "error"`, `type: "TimeoutError"`. (Note : on ne peut pas tuer
  un `exec` en cours sur le thread principal — documenter cette limite
  dans le README ; le vrai garde-fou anti-boucle-infinie viendra du Bloc 4.)
- Si le client se déconnecte : nettoyer et revenir en écoute (pas de crash,
  pas de port bloqué — `SO_REUSEADDR`).
- Toute exception dans le thread socket est loggée dans la console Blender,
  jamais propagée jusqu'à faire planter Blender.

### 6. Sécurité (garde-fou minimal côté add-on)

La validation complète est côté app (Bloc 4). L'add-on applique néanmoins
une liste noire de secours avant `exec` — rejet si le code contient
(recherche insensible à la casse, mot entier) :
`os.system`, `subprocess`, `shutil.rmtree`, `socket.`, `urllib`, `requests`,
`eval(`, `__import__`, `ctypes`, `sys.exit`, `exec(`.

Rejet = `status: "error"`, `type: "SecurityError"`, sans exécution.
⚠️ Documenter dans le code que c'est une défense en profondeur, PAS la
sandbox principale.

### 7. En-têtes et licence

- En-tête GPL-3.0 dans `studiopilot_bridge.py`.
- `bl_info` : name "StudioPilot Bridge", version (0,1,0), blender (4,2,0),
  category "System".
- README : mention claire que l'add-on est GPL et communique avec StudioPilot
  (propriétaire) uniquement par socket.

---

## [TESTS] — `test_client.py`

Client stdlib pur (socket + json + struct + base64), exécutable hors Blender :

1. `ping` → vérifie `pong: true` et version Blender.
2. `execute_code` : `bpy.ops.mesh.primitive_cube_add(location=(2,0,0))`
   → status ok, puis `get_scene_info` doit montrer le nouveau cube.
3. `execute_code` avec une erreur volontaire (`bpy.data.objects['Inexistant']`)
   → status error + traceback présent.
4. `execute_code` avec `import os; os.system('echo pwned')`
   → status error, type SecurityError.
5. `get_screenshot` → décode le base64, sauve `test_screenshot.png`,
   vérifie taille ≤ 800 px.
6. Test de charge léger : 20 `get_scene_info` d'affilée → aucune fuite,
   Blender reste réactif.

Mode d'emploi dans le README : ouvrir Blender → activer l'add-on →
démarrer le serveur (panneau N) → `python test_client.py` dans un terminal.

---

## [VÉRIFICATION] — critères d'acceptation du Bloc 1

- ✅ Add-on installable via le menu Add-ons de Blender 4.2, sans dépendance
- ✅ Les 6 tests de `test_client.py` passent sur Windows
- ✅ Blender reste fluide pendant que le serveur écoute (pas de freeze UI)
- ✅ Kill du client → serveur revient en écoute sans redémarrer Blender
- ✅ Port occupé au démarrage → message d'erreur clair dans le panneau, pas de crash
- ✅ Aucun bind hors 127.0.0.1 ; grep du code pour `0.0.0.0` = zéro résultat
- 🔄 À tester manuellement : screenshot correct avec 0 objet, 1 objet, 200 objets

---

## ORDRE DE TRAVAIL SUGGÉRÉ (sessions Claude Code)

1. Squelette add-on + panneau N + start/stop serveur (sans commandes) → tester l'UI
2. Boucle queue + `bpy.app.timers` + commande `ping` → tester le round-trip
3. `execute_code` + capture stdout + gestion erreurs
4. `get_scene_info`
5. `get_screenshot`
6. Liste noire sécurité + `test_client.py` complet + README

Chaque session se termine par la section ✅ Vérification et un résumé d'état copiable.
