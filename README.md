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

---

## Skill /rlm-analyze

Analyser un chunk avec un sub-agent dedie (contexte isole 200k tokens).

```
/rlm-analyze <chunk_id> "<question>"
```

### Exemples

```
/rlm-analyze 2026-01-18_001 "Quelle decision a ete prise ?"
/rlm-analyze 2026-01-17_003 "Resume les points cles"
```

### Quand l'utiliser

- Apres avoir trouve un chunk pertinent via `rlm_grep`
- Pour analyser un ancien historique sans le charger en contexte
- Quand le contexte actuel est > 50%

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

# Voir ce qui est stocke
rlm_list_chunks()

# Lire un chunk specifique
rlm_peek("2026-01-18_001")

# Chercher dans l'historique
rlm_grep("business plan")
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
│   ├── server.py              # Serveur MCP (8 tools)
│   └── tools/
│       ├── memory.py          # Phase 1 (insights)
│       └── navigation.py      # Phase 2 (chunks)
│
├── hooks/                     # Phase 3 (auto-chunking)
│   ├── auto_chunk_check.py    # Hook Stop - detection
│   └── reset_chunk_counter.py # Hook PostToolUse - reset
│
├── templates/
│   ├── hooks_settings.json    # Config hooks a copier
│   ├── CLAUDE_RLM_SNIPPET.md  # Instructions CLAUDE.md
│   └── skills/
│       └── rlm-analyze/
│           └── skill.md       # Skill /rlm-analyze
│
├── context/                   # Stockage (cree a l'install)
│   ├── session_memory.json    # Insights stockes
│   ├── index.json             # Index des chunks
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
      "matcher": "*",
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
- [ ] **Phase 4** : Production (resumes auto, optimisations)
- [ ] **Phase 5** : Avance (embeddings, multi-sessions)

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

**Derniere mise a jour** : 2026-01-18 (Phase 3 validee)
