# RLM - Contexte de Session

> **Fichier de reprise** : À lire au début de chaque session pour restaurer le contexte complet.
> **Dernière MAJ** : 2026-01-18

---

## 1. Qu'est-ce que RLM ?

**Recursive Language Models** - Solution maison inspirée du paper MIT CSAIL (arXiv:2512.24601, Dec 2025) pour résoudre le problème de dégradation de Claude avec les contextes longs (>60% = début des problèmes).

**Principe** : Au lieu de charger tout le contexte dans l'attention, on :
1. Traite le contexte comme un **objet externe navigable**
2. Utilise des **tools MCP** pour explorer (peek, grep, search)
3. Permet des **appels récursifs** (sub-agents sur des chunks)
4. Sauvegarde les **insights clés** en mémoire persistante

---

## 2. Architecture

```
RLM/
├── mcp_server/           # Serveur MCP Python (FastMCP)
│   ├── server.py         # Point d'entrée (stdio transport)
│   └── tools/
│       └── memory.py     # remember, recall, forget, status
│
├── context/              # Stockage persistant
│   ├── session_memory.json   # Insights (ignoré par git)
│   └── chunks/               # Historique découpé (Phase 2+)
│
└── docs/
    ├── STATE_OF_ART.md           # État de l'art (RLM, Letta, TTT-E2E)
    ├── IMPLEMENTATION_PROPOSAL.md # Architecture détaillée
    └── CHECKLIST_PAPER_VS_SOLUTION.md # 85% couverture paper MIT
```

---

## 3. État d'Avancement

### Phase 1 : Fondations ✅ VALIDÉE (2026-01-18)

| Tâche | Statut |
|-------|--------|
| Structure fichiers MCP Server | ✅ |
| Tools memory (remember/recall/forget/status) | ✅ |
| Configuration Claude Code (`claude mcp add`) | ✅ |
| Tests locaux | ✅ |
| GitHub repo créé et poussé | ✅ |
| **Validation nouvelle session** | ✅ |

**Test validation** : Les 4 tools fonctionnent dans une session Claude Code fraîche. Le fichier SESSION_CONTEXT.md permet une reprise de contexte complète.

**GitHub** : https://github.com/EncrEor/rlm-claude

### Phase 2 : Navigation (PROCHAINE)

| Tâche | Statut |
|-------|--------|
| Tool `rlm_peek` (voir portion de chunk) | ⏳ |
| Tool `rlm_grep` (chercher pattern) | ⏳ |
| Tool `rlm_chunk` (découper contenu) | ⏳ |
| Index.json avec métadonnées | ⏳ |
| Tests end-to-end | ⏳ |

### Phase 3 : Sub-agents

- Tool `rlm_sub_query`
- Hooks auto-chunking
- Verification optionnelle
- Metrics coût

### Phase 4 : Production

- Résumés automatiques
- Documentation CLAUDE.md
- Optimisations

### Phase 5 : Avancé

- Embeddings locaux
- Multi-sessions
- n8n analytics (optionnel)

---

## 4. Tools MCP Disponibles

| Tool | Description | Phase |
|------|-------------|-------|
| `rlm_remember` | Sauvegarder un insight | 1 ✅ |
| `rlm_recall` | Récupérer des insights | 1 ✅ |
| `rlm_forget` | Supprimer un insight | 1 ✅ |
| `rlm_status` | Stats du système mémoire | 1 ✅ |
| `rlm_peek` | Voir portion de chunk | 2 ⏳ |
| `rlm_grep` | Chercher un pattern | 2 ⏳ |
| `rlm_chunk` | Découper du contenu | 2 ⏳ |
| `rlm_sub_query` | Lancer sub-agent | 3 ⏳ |

---

## 5. Décisions Architecturales

| Question | Décision | Justification |
|----------|----------|---------------|
| Taille chunks | 2000 tokens + 200 overlap | Balance contexte/performance |
| Transport MCP | stdio | Compatible Claude Code natif |
| Stockage | Fichiers JSON | Simple, portable, versionnable |
| Sub-model | Haiku pour sub-queries | Économie tokens (à implémenter) |
| n8n pour hooks | Non (v1) | Scripts locaux suffisent |

---

## 6. Fichiers Clés

| Fichier | Description |
|---------|-------------|
| `mcp_server/server.py` | Serveur MCP principal |
| `mcp_server/tools/memory.py` | Fonctions remember/recall |
| `context/session_memory.json` | Données mémoire (runtime) |
| `STATE_OF_ART.md` | Recherche complète |
| `IMPLEMENTATION_PROPOSAL.md` | Architecture détaillée |

---

## 7. Commandes Utiles

```bash
# Vérifier status MCP
claude mcp list

# Voir les insights stockés
cat /Users/amx/Documents/Joy_Claude/RLM/context/session_memory.json

# Git status
cd /Users/amx/Documents/Joy_Claude/RLM && git status

# Pousser sur GitHub
cd /Users/amx/Documents/Joy_Claude/RLM && git add . && git commit -m "message" && git push
```

---

## 8. Prochaine Action

**Tester les tools Phase 1** dans cette nouvelle session :
1. Utiliser `rlm_remember` pour sauvegarder un insight
2. Utiliser `rlm_recall` pour le récupérer
3. Utiliser `rlm_status` pour voir les stats

Si tout fonctionne → passer à Phase 2.

---

**Auteur** : Ahmed + Claude
**Repo** : https://github.com/EncrEor/rlm-claude
