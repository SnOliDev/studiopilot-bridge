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

## 🔄 Prochaines tâches (dans l'ordre)
- [ ] Session 2 Bloc 1 : boucle queue + bpy.app.timers + commande ping
- [ ] Session 3 Bloc 1 : execute_code + stdout + gestion erreurs
- [ ] Session 4 Bloc 1 : get_scene_info
- [ ] Session 5 Bloc 1 : get_screenshot
- [ ] Session 6 Bloc 1 : liste noire sécurité + test_client.py + README

## ❌ Problèmes ouverts
Aucun pour l'instant.

## ⚠️ Questions bloquantes (attendre Olivier)
Aucune pour l'instant.

## 🔒 Alertes sécurité
Aucune. Vérifié en Session 1 : `grep "0.0.0.0"` et `grep "sk-ant"` sur
`studiopilot_bridge.py` = zéro résultat.

## 📁 Fichiers créés ce jour
- `studiopilot_bridge.py` — add-on Blender, squelette Session 1 (panneau N,
  start/stop serveur socket, indicateur d'état ⚫/🟢/🔵, préférences port +
  auto-start)

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

## ▶️ Prochaine étape exacte
Session 2 Bloc 1 : boucle `queue.Queue` + `bpy.app.timers` pour exécuter les
commandes sur le thread principal, implémenter la commande `ping`, tester le
round-trip complet (client TCP → réponse JSON préfixée longueur).

---

## Contexte technique rappel
- Blender 4.2 LTS, Windows
- Socket TCP 127.0.0.1:9876, préfixe longueur 4 octets big-endian
- bpy NON thread-safe → queue.Queue + bpy.app.timers obligatoires
- Branches Git : `dev` (travail Claude Code) / `main` (merge Olivier uniquement)
- Port 9877 sur ce PC dev (9876 occupé par BlenderMCP)