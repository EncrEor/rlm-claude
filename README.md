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
|                  RLM - Architecture v0.8.0                         |
+-------------------------------------------------------------------+
|                                                                    |
|  HOOKS CLAUDE CODE (3 hooks)                                      |
|  +--------------------------------------------------------------+ |
|  | Hook "PreCompact" (AVANT /compact ou auto-compact)           | |
|  |   -> pre_compact_chunk.py                                    | |
|  |   -> Force chunk AVANT perte de contexte                     | |
|  |   -> Message bloquant avec instructions                       | |
|  +--------------------------------------------------------------+ |
|  | Hook "Stop" (apres chaque reponse) - BACKUP                  | |
|  |   -> auto_chunk_check.py - progressif + context-aware        | |
|  |   -> 10/20/30 tours + contexte >= 55%                        | |
|  |   -> 3 niveaux: doux / insistant / critique                  | |
|  +--------------------------------------------------------------+ |
|  | Hook "PostToolUse" (apres rlm_chunk)                         | |
|  |   -> reset_chunk_counter.py remet compteur a 0               | |
|  +--------------------------------------------------------------+ |
|                              |                                     |
|                              v                                     |
|  CLAUDE (avec triggers manuels)                                   |
|    - Chunk aux moments cles: decision, fin tache, insight        |
|    - Peut utiliser /rlm-analyze pour analyser d'anciens chunks   |
|                              |                                     |
|                              v                                     |
|  MCP SERVER RLM (14 tools)                                        |
|    - rlm_remember/recall/forget/status (insights)                |
|    - rlm_chunk/peek/grep/list_chunks + search/sessions (nav)     |
|    - rlm_retention_preview/run/restore (retention)               |
|    - Stockage persistant dans ~/.claude/rlm/context/             |
|                                                                    |
+-------------------------------------------------------------------+
```

### Strategie de Chunking (v0.8.0)

**Principe** : Chunk aux moments importants, pas sur des seuils arbitraires.

#### Hook PreCompact (PRINCIPAL)

Avant `/compact` ou auto-compact → message obligatoire :
```
[🔄 COMPACT DÉTECTÉ - SAUVEGARDE OBLIGATOIRE]
Le contexte va être compacté. AVANT de continuer:
1. rlm_chunk() - Résumer les points clés
2. rlm_remember() - Sauvegarder chaque décision
```

#### Hook Stop (BACKUP - progressif + context-aware)

| Seuil | Contexte | Message |
|-------|----------|---------|
| 10+ tours | >= 55% | 📝 Doux |
| 20+ tours | >= 55% | ⚠️ Insistant |
| 30+ tours | >= 55% | 🛑 Critique |

**Note** : Si contexte < 55%, pas de reminder (conversation légère).

#### Triggers Manuels (reflexe Claude)

- 🎯 Décision prise
- ✅ Tâche terminée
- 💡 Insight découvert
- 🔄 Changement de sujet
- ⚠️ Erreur corrigée

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
| `rlm_grep(..., fuzzy=True)` | **NEW v0.6.1** Recherche fuzzy tolerant les typos |
| `rlm_list_chunks` | Lister les chunks disponibles avec metadonnees |

### Phase 5.1 - Search (BM25)

| Tool | Description |
|------|-------------|
| `rlm_search` | Recherche BM25 par pertinence (FR/EN, accents normalises) |

### Phase 5.5 - Multi-sessions

| Tool | Description |
|------|-------------|
| `rlm_sessions` | Lister sessions par projet/domaine |
| `rlm_domains` | Lister domaines suggeres (31 domaines) |
| `rlm_grep` | + params `project=`, `domain=` pour filtrer |
| `rlm_search` | + params `project=`, `domain=` pour filtrer |

**Nouveau format chunk ID** : `{date}_{project}_{seq}[_{ticket}][_{domain}]`
- Exemple : `2026-01-18_RLM_001_r&d`
- Auto-detection du projet via git ou cwd
- Backward compat : chunks existants (format 1.0) restent accessibles

### Phase 5.6 - Retention (v0.7.0)

| Tool | Description |
|------|-------------|
| `rlm_retention_preview` | **NEW** Preview des actions archive/purge (dry-run) |
| `rlm_retention_run` | **NEW** Executer archivage et/ou purge |
| `rlm_restore` | **NEW** Restaurer un chunk archive |

**Architecture 3 zones** : ACTIF → ARCHIVE (.gz) → PURGE
- Archive apres 30 jours si `access_count == 0` et non-immune
- Purge apres 180 jours en archive
- Immunite : tags `critical`/`decision`, `access_count >= 3`, keywords `DECISION:`/`IMPORTANT:`
- Auto-restore : `peek()` restaure automatiquement les chunks archives

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

# Phase 5.2: Recherche fuzzy (tolere les typos)
rlm_grep("buisness", fuzzy=True)           # → trouve "business"
rlm_grep("validaton", fuzzy=True)          # → trouve "validation"
rlm_grep("senario", fuzzy=True, fuzzy_threshold=70)  # Plus tolerant

# Phase 5.5c: Filtrer par projet/domaine
rlm_grep("equipment", project="JoyJuice", domain="bp")

# Recherche BM25 par pertinence (Phase 5)
rlm_search("discussion sur le business plan")
# → Retourne les chunks tries par score de pertinence
# → Supporte FR/EN, normalise les accents (realiste = réaliste)

# Phase 5.5c: Filtrer les recherches
rlm_search("scenarios", project="JoyJuice")

# Lister les sessions disponibles
rlm_sessions()                          # Toutes
rlm_sessions(project="RLM")             # Par projet
rlm_sessions(domain="bp")               # Par domaine

# Voir les domaines disponibles
rlm_domains()  # → 31 domaines (23 Joy Juice + 8 default)
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
│   ├── server.py              # Serveur MCP (14 tools)
│   └── tools/
│       ├── memory.py          # Phase 1 (insights)
│       ├── navigation.py      # Phase 2 + 5.5 (chunks + auto-restore)
│       ├── tokenizer_fr.py    # Phase 5.1 (tokenization FR/EN)
│       ├── search.py          # Phase 5.1 (BM25 search)
│       ├── sessions.py        # Phase 5.5 (sessions, domains)
│       └── retention.py       # Phase 5.6 (archive/restore/purge)
│
├── hooks/                     # Phase 3+ (auto-chunking)
│   ├── pre_compact_chunk.py   # Hook PreCompact - force chunk avant compact
│   ├── auto_chunk_check.py    # Hook Stop - progressif + context-aware
│   └── reset_chunk_counter.py # Hook PostToolUse - reset compteur
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
│   ├── session_memory.json    # Insights stockes (local, git-ignored)
│   ├── index.json             # Index des chunks (local, git-ignored)
│   ├── sessions.json          # Index des sessions (local, git-ignored)
│   ├── domains.json           # Domaines suggeres (local, auto-genere)
│   ├── domains.json.example   # Exemple avec domaines Joy Juice
│   ├── chunks/                # Historique decoupe
│   ├── archive/               # Chunks archives .gz (Phase 5.6)
│   ├── archive_index.json     # Index des archives (Phase 5.6)
│   └── purge_log.json         # Log des purges (Phase 5.6)
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

### Personnalisation des Domaines

Les domaines sont des suggestions pour organiser vos chunks par theme.
Un fichier `domains.json` generique est cree automatiquement au premier lancement.

Pour personnaliser :

```bash
# Voir l'exemple complet (Joy Juice)
cat context/domains.json.example

