# RLM - Contexte de Session

> **Fichier de reprise** : À lire au début de chaque session pour restaurer le contexte complet.
> **Dernière MAJ** : 2026-01-18 (Phase 2 implémentée)

---

## 1. Qu'est-ce que RLM ?

**Recursive Language Models** - Solution maison inspirée du paper MIT CSAIL (arXiv:2512.24601, Dec 2025) pour résoudre le problème de dégradation de Claude avec les contextes longs (>60% = début des problèmes).

**Problème résolu** :
- Au-delà de 60% de contexte, Claude devient "lazy et dumb"
- Régressions dans le code, oubli d'étapes cruciales
- Besoin de jongler manuellement pour maintenir le contexte bas

**Principe** : Au lieu de charger tout le contexte dans l'attention, on :
1. Traite le contexte comme un **objet externe navigable**
2. Utilise des **tools MCP** pour explorer (peek, grep, search)
3. Permet des **appels récursifs** (sub-agents sur des chunks)
4. Sauvegarde les **insights clés** en mémoire persistante

---

## ⚠️ CLARIFICATION IMPORTANTE

**Ne pas confondre** :

| Tool natif Claude Code | Tool RLM | Différence |
|------------------------|----------|------------|
| `Read` | `rlm_peek` | Read = fichiers du disque / rlm_peek = chunks de conversation |
| `Grep` | `rlm_grep` | Grep = recherche dans fichiers / rlm_grep = recherche dans historique |
| N/A | `rlm_chunk` | Sauvegarder l'historique de conversation externalement |
| N/A | `rlm_remember` | Sauvegarder des insights clés |

**Les tools RLM ne dupliquent pas les tools natifs !**
- Tools natifs = navigation dans le **code et fichiers projet**
- Tools RLM = navigation dans l'**historique de conversation** externalisé

---

## 2. Architecture

```
RLM/
├── mcp_server/           # Serveur MCP Python (FastMCP)
│   ├── server.py         # Point d'entrée (stdio transport)
│   └── tools/
│       ├── memory.py     # remember, recall, forget, status (Phase 1)
│       └── navigation.py # chunk, peek, grep, list_chunks (Phase 2)
│
├── context/              # Stockage persistant
│   ├── session_memory.json   # Insights clés
│   ├── index.json            # Index des chunks
│   └── chunks/               # Historique découpé
│       └── YYYY-MM-DD_NNN.md
│
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

### Phase 2 : Navigation ✅ VALIDÉE (2026-01-18)

| Tâche | Statut |
|-------|--------|
| Tool `rlm_chunk` (sauvegarder contenu) | ✅ |
| Tool `rlm_peek` (voir portion de chunk) | ✅ |
| Tool `rlm_grep` (chercher pattern) | ✅ |
| Tool `rlm_list_chunks` (lister les chunks) | ✅ |
| Index.json v2.0.0 avec métadonnées | ✅ |
| Tests fonctions Python | ✅ |
| Tests MCP end-to-end | ✅ |
| `rlm_status()` inclut chunks | ✅ |
| GitHub push | ✅ |

**Validation** : Tous les tools testés avec succès dans une nouvelle session Claude Code.

### Phase 3 : Sub-agents (PROCHAINE)

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

### Phase 1 - Memory (insights)

| Tool | Description | Statut |
|------|-------------|--------|
| `rlm_remember` | Sauvegarder un insight (décision, fait, préférence) | ✅ |
| `rlm_recall` | Récupérer des insights par query/catégorie | ✅ |
| `rlm_forget` | Supprimer un insight | ✅ |
| `rlm_status` | Stats du système mémoire | ✅ |

### Phase 2 - Navigation (chunks)

| Tool | Description | Statut |
|------|-------------|--------|
| `rlm_chunk` | Sauvegarder du contenu en chunk externe | ✅ |
| `rlm_peek` | Lire un chunk (ou portion) | ✅ |
| `rlm_grep` | Chercher un pattern dans les chunks | ✅ |
| `rlm_list_chunks` | Lister les chunks disponibles | ✅ |

### Phase 3+ (à venir)

| Tool | Description | Statut |
|------|-------------|--------|
| `rlm_sub_query` | Lancer sub-agent sur chunk | ⏳ |

---

## 5. Décisions Architecturales

| Question | Décision | Justification |
|----------|----------|---------------|
| Format chunks | Markdown (.md) | Lisible, facile à éditer |
| ID chunks | `YYYY-MM-DD_NNN` | Chronologique, unique |
| Taille max chunk | 3000 tokens | Balance contexte/granularité |
| Transport MCP | stdio | Compatible Claude Code natif |
| Stockage | Fichiers JSON/MD | Simple, portable, versionnable |
| Sub-model | Haiku pour sub-queries | Économie tokens (à implémenter) |
| n8n pour hooks | Non (v1) | Scripts locaux suffisent |

---

## 6. Fichiers Clés

| Fichier | Description |
|---------|-------------|
| `mcp_server/server.py` | Serveur MCP principal (8 tools) |
| `mcp_server/tools/memory.py` | Fonctions Phase 1 |
| `mcp_server/tools/navigation.py` | Fonctions Phase 2 |
| `context/session_memory.json` | Insights stockés |
| `context/index.json` | Index des chunks |
| `context/chunks/*.md` | Chunks de conversation |

---

## 7. Commandes Utiles

```bash
# Vérifier status MCP
claude mcp list

# Voir les insights stockés
cat /Users/amx/Documents/Joy_Claude/RLM/context/session_memory.json

# Voir les chunks
cat /Users/amx/Documents/Joy_Claude/RLM/context/index.json

# Lister les chunks
ls -la /Users/amx/Documents/Joy_Claude/RLM/context/chunks/

# Git status
cd /Users/amx/Documents/Joy_Claude/RLM && git status

# Pousser sur GitHub
cd /Users/amx/Documents/Joy_Claude/RLM && git add . && git commit -m "message" && git push
```

---

## 8. Prochaine Action

**Phase 3 : Sub-agents** - Prochaine étape du développement RLM.

Tools à implémenter :
- `rlm_sub_query` : Déléguer une question à un sub-agent sur un chunk spécifique
- Hooks auto-chunking : Sauvegarder automatiquement l'historique
- Metrics coût : Suivre l'utilisation tokens

**Pour tester les tools existants** :
```
rlm_status()           → Insights + Chunks stats
rlm_list_chunks()      → Liste des chunks disponibles
rlm_recall()           → Insights sauvegardés
```

---

## 9. Cas d'Usage Concrets Joy Juice

| Situation | Tool RLM | Exemple |
|-----------|----------|---------|
| "On a parlé de quoi il y a 2h ?" | `rlm_list_chunks` | Voir l'historique externalisé |
| "Où on a discuté des scénarios ?" | `rlm_grep("scénario")` | Trouver les discussions |
| "Cette discussion est importante" | `rlm_chunk(...)` | Sauvegarder pour plus tard |
| "Rappelle-moi la décision sur X" | `rlm_recall("X")` | Retrouver un insight |
| "On a décidé que..." | `rlm_remember(...)` | Sauvegarder la décision |

---

**Auteur** : Ahmed + Claude
**Repo** : https://github.com/EncrEor/rlm-claude
