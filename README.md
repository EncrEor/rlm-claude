# RLM - Recursive Language Models for Claude Code

> **Mémoire infinie pour Claude** - Solution MCP inspirée du paper MIT CSAIL

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Le Problème

Les LLMs souffrent de **dégradation avec les contextes longs** :
- **Lost in the Middle** : Performance dégradée sur les informations au milieu du contexte
- **Context Rot** : Dégradation progressive (~60% = début des problèmes)
- Claude devient "lazy et dumb" au-delà de 60-65% de contexte

## La Solution : RLM

Inspiré du paper **"Recursive Language Models"** (MIT CSAIL, arXiv:2512.24601, Dec 2025) :

1. **Contexte comme objet externe** - L'historique est stocké en fichiers, pas chargé en mémoire
2. **Tools de navigation** - Peek, grep, search au lieu de tout lire
3. **Mémoire d'insights** - Décisions et faits clés sauvegardés séparément
4. **Appels récursifs** - Sub-agents pour paralléliser (Phase 3)

---

## Installation

```bash
# 1. Cloner le repo
git clone https://github.com/EncrEor/rlm-claude.git
cd rlm-claude

# 2. Installer les dépendances
pip install -r mcp_server/requirements.txt

# 3. Ajouter le serveur MCP à Claude Code
claude mcp add rlm-server -- python3 $(pwd)/mcp_server/server.py

# 4. Relancer Claude Code et vérifier
claude mcp list
```

**Prérequis** : Python 3.10+, Claude Code CLI

---

## Tools Disponibles

### Phase 1 - Memory (Insights)

| Tool | Description |
|------|-------------|
| `rlm_remember` | Sauvegarder un insight (décision, fait, préférence) |
| `rlm_recall` | Récupérer des insights par recherche ou catégorie |
| `rlm_forget` | Supprimer un insight par ID |
| `rlm_status` | Stats du système (insights + chunks) |

### Phase 2 - Navigation (Chunks)

| Tool | Description |
|------|-------------|
| `rlm_chunk` | Sauvegarder du contenu en chunk externe |
| `rlm_peek` | Lire un chunk (ou portion par lignes) |
| `rlm_grep` | Chercher un pattern regex dans tous les chunks |
| `rlm_list_chunks` | Lister les chunks disponibles avec métadonnées |

---

## Usage

### Sauvegarder des insights

```python
# Sauvegarder une décision importante
rlm_remember("Le client préfère les formats 500ml",
             category="preference",
             importance="high",
             tags="client,format")

# Retrouver des insights
rlm_recall(query="client")           # Recherche par mot-clé
rlm_recall(category="decision")      # Filtrer par catégorie
rlm_recall(importance="critical")    # Filtrer par importance
```

### Gérer l'historique de conversation

```python
# Sauvegarder une partie de conversation importante
rlm_chunk("Discussion sur le business plan... [contenu long]",
          summary="BP Joy Juice - Scénarios REA",
          tags="bp,scenario,2026")

# Voir ce qui est stocké
rlm_list_chunks()

# Lire un chunk spécifique
rlm_peek("2026-01-18_001")

# Chercher dans l'historique
rlm_grep("business plan")
```

### Voir l'état du système

```python
rlm_status()
# Output:
# RLM Memory Status (v1.0.0)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Insights: 5
#   By category: decision: 2, finding: 3
#   By importance: high: 3, medium: 2
# Chunks: 3 (~4500 tokens)
```

---

## Catégories d'Insights

| Catégorie | Usage |
|-----------|-------|
| `decision` | Décisions prises pendant la session |
| `fact` | Faits découverts ou confirmés |
| `preference` | Préférences de l'utilisateur |
| `finding` | Découvertes techniques |
| `todo` | Actions à faire |
| `general` | Autre |

## Niveaux d'Importance

- `low` : Info de contexte
- `medium` : Standard (défaut)
- `high` : Important à retenir
- `critical` : Ne jamais oublier

---

## Architecture

```
RLM/
├── mcp_server/
│   ├── server.py              # Serveur MCP (8 tools)
│   └── tools/
│       ├── memory.py          # Phase 1 (insights)
│       └── navigation.py      # Phase 2 (chunks)
│
├── context/
│   ├── session_memory.json    # Insights stockés
│   ├── index.json             # Index des chunks
│   └── chunks/                # Historique découpé
│       └── YYYY-MM-DD_NNN.md
│
├── STATE_OF_ART.md            # Recherche (RLM, Letta, TTT)
├── IMPLEMENTATION_PROPOSAL.md # Architecture détaillée
└── SESSION_CONTEXT.md         # Contexte de reprise
```

---

## Roadmap

- [x] **Phase 1** : Memory tools (remember/recall/forget/status) ✅
- [x] **Phase 2** : Navigation tools (chunk/peek/grep/list) ✅
- [ ] **Phase 3** : Sub-agents + Hooks auto-chunking
- [ ] **Phase 4** : Production (résumés auto, optimisations)
- [ ] **Phase 5** : Avancé (embeddings, multi-sessions)

---

## Documentation

| Fichier | Contenu |
|---------|---------|
| [STATE_OF_ART.md](STATE_OF_ART.md) | État de l'art (RLM, Letta, TTT-E2E) |
| [IMPLEMENTATION_PROPOSAL.md](IMPLEMENTATION_PROPOSAL.md) | Architecture détaillée |
| [CHECKLIST_PAPER_VS_SOLUTION.md](CHECKLIST_PAPER_VS_SOLUTION.md) | Couverture paper MIT (85%) |
| [SESSION_CONTEXT.md](SESSION_CONTEXT.md) | Contexte pour reprendre une session |

---

## Références

- [Paper RLM (MIT CSAIL)](https://arxiv.org/abs/2512.24601) - Zhang et al., Dec 2025
- [Prime Intellect Blog](https://www.primeintellect.ai/blog/rlm)
- [Letta/MemGPT](https://github.com/letta-ai/letta)

---

## Auteurs

- Ahmed MAKNI ([@EncrEor](https://github.com/EncrEor))
- Claude Opus 4.5 (R&D conjointe)

## License

MIT License - voir [LICENSE](LICENSE)

---

**Dernière mise à jour** : 2026-01-18 (Phase 2 validée)