# Editer votre fichier local
nano context/domains.json
```

Structure du fichier :

```json
{
  "domains": {
    "mon_projet": {
      "description": "Domaines pour mon projet",
      "list": ["feature", "bugfix", "infra", "docs"]
    }
  }
}
```

Note : Vous pouvez utiliser n'importe quel domaine, meme s'il n'est pas dans la liste.

### Seuils Auto-Chunking

Dans `hooks/auto_chunk_check.py` :

```python
# Seuils progressifs (v0.8.0)
TURNS_SOFT = 10       # Reminder doux
TURNS_MEDIUM = 20     # Reminder insistant
TURNS_HARD = 30       # Reminder critique

# Condition contexte
CONTEXT_THRESHOLD = 55  # Ne trigger que si contexte >= 55%

# Seuils temps (backup)
TIME_SOFT = 2700      # 45 minutes
TIME_HARD = 5400      # 90 minutes
```

### Hooks Claude Code

Dans `~/.claude/settings.json` :

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "manual",
        "hooks": [{
          "type": "command",
          "command": "python3 ~/.claude/rlm/hooks/pre_compact_chunk.py"
        }]
      },
      {
        "matcher": "auto",
        "hooks": [{
          "type": "command",
          "command": "python3 ~/.claude/rlm/hooks/pre_compact_chunk.py"
        }]
      }
    ],
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
```

**Notes** :
- `PreCompact` supporte les matchers `manual` (commande /compact) et `auto` (auto-compact)
- Le hook `Stop` ne supporte pas les matchers

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
- [x] **Phase 5** : Avance
  - [x] 5.1 : BM25 search (rlm_search)
  - [x] 5.2 : Fuzzy grep (v0.6.1 - tolere typos)
  - [x] 5.3 : Sub-agents paralleles (/rlm-parallel)
  - [x] 5.5 : Multi-sessions (sessions, domains, filtres project/domain)
  - [x] **5.6 : Retention** (v0.7.0 - archive/purge)
- [ ] **Phase 6** : Production-Ready (tests, CI/CD, PyPI)

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

**Derniere mise a jour** : 2026-01-24 (v0.8.0 - Hook PreCompact + Context-aware)
