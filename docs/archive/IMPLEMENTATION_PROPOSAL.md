# Proposition d'Implémentation : RLM Maison pour Claude Code

> **Version** : 2.3 (v0.9.0 - Systeme Simplifie)
> **Date** : 2026-01-24
> **Statut** : Production - Systeme simplifie user-driven + auto-compact

---

## 0. Analyse de rlm-minimal : Fit avec notre besoin

### 0.1 Ce que fait rlm-minimal

| Composant | Description |
|-----------|-------------|
| **RLM_REPL** | Classe principale qui wrap les appels LLM |
| **REPLEnv** | Environnement Python sandboxé pour exécuter du code |
| **Sub_RLM** | Client LLM léger pour appels récursifs (depth=1) |
| **System Prompt** | Instructions pour naviguer via Python REPL |

**Mécanisme** :
1. Le contexte est stocké comme variable `context`
2. Le LLM écrit du code Python dans des blocs ```repl
3. Le code est exécuté (peek, grep, llm_query)
4. Résultats renvoyés au LLM pour itération
5. Réponse finale via `FINAL(answer)` ou `FINAL_VAR(var)`

### 0.2 Analyse de compatibilité

| Aspect | rlm-minimal | Claude Code | Compatibilité |
|--------|-------------|-------------|---------------|
| **LLM API** | OpenAI SDK | Anthropic SDK | ⚠️ Adapter |
| **REPL** | Python exec() sandboxé | Bash tool existant | ⚠️ Différent |
| **Sub-calls** | Via API programmatique | Via Task tool (subagents) | ✅ Possible |
| **Context storage** | Variable Python | Fichiers | ⚠️ Adapter |
| **Récursion** | Limité à depth=1 | Subagents illimités | ✅ Mieux |

### 0.3 Verdict : Adapter ou Repartir de Zéro ?

**% de Fit : ~40%**

**Ce qu'on peut réutiliser** :
- Les concepts (REPL, sub-calls, chunking)
- Le system prompt (avec adaptation)
- La logique de terminaison (FINAL tags)

**Ce qu'on doit refaire** :
- L'intégration API (OpenAI → Claude)
- Le REPL (exec Python → Tools Claude Code)
- Le stockage (variables → fichiers)

**Recommandation** : Repartir de zéro en s'inspirant des concepts

rlm-minimal est un **excellent référentiel conceptuel** mais l'adapter prendrait autant de temps que créer notre propre solution mieux intégrée à Claude Code. De plus, notre solution sera plus native et maintenable.

---

## 0.4 Relation avec FOCUS_ACTUEL.md

**Question d'Ahmed** : Est-ce que `FOCUS_ACTUEL.md` est la même chose que "session memory" ?

**Analyse** :

| Aspect | FOCUS_ACTUEL.md | Session Memory RLM |
|--------|-----------------|-------------------|
| **Objectif** | Suivi macro projet | Mémoire conversation |
| **Contenu** | Roadmap, décisions stratégiques | Insights session, contexte local |
| **Persistance** | Entre sessions | Session uniquement |
| **Mise à jour** | Fin de session | Continue |
| **Granularité** | Haute (projet) | Fine (conversation) |

**Verdict** : Ce sont **deux choses complémentaires**, pas redondantes.

- `FOCUS_ACTUEL.md` = **Mémoire long-terme** (projet)
- `session_memory.md` = **Mémoire court-terme** (conversation)

**Le RLM va** :
1. Continuer à utiliser `FOCUS_ACTUEL.md` pour le contexte projet
2. Ajouter `session_memory.md` pour le contexte conversation
3. Ajouter le chunking pour l'historique détaillé

**Pas de désactivation prévue** - les deux coexistent.

---

## 0.5 Checklist : Ce qu'un RLM doit apporter

### Capacités attendues (selon le papier MIT)

| # | Capacité | Description | Notre solution |
|---|----------|-------------|----------------|
| 1 | **Navigation contexte** | Peek/Grep dans 10M+ tokens | ✅ rlm_peek/grep/search |
| 2 | **Sub-LLM calls** | Déléguer à des instances parallèles | ✅ /rlm-parallel skill |
| 3 | **Chunking intelligent** | Découper par sémantique | ✅ rlm_chunk + auto-summary |
| 4 | **Agrégation résultats** | Combiner les réponses sub-calls | ✅ Via Claude synthèse |
| 5 | **Mémoire de session** | Retenir les insights importants | ✅ rlm_remember/recall |
| 6 | **Persistance chunks** | Stocker hors contexte | ✅ context/chunks/ |
| 7 | **Index/métadonnées** | Retrouver les chunks pertinents | ✅ index.json + BM25 |
| 8 | **Stratégies émergentes** | Peeking, grepping, partition | ✅ Via prompts adaptés |
| 9 | **Terminaison propre** | Détecter la fin | ✅ Naturel avec Claude |
| 10 | **Coût contrôlé** | Pas d'explosion tokens | ✅ Retention (archive/purge) |

### Capacités bonus (au-delà du papier)

| # | Capacité | Description | Notre solution |
|---|----------|-------------|----------------|
| 11 | **Persistance inter-sessions** | Garder entre sessions | ✅ Fichiers + multi-sessions |
| 12 | **Intégration native** | Pas de setup externe | ✅ Skills + MCP |
| 13 | **Résumés automatiques** | Chunks avec summaries | ✅ Auto-summary Phase 4 |
| 14 | **Recherche sémantique** | Au-delà du keyword | ✅ BM25 + Fuzzy search |
| 15 | **Hooks automatiques** | Chunking auto | ✅ Hooks Claude Code |
| 16 | **Retention intelligente** | Archive/purge avec immunité | ✅ Phase 5.6 (v0.7.0) |

---

## 1. Vision

### 1.1 Ce qu'on veut

Un système qui permet à Claude de :
1. **Naviguer** dans des contextes de 1M+ tokens sans dégradation
2. **Se souvenir** des décisions et insights de la session
3. **Récupérer** l'information pertinente à la demande
4. **Rester performant** même après 2-3 heures de conversation

### 1.2 Ce qu'on ne veut PAS

- Complexité excessive (pas de Kubernetes, pas de vector DB)
- Latence importante (pas de recherche vectorielle lente)
- Coût exorbitant (pas de duplication inutile de tokens)

---

## 2. Architecture Proposée

### 2.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────┐
│                     RLM Joy Juice v1                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Claude (Root)                             │   │
│  │  - Reçoit la query utilisateur                               │   │
│  │  - Décide de la stratégie (direct vs exploration)            │   │
│  │  - Peut invoquer les tools RLM                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    RLM Tools Layer                           │   │
│  │                                                               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │   │
│  │  │ rlm_peek │ │ rlm_grep │ │rlm_chunk │ │rlm_query │        │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │   │
│  │                                                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  Context Store (Fichiers)                    │   │
│  │                                                               │   │
│  │  RLM/context/                                                 │   │
│  │  ├── session_memory.md      # Insights de session            │   │
│  │  ├── conversation_chunks/   # Historique découpé             │   │
│  │  │   ├── chunk_001.md                                        │   │
│  │  │   ├── chunk_002.md                                        │   │
│  │  │   └── ...                                                 │   │
│  │  └── index.json             # Index des chunks               │   │
│  │                                                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Composants clés

#### A. RLM Tools (MCP ou Skills)

| Tool | Description | Input | Output |
|------|-------------|-------|--------|
| `rlm_peek` | Voir une portion du contexte | chunk_id, start, end | Texte |
| `rlm_grep` | Chercher un pattern | pattern, scope | Matches + locations |
| `rlm_chunk` | Découper et indexer du contenu | content, chunk_size | chunk_ids |
| `rlm_query` | Appeler un sub-agent sur un chunk | prompt, chunk_ids | Réponse |
| `rlm_remember` | Sauvegarder un insight important | key, value | Confirmation |
| `rlm_recall` | Récupérer un insight sauvegardé | key (or pattern) | Value(s) |

#### B. Context Store (Fichiers)

```
RLM/context/
├── session_memory.md          # Format libre, insights clés
├── conversation_chunks/       # Historique découpé
│   ├── chunk_001.md          # ~2000 tokens chacun
│   ├── chunk_002.md
│   └── ...
├── index.json                 # Métadonnées des chunks
└── reference_docs.json        # Index des docs de référence
```

**Format `index.json`** :
```json
{
  "chunks": [
    {
      "id": "chunk_001",
      "file": "conversation_chunks/chunk_001.md",
      "tokens": 1850,
      "summary": "Discussion sur le business plan, scénarios REA",
      "keywords": ["business plan", "REA", "scénarios", "2026"],
      "timestamp": "2026-01-18T10:30:00Z"
    }
  ],
  "total_tokens": 185000,
  "last_updated": "2026-01-18T14:45:00Z"
}
```

#### C. Session Memory

```markdown
# Session Memory - 2026-01-18

