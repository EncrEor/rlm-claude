# RLM - Contexte de Session

> **Fichier de reprise** : A lire au debut de chaque session pour restaurer le contexte complet.
> **Derniere MAJ** : 2026-01-18 (Phase 3 validee)

---

## DEMARRAGE DE SESSION

**A faire au debut de chaque session RLM :**

1. **Lire ce fichier** (SESSION_CONTEXT.md) pour le contexte global
2. **Invoquer `/strategie`** pour activer le mindset R&D (explorer et challenger avant d'executer)
3. **Lire la doc si besoin** :
   - `IMPLEMENTATION_PROPOSAL.md` - Architecture detaillee
   - `STATE_OF_ART.md` - Recherche sur RLM, Letta, TTT
   - `CHECKLIST_PAPER_VS_SOLUTION.md` - Couverture du paper MIT
   - `ROADMAP.md` - Pistes futures

**Mindset R&D** : On explore, on challenge, on ameliore AVANT d'executer. Profondeur > Rapidite.

---

## 1. Qu'est-ce que RLM ?

**Recursive Language Models** - Solution maison inspiree du paper MIT CSAIL (arXiv:2512.24601, Dec 2025) pour resoudre le probleme de degradation de Claude avec les contextes longs (>60% = debut des problemes).

**Probleme resolu** :
- Au-dela de 60% de contexte, Claude devient "lazy et dumb"
- Regressions dans le code, oubli d'etapes cruciales
- Besoin de jongler manuellement pour maintenir le contexte bas

**Principe** : Au lieu de charger tout le contexte dans l'attention, on :
1. Traite le contexte comme un **objet externe navigable**
2. Utilise des **tools MCP** pour explorer (peek, grep, search)
3. Permet des **appels recursifs** (sub-agents sur des chunks)
4. Sauvegarde les **insights cles** en memoire persistante
5. **Auto-chunking** via hooks Claude Code (Phase 3)

---

## CLARIFICATION IMPORTANTE

**Ne pas confondre** :

| Tool natif Claude Code | Tool RLM | Difference |
|------------------------|----------|------------|
| `Read` | `rlm_peek` | Read = fichiers du disque / rlm_peek = chunks de conversation |
| `Grep` | `rlm_grep` | Grep = recherche dans fichiers / rlm_grep = recherche dans historique |
| N/A | `rlm_chunk` | Sauvegarder l'historique de conversation externalement |
| N/A | `rlm_remember` | Sauvegarder des insights cles |
| N/A | `/rlm-analyze` | Analyser un chunk avec un sub-agent |

**Les tools RLM ne dupliquent pas les tools natifs !**
- Tools natifs = navigation dans le **code et fichiers projet**
- Tools RLM = navigation dans l'**historique de conversation** externalise

---

## 2. Architecture

```
RLM/
├── mcp_server/           # Serveur MCP Python (FastMCP)
│   ├── server.py         # Point d'entree (stdio transport)
│   └── tools/
│       ├── memory.py     # remember, recall, forget, status (Phase 1)
│       └── navigation.py # chunk, peek, grep, list_chunks (Phase 2)
│
├── hooks/                # Phase 3 - Auto-chunking
│   ├── auto_chunk_check.py    # Hook Stop - detection
│   └── reset_chunk_counter.py # Hook PostToolUse - reset
│
├── templates/            # Templates pour installation
│   ├── hooks_settings.json
│   ├── CLAUDE_RLM_SNIPPET.md
│   └── skills/rlm-analyze/skill.md
│
├── context/              # Stockage persistant
│   ├── session_memory.json   # Insights cles
│   ├── index.json            # Index des chunks
│   └── chunks/               # Historique decoupe
│       └── YYYY-MM-DD_NNN.md
│
├── install.sh                # Script installation automatique
├── STATE_OF_ART.md           # Etat de l'art (RLM, Letta, TTT-E2E)
├── IMPLEMENTATION_PROPOSAL.md # Architecture detaillee
├── CHECKLIST_PAPER_VS_SOLUTION.md # 85% couverture paper MIT
└── ROADMAP.md                # Pistes futures
```

---

## 3. Etat d'Avancement

### Phase 1 : Fondations - VALIDEE (2026-01-18)

| Tache | Statut |
|-------|--------|
| Structure fichiers MCP Server | OK |
| Tools memory (remember/recall/forget/status) | OK |
| Configuration Claude Code (`claude mcp add`) | OK |
| Tests locaux | OK |
| GitHub repo cree et pousse | OK |
| **Validation nouvelle session** | OK |

### Phase 2 : Navigation - VALIDEE (2026-01-18)

| Tache | Statut |
|-------|--------|
| Tool `rlm_chunk` (sauvegarder contenu) | OK |
| Tool `rlm_peek` (voir portion de chunk) | OK |
| Tool `rlm_grep` (chercher pattern) | OK |
| Tool `rlm_list_chunks` (lister les chunks) | OK |
| Index.json v2.0.0 avec metadonnees | OK |
| Tests fonctions Python | OK |
| Tests MCP end-to-end | OK |
| `rlm_status()` inclut chunks | OK |
| GitHub push | OK |

**Validation** : Tous les tools testes avec succes dans une nouvelle session Claude Code.

### Phase 3 : Auto-chunking & Sub-agents - VALIDEE (2026-01-18)

| Tache | Statut |
|-------|--------|
| Hook `auto_chunk_check.py` (detection) | OK |
| Hook `reset_chunk_counter.py` (reset) | OK |
| Template `hooks_settings.json` | OK |
| Skill `/rlm-analyze` | OK |
| Instructions `CLAUDE_RLM_SNIPPET.md` | OK |
| Script `install.sh` | OK |
| Documentation README.md mise a jour | OK |
| ROADMAP.md | OK |

**Nouveautes Phase 3** :
- Auto-chunking 100% automatique via hooks Claude Code
- Skill `/rlm-analyze` pour deleguer analyses a sub-agents
- Installation en une commande (`./install.sh`)
- Zero intervention humaine pour la gestion memoire

### Phase 4+ (A venir)

Voir [ROADMAP.md](ROADMAP.md) pour les details.

---

## 4. Tools MCP Disponibles

### Phase 1 - Memory (insights)

| Tool | Description | Statut |
|------|-------------|--------|
| `rlm_remember` | Sauvegarder un insight (decision, fait, preference) | OK |
| `rlm_recall` | Recuperer des insights par query/categorie | OK |
| `rlm_forget` | Supprimer un insight | OK |
| `rlm_status` | Stats du systeme memoire | OK |

### Phase 2 - Navigation (chunks)

| Tool | Description | Statut |
|------|-------------|--------|
| `rlm_chunk` | Sauvegarder du contenu en chunk externe | OK |
| `rlm_peek` | Lire un chunk (ou portion) | OK |
| `rlm_grep` | Chercher un pattern dans les chunks | OK |
| `rlm_list_chunks` | Lister les chunks disponibles | OK |

### Phase 3 - Auto-chunking

| Composant | Description | Statut |
|-----------|-------------|--------|
| Hook Stop | Detection auto-chunk (10 tours / 30 min) | OK |
| Hook PostToolUse | Reset compteur apres chunk | OK |
| Skill `/rlm-analyze` | Analyser chunk avec sub-agent | OK |

---

## 5. Decisions Architecturales

| Question | Decision | Justification |
|----------|----------|---------------|
| Format chunks | Markdown (.md) | Lisible, facile a editer |
| ID chunks | `YYYY-MM-DD_NNN` | Chronologique, unique |
| Taille max chunk | 3000 tokens | Balance contexte/granularite |
| Transport MCP | stdio | Compatible Claude Code natif |
| Stockage | Fichiers JSON/MD | Simple, portable, versionnable |
| Sub-agents | Task tool (skill) | $0, partageable, migrable |
| Auto-chunking | Hooks Claude Code | Integration native |
| Seuil tours | 10 | Balance frequence/pertinence |
| Seuil temps | 30 min | Sessions longues |

---

## 6. Fichiers Cles

| Fichier | Description |
|---------|-------------|
| `mcp_server/server.py` | Serveur MCP principal (8 tools) |
| `mcp_server/tools/memory.py` | Fonctions Phase 1 |
| `mcp_server/tools/navigation.py` | Fonctions Phase 2 |
| `hooks/auto_chunk_check.py` | Detection auto-chunk |
| `hooks/reset_chunk_counter.py` | Reset compteur |
| `templates/skills/rlm-analyze/skill.md` | Skill sub-agent |
| `context/session_memory.json` | Insights stockes |
| `context/index.json` | Index des chunks |
| `context/chunks/*.md` | Chunks de conversation |

---

## 7. Commandes Utiles

```bash
# Verifier status MCP
claude mcp list

# Voir les insights stockes
cat /Users/amx/Documents/Joy_Claude/RLM/context/session_memory.json

# Voir les chunks
cat /Users/amx/Documents/Joy_Claude/RLM/context/index.json

# Lister les chunks
ls -la /Users/amx/Documents/Joy_Claude/RLM/context/chunks/

# Voir l'etat auto-chunk
cat ~/.claude/rlm/chunk_state.json

# Tester hook manuellement
python3 ~/.claude/rlm/hooks/auto_chunk_check.py

# Git status
cd /Users/amx/Documents/Joy_Claude/RLM && git status

# Pousser sur GitHub
cd /Users/amx/Documents/Joy_Claude/RLM && git add . && git commit -m "message" && git push
```

---

## 8. Prochaine Action

**Phase 4 : Production** - Prochaine etape du developpement RLM.

A implementer :
- Resumes automatiques (auto-summarization des chunks)
- Optimisations (compression, deduplication)
- Metrics d'usage (tokens, frequence)

**Pour tester les tools existants** :
```
rlm_status()           -> Insights + Chunks stats
rlm_list_chunks()      -> Liste des chunks disponibles
rlm_recall()           -> Insights sauvegardes
/rlm-analyze chunk_id "question"  -> Analyser avec sub-agent
```

---

## 9. Cas d'Usage Concrets Joy Juice

| Situation | Tool RLM | Exemple |
|-----------|----------|---------|
| "On a parle de quoi il y a 2h ?" | `rlm_list_chunks` | Voir l'historique externalise |
| "Ou on a discute des scenarios ?" | `rlm_grep("scenario")` | Trouver les discussions |
| "Cette discussion est importante" | `rlm_chunk(...)` | Sauvegarder pour plus tard |
| "Rappelle-moi la decision sur X" | `rlm_recall("X")` | Retrouver un insight |
| "On a decide que..." | `rlm_remember(...)` | Sauvegarder la decision |
| "Analyse ce vieux chunk" | `/rlm-analyze chunk_id` | Deleguer a un sub-agent |

---

**Auteur** : Ahmed + Claude
**Repo** : https://github.com/EncrEor/rlm-claude
