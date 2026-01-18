# RLM - Roadmap

> Pistes futures pour RLM - Memoire infinie pour Claude Code
> **Derniere MAJ** : 2026-01-18

---

## Vue d'ensemble

| Phase | Statut | Description |
|-------|--------|-------------|
| **Phase 1** | VALIDEE | Memory tools (remember/recall/forget/status) |
| **Phase 2** | VALIDEE | Navigation tools (chunk/peek/grep/list) |
| **Phase 3** | VALIDEE | Auto-chunking + Skill /rlm-analyze |
| **Phase 4** | VALIDEE | Production (auto-summary, dedup, access tracking) |
| **Phase 5** | EN COURS | Avance (BM25, multi-sessions, sub-agents) |

---

## Phase 4 : Production

**Objectif** : Rendre RLM production-ready avec optimisations et metriques.

### 4.1 Resumes automatiques

| Tache | Description | Priorite |
|-------|-------------|----------|
| Auto-summarization | Resume automatique des chunks longs | P1 |
| Hierarchie de resumes | Resume de resumes pour navigation rapide | P2 |
| Titre intelligent | Generation automatique de titres pertinents | P2 |

**Implementation proposee** :
```python
# Dans navigation.py
def auto_summarize(content: str, max_tokens: int = 200) -> str:
    """Generate a summary using local model or simple extraction."""
    # Option 1: Extraction des premieres phrases
    # Option 2: Appel a un modele local (llama.cpp)
    pass
```

### 4.2 Compression et deduplication

| Tache | Description | Priorite |
|-------|-------------|----------|
| Detection doublons | Eviter de stocker le meme contenu 2 fois | P1 |
| Compression | Compresser les vieux chunks (gzip) | P2 |
| Archivage | Deplacer vieux chunks vers archive | P3 |

### 4.3 Metriques d'usage

| Tache | Description | Priorite |
|-------|-------------|----------|
| Token counter | Compter les tokens reellement utilises | P1 |
| Usage stats | Frequence d'acces aux chunks | P2 |
| Dashboard | Visualisation simple des stats | P3 |

---

## Phase 5 : RLM Authentique

**Objectif** : Suivre le paper MIT avec BM25 + sub-agents, embeddings en backup.

**Changement strategique (2026-01-18)** : Apres recherche approfondie, on decouvre que le paper RLM MIT n'utilise PAS d'embeddings. Letta benchmark confirme : filesystem + grep = 74% accuracy > embeddings.

### 5.1 BM25 Ranking - FAIT

| Tache | Description | Statut |
|-------|-------------|--------|
| Tool `rlm_search` | Recherche BM25S (500x plus rapide) | FAIT |
| Tokenization FR/EN | Stopwords, normalisation | FAIT |
| Scoring pertinence | Trier par score BM25 | FAIT |

**Implementation** : BM25S avec tokenizer FR/EN zero dependance
- `mcp_server/tools/search.py`
- `mcp_server/tools/tokenizer_fr.py`

### 5.2 Grep Optimise

| Tache | Description | Priorite |
|-------|-------------|----------|
| Fuzzy matching | Tolerance typos (thefuzz) | P1 |
| Multi-pattern | Chercher plusieurs termes | P2 |
| Scoring | Trier resultats grep par pertinence | P2 |

### 5.3 Sub-agents Paralleles - FAIT

| Tache | Description | Statut |
|-------|-------------|--------|
| Partition + Map | Analyser 3 chunks en parallele | FAIT |
| Skill `/rlm-parallel` | Pattern auto-applique par Claude | FAIT |
| Merger intelligent | Synthetiser avec citations [chunk_id] | FAIT |

