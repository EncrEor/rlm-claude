# RLM - Recursive Language Models for Claude Code

> **Memoire infinie pour Claude** - Solution MCP avec auto-chunking 100% automatique

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Le Probleme

Les LLMs souffrent de **degradation avec les contextes longs** :
- **Lost in the Middle** : Performance degradee sur les informations au milieu du contexte
- **Context Rot** : Degradation progressive (~60% = debut des problemes)
- Claude devient "lazy et dumb" au-dela de 60-65% de contexte

## La Solution : RLM

Inspire du paper **"Recursive Language Models"** (MIT CSAIL, arXiv:2512.24601, Dec 2025) :

1. **Contexte comme objet externe** - L'historique est stocke en fichiers, pas charge en memoire
2. **Tools de navigation** - Peek, grep, search au lieu de tout lire
3. **Memoire d'insights** - Decisions et faits cles sauvegardes separement
4. **Auto-chunking** - Sauvegarde automatique via hooks Claude Code
5. **Sub-agents** - Deleguer des analyses a des workers isoles

---

## Installation Rapide

```bash
# 1. Cloner le repo
git clone https://github.com/EncrEor/rlm-claude.git
cd rlm-claude

# 2. Installer (100% automatique)
./install.sh

# 3. Relancer Claude Code
# RLM est pret !
```

**Prerequis** : Python 3.10+, Claude Code CLI

### Installation Manuelle

Si vous preferez installer manuellement :

```bash
# Installer les dependances
pip install -r mcp_server/requirements.txt

# Ajouter le serveur MCP
claude mcp add rlm-server -- python3 $(pwd)/mcp_server/server.py

# Copier les hooks
mkdir -p ~/.claude/rlm/hooks
cp hooks/*.py ~/.claude/rlm/hooks/
chmod +x ~/.claude/rlm/hooks/*.py

# Copier le skill
mkdir -p ~/.claude/skills/rlm-analyze
cp templates/skills/rlm-analyze/skill.md ~/.claude/skills/rlm-analyze/

# Configurer les hooks dans ~/.claude/settings.json
# (voir templates/hooks_settings.json)
```

---

## Comment Ca Marche

### Architecture

```
+-------------------------------------------------------------------+
|                  RLM - Architecture Phase 3                        |
+-------------------------------------------------------------------+
|                                                                    |
|  AUTO-CHUNKING (Hooks Claude Code)                                |
|  +--------------------------------------------------------------+ |
|  | Hook "Stop" (apres chaque reponse)                           | |
|  |   -> auto_chunk_check.py compte les tours                    | |
|  |   -> Si tours >= 10 ou temps >= 30min                        | |
|  |   -> Injecte "AUTO-CHUNK REQUIS" dans contexte Claude        | |
|  +--------------------------------------------------------------+ |
|  | Hook "PostToolUse" (apres rlm_chunk)                         | |
|  |   -> reset_chunk_counter.py remet compteur a 0               | |
|  +--------------------------------------------------------------+ |
|                              |                                     |
|                              v                                     |
|  CLAUDE (avec instructions RLM)                                   |
|    - Voit "AUTO-CHUNK REQUIS" -> chunke automatiquement          |
|    - Peut utiliser /rlm-analyze pour analyser d'anciens chunks   |
|                              |                                     |
|                              v                                     |
|  MCP SERVER RLM (8 tools)                                         |
|    - rlm_remember/recall/forget/status (insights)                |
|    - rlm_chunk/peek/grep/list_chunks (navigation)                |
|    - Stockage persistant dans ~/.claude/rlm/context/             |
|                                                                    |
+-------------------------------------------------------------------+
```

### Flux Auto-Chunking

1. **Hook Stop** : A chaque reponse, `auto_chunk_check.py` s'execute
2. **Compteur** : Incremente le nombre de tours
3. **Seuils** : Si 10 tours OU 30 minutes depuis dernier chunk
4. **Injection** : Message "AUTO-CHUNK REQUIS" dans le contexte Claude
5. **Action** : Claude chunke automatiquement sans demander permission
6. **Reset** : Apres `rlm_chunk`, le compteur revient a 0

---

## Tools MCP Disponibles

### Phase 1 - Memory (Insights)

| Tool | Description |
|------|-------------|
| `rlm_remember` | Sauvegarder un insight (decision, fait, preference) |
| `rlm_recall` | Recuperer des insights par recherche ou categorie |
| `rlm_forget` | Supprimer un insight par ID |
| `rlm_status` | Stats du systeme (insights + chunks) |

### Phase 2 - Navigation (Chunks)