## Décisions prises
- BP Odoo est priorité #1 pour janvier
- Scénarios renommés OPT → AGR (agressif)

## Contexte important
- Ahmed préfère qu'on challenge ses idées
- Joy Juice = Alpes-Maritimes, pas Tunisie

## Questions ouvertes
- Équipements 2028 à définir
- Charges patronales négligées pour l'instant

## Insights techniques
- Version module actuelle : 19.0.2.19.0
- Bug Phase 2 (Équipe) à corriger
```

---

## 3. Stratégies de Navigation

### 3.1 Quand utiliser RLM ?

| Situation | Action |
|-----------|--------|
| Contexte < 50% | Mode normal, pas de RLM |
| Contexte 50-70% | RLM sélectif (questions complexes) |
| Contexte > 70% | RLM systématique |

### 3.2 Stratégies émergentes attendues

1. **Peeking** : Regarder le début/fin des chunks
2. **Grepping** : Chercher par mots-clés pertinents
3. **Chunked Query** : Envoyer la question à plusieurs chunks, agréger
4. **Memory First** : Vérifier session_memory avant de chercher

---

## 4. Comparaison Approches : MCP vs Skills vs Hooks

### 4.1 Tableau comparatif détaillé

| Critère | MCP Server | Skills | Hooks Claude | Hybride |
|---------|------------|--------|--------------|---------|
| **Complexité setup** | Haute | Basse | Moyenne | Moyenne |
| **Maintenance** | Serveur à gérer | Fichiers .md | Scripts bash | Mix |
| **Persistance** | ✅ Toujours actif | ❌ À invoquer | ✅ Automatique | ✅ |
| **Performance** | Rapide (local) | Via tools existants | Rapide | Optimale |
| **Extensibilité** | Excellente | Bonne | Limitée | Excellente |
| **Intégration Claude Code** | Native (tools) | Native (/) | Native | Native |
| **Parallélisme** | ✅ Multi-tools | ✅ Subagents | ❌ Séquentiel | ✅ |
| **Debug** | Logs serveur | Visible dans chat | Logs fichiers | Mix |

### 4.2 Recommandation : Architecture MCP + Hooks

Après analyse, **MCP Server + Hooks** est l'approche la plus puissante et pérenne.

**Pourquoi ?**
1. **MCP** : Tools toujours disponibles, pas besoin d'invoquer manuellement
2. **Hooks** : Chunking automatique sans intervention humaine
3. **Scalable** : Peut évoluer vers recherche sémantique, etc.
4. **Standard** : Suit les patterns Anthropic officiels

---

## 5. Architecture Complète Définitive

### 5.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     RLM Joy Juice - Architecture Complète               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        Claude Code                               │   │
│  │  - Conversation avec l'utilisateur                               │   │
│  │  - Accès aux tools RLM via MCP                                   │   │
│  │  - Subagents pour tâches parallèles                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│              ┌───────────────┼───────────────┐                          │
│              ▼               ▼               ▼                          │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │  MCP Server   │  │    Hooks      │  │   Fichiers    │               │
│  │  (Tools RLM)  │  │  (Auto-chunk) │  │   (Storage)   │               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
│         │                   │                   │                       │
│         └───────────────────┼───────────────────┘                       │
│                             ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     Context Store                                │   │
│  │                                                                   │   │
│  │  RLM/                                                            │   │
│  │  ├── mcp_server/           # Serveur MCP Python                  │   │
│  │  │   ├── server.py                                               │   │
│  │  │   └── tools/                                                  │   │
│  │  │       ├── navigation.py     # peek, grep, search              │   │
│  │  │       ├── memory.py         # remember, recall                │   │
│  │  │       ├── chunking.py       # chunk, summarize                │   │
│  │  │       └── query.py          # sub_query (sub-agent)           │   │
│  │  │                                                               │   │
│  │  ├── context/              # Stockage persistant                 │   │
│  │  │   ├── session_memory.json   # Insights clés (structuré)       │   │
│  │  │   ├── chunks/               # Historique découpé              │   │
│  │  │   │   ├── 2026-01-18_001.md                                   │   │
│  │  │   │   └── ...                                                 │   │
│  │  │   ├── index.json            # Métadonnées chunks              │   │
│  │  │   └── embeddings.db         # Futur : recherche sémantique    │   │
│  │  │                                                               │   │
│  │  ├── hooks/                # Scripts de hook                     │   │
│  │  │   ├── post_response.sh      # Chunking auto après réponse     │   │
│  │  │   └── session_end.sh        # Sauvegarde fin de session       │   │
│  │  │                                                               │   │
│  │  └── docs/                 # Cette documentation                 │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 MCP Tools Détaillés

| Tool | Fonction | Paramètres | Retour |
|------|----------|------------|--------|
| `rlm_peek` | Voir une portion | `chunk_id`, `start`, `end` | Texte |
| `rlm_grep` | Chercher pattern | `pattern`, `scope`, `max_results` | Matches + contexte |
| `rlm_search` | Recherche sémantique | `query`, `top_k` | Chunks similaires |
| `rlm_remember` | Sauvegarder insight | `category`, `key`, `value` | Confirmation |
| `rlm_recall` | Récupérer insight | `category`, `key` (optionnel) | Value(s) |
| `rlm_chunk` | Découper contenu | `content`, `strategy` | Chunk IDs |
| `rlm_summarize` | Résumer chunk | `chunk_id` | Summary |
| `rlm_sub_query` | Appel sub-agent | `prompt`, `chunk_ids` | Réponse agrégée |
| `rlm_status` | État du système | - | Stats (tokens, chunks, etc.) |

### 5.3 Stratégies de Chunking

| Stratégie | Description | Quand utiliser |
|-----------|-------------|----------------|
| **size** | Découpe par taille fixe (~2000 tokens) | Par défaut |
| **semantic** | Découpe par changement de sujet | Conversations variées |
| **turn** | Découpe par tour de conversation | Historique dialogue |
| **overlap** | Chunks avec recouvrement 10% | Éviter perte contexte |

### 5.4 Format session_memory.json

```json
{
  "session_id": "2026-01-18_afternoon",
  "created_at": "2026-01-18T14:00:00Z",
  "updated_at": "2026-01-18T16:30:00Z",

  "decisions": [
    {
      "key": "bp_priority",
      "value": "Business Plan est priorité #1 pour janvier",
      "timestamp": "2026-01-18T14:15:00Z",
      "context": "Roadmap Q1 validée"
    }
  ],

  "context": [
    {
      "key": "joy_juice_location",
      "value": "Alpes-Maritimes, France (pas Tunisie)",
      "permanent": true
    }
  ],

  "insights": [
    {
      "key": "rlm_research",
      "value": "RLM = Recursive Language Models de MIT CSAIL",
      "source": "arXiv:2512.24601"
    }
  ],

  "questions_open": [
    {
      "key": "equipments_2028",
      "value": "Équipements 2028 à définir",
      "priority": "low"
    }
  ],

  "technical": {
    "module_version": "19.0.2.19.0",
    "pending_bugs": ["Phase 2 Équipe mal implémentée"]
  }
}
```

---

## 6. Décisions Architecturales (Réponses aux Questions Ouvertes)

### 6.1 Taille optimale des chunks

**Décision** : 2000 tokens avec overlap de 200 tokens

**Justification** :
- Assez grand pour garder le contexte sémantique
- Assez petit pour tenir dans des sub-queries
- L'overlap évite de couper au milieu d'une idée

### 6.2 Quand déclencher le chunking

**Décision (v0.9.0)** : User-driven + auto-save avant /compact

**Justification** :
- L'utilisateur décide quand chunker (instruction explicite)
- Claude propose aux moments clés (décision, fin tâche, insight)
- Hook PreCompact sauvegarde automatiquement avant /compact
- Plus de reminders automatiques (10/20/30 tours supprimés)

### 6.3 Profondeur de récursion

**Décision** : Depth=2 maximum (root → sub → sub-sub)

**Justification** :
- Depth=1 suffisant pour 90% des cas
- Depth=2 pour les tâches vraiment complexes
- Au-delà, risque d'explosion de coûts et de latence

### 6.4 Persistance entre sessions

**Décision** : Oui, via fichiers + FOCUS_ACTUEL.md

**Mécanisme** :
1. `session_memory.json` → fusionné avec précédent si pertinent
2. `FOCUS_ACTUEL.md` → mis à jour en fin de session
3. `chunks/` → conservés 7 jours, puis archivés

---

## 7. Roadmap Détaillée

### Phase 1 : Fondations ✅ TERMINÉE (2026-01-18)

| Tâche | Description | Livrable |
|-------|-------------|----------|
| 1.1 | Structure fichiers RLM/ | ✅ Répertoires créés |
| 1.2 | MCP Server minimal | ✅ server.py fonctionnel |
| 1.3 | Tool `rlm_remember`/`rlm_recall` | ✅ Mémoire session OK |
| 1.4 | Intégration settings.json | ✅ MCP activé dans Claude Code |
| 1.5 | Test manuel | ✅ Validation basique |

### Phase 2 : Navigation ✅ TERMINÉE (2026-01-18)

| Tâche | Description | Livrable |
|-------|-------------|----------|
| 2.1 | Tool `rlm_peek` | ✅ Navigation dans chunks |
| 2.2 | Tool `rlm_grep` | ✅ Recherche par pattern |
| 2.3 | Tool `rlm_chunk` | ✅ Sauvegarde contenu |
| 2.4 | Tool `rlm_list_chunks` | ✅ Liste des chunks |
| 2.5 | Index.json v2.0.0 | ✅ Métadonnées chunks |
| 2.6 | Tests MCP end-to-end | ✅ Validation complète |

### Phase 3 : Sub-agents (PROCHAINE)

| Tâche | Description | Livrable |
|-------|-------------|----------|
| 3.1 | Tool `rlm_sub_query` | Appels parallèles |
| 3.2 | Agrégation résultats | Synthèse intelligente |
| 3.3 | Hooks auto-chunking | `post_response.sh` |
| 3.4 | Benchmarks | Métriques performance |

### Phase 4 : Production (Session +4)

| Tâche | Description | Livrable |
|-------|-------------|----------|
| 4.1 | Résumés automatiques | Summaries dans index |
| 4.2 | Documentation utilisateur | Guide dans CLAUDE.md |
| 4.3 | Skill `/rlm-status` | Vue d'ensemble |
| 4.4 | Optimisations | Performance tuning |

### Phase 5 : Avancé - EN COURS

| Tâche | Description | Statut |
|-------|-------------|--------|
| 5.1 | BM25 search (FR/EN) | ✅ FAIT |
| 5.2 | Fuzzy grep (tolère typos) | ✅ FAIT (v0.6.1) |
| 5.3 | Sub-agents parallèles | ✅ FAIT (/rlm-parallel) |
| 5.5 | Multi-sessions | ✅ FAIT (sessions, domains) |
| 5.6 | Retention (archive/purge) | ✅ FAIT (v0.7.0) |

### Phase 6 : Production-Ready - EN COURS

| Tâche | Description | Statut |
|-------|-------------|--------|
| 6.1 | Tests automatisés (80%+) | ⏳ En cours |
| 6.2 | CI/CD GitHub Actions | ✅ FAIT (ruff lint + format) |
| 6.3 | Distribution PyPI | ⏳ À FAIRE |
| 6.4 | Robustesse (atomic writes, path traversal, locking) | ✅ FAIT (fileutil.py) |
| 6.5 | SECURITY.md + vulnerability reporting | ✅ FAIT |

### Phase 7 : MAGMA-Inspired Search Upgrade - VALIDÉE

> **Source** : [MAGMA (arXiv:2601.03236)](https://arxiv.org/abs/2601.03236) — Upgrade chirurgical, pas réécriture
> **Décidé** : 01/02/2026 | **Complété** : 01/02/2026

| Tâche | Description | Statut |
|-------|-------------|--------|
| 7.1 | Filtre temporel (`date_from`/`date_to`) sur `rlm_search` et `rlm_grep` | ✅ FAIT (28 tests) |
| 7.2 | Extraction d'entités auto dans `rlm_chunk()` (files, versions, modules, tickets, functions) | ✅ FAIT (36 tests) |

---

## 8. Risques et Mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **MCP Server instable** | Low | High | Tests unitaires, fallback skills |
| **Latence sub-queries** | Medium | Medium | Parallélisation, cache |
| **Coût API élevé** | Medium | Medium | Monitoring, limites, chunking intelligent |
| **Perte info au chunking** | Low | High | Overlap, résumés, validation |
| **Hooks non exécutés** | Low | Medium | Logs, alertes, mode manuel backup |
| **Complexité excessive** | Medium | Medium | Itérations, KISS |
| **Dépendance externe** | Low | Low | Tout est local, pas de cloud |

---

## 9. Métriques de Succès

### 9.1 Métriques Quantitatives

| Métrique | Baseline | Cible v1 | Cible v2 |
|----------|----------|----------|----------|
| **Recall précision** | ~60% (contexte long) | >85% | >95% |
| **Latence moyenne** | N/A | <3s | <1s |
| **Tokens/query** | 100% contexte | <50% | <30% |
| **Contexte supporté** | ~150k tokens | 500k | 1M+ |
| **Sessions sans perte** | ~60% | 90% | 99% |

### 9.2 Métriques Qualitatives

- [ ] Claude peut répondre à des questions sur des sujets discutés "il y a longtemps"
- [ ] Pas de "je ne me souviens pas" sur des décisions documentées
- [ ] Navigation fluide sans latence perceptible
- [ ] Ahmed valide que la qualité de réflexion est maintenue

---

## 10. Prochaines Actions Immédiates

1. **Valider cette architecture** avec Ahmed
2. **Créer la structure de fichiers** RLM/
3. **Prototyper le MCP Server** avec `rlm_remember`/`rlm_recall`
4. **Tester l'intégration** dans Claude Code

---

## 11. Appendices

### A. Références Techniques

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [Claude Code Hooks](https://docs.anthropic.com/claude-code/hooks)
- [arXiv:2512.24601 - RLM Paper](https://arxiv.org/abs/2512.24601)
- [Letta/MemGPT](https://github.com/letta-ai/letta)

### B. Exemple System Prompt RLM

```markdown
Tu disposes d'outils RLM pour naviguer dans le contexte étendu.

**Outils disponibles** :
- `rlm_peek(chunk_id, start, end)` : Voir une portion
- `rlm_grep(pattern)` : Chercher un pattern
- `rlm_recall(category, key)` : Récupérer un insight sauvegardé
- `rlm_sub_query(prompt, chunk_ids)` : Déléguer à un sub-agent

**Stratégies recommandées** :
1. Vérifie d'abord `rlm_recall("decisions")` pour les décisions passées
2. Utilise `rlm_grep` pour localiser l'information
3. `rlm_peek` pour voir le contexte autour
4. `rlm_sub_query` pour analyser plusieurs chunks en parallèle

**Ne jamais** :
- Répondre "je ne me souviens pas" sans avoir cherché
- Ignorer les chunks disponibles
- Faire des suppositions sur l'historique
```

---

**Version** : 2.4
**Date** : 2026-02-01
**Statut** : Production v0.9.0 — Phase 6 en cours, Phase 7 planifiée (MAGMA-inspired)
