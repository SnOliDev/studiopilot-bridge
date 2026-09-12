---
name: audit-securite
description: Audit de sécurité StudioPilot. Utiliser avant tout commit touchant la clé API, le socket, la sandbox, ou l'exécution de code généré par le LLM.
allowed-tools: Read, Grep, Glob
---

# Audit sécurité StudioPilot (lecture seule)

Vérifier point par point, rapporter ✅/❌/⚠️ pour chacun :

## Clé API
- Aucune clé (`sk-ant`, `ANTHROPIC_API_KEY=` avec valeur) en dur dans le code,
  les configs, les tests, ou les fichiers d'exemple.
- La clé vient d'une variable d'environnement ou du keychain OS,
  saisie au premier lancement. Jamais loggée, jamais dans localStorage en clair.

## Socket Blender
- Bind exclusivement 127.0.0.1 (grep `0.0.0.0` = zéro résultat).
- Un seul client accepté ; les autres refusés proprement.
- Aucune donnée du socket interprétée côté app avec eval/exec.

## Code généré par le LLM
- Validation liste noire AVANT envoi au socket : os.system, subprocess,
  shutil.rmtree, socket., urllib, requests, eval(, __import__, ctypes,
  sys.exit, exec(, et open() en écriture hors du dossier projet.
- Le code LLM ne s'exécute QUE dans Blender via le socket, jamais côté app.

## Divers
- Aucune route réseau exposée non documentée (grep listen/bind/serve).
- Dépendances : signaler tout paquet inconnu ajouté depuis le dernier audit.

## Rapport
Terminer par : liste des ❌ (bloquants, à corriger avant commit),
puis ⚠️ (à discuter), puis ✅. Si un ❌ existe : NE PAS committer.
