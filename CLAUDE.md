# CLAUDE.md — StudioPilot (FaciliX)
> Fichier de référence lu par Claude Code à chaque session.
> Toute décision d'architecture non couverte ici → STOP et documenter dans ETAT.md avant de coder.

---

## IDENTITÉ DU PROJET

**Produit** : StudioPilot — studio de création 3D et audio piloté en langage naturel.
**Fondateur** : Olivier (Saint-Marc, Haïti) — non-technique, décideur final sur le produit.
**Cible** : PME et créateurs francophones/caribéens sans expertise 3D.
**Gamme** : ClassPilot / ShopPilot / TradePilot / StudioPilot (FaciliX).
**Référence de complexité** : SchoolPilot = 1 semaine. MVP StudioPilot (Blocs 1–3) = 2–2,5 semaines.

---

## ARCHITECTURE — NE PAS DÉVIER SANS DISCUSSION

```
[Utilisateur]
     ↓ langage naturel
[StudioPilot App — Tauri + React] ← propriétaire, commercial
     ↓ JSON via socket TCP 127.0.0.1:9877
[Add-on studiopilot_bridge.py — Blender] ← GPL, dépôt séparé
     ↓ bpy (thread principal uniquement)
[Blender 4.2 LTS — officiel, non modifié]
     +
[MeloTTS — service FastAPI local :8000]
     +
[Whisper — sous-titres locaux]
     +
[FFmpeg — assemblage vidéo final]
```

