---
name: bpy-blender
description: Conventions et pièges de l'API Python Blender (bpy) 4.2 LTS pour le bridge StudioPilot. Utiliser dès qu'on écrit, corrige ou révise du code bpy, l'add-on socket, ou du code généré par le LLM destiné à Blender.
---

# Règles bpy / Blender 4.2 — StudioPilot

## Pièges critiques (causes de crash n°1)
1. **bpy n'est PAS thread-safe.** Jamais d'appel bpy depuis le thread socket.
   Toujours : queue.Queue → callback `bpy.app.timers.register()` → exécution
   sur le thread principal → queue de réponse.
2. **Contexte requis.** Beaucoup d'opérateurs (`bpy.ops.*`) exigent un contexte
   (viewport actif, objet sélectionné). Préférer l'API data (`bpy.data.*`)
   aux opérateurs quand c'est possible — plus fiable hors interaction.
3. **Blender 4.2** : le moteur EEVEE s'appelle `BLENDER_EEVEE_NEXT`.
   Vérifier les noms d'API contre la doc 4.2, pas 2.8/3.x (beaucoup
   d'exemples en ligne sont obsolètes).
4. **Références invalides** : après suppression d'un objet, toute référence
   Python devient invalide (crash). Toujours re-résoudre par nom :
   `bpy.data.objects.get("Nom")` et tester None.

## Patterns préférés
- Créer un objet : `bpy.data.meshes.new()` + `bpy.data.objects.new()` +
  `collection.objects.link()` plutôt que `bpy.ops.mesh.primitive_*` quand
  le contrôle fin compte. Pour les primitives simples, `bpy.ops` est OK.
- Matériaux : toujours `use_nodes = True`, modifier via
  `material.node_tree.nodes["Principled BSDF"].inputs[...]`.
- Animation : `obj.keyframe_insert(data_path="location", frame=N)`.
- Toujours arrondir les floats à 4 décimales dans les sorties JSON.

## Protocole socket StudioPilot (rappel)
- JSON UTF-8, préfixe longueur 4 octets big-endian (uint32).
- Commandes : ping, execute_code, get_scene_info, get_screenshot.
- Réponses : `{id, status: "ok"|"error", result, error:{type,message,traceback}}`.
- Bind 127.0.0.1:9876 UNIQUEMENT. Grep "0.0.0.0" doit rendre zéro résultat.

## Quand le code bpy échoue
1. Lire le traceback COMPLET renvoyé par le bridge.
2. Vérifier version d'API (4.2) avant de supposer un bug logique.
3. Vérifier le contexte (mode objet vs édition, sélection).
4. Ne jamais "réessayer au hasard" — identifier la cause racine d'abord.
