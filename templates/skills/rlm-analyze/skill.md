# /rlm-analyze

Analyser un chunk RLM avec un sub-agent dedie.

## Usage

```
/rlm-analyze <chunk_id> "<question>"
```

## Exemples

```
/rlm-analyze 2026-01-18_001 "Quelle decision a ete prise ?"
/rlm-analyze 2026-01-17_003 "Resume les points cles"
/rlm-analyze 2026-01-18_002 "Quels bugs ont ete corriges ?"
```

## Comportement

**Etape 1** : Valide que le chunk existe via `rlm_list_chunks`

**Etape 2** : Charge le contenu via `rlm_peek(chunk_id)`

**Etape 3** : Lance un subagent Task avec le contexte suivant :

---

Tu es un assistant d'analyse. Reponds a la question basee UNIQUEMENT sur le contexte fourni.

### Question
{La question de l'utilisateur}

### Contexte (Chunk {chunk_id})
{Contenu du chunk charge via rlm_peek}

### Instructions
- Reponds de maniere concise et precise
- Cite des passages pertinents si utile
- Si l'information n'est pas dans le contexte, dis-le clairement
- Ne fais pas de suppositions au-dela du contexte

---

**Etape 4** : Retourne le resultat du subagent a l'utilisateur

## Quand utiliser ce skill

- Apres avoir trouve un chunk pertinent via `rlm_grep`
- Pour analyser un ancien historique sans le charger en contexte principal
- Quand le contexte actuel est > 50% et tu dois deleguer
- Pour extraire des informations specifiques d'une longue conversation passee

## Notes techniques

- Le subagent utilise `subagent_type="Explore"` (lecture seule)
- Le contexte du subagent est isole (200k tokens dedies)
- Aucune modification de fichier n'est faite
- Le resultat est synthetise avant d'etre retourne