| Tool | Description |
|------|-------------|
| `rlm_chunk` | Sauvegarder du contenu en chunk externe |
| `rlm_peek` | Lire un chunk (ou portion par lignes) |
| `rlm_grep` | Chercher un pattern regex dans tous les chunks |
| `rlm_list_chunks` | Lister les chunks disponibles avec metadonnees |

### Phase 5.1 - Search (BM25)

| Tool | Description |
|------|-------------|
| `rlm_search` | Recherche BM25 par pertinence (FR/EN, accents normalises) |

### Phase 5.5 - Multi-sessions (EN COURS)

| Tool | Description |
|------|-------------|
| `rlm_sessions` | Lister sessions par projet/domaine |
| `rlm_domains` | Lister domaines suggeres |

**Nouveau format chunk ID** : `{date}_{project}_{seq}[_{ticket}][_{domain}]`
- Exemple : `2026-01-18_RLM_001_r&d`
- Backward compat : chunks existants restent accessibles

---

## Skills RLM

Claude utilise ces patterns automatiquement quand pertinent (aucune action humaine requise).

### /rlm-analyze

Analyser un chunk avec un sub-agent dedie (contexte isole).

### /rlm-parallel

Analyser plusieurs chunks en parallele et fusionner les resultats.
Pattern "Partition + Map" du paper MIT RLM.

- 3 analyses paralleles (Task tools Sonnet)
- 1 merger qui synthetise avec citations [chunk_id]
- Detection automatique des contradictions

---

## Usage

### Sauvegarder des insights

```python
# Sauvegarder une decision importante
rlm_remember("Le client prefere les formats 500ml",
             category="preference",
             importance="high",
             tags="client,format")

# Retrouver des insights
rlm_recall(query="client")           # Recherche par mot-cle
rlm_recall(category="decision")      # Filtrer par categorie
rlm_recall(importance="critical")    # Filtrer par importance
```

### Gerer l'historique de conversation

```python
# Sauvegarder une partie de conversation importante
rlm_chunk("Discussion sur le business plan... [contenu long]",
          summary="BP Joy Juice - Scenarios REA",
          tags="bp,scenario,2026")

# Phase 4: Auto-summary si pas de summary fourni
rlm_chunk("Mon contenu ici...", tags="auto")
# → Summary auto-genere depuis la premiere ligne

# Phase 4: Detection des doublons
rlm_chunk("Meme contenu...")  # → "Duplicate detected"

# Voir ce qui est stocke (avec access_count Phase 4)
rlm_list_chunks()

# Lire un chunk specifique (incremente access_count)
rlm_peek("2026-01-18_001")

# Chercher dans l'historique (regex)
rlm_grep("business plan")

# Recherche BM25 par pertinence (Phase 5)
rlm_search("discussion sur le business plan")
# → Retourne les chunks tries par score de pertinence
# → Supporte FR/EN, normalise les accents (realiste = réaliste)
```

### Voir l'etat du systeme

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

## Categories d'Insights

| Categorie | Usage |
|-----------|-------|
| `decision` | Decisions prises pendant la session |
| `fact` | Faits decouverts ou confirmes |
| `preference` | Preferences de l'utilisateur |
| `finding` | Decouvertes techniques |
| `todo` | Actions a faire |
| `general` | Autre |

## Niveaux d'Importance

- `low` : Info de contexte
- `medium` : Standard (defaut)
- `high` : Important a retenir
- `critical` : Ne jamais oublier

---

## Structure du Projet

```
RLM/
├── mcp_server/
│   ├── server.py              # Serveur MCP (11 tools)
│   └── tools/
│       ├── memory.py          # Phase 1 (insights)
│       ├── navigation.py      # Phase 2 + 5.5 (chunks)
│       ├── tokenizer_fr.py    # Phase 5.1 (tokenization FR/EN)
│       ├── search.py          # Phase 5.1 (BM25 search)
│       └── sessions.py        # Phase 5.5 (sessions, domains)
│
├── hooks/                     # Phase 3 (auto-chunking)
│   ├── auto_chunk_check.py    # Hook Stop - detection
│   └── reset_chunk_counter.py # Hook PostToolUse - reset
│
├── templates/
│   ├── hooks_settings.json    # Config hooks a copier
│   ├── CLAUDE_RLM_SNIPPET.md  # Instructions CLAUDE.md
│   └── skills/
│       ├── rlm-analyze/
│       │   └── skill.md       # Skill analyse 1 chunk
│       └── rlm-parallel/
│           └── skill.md       # Skill analyse parallele
│
├── context/                   # Stockage (cree a l'install)
│   ├── session_memory.json    # Insights stockes
│   ├── index.json             # Index des chunks (v2.1.0)
│   ├── sessions.json          # Index des sessions (Phase 5.5)
│   ├── domains.json           # Domaines suggeres (Phase 5.5)
│   └── chunks/                # Historique decoupe
│
├── install.sh                 # Script installation
├── README.md                  # Cette documentation
├── SESSION_CONTEXT.md         # Contexte de reprise
├── ROADMAP.md                 # Pistes futures
└── docs/
    ├── STATE_OF_ART.md        # Recherche (RLM, Letta, TTT)
    ├── IMPLEMENTATION_PROPOSAL.md
    └── CHECKLIST_PAPER_VS_SOLUTION.md
```

