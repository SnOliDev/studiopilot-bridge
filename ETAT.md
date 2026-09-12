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

## 🔄 Prochaines tâches (dans l'ordre)
- [ ] Session 4 Bloc 1 : get_scene_info
- [ ] Session 5 Bloc 1 : get_screenshot
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

## ▶️ Prochaine étape exacte
Session 4 Bloc 1 : commande `get_scene_info` (objets, matériaux, caméra,
lumières, arrondi à 4 décimales, troncature si > `max_objects`).

## 🙋 Pour toi, Olivier
Deux choses à confirmer sur ta machine (Blender GUI déjà ouvert, port 9877) :
1. Réinstalle `studiopilot_bridge.py` mis à jour (désactive/réactive l'add-on
   ou redémarre Blender), redémarre le serveur, puis lance un `ping` externe
   **sans toucher à la souris/fenêtre Blender** — ça doit répondre maintenant
   (c'est le bug modal/timer corrigé).
2. Vérifie si la connexion automatique mystère (probablement BlenderMCP) se
   reproduit — elle devrait maintenant disparaître d'elle-même après ~5 s
   sans bloquer le vrai client, et une tentative de connexion StudioPilot
   pendant qu'un autre client est actif doit recevoir une erreur claire
   plutôt que de rester bloquée.

Dis-moi si tu veux que je lance un test `ping`/`execute_code` réel depuis un
terminal une fois l'add-on rechargé.

---

## Contexte technique rappel
- Blender 4.2 LTS, Windows
- Socket TCP 127.0.0.1:9877, préfixe longueur 4 octets big-endian
- bpy NON thread-safe → queue.Queue + opérateur modal (event_timer_add)
  obligatoires — bpy.app.timers abandonné (Session 3, peu fiable sans
  interaction Blender)
- Branches Git : `dev` (travail Claude Code) / `main` (merge Olivier uniquement)
- Port 9877 sur ce PC dev (9876 occupé par BlenderMCP)