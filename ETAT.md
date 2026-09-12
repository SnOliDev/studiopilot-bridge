# ÉTAT STUDIOPILOT — Initialisation

> Ce fichier est mis à jour par le skill `fin-de-session` à chaque fin de session.
> Il est la seule source de vérité entre deux sessions.
> Claude Code doit le lire EN PREMIER avant toute action.

---

## Bloc en cours : **Bloc 1 — Bridge Blender**
Spec complète : `BLOC1_bridge_blender.md`
Dépôt cible : `studiopilot-bridge/` (GPL, séparé de l'app)

---

## ✅ Fait (avant première session)
- [x] Architecture complète définie et validée par Olivier
- [x] CLAUDE.md rédigé — règles, blocs, autonomie, sécurité
- [x] BLOC1_bridge_blender.md rédigé — spec technique complète
- [x] 4 skills Claude Code créés (bpy-blender, verifier-studiopilot, audit-securite, fin-de-session)
- [x] Plan de monétisation esquissé (crédits prépayés, MonCash/NatCash/Stripe)
- [x] Feuille de route Blocs 1–9 validée
- [x] Décision : GitHub obligatoire dès le Bloc 1
- [x] Dépôt GitHub `studiopilot-bridge` déjà connecté (remote `origin` présent)
- [x] Branche `dev` créée (travail autonome, `main` réservé au merge manuel d'Olivier)
- [x] Session 1 Bloc 1 : squelette add-on + panneau N + start/stop serveur
- [x] Port par défaut aligné sur **9877** (CLAUDE.md) — 9876 occupé par
  BlenderMCP sur la machine de dev
- [x] Session 2 Bloc 1 : boucle queue + bpy.app.timers + commande ping
- [x] Correctif confirmé par Olivier : bpy.app.timers → opérateur modal
  (event_timer_add) pour un déclenchement fiable sans interaction Blender
- [x] Correctif confirmé par Olivier : refus propre (BusyError JSON) des
  connexions supplémentaires + abandon d'une connexion silencieuse après
  5 s (probe/health-check externe, probablement BlenderMCP)
- [x] Session 3 Bloc 1 : execute_code + stdout + gestion erreurs
- [x] Confirmé par Olivier en conditions réelles : `ping` fonctionne
  parfaitement (correctif opérateur modal validé)
- [x] Session 4 Bloc 1 : get_scene_info
- [x] Confirmé par Olivier en conditions réelles : `get_scene_info` lit
  correctement sa scène (3 objets, caméra, moteur EEVEE détectés)
- [x] Session 5 Bloc 1 : get_screenshot

## 🔄 Prochaines tâches (dans l'ordre)
- [ ] Session 6 Bloc 1 : liste noire sécurité + test_client.py + README

## ❌ Problèmes ouverts
- ⚠️ **Limite connue et acceptée (pas bloquante)** : une connexion qui envoie
  UN message invalide (garbage) puis reste ensuite silencieuse indéfiniment
  occupe le slot client sans être expulsée — le délai de grâce
  `_FIRST_MESSAGE_TIMEOUT_S` ne s'applique qu'avant le tout premier message
  reçu, pas après. Pas de protocole de heartbeat prévu par la spec Bloc 1 ;
  à surveiller si ça se reproduit en usage réel avec le vrai client
  StudioPilot (Bloc 2/3).

## ⚠️ Questions bloquantes (attendre Olivier)
Aucune pour l'instant.

## 🔒 Alertes sécurité
Aucune. Vérifié en Session 1, 2 et 3 : `grep "0.0.0.0"` et `grep "sk-ant"` sur
`studiopilot_bridge.py` = zéro résultat.
⚠️ Rappel : `execute_code` (Session 3) n'a **aucune** liste noire — c'est prévu
par la spec Bloc 1 (liste noire = Session 6, garde-fou de défense en
profondeur, la vraie validation est côté app au Bloc 4). Ne pas exposer ce
bridge à un réseau non fiable avant la Session 6.

## 📁 Fichiers modifiés ce jour
- `studiopilot_bridge.py` — Session 1 (panneau N, start/stop serveur,
  indicateur ⚫/🟢/🔵) + Session 2 (protocole JSON préfixé longueur,
  `queue.Queue` + commande `ping`) + Session 3 (`execute_code`, opérateur
  modal remplaçant `bpy.app.timers`, refus propre des connexions
  supplémentaires, abandon des connexions silencieuses, port par défaut 9877)
  + Session 4 (`get_scene_info`) + Session 5 (`get_screenshot`)
- `BLOC1_bridge_blender.md` — port 9876 → 9877 (cohérence avec CLAUDE.md)

## 🧪 Session 1 — ✅ Vérification
**Fichiers touchés** : `studiopilot_bridge.py` (nouveau).
**Effet attendu** : add-on installable dans Blender 4.2, panneau "StudioPilot"
dans la sidebar N du viewport 3D, bouton démarrer/arrêter le serveur socket
(bind 127.0.0.1 uniquement), indicateur d'état live, message d'erreur clair
si le port est occupé. Pas encore de protocole de commandes (ping/execute_code
arrivent en Session 2) — le thread socket accepte une connexion et la maintient
ouverte sans encore rien en faire.

**Ce qui a été testé** (headless, hors GUI) :
- `ast.parse` : syntaxe valide.
- Test fumée dans Blender 5.1 en mode `--background` (addon activé via
  `addon_utils.enable`, opérateurs start/stop appelés directement) :
  démarrage/arrêt du serveur, détection de connexion/déconnexion client
  (`client_connected` bascule bien à True/False), gestion du port occupé.
- 🐛 **Bug trouvé et corrigé pendant ce test** : `SO_REUSEADDR` sur Windows
  autorise un bind sur un port déjà occupé (sémantique différente de POSIX) —
  le critère d'acceptation "port occupé → erreur claire, pas de crash" échouait
  silencieusement. Remplacé par `SO_EXCLUSIVEADDRUSE` sous Windows
  (`sys.platform == "win32"`), `SO_REUSEADDR` conservé ailleurs.

**⚠️ Limite du test** : seul Blender **5.1** est installé dans cet
environnement, pas la cible officielle **4.2 LTS**. Le test fumée valide la
logique du serveur socket (thread, bind, queue de connexion) mais PAS :
le rendu réel du panneau N, les icônes/emojis dans l'UI, ni la compatibilité
API 4.2 spécifique. 🔄 **À tester manuellement par Olivier sur Blender 4.2 LTS** :
installation de l'add-on via Preferences → Add-ons → Install, apparence du
panneau, démarrage/arrêt via clic, option auto-start.

**Sécurité** : bind `127.0.0.1` uniquement, `SO_EXCLUSIVEADDRUSE`/`SO_REUSEADDR`
selon plateforme, aucune clé/secret, aucun `eval`/`exec` de code externe dans
ce squelette (le garde-fou liste noire arrive Session 6, `execute_code`
Session 3).

## 🧪 Session 2 — ✅ Vérification
**Fichiers touchés** : `studiopilot_bridge.py`, `BLOC1_bridge_blender.md` (port 9877).

**Effet attendu** : le serveur comprend maintenant le protocole complet —
JSON UTF-8 préfixé longueur (4 octets big-endian) — et la commande `ping`.
Architecture thread-safe respectée : le thread socket (`_handle_client`)
ne fait QUE lire/écrire des octets et empiler les requêtes dans
`_request_queue` ; seul `_process_queue`, appelé par `bpy.app.timers` sur
le thread principal, invoque du code lié à `bpy` (ici `bpy.app.version_string`).
Registre `_COMMAND_HANDLERS` extensible : ajouter une commande (Session 3+)
= une fonction + une entrée, sans toucher à la boucle.

**Ce qui a été testé** (headless, hors GUI, port 19877 pour ne pas entrer
en conflit avec le port 9877 déjà utilisé par le Blender GUI de la machine) :
- Round-trip `ping` complet (id echo, status ok, pong=True, blender_version,
  addon_version, error=None).
- 5 requêtes consécutives sur la même connexion.
- Commande inconnue → `status: error`, `type: UnknownCommand`, pas de crash.
- Requête malformée (champ `command` manquant) → `type: ProtocolError`,
  le serveur continue de répondre normalement ensuite.
- Déconnexion/reconnexion d'un second client → le serveur revient bien en
  écoute sans redémarrer.
- Arrêt propre du serveur après tous les échanges.

**⚠️ Limite du test découverte et contournée** : `bpy.app.timers` ne se
déclenche PAS tout seul en mode `--background` (limitation Blender connue,
confirmée par l'avertissement de l'add-on BlenderMCP déjà présent sur cette
machine : *"cannot start server in background mode - commands would never
execute"*). Le test pompe donc manuellement `_process_queue()` depuis le
thread principal — ce qui reproduit exactement ce que fait le timer réel en
Blender GUI (la cible du projet) — pendant qu'un thread séparé simule le
client StudioPilot. La logique métier est donc validée ; le déclenchement
automatique par `bpy.app.timers` en usage interactif reste 🔄 **à confirmer
manuellement en GUI** (Session 1 l'avait déjà signalé pour le panneau).

**Note d'environnement** : le PC de dev a un Blender 5.1 GUI déjà ouvert par
Olivier avec, semble-t-il, l'add-on Session 1 installé et le serveur démarré
sur le port 9877 (conforme à l'instruction reçue). Je n'ai pas touché à cette
session ni envoyé de trafic dessus — le code Session 2 n'y est pas encore
chargé (il faudra désactiver/réactiver l'add-on ou redémarrer Blender pour
charger le nouveau fichier).

**Sécurité** : toujours bind `127.0.0.1` uniquement, aucune clé/secret,
aucun `eval`/`exec` de code externe (la commande `execute_code` et sa liste
noire arrivent Session 3/6).

## 🧪 Session 3 — ✅ Vérification
**Fichiers touchés** : `studiopilot_bridge.py`.

**Effet attendu** :
1. **Commande `execute_code`** : `exec(code, namespace)` avec `bpy`, `math`,
   `mathutils`, `random` dans le namespace, stdout capturé via
   `contextlib.redirect_stdout(io.StringIO())`. Succès → `{"stdout":...,
   "executed": true}`. Exception → `status: error` avec type/message/
   traceback complet (géré par le wrapper générique déjà en place depuis
   la Session 2, aucun code spécifique nécessaire). **Aucune liste noire**
   à ce stade (prévue Session 6) — voir section Alertes sécurité.
2. **Correctif bpy.app.timers → opérateur modal** (`STUDIOPILOT_OT_modal_server`) :
   remplace le `bpy.app.timers.register(_process_queue, ...)` de la Session 2
   par un opérateur modal avec `window_manager.event_timer_add(0.05, ...)`,
   invoqué automatiquement au démarrage du serveur. `_process_queue()` et le
   `tag_redraw` du panneau sont maintenant appelés à chaque événement TIMER
   reçu par l'opérateur modal — mécanisme piloté par la boucle d'événements
   de la fenêtre, indépendant de l'activité de redraw/souris.
3. **Correctif connexions parasites** : `_accept_loop` accepte maintenant en
   continu (jamais bloqué par le client en cours, qui vit dans son propre
   thread `_serve_client`). Une connexion supplémentaire pendant qu'un
   client est actif reçoit immédiatement `{"status":"error","error":
   {"type":"BusyError",...}}` puis est fermée. Une connexion qui n'envoie
   aucun octet dans les `_FIRST_MESSAGE_TIMEOUT_S` (5 s) est abandonnée,
   libérant le slot pour un vrai client.

**Ce qui a été testé** (headless, hors GUI, port 19877) :
- `execute_code` : création d'un cube + `print()` → stdout capturé correctement.
- `execute_code` avec erreur volontaire (`bpy.data.objects['Inexistant']`)
  → `status: error`, `type: KeyError`, traceback présent (test 3 de la spec
  Bloc 1, validé).
- `execute_code` avec `params` vide → `code` par défaut `""`, no-op, status ok.
- Une 2ᵉ connexion pendant qu'une 1ʳᵉ est active reçoit bien `BusyError` et
  est fermée ; la 1ʳᵉ connexion reste active.
- Une connexion qui ne parle pas (aucun octet envoyé) est bien fermée par le
  serveur après ~5 s ; un nouveau client peut ensuite se connecter et obtenir
  une réponse `ping` normale — le slot est bien libéré.

**⚠️ Ce qui n'a PAS pu être testé (limitation du mode `--background`)** :
le déclenchement de l'opérateur modal lui-même. Les opérateurs modaux, comme
`bpy.app.timers`, dépendent de la boucle d'événements de la fenêtre Blender —
absente en mode headless. Le test a pompé `_process_queue()` manuellement
depuis le thread principal (= exactement ce que fait `modal()` à chaque
TIMER en usage réel) pour valider la logique métier indépendamment du
déclencheur. 🔄 **Confirmation manuelle nécessaire par Olivier** : redémarrer
le serveur dans le Blender GUI et vérifier qu'un `ping` externe reçoit
maintenant une réponse SANS bouger la souris ni interagir avec la fenêtre
(c'était précisément le bug signalé).

**Sécurité** : bind `127.0.0.1` uniquement, `grep "0.0.0.0"`/`grep "sk-ant"`
= zéro résultat. `execute_code` sans liste noire (Session 6, planifié ainsi
depuis le départ) — ne pas connecter d'app tierce non fiable à ce port avant
la Session 6.

## 🧪 Session 4 — ✅ Vérification
**Fichiers touchés** : `studiopilot_bridge.py`.

**Effet attendu** : commande `get_scene_info` complète conforme au schéma
§4 de la spec Bloc 1 — `scene_name`, `frame_current/start/end`, `objects`
(tronqué à `max_objects`, défaut 100), `object_count_total`, `truncated`,
`camera` (ou `null` si aucune caméra active), `lights`, `materials`
(dédupliqués, uniquement ceux référencés par les objets renvoyés), `render`
(engine/résolution/fps, fps calculé via `fps/fps_base` pour gérer les
fréquences fractionnaires type 29.97). Tous les floats arrondis à 4
décimales. `camera`/`lights` couvrent TOUTE la scène (pas limités par
`max_objects`) car peu nombreux et utiles même si `objects` est tronqué.
Matériaux lus en priorité via le node Principled BSDF (valeurs réellement
rendues), repli sur les propriétés "affichage viewport" du matériau si pas
de setup nodes (jamais de crash).

**Ce qui a été testé** (headless, hors GUI, port 19877) :
- Scène par défaut (Cube/Light/Camera) : schéma complet correct,
  `object_count_total == 3`, `truncated == False`, 1 lumière, caméra avec
  `lens_mm` numérique, matériau du Cube avec `base_color`/`metallic`/
  `roughness` corrects.
- Arrondi à 4 décimales vérifié (`1.234567891` → `1.2346`).
- `max_objects: 0` → `objects` vide, `truncated: True`, mais `camera` et
  `lights` toujours présents.
- 200 objets ajoutés → `object_count_total >= 203`, `objects` tronqué à 100
  (défaut), `truncated: True` ; avec `max_objects: 500` → plus de troncature.
- `max_objects` invalide (chaîne) → `status: error`, `type: TypeError`, pas
  de crash, le serveur répond normalement ensuite (`ping` final OK).

**🔄 À confirmer par toi** : contenu réel dans TA scène Blender (objets,
matériaux, éclairage de ton propre projet) — les tests ci-dessus utilisent
la scène factory-default, pas une scène de travail réelle.

**Sécurité** : bind `127.0.0.1` uniquement, `grep "0.0.0.0"`/`grep "sk-ant"`
= zéro résultat. Aucune donnée sensible dans `get_scene_info` (uniquement
des données géométriques/matériaux de la scène).

## 🧪 Session 5 — ✅ Vérification
**Fichiers touchés** : `studiopilot_bridge.py`.

**Effet attendu** : commande `get_screenshot` — capture le viewport actif
via `bpy.ops.render.opengl(view_context=True)` (context override sur la
première zone VIEW_3D/région WINDOW trouvée dans n'importe quelle fenêtre
ouverte), redimensionnée en ajustant `resolution_percentage` (jamais
`resolution_x/y`, pour ne pas altérer les réglages du projet) afin que le
plus grand côté soit ≤ `max_size` (défaut 800), encodée en PNG ou JPEG
(`params.format`) puis en base64. Réglages de rendu (filepath, format,
résolution %) toujours restaurés via `try/finally`, fichier temporaire
(`bpy.app.tempdir`) toujours supprimé après lecture — y compris en cas
d'erreur. Repli sur un rendu complet (`bpy.ops.render.render`) si aucun
viewport n'est utilisable (ex. mode `--background` — ne se produit jamais
en usage réel, l'app StudioPilot suppose toujours un Blender GUI ouvert).

**🐛 Deux bugs trouvés et corrigés pendant le test** :
1. `_find_view3d_context()` trouvait une zone VIEW_3D même en mode
   `--background` (Blender conserve la mise en page fenêtre/écran du
   fichier de démarrage même sans contexte OpenGL réel), ce qui faisait
   planter `bpy.ops.render.opengl` avec *"Cannot use OpenGL render in
   background mode"*. Corrigé en vérifiant `bpy.app.background` en premier.
2. Le nom de fichier réellement écrit par Blender pour un rendu still
   (`write_still=True`) ne correspondait pas à celui calculé par
   `render.frame_path()` (suffixe de numéro de frame ajouté à tort).
   Remplacé par une recherche `glob` sur le préfixe unique (UUID) du
   fichier temporaire — plus robuste, ne dépend d'aucune supposition sur
   le format de nom de Blender.
3. (mineur) `resolution_percentage` arrondi au plus proche pouvait dépasser
   `max_size` de quelques pixels (806 au lieu de ≤800) — remplacé par un
   arrondi par défaut (`floor`) pour garantir strictement la limite.

**Ce qui a été testé** (headless, hors GUI) : le rendu logiciel dans cet
environnement (pas de GPU) prend ~70-90 s par capture (chemin de repli
"rendu complet" — en usage réel avec viewport OpenGL + GPU, c'est quasi
instantané). Pour éviter le mismatch avec `_COMMAND_TIMEOUT_S` (30 s), la
fonction `_cmd_get_screenshot()` a été testée en appel direct (sans passer
par le socket) — le round-trip socket/queue/dispatch lui-même est déjà
prouvé par les Sessions 2-4 sur exactement le même chemin de code :
- Scène par défaut : PNG valide (magic number), 787×442 ≤ 800, fichier
  temp nettoyé, réglages de rendu restaurés.
- `max_size: 200, format: "jpeg"` : JPEG valide (magic bytes), 192×108 ≤ 200.
- `max_size` négatif → `TypeError` propre, pas de rendu déclenché.
- `format` invalide (`"tiff"`) → `ValueError` propre, pas de rendu déclenché.
- 200 objets ajoutés → capture réussie, pas de fuite de fichier temporaire.
- 0 objet (donc aucune caméra) → échoue proprement (`RuntimeError: Cannot
  render, no camera`), pas de crash Blender, réglages de rendu restaurés
  malgré l'échec (`try/finally` validé sur le chemin d'erreur aussi).

**⚠️ Ce qui n'a PAS pu être testé (limitation `--background`)** : le chemin
`bpy.ops.render.opengl` via un vrai viewport (nécessite une fenêtre Blender
réelle avec contexte OpenGL, comme l'opérateur modal de la Session 3).
🔄 **Confirmation manuelle nécessaire par Olivier** : demander un
`get_screenshot` via un client réel doit renvoyer quasi instantanément une
image du viewport actuel (pas un rendu caméra) — objectif < 500 Ko et
< 1 s en usage normal.

**Sécurité** : bind `127.0.0.1` uniquement, `grep "0.0.0.0"`/`grep "sk-ant"`
= zéro résultat. Aucune fuite de fichier temporaire constatée dans aucun cas
testé, y compris les chemins d'erreur.

## ▶️ Prochaine étape exacte
Session 6 Bloc 1 (dernière session du bloc) : liste noire de sécurité
côté add-on (défense en profondeur sur `execute_code` — `os.system`,
`subprocess`, `shutil.rmtree`, `socket.`, `urllib`, `requests`, `eval(`,
`__import__`, `ctypes`, `sys.exit`, `exec(`), `test_client.py` complet
(les 6 tests de la spec Bloc 1), et README (installation + licence GPL).
Critère de sortie du Bloc 1 : les 6 tests de `test_client.py` passent sur
Windows + Blender 4.2.

## 🙋 Pour toi, Olivier
Rien de bloquant. Si tu veux valider Session 5 en conditions réelles :
réinstalle `studiopilot_bridge.py` mis à jour, redémarre le serveur, et
demande un `get_screenshot` (je peux t'écrire un script comme pour les
sessions précédentes) — ça doit répondre vite avec une image de ton
viewport actuel, pas un rendu caméra complet.

---

## Contexte technique rappel
- Blender 4.2 LTS, Windows
- Socket TCP 127.0.0.1:9877, préfixe longueur 4 octets big-endian
- bpy NON thread-safe → queue.Queue + opérateur modal (event_timer_add)
  obligatoires — bpy.app.timers abandonné (Session 3, peu fiable sans
  interaction Blender)
- Branches Git : `dev` (travail Claude Code) / `main` (merge Olivier uniquement)
- Port 9877 sur ce PC dev (9876 occupé par BlenderMCP)