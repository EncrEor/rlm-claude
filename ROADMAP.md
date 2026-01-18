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
| **Phase 5** | A FAIRE | Avance (embeddings, multi-sessions) |

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

## Phase 5 : Avance

**Objectif** : Fonctionnalites avancees pour power users.

### 5.1 Recherche semantique (Embeddings)

| Tache | Description | Priorite |
|-------|-------------|----------|
| Embeddings locaux | Utiliser sentence-transformers localement | P1 |
| Index vectoriel | FAISS ou ChromaDB pour recherche | P1 |
| Tool `rlm_search` | Recherche semantique vs grep exact | P1 |

**Avantage** : Trouver des chunks conceptuellement similaires meme sans mot-cle exact.

**Implementation proposee** :
```python
# Nouveau fichier: tools/semantic.py
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

def semantic_search(query: str, top_k: int = 5) -> list:
    """Search chunks by semantic similarity."""
    query_embedding = model.encode(query)
    # Compare avec embeddings pre-calcules des chunks
    pass
```

### 5.2 Multi-sessions

| Tache | Description | Priorite |
|-------|-------------|----------|
| Session ID | Identifier les sessions distinctes | P1 |
| Historique cross-session | Acceder aux chunks d'autres sessions | P2 |
| Merge sessions | Combiner des sessions reliees | P3 |

### 5.3 Export et backup

| Tache | Description | Priorite |
|-------|-------------|----------|
| Export JSON | Exporter toute la memoire en JSON | P2 |
| Backup automatique | Sauvegarder periodiquement | P2 |
| Import | Restaurer depuis backup | P2 |

---

## Pistes R&D (non planifiees)

### Option : API Haiku direct

Si un jour on veut plus d'automatisation, on pourrait :
1. Stocker une cle API Anthropic dans `RLM/config.json`
2. Appeler Claude Haiku directement depuis le MCP server
3. Cout estime : ~$5/mois pour usage intensif

**Avantages** :
- Resumes de qualite superieure
- Sub-queries plus intelligentes
- Verification automatique

**Inconvenients** :
- Necessite cle API ($)
- Plus de latence
- Dependance externe

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
