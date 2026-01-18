# /rlm-parallel

Analyser plusieurs chunks RLM en parallele et fusionner les resultats.

Pattern "Partition + Map" du paper MIT RLM (arXiv:2512.24601).

## Usage

```
/rlm-parallel "<question>"
/rlm-parallel "<question>" chunk_id1 chunk_id2 chunk_id3
```

## Exemples

```
/rlm-parallel "Quelles decisions ont ete prises sur Phase 5?"
/rlm-parallel "Resume les points cles" 2026-01-18_005 2026-01-18_006 2026-01-18_007
/rlm-parallel "Quels bugs ont ete corriges cette semaine?"
```

## Comportement

### Etape 1 : Selection des chunks

**Si chunk_ids fournis** : Utiliser ces chunks directement.

**Sinon** : Appeler `rlm_search(question, limit=3)` pour trouver les top-3 chunks pertinents.

### Etape 2 : Chargement parallele

Charger le contenu de chaque chunk via `rlm_peek(chunk_id)`.

### Etape 3 : Analyse parallele (CRITIQUE)

Lancer **exactement 3 Task tools dans un seul message** pour execution parallele :

```
Task #1 : subagent_type="Explore", model="sonnet"
  → Analyse chunk 1 avec la question

Task #2 : subagent_type="Explore", model="sonnet"
  → Analyse chunk 2 avec la question

Task #3 : subagent_type="Explore", model="sonnet"
  → Analyse chunk 3 avec la question
```

**Prompt pour chaque sub-agent** :

---

Tu es un assistant d'analyse. Reponds a la question basee UNIQUEMENT sur ce chunk.

### Question
{question}

### Chunk {chunk_id}
{contenu du chunk}

### Instructions
- Extrais les informations pertinentes a la question
- Cite les passages cles entre guillemets si utile
- Si rien de pertinent, reponds "Pas d'information pertinente dans ce chunk"
- Sois concis (max 200 mots)

---

### Etape 4 : Collecte des resultats

Attendre les 3 reponses des sub-agents.

### Etape 5 : Fusion (Merger)

Lancer un Task final pour synthetiser :

```
Task Merger : subagent_type="Explore", model="sonnet"
```

**Prompt Merger** :

---

Tu es un synthetiseur. Combine ces analyses partielles en une reponse coherente.

### Question originale
{question}

### Analyses partielles
**Chunk {chunk_id_1}** :
{reponse_1}

**Chunk {chunk_id_2}** :
{reponse_2}

**Chunk {chunk_id_3}** :
{reponse_3}

### Instructions
- Synthetise les insights sans repetition
- Si des analyses se contredisent, signale-le : "Contradiction : ..."
- Cite les sources : [chunk_id] pour chaque fait
- Structure la reponse avec des bullet points si utile
- Max 400 mots

---

### Etape 6 : Reponse finale

Retourner le resultat synthetise a l'utilisateur avec les sources.

## Quand utiliser ce skill

- Recherche d'information dispersee dans plusieurs chunks
- Questions complexes necessitant plusieurs sources
- Apres `rlm_search` pour approfondir les top resultats
- Quand une seule analyse `/rlm-analyze` ne suffit pas
- Pour croiser des informations de sessions differentes

## Notes techniques

- **Modele** : Sonnet (preference utilisateur)
- **Cout** : $0 supplementaire (Task tools inclus dans abonnement Claude Code Pro/Max)
- **Parallelisme** : Les 3 Task tools dans un seul message = execution parallele native
- **Contexte** : Chaque sub-agent a son contexte isole
- **Limite** : Maximum 3 chunks par appel (evite explosion de tokens)

## Difference avec /rlm-analyze

| Aspect | /rlm-analyze | /rlm-parallel |
|--------|--------------|---------------|
| Chunks | 1 seul | 3 en parallele |
| Use case | Question precise | Recherche large |
| Fusion | Non | Oui (merger) |
| Contradictions | N/A | Detectees |