---

## Configuration

### Seuils Auto-Chunking

Dans `hooks/auto_chunk_check.py` :

```python
TURNS_THRESHOLD = 10      # Nombre de tours avant auto-chunk
TIME_THRESHOLD = 1800     # Temps en secondes (30 min)
```

### Hooks Claude Code

Dans `~/.claude/settings.json` :

```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "python3 ~/.claude/rlm/hooks/auto_chunk_check.py"
      }]
    }],
    "PostToolUse": [{
      "matcher": "mcp__rlm-server__rlm_chunk",
      "hooks": [{
        "type": "command",
        "command": "python3 ~/.claude/rlm/hooks/reset_chunk_counter.py"
      }]
    }]
  }
}

**Note**: Le hook `Stop` ne supporte pas les matchers (contrairement à `PostToolUse`).
```

---

## Troubleshooting

### "MCP server not found"

```bash
claude mcp list                    # Verifier les serveurs
claude mcp remove rlm-server       # Supprimer si existe
claude mcp add rlm-server -- python3 /path/to/mcp_server/server.py
```

### "Hooks ne fonctionnent pas"

```bash
# Tester manuellement
python3 ~/.claude/rlm/hooks/auto_chunk_check.py
cat ~/.claude/rlm/chunk_state.json

# Verifier settings.json
cat ~/.claude/settings.json | grep -A 10 "hooks"
```

### "Skill /rlm-analyze non trouve"

```bash
ls ~/.claude/skills/rlm-analyze/
# Doit contenir skill.md
```

---

## Roadmap

- [x] **Phase 1** : Memory tools (remember/recall/forget/status)
- [x] **Phase 2** : Navigation tools (chunk/peek/grep/list)
- [x] **Phase 3** : Auto-chunking + Skill /rlm-analyze
- [x] **Phase 4** : Production (auto-summary, dedup, access tracking)
- [ ] **Phase 5** : Avance
  - [x] 5.1 : BM25 search (rlm_search)
  - [ ] 5.2 : Fuzzy grep
  - [x] 5.3 : Sub-agents paralleles (/rlm-parallel)
  - [ ] **5.5 : Multi-sessions (EN COURS)**
  - [ ] 5.6 : Retention (archive/purge)

Voir [ROADMAP.md](ROADMAP.md) pour les details.

---

## Documentation

| Fichier | Contenu |
|---------|---------|
| [STATE_OF_ART.md](STATE_OF_ART.md) | Etat de l'art (RLM, Letta, TTT-E2E) |
| [IMPLEMENTATION_PROPOSAL.md](IMPLEMENTATION_PROPOSAL.md) | Architecture detaillee |
| [CHECKLIST_PAPER_VS_SOLUTION.md](CHECKLIST_PAPER_VS_SOLUTION.md) | Couverture paper MIT (85%) |
| [SESSION_CONTEXT.md](SESSION_CONTEXT.md) | Contexte pour reprendre une session |
| [ROADMAP.md](ROADMAP.md) | Pistes futures |

---

## References

- [Paper RLM (MIT CSAIL)](https://arxiv.org/abs/2512.24601) - Zhang et al., Dec 2025
- [Prime Intellect Blog](https://www.primeintellect.ai/blog/rlm)
- [Letta/MemGPT](https://github.com/letta-ai/letta)
- [MCP Specification](https://modelcontextprotocol.io/specification)
- [Claude Code Hooks](https://docs.anthropic.com/claude-code/hooks)

---

## Auteurs

- Ahmed MAKNI ([@EncrEor](https://github.com/EncrEor))
- Claude Opus 4.5 (R&D conjointe)

## License

MIT License - voir [LICENSE](LICENSE)

---

**Derniere mise a jour** : 2026-01-18 (Phase 5.5 - Multi-sessions en cours)
