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

## 🔄 Prochaines tâches (dans l'ordre)
- [ ] Créer le dépôt GitHub `studiopilot-bridge`
- [ ] Session 1 Bloc 1 : squelette add-on + panneau N + start/stop serveur
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
Aucune.

## 📁 Fichiers créés ce jour
- `CLAUDE.md` — instructions permanentes Claude Code
- `ETAT.md` — ce fichier
- `BLOC1_bridge_blender.md` — spec Bloc 1
- `.claude/skills/bpy-blender/SKILL.md`
- `.claude/skills/verifier-studiopilot/SKILL.md`
- `.claude/skills/audit-securite/SKILL.md`
- `.claude/skills/fin-de-session/SKILL.md`

## ▶️ Prochaine étape exacte
Créer le dépôt GitHub `studiopilot-bridge` (public, licence GPL-3.0),
puis ouvrir Claude Code et dire :
**"Lis ETAT.md et BLOC1_bridge_blender.md, puis commence la Session 1."**

---

## Contexte technique rappel
- Blender 4.2 LTS, Windows
- Socket TCP 127.0.0.1:9876, préfixe longueur 4 octets big-endian
- bpy NON thread-safe → queue.Queue + bpy.app.timers obligatoires
- Branches Git : `dev` (travail Claude Code) / `main` (merge Olivier uniquement)