**Couche provider (Bloc 3)** : interface générique `sendMessage(messages, tools)`
- Implémentation 1 : Anthropic API (défaut, claude-sonnet-4-6)
- Implémentation 2 : LLM local via Ollama (futur, offline total)
- Implémentation 3 : Veo 3 Google (futur, provider vidéo — indisponible en Haïti
  sans VPN, option activable par l'utilisateur uniquement)
- Ajouter un provider = un nouveau fichier, zéro réécriture.

**Frontend** : App.jsx unique (monolithique), Tauri léger, faible RAM.
**Stockage** : localStorage / SQLite local. Aucun cloud obligatoire.
**Langue interface** : FR d'abord, puis EN, HT, ES.

---

## RÈGLES DE CODE (obligatoires)

1. **Avant tout code** : résumer ce qui est touché et ce qui ne l'est pas.
2. **Après chaque bloc** : section ✅ Vérification (fichiers affectés, effet attendu, quoi tester).
3. **Ambiguïté → écrire dans ETAT.md**, section "Questions bloquantes", et STOP.
   Ne jamais inventer une décision de produit. Ne jamais supposer l'intention d'Olivier.
4. **Jamais de réécriture complète** d'un fichier pour un changement partiel — diffs ciblés.
5. **Bug multi-origine** : lister les causes par probabilité, cause racine d'abord.
6. **Structure blocs complexes** : [OBJECTIF]→[FICHIERS]→[CODE]→[TESTS]→[VÉRIFICATION].
7. **Emojis** : ✅ OK  ⚠️ Attention  ❌ Problème  🔄 À tester  📁 Fichier.
8. **Fin de session** : invoquer le skill `/fin-de-session` et mettre ETAT.md à jour.
9. **Tokens** : compter et loguer les tokens consommés par requête LLM dès le Bloc 3.
   Format : `{"input": N, "output": N, "cached": N, "cost_usd": X}` dans le log local.

---

## SÉCURITÉ (non négociable)

- **Clé API Anthropic** : JAMAIS en dur. Variable d'environnement ou keychain OS.
  `grep -r "sk-ant"` doit rendre zéro résultat avant tout commit.
- **Socket Blender** : bind 127.0.0.1:9877 UNIQUEMENT. `grep "0.0.0.0"` = zéro résultat.
- **Code LLM** : exécuté UNIQUEMENT dans Blender via socket, jamais `eval()` côté app.
- **Liste noire sandbox** (côté app, Bloc 4, ET côté add-on en défense profondeur) :
  `os.system`, `subprocess`, `shutil.rmtree`, `socket.`, `urllib`, `requests`,
  `eval(`, `__import__`, `ctypes`, `sys.exit`, `exec(`, `open()` hors dossier projet.
- **Hook PreToolUse** (fichier `.claude/hooks/`, pas juste un skill — une porte physique) :
  Bloquer toute commande Bash contenant `rm -rf`, `git push --force`,
  ou touchant `.env`, `sk-ant`, fichiers de clé. Exit code 2 = blocage immédiat.
- Signaler toute route/clé exposée dans ETAT.md section "Alertes sécurité" immédiatement.

---

## LICENCES

- Add-on Blender = GPL-3.0 (dépôt public `studiopilot-bridge/`).
- App StudioPilot = propriétaire (socket = pas un dérivé GPL).
- MeloTTS = MIT (usage commercial OK).
- Whisper OpenAI = MIT (usage commercial OK).
- FFmpeg = LGPL (usage commercial OK avec librairies dynamiques).
- Poly Haven assets = CC0 (usage commercial OK, aucune attribution requise).
- Veo 3 = API Google (CGU à vérifier avant activation commerciale).
- Ne jamais copier de code source Blender dans l'app.
- Ne jamais embarquer Blender dans l'installeur — l'utilisateur l'installe depuis blender.org.

---

## BLOCS DE DÉVELOPPEMENT

### Bloc 1 — Bridge Blender ← ACTIF
Fichier de spec complet : `BLOC1_bridge_blender.md`
Dépôt séparé : `studiopilot-bridge/`
Contrainte critique : bpy NON thread-safe → queue.Queue + bpy.app.timers obligatoires.
Sessions : 6 sessions ordonnées définies dans BLOC1_bridge_blender.md.
Critère de sortie : les 6 tests de test_client.py passent sur Windows + Blender 4.2.

### Bloc 2 — Shell Tauri + Chat UI
- App.jsx monolithique, Tauri (léger, faible RAM).
- Gestion clé API : saisie premier lancement, stockage keychain OS, jamais localStorage.
- Upload d'image dans le chat (pour la vision LLM, Bloc 3).
- Indicateur d'état du bridge : ⚫ arrêté / 🟢 connecté.

### Bloc 3 — Boucle LLM + Couche Provider
- Contexte scène Blender envoyé à chaque requête (get_scene_info).
- Prompt caching Anthropic activé (réduire les coûts).
- Réponse LLM → extraction du code bpy → validation sandbox → envoi socket.
- En cas d'erreur d'exécution : traceback renvoyé au LLM pour auto-correction (max 3 tentatives).
- Image en entrée : encodage base64, envoi dans le message vision Claude.
- Comptage tokens logué localement à chaque requête.
- Provider abstrait : Anthropic par défaut, extensible sans réécriture.

### Bloc 4 — Sandbox Sécurité + Hook
- Validation liste noire côté app AVANT envoi au socket.
- Hook PreToolUse Claude Code (fichier de config, pas skill).
- Tests d'attaque obligatoires (os.system, subprocess, open() hors projet).

### Bloc 5 — Bibliothèque Guidée
- 20 commandes types cliquables (logos 3D, éclairage produit, animations simples).
- Scripts pré-écrits validés : ZÉRO appel LLM, ZÉRO latence réseau → offline-first.
- Mode "coller un script" : validation sandbox → exécution, même chemin que le LLM.
- Intégration Poly Haven : téléchargement assets CC0 à la demande (textures, HDRIs).
- Bibliothèque d'avatars de base libres de droits, personnalisables par chat.

### Bloc 6 — MeloTTS + Whisper
- Service FastAPI local :8000, exécution CPU.
- Langues : FR, EN, ES (HT dès que modèle disponible — priorité marché).
- Whisper local (offline) pour sous-titres automatiques.
- Pipeline : texte → MeloTTS → audio → Whisper → fichier SRT.

### Bloc 7 — FFmpeg Export
- Assemblage : rendu Blender + audio MeloTTS + sous-titres SRT → MP4.
- Preset réseaux sociaux : 9:16 (Reels/TikTok), 1:1 (Instagram), 16:9 (YouTube).

### Bloc 8 — Packaging Windows
- Installeur NSIS ou WiX via Tauri.
- Installeur vérifie la présence de Blender et guide l'installation si absent.
- Copie automatique de l'add-on dans le dossier add-ons Blender.
- Onboarding : 3 étapes max, aucune mention de Python ou de socket.

### Bloc 9 — Providers Avancés (post-MVP)
- Veo 3 (Google) : option activable, message clair si non disponible géographiquement.
- Image-to-3D : Tencent Hunyuan3D (open source, local GPU) ou API externe (cloud).
- LLM local : Ollama + Llama/Mistral pour offline complet.

---

## WORKFLOW AUTONOME

**ETAT.md** : fichier à la racine, mis à jour à chaque fin de session.
Format imposé par le skill `fin-de-session`. C'est la mémoire inter-sessions.

**Mode autonome** (sessions sans Olivier) :
1. Lire ETAT.md → identifier la prochaine tâche non cochée.
2. Lire le fichier de spec du bloc actif.
3. Coder, tester, committer sur branche `dev`.
4. Mettre ETAT.md à jour.
5. STOP si : ambiguïté de produit, décision de sécurité, ou 3 erreurs consécutives non résolues.
   → Écrire la question dans ETAT.md section "Questions bloquantes" et attendre Olivier.

**Branches Git** :
- `main` : merge manuel par Olivier uniquement.
- `dev` : travail autonome de Claude Code.
- `bloc-X-nom` : branches par bloc si nécessaire.

**GitHub** : obligatoire dès le Bloc 1 (pont entre sessions mobiles et PC maison).
Push systématique en fin de session — connectivité intermittente oblige.

---

## MONÉTISATION (contexte pour les décisions techniques)

- Modèle cible : crédits prépayés (compatible MonCash/NatCash) + licence one-time.
- Stripe pour l'international et la diaspora.
- Freemium : bibliothèque guidée gratuite (Bloc 5, offline, zéro coût API).
  Requêtes LLM libres = payantes après quota.
- Licence agence : tarif B2B pour production en volume.
- **Implication technique** : le comptage de tokens (Bloc 3) est obligatoire
  pour calculer le coût réel par génération et fixer les prix.

---

## CE QUE CLAUDE CODE NE DÉCIDE PAS SEUL

- Choix de prix et modèle de monétisation.
- Sélection des 20 commandes guidées du Bloc 5 (Olivier connaît sa cible).
- Validation "est-ce assez bon pour l'utilisateur final ?" — test utilisateur humain.
- Toute décision touchant la clé API, le paiement, ou la licence.
- Merge de `dev` vers `main`.

---

## SKILLS DISPONIBLES (.claude/skills/)

- `bpy-blender` : pièges API Blender 4.2, thread-safety, protocole socket.
- `verifier-studiopilot` : validation complète avant clôture de bloc.
- `audit-securite` : lecture seule, vérifie clé API / socket / sandbox.
- `fin-de-session` : produit le résumé ETAT.md copiable, propose le commit.
