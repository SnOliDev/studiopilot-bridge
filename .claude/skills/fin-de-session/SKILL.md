---
name: fin-de-session
description: Produire un résumé d'état copiable en fin de session StudioPilot. Utiliser quand l'utilisateur dit "on arrête", "résumé", "fin de session", ou avant une coupure de connexion.
disable-model-invocation: true
---

# Résumé d'état de session — StudioPilot

Produire un bloc copiable, format exact :

```
## ÉTAT STUDIOPILOT — [date]
### Bloc en cours : [n° et nom]
### ✅ Fait cette session
- ...
### 🔄 En cours / à tester
- ...
### ❌ Problèmes ouverts (cause probable)
- ...
### 📁 Fichiers modifiés
- ...
### ▶️ Prochaine étape exacte
[une phrase actionnable : "Ouvrir X, faire Y"]
```

Règles :
- Assez complet pour reprendre dans une session VIERGE sans autre contexte.
- Mentionner l'état de Blender requis (add-on actif ? serveur démarré ?).
- Proposer un message de commit si des changements ne sont pas committés.
- Rappeler `git push` si la connexion le permet (connectivité intermittente).