**Implementation** : Task tools paralleles (natif Claude Code, $0)
**Note** : MCP Sampling non supporte par Claude Code (issue #1785) → Skill = seule option

### 5.4 Embeddings (BACKUP)

**Activer SEULEMENT SI** : BM25 < 70% precision ou queries semantiques pures echouent.

| Tache | Description | Priorite |
|-------|-------------|----------|
| Nomic Embed v2 MoE | Modele multilingue leger | P3 |
| LanceDB | Stockage vectoriel Rust | P3 |
| Dimensions Matryoshka | 384 dims (tronque de 768) | P3 |

### 5.5 Multi-sessions - EN COURS

**Objectif** : Organiser les chunks par projet/domaine pour navigation cross-session.

| Sous-phase | Description | Statut |
|------------|-------------|--------|
| **5.5a** | Format ID enrichi + detection projet | EN COURS |
| **5.5b** | Sessions tracking + tools | A FAIRE |
| **5.5c** | Cross-session queries (@syntax) | A FAIRE |

**Nouveau format ID** : `{date}_{project}_{seq}[_{ticket}][_{domain}]`
- Exemple : `2026-01-18_RLM_001_r&d`
- Exemple : `2026-01-18_JoyJuice_005_TIC-123_bp`

**Decisions validees** :
- Chunks existants restent en format 1.0 (backward compat)
- Domaines flexibles (pas de validation stricte)
- Detection auto projet via git root ou cwd

**Nouveaux tools** :
| Tool | Description |
|------|-------------|
| `rlm_sessions` | Lister sessions par projet/domaine |
| `rlm_domains` | Lister domaines suggeres |

**Fichiers a creer** :
- `sessions.py` - Gestion sessions
- `sessions.json` - Index des sessions
- `domains.json` - Domaines suggeres

### 5.6 Export et backup

| Tache | Description | Priorite |
|-------|-------------|----------|
| Export JSON | Exporter toute la memoire en JSON | P3 |
| Backup automatique | Sauvegarder periodiquement | P3 |
| Import | Restaurer depuis backup | P3 |

**Documentation complete** : `docs/PHASE5_PLAN.md`

---

## Pistes R&D (non planifiees)

### Option : API Haiku direct (OBSOLETE)

**Cette option n'est plus necessaire.**

Les Task tools de Claude Code sont inclus dans l'abonnement Pro/Max = **$0 supplementaire**.
Le skill `/rlm-parallel` utilise ce mecanisme natif.

### Support MCP Sampling

Quand Claude Code supportera le sampling ([#1785](https://github.com/anthropics/claude-code/issues/1785)) :

1. Ajouter `rlm_sub_query` utilisant `ctx.session.create_message()`
2. Retirer le skill `/rlm-analyze` (ou le garder en fallback)
3. UX identique, implementation plus elegante

**Tracking** : Surveiller le GitHub issue pour savoir quand implementer.

### Integration n8n (optionnel)

Pour des workflows plus complexes :
- Webhook quand un chunk important est cree
- Dashboard analytics externe
- Notifications

---

## Non-goals (explicites)

Ce que RLM ne fera PAS :

| Non-goal | Raison |
|----------|--------|
| Remplacer tools natifs | RLM est complementaire, pas un remplacement |
| Cloud storage | Tout reste local pour la privacy |
| Interface graphique | CLI first, simplicity wins |
| Multi-user | Un utilisateur = une instance |

---

## Contribution

Pour contribuer a RLM :

1. Fork le repo
2. Creer une branche pour votre feature
3. Implementer avec tests
4. PR avec description claire

**Guidelines** :
- Keep it simple
- Zero dependencies externes si possible
- Documentation en francais ou anglais
- Tests pour toute nouvelle fonction

---

## Timeline estimee

| Phase | Estimation | Notes |
|-------|------------|-------|
| Phase 4.1 (resumes) | 1-2 sessions | Simple extraction d'abord |
| Phase 4.2 (compression) | 1 session | Optionnel |
| Phase 4.3 (metriques) | 1 session | Simple compteur |
| Phase 5.1 (embeddings) | 2-3 sessions | Necessite choix librairie |
| Phase 5.2 (multi-sessions) | 2 sessions | Architecture a definir |

**Note** : Ces estimations sont indicatives. L'approche RLM est iterative - on implemente ce qui est utile quand c'est necessaire.

---

## References

- [Paper RLM (MIT CSAIL)](https://arxiv.org/abs/2512.24601) - Zhang et al., Dec 2025
- [MCP Sampling Spec](https://modelcontextprotocol.io/specification/2025-06-18/client/sampling)
- [Claude Code Sampling Issue](https://github.com/anthropics/claude-code/issues/1785)
- [sentence-transformers](https://www.sbert.net/)
- [FAISS](https://github.com/facebookresearch/faiss)
- [ChromaDB](https://www.trychroma.com/)

---

**Auteur** : Ahmed + Claude
**Repo** : https://github.com/EncrEor/rlm-claude
