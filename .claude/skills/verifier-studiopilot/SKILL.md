---
name: verifier-studiopilot
description: Validation complète du projet StudioPilot avant de clore un bloc ou une session. Lancer quand l'utilisateur demande de vérifier, valider, ou termine un bloc de travail.
disable-model-invocation: false
---

# Validation StudioPilot

Exécuter dans l'ordre, sans rien modifier :

1. **Tests bridge** : si Blender tourne avec l'add-on actif,
   lancer `python test_client.py` et noter chaque test ✅/❌.
   Sinon, le signaler comme 🔄 À tester manuellement.
2. **Frontend** : `npm run build` (ou `cargo tauri build --debug` si demandé)
   → noter les erreurs de compilation.
3. **Sécurité rapide** (voir aussi le skill audit-securite) :
   - grep clé API en dur (`sk-ant`) → doit rendre zéro résultat
   - grep `0.0.0.0` → zéro résultat
   - grep `eval(` côté app → zéro résultat
4. **Résumé** au format du projet :
   - ✅ ce qui passe
   - ❌ ce qui casse (cause racine probable en premier)
   - 🔄 ce qui reste à tester manuellement
   - 📁 fichiers touchés depuis le dernier commit (`git status`)

Si tout est vert : le dire en une ligne et proposer un message de commit.
Ne jamais corriger pendant la validation — lister d'abord, corriger après accord.
