# RLM - Recursive Language Models for Claude Code

> **Mémoire infinie pour Claude** - Solution maison inspirée du paper MIT CSAIL

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Le Problème

Les LLMs actuels souffrent de **dégradation avec les contextes longs** :
- **Lost in the Middle** : Performance dégradée sur les informations au milieu du contexte
- **Context Rot** : Dégradation progressive (~60% = début des problèmes)
- **Coût quadratique** : O(n²) pour l'attention standard

## La Solution : RLM

Inspiré du paper **"Recursive Language Models"** (MIT CSAIL, arXiv:2512.24601, Dec 2025) :

1. **Contexte comme objet externe** - Le texte devient navigable, pas chargé en entier
2. **Tools de navigation** - Peek, grep, search au lieu de tout lire
3. **Appels récursifs** - Sub-agents pour paralléliser sur des chunks
4. **Mémoire persistante** - Insights sauvegardés entre les requêtes

### Résultats du paper original

| Benchmark | RLM vs Base | Amélioration |
|-----------|-------------|--------------|
| S-NIAH (10M+ tokens) | Stable vs Dégradation | 2× |
| BrowseComp+ | 91% vs 0% | Massif |
| CodeQA | 62% vs 24% | +158% |

## Notre Architecture

```
MCP Server + Hooks + Fichiers
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `rlm_peek` | Voir une portion de chunk |
| `rlm_grep` | Chercher un pattern regex |
| `rlm_remember` | Sauvegarder un insight clé |
| `rlm_recall` | Récupérer les insights pertinents |
| `rlm_chunk` | Découper du contenu |
| `rlm_sub_query` | Lancer un sub-agent sur un chunk |
| `rlm_status` | État du système (chunks, mémoire) |

### Hooks Automatiques

- **post_response.sh** : Chunking auto tous les 5 tours ou à 60% contexte
- **session_end.sh** : Sauvegarde mémoire en fin de session

## Documentation

| Fichier | Contenu |
|---------|---------|
| [STATE_OF_ART.md](STATE_OF_ART.md) | État de l'art complet (RLM, Letta, TTT-E2E) |
| [IMPLEMENTATION_PROPOSAL.md](IMPLEMENTATION_PROPOSAL.md) | Architecture détaillée |
| [CHECKLIST_PAPER_VS_SOLUTION.md](CHECKLIST_PAPER_VS_SOLUTION.md) | Vérification vs paper MIT (85% couverture) |

## Roadmap

- [x] **Phase 1** : MCP Server minimal (remember/recall) ✅
- [ ] **Phase 2** : Navigation (peek/grep/chunk)
- [ ] **Phase 3** : Sub-agents + Hooks
- [ ] **Phase 4** : Production (résumés auto, docs)
- [ ] **Phase 5** : Avancé (embeddings, multi-sessions)

## Installation

```bash
# 1. Cloner le repo
git clone https://github.com/EncrEor/rlm-claude.git
cd rlm-claude

# 2. Installer les dépendances
pip install -r mcp_server/requirements.txt

# 3. Ajouter à Claude Code
claude mcp add rlm-server -- python3 $(pwd)/mcp_server/server.py

# 4. Vérifier la connexion
claude mcp list
```

## Usage

Une fois installé, Claude a accès aux tools RLM :

```python
# Sauvegarder un insight important
rlm_remember("Le client préfère les formats 500ml", category="preference", importance="high")

# Retrouver des insights
rlm_recall(query="client")  # Recherche par mot-clé
rlm_recall(category="decision")  # Filtrer par catégorie

# Voir l'état de la mémoire
rlm_status()

# Supprimer un insight
rlm_forget("abc12345")  # Par ID
```

### Catégories disponibles
- `decision` : Décisions prises
- `fact` : Faits découverts
- `preference` : Préférences utilisateur
- `finding` : Découvertes techniques
- `todo` : Actions à faire
- `general` : Autre

## Références

- [Paper RLM (MIT CSAIL)](https://arxiv.org/abs/2512.24601)
- [Prime Intellect Blog](https://www.primeintellect.ai/blog/rlm)
- [rlm-minimal (référence)](https://github.com/alexzhang13/rlm-minimal)
- [Letta/MemGPT](https://github.com/letta-ai/letta)

## Auteurs

- Ahmed MAKNI ([@EncrEor](https://github.com/EncrEor))
- Claude (R&D conjointe)

## License

MIT License - voir [LICENSE](LICENSE)

---

**Note** : Phase 1 terminée (2026-01-18). Phase 2 (navigation tools) en cours de développement.
