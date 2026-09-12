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

## 🔄 Prochaines tâches (dans l'ordre)
- [ ] Session 3 Bloc 1 : execute_code + stdout + gestion erreurs
- [ ] Session 4 Bloc 1 : get_scene_info
- [ ] Session 5 Bloc 1 : get_screenshot
- [ ] Session 6 Bloc 1 : liste noire sécurité + test_client.py + README

## ❌ Problèmes ouverts
Aucun pour l'instant.

## ⚠️ Questions bloquantes (attendre Olivier)
Aucune pour l'instant.

## 🔒 Alertes sécurité
Aucune. Vérifié en Session 1 et 2 : `grep "0.0.0.0"` et `grep "sk-ant"` sur
`studiopilot_bridge.py` = zéro résultat.

## 📁 Fichiers modifiés ce jour
- `studiopilot_bridge.py` — Session 1 (panneau N, start/stop serveur,
  indicateur ⚫/🟢/🔵) + Session 2 (protocole JSON préfixé longueur,
  `queue.Queue` + `bpy.app.timers`, commande `ping`, port par défaut 9877)
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

## ▶️ Prochaine étape exacte
Session 3 Bloc 1 : commande `execute_code` — `exec(code, namespace)` avec
`bpy`/`math`/`mathutils`/`random`, capture stdout via `io.StringIO`, et en
cas d'exception : `status: error` avec type/message/traceback complet
(prépare l'auto-correction LLM du Bloc 3).

## 🙋 Pour toi, Olivier
Pour valider Session 2 en conditions réelles sur ta machine : dans le
Blender déjà ouvert, désactive puis réactive l'add-on StudioPilot Bridge
dans Preferences → Add-ons (ou redémarre Blender) après avoir réinstallé
`studiopilot_bridge.py` mis à jour, redémarre le serveur (port 9877), puis
dis-moi si tu veux que je lance un vrai `ping` dessus depuis un terminal.

---

## Contexte technique rappel
- Blender 4.2 LTS, Windows
- Socket TCP 127.0.0.1:9876, préfixe longueur 4 octets big-endian
- bpy NON thread-safe → queue.Queue + bpy.app.timers obligatoires
- Branches Git : `dev` (travail Claude Code) / `main` (merge Olivier uniquement)
- Port 9877 sur ce PC dev (9876 occupé par BlenderMCP)