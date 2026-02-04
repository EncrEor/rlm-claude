## RLM - MÉMOIRE PERSISTANTE (v0.10.0)

### Philosophie

L'utilisateur décide quand chunker. Le système sauvegarde automatiquement avant /compact.

### Début de session (obligatoire)

```python
# 1. Charger les règles universelles
rlm_recall(importance="critical")

# 2. Si travail sur un sujet spécifique, charger le contexte
rlm_recall(query="le_sujet")

# 3. Status mémoire
rlm_status()
```

### Quand chunker (réflexe Claude)

**Chunk proactivement quand :**
- Décision importante prise
- Tâche terminée avec succès
- Insight ou règle découverte
- Changement de sujet majeur
- Bug corrigé (documenter la cause)

**Chunk sur instruction utilisateur :**
- "garde ça en mémoire"
- "chunk cette discussion"
- "rlm_remember cette décision"

### Types de chunks (chunk_type)

| Type | Usage |
|------|-------|
| `session` | Log de session (défaut) |
| `snapshot` | État d'un sujet à l'instant T |
| `debug` | Bug + solution |
| `insight` | Redirigé vers `rlm_remember()` |

### Niveaux d'importance (insights)

| Importance | Quand l'utiliser |
|------------|-----------------|
| `critical` | Règle universelle (s'applique quel que soit le sujet) |
| `high` | Règle liée à un sujet spécifique |
| `medium` | Info utile, pas bloquante |

**Test** : "S'applique même si on parle d'un tout autre sujet ?" → `critical`

### Sauvegarde automatique

Le hook PreCompact crée un chunk minimal avant chaque /compact.
Après le compact, tu peux lire ce chunk et l'enrichir si nécessaire.

### Cette mémoire est LA TIENNE

Tu n'as pas besoin de demander permission pour :
- Chunker l'historique
- Sauvegarder des insights
- Consulter ta mémoire

C'est ton outil personnel de gestion de contexte.

### Commandes utiles

```python
# Sauvegarder un insight universel
rlm_remember("contenu", category="decision", importance="critical", tags="universal")

# Sauvegarder un insight contextuel
rlm_remember("contenu", category="finding", importance="high", tags="odoo,weasyprint")

# Chunker une discussion (typé)
rlm_chunk("résumé", summary="Session du 04/02", tags="session", chunk_type="session")

# Chercher dans l'historique
rlm_search("sujet")
rlm_recall(query="mot-clé")
rlm_recall(importance="critical")  # règles universelles
```
