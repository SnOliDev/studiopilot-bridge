# StudioPilot Bridge

Add-on Blender **GPL-3.0** qui expose un serveur socket TCP local
(`127.0.0.1` uniquement) permettant à l'application **StudioPilot**
(FaciliX — logiciel propriétaire, dépôt séparé) de piloter Blender :
exécuter du code, lire l'état de la scène, capturer le viewport.

⚠️ **Cet add-on ne communique avec StudioPilot QUE par socket local.** Il
ne contient, n'embarque et ne dépend d'aucun code de l'application
StudioPilot. L'inverse est également vrai : StudioPilot est un logiciel
propriétaire distinct qui se contente d'envoyer des requêtes JSON à ce
bridge — la licence GPL de cet add-on ne s'applique pas à StudioPilot.

## Installation (3 étapes)

1. **Installer Blender 4.2 LTS** depuis [blender.org](https://www.blender.org/download/)
   si ce n'est pas déjà fait (cet add-on ne l'installe pas pour vous).
2. Dans Blender : **Edit > Preferences > Add-ons > Install...**, puis
   sélectionner le fichier `studiopilot_bridge.py` de ce dépôt. Cocher la
   case pour activer l'add-on une fois installé.
3. Ouvrir la sidebar du viewport 3D (touche **N**), onglet **StudioPilot**,
   et cliquer **Démarrer le serveur**. L'indicateur passe à 🟢 (en écoute).

Une fois qu'un client (StudioPilot ou `test_client.py`) se connecte,
l'indicateur passe à 🔵.

### Préférences de l'add-on

Dans **Edit > Preferences > Add-ons > StudioPilot Bridge** :

- **Port** : port TCP local du serveur (défaut `9877`). À changer si ce
  port est déjà utilisé par un autre outil sur votre machine (par exemple
  un autre add-on de type MCP).
- **Démarrer automatiquement à l'ouverture de Blender** : démarre le
  serveur dès que Blender s'ouvre, sans avoir à cliquer sur le panneau.

## Tester le bridge

Un client de test en Python standard (aucune dépendance externe) est
fourni : `test_client.py`.

```bash
# 1. Ouvrir Blender, activer l'add-on, démarrer le serveur (voir ci-dessus)
# 2. Dans un terminal :
python test_client.py
# ou, si le port a été changé dans les préférences :
python test_client.py --host 127.0.0.1 --port 9877
```

Il exécute 6 tests (ping, exécution de code, gestion d'erreur, liste noire
de sécurité, capture d'écran, charge légère) et affiche ✅/❌ pour chacun.

## Protocole

JSON UTF-8, chaque message précédé de sa taille sur 4 octets big-endian
(uint32) — plus robuste qu'un délimiteur ligne pour les captures d'écran
volumineuses encodées en base64.

**Requête** : `{ "id": "<uuid>", "command": "...", "params": { ... } }`
**Réponse** : `{ "id": "<même-uuid>", "status": "ok" | "error", "result": {...}, "error": null | {"type", "message", "traceback"} }`

| Commande | Description |
|---|---|
| `ping` | Vérifie que le bridge répond ; renvoie les versions Blender/add-on |
| `execute_code` | Exécute du code Python `bpy` et renvoie le stdout capturé |
| `get_scene_info` | État compact de la scène (objets, caméra, lumières, matériaux) |
| `get_screenshot` | Capture le viewport actif, redimensionnée, en base64 |

## Sécurité — ce que ce bridge protège, et ce qu'il NE protège PAS

- Le serveur se lie **uniquement** à `127.0.0.1` — jamais accessible
  depuis le réseau local ou Internet.
- Un seul client à la fois ; toute connexion supplémentaire pendant qu'un
  client est actif reçoit un refus JSON propre (`BusyError`), et une
  connexion qui n'envoie jamais de requête est abandonnée après quelques
  secondes.
- `execute_code` applique une **liste noire de secours** (recherche de
  motifs comme `os.system`, `subprocess`, `eval(`, `socket.`, etc.) avant
  d'exécuter le code reçu.
  **⚠️ Cette liste noire est une défense en profondeur, PAS une sandbox.**
  Elle bloque les tentatives les plus évidentes mais peut être contournée
  par du code suffisamment habile (imports détournés, obfuscation...). La
  validation réelle du code généré par l'IA se fait **côté application
  StudioPilot**, avant même que la requête n'atteigne ce bridge.
- **Une commande qui bloque le thread principal de Blender ne peut pas
  être annulée.** Le timeout de 30 secondes côté serveur fait juste
  répondre une erreur `TimeoutError` au client — il n'interrompt PAS
  l'exécution en cours dans Blender (impossible avec l'API Python de
  Blender). Une boucle infinie envoyée via `execute_code` gèlera donc
  l'interface de Blender jusqu'à ce qu'elle se termine d'elle-même (ou que
  Blender soit fermé manuellement). Le garde-fou anti-boucle-infinie
  complet est prévu côté application (Bloc 4 de StudioPilot), pas dans cet
  add-on.
- N'installez et ne démarrez ce bridge que si vous faites confiance à
  l'application qui s'y connecte.

## Licences

- Cet add-on (`studiopilot_bridge.py`, `test_client.py`) : **GPL-3.0**,
  voir `LICENSE`.
- L'application StudioPilot qui s'y connecte est un logiciel **propriétaire
  distinct** — la communication se fait uniquement par socket TCP local,
  ce qui n'en fait pas une œuvre dérivée au sens de la GPL.

## Limites connues (Bloc 1 — bridge seul, hors app StudioPilot)

- Cible testée : Windows + Blender 4.2 LTS. D'autres plateformes
  (macOS/Linux) devraient fonctionner (aucune dépendance spécifique à
  Windows en dehors du choix `SO_EXCLUSIVEADDRUSE`/`SO_REUSEADDR`) mais
  n'ont pas été testées.
- `get_screenshot` sans viewport ouvert (cas rare, ne se produit pas en
  usage normal avec l'app StudioPilot) se rabat sur un rendu complet
  depuis la caméra active, plus lent qu'une vraie capture de viewport.
