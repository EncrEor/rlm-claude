# RLM - Mémoire Infinie pour Claude Code

> **Mémoire infinie pour Claude** - Solution MCP avec auto-chunking 100% automatique

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English](README.md) | Français | [日本語](README.ja.md)

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
4. **Auto-chunking** - Sauvegarde automatique via hooks Claude Code
5. **Sub-agents** - Déléguer des analyses à des workers isolés

---

## Installation Rapide

```bash
# 1. Cloner le repo
git clone https://github.com/EncrEor/rlm-claude.git
cd rlm-claude

# 2. Installer (100% automatique)
./install.sh

# 3. Relancer Claude Code
# RLM est prêt !
```

**Prérequis** : Python 3.10+, Claude Code CLI

### Installation Manuelle

Si vous préférez installer manuellement :

```bash
# Installer les dépendances
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

## Comment Ça Marche

### Architecture

```
+-------------------------------------------------------------------+
|                  RLM - Architecture v0.9.0                         |
+-------------------------------------------------------------------+
|                                                                    |
|  HOOKS CLAUDE CODE (2 hooks)                                      |
|  +--------------------------------------------------------------+ |
|  | Hook "PreCompact" (AVANT /compact ou auto-compact)           | |
|  |   -> pre_compact_chunk.py                                    | |
|  |   -> Crée un chunk automatique minimal                       | |
|  |   -> Sauvegarde garantie avant perte de contexte             | |
|  +--------------------------------------------------------------+ |
|  | Hook "PostToolUse" (après rlm_chunk)                         | |
|  |   -> reset_chunk_counter.py (pour stats)                     | |
|  +--------------------------------------------------------------+ |
|                              |                                     |
|                              v                                     |
|  UTILISATEUR + CLAUDE                                             |
|    - User: "chunk ça", "garde en mémoire", "rlm_remember"        |
|    - Claude: Propose chunk aux moments clés                       |
|    - Post-compact: Claude lit le chunk auto et enrichit           |
|                              |                                     |
|                              v                                     |
|  MCP SERVER RLM (14 tools)                                        |
|    - rlm_remember/recall/forget/status (insights)                |
|    - rlm_chunk/peek/grep/list_chunks + search/sessions (nav)     |
|    - rlm_retention_preview/run/restore (rétention)               |
|    - Stockage persistant dans context/                           |
|                                                                    |
+-------------------------------------------------------------------+
```

### Stratégie de Chunking (v0.9.0)

**Principe** : L'utilisateur décide, le système sauvegarde automatiquement avant /compact.

| Moment | Action | Déclencheur |
|--------|--------|-------------|
| Instruction explicite | `rlm_chunk()` / `rlm_remember()` | Utilisateur |
| Moment clé | Claude propose de chunker | Réflexe Claude |
| `/compact` | Chunk automatique minimal | Hook PreCompact |
| Post-compact | Claude lit et enrichit | Réflexe Claude |

#### Hook PreCompact (SAUVEGARDE AUTO)

Avant `/compact` ou auto-compact → chunk automatique créé :
- Résumé basique de la session
- Tags: `auto,precompact`
- Claude peut enrichir après le compact

#### Triggers Manuels (réflexe Claude)

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
| `rlm_grep(..., fuzzy=True)` | Recherche fuzzy tolérant les typos |
| `rlm_list_chunks` | Lister les chunks disponibles avec métadonnées |

### Phase 5.1 - Search (BM25)

| Tool | Description |
|------|-------------|
| `rlm_search` | Recherche BM25 par pertinence (FR/EN, accents normalisés) |

### Phase 5.5 - Multi-sessions

| Tool | Description |
|------|-------------|
| `rlm_sessions` | Lister sessions par projet/domaine |
| `rlm_domains` | Lister domaines suggérés (31 domaines) |
| `rlm_grep` | + params `project=`, `domain=` pour filtrer |
| `rlm_search` | + params `project=`, `domain=` pour filtrer |

**Nouveau format chunk ID** : `{date}_{project}_{seq}[_{ticket}][_{domain}]`
- Exemple : `2026-01-18_RLM_001_r&d`
- Auto-détection du projet via git ou cwd
- Backward compat : chunks existants (format 1.0) restent accessibles

### Phase 5.6 - Rétention (v0.7.0)

| Tool | Description |
|------|-------------|
| `rlm_retention_preview` | Preview des actions archive/purge (dry-run) |
| `rlm_retention_run` | Exécuter archivage et/ou purge |
| `rlm_restore` | Restaurer un chunk archivé |

**Architecture 3 zones** : ACTIF → ARCHIVE (.gz) → PURGE
- Archive après 30 jours si `access_count == 0` et non-immune
- Purge après 180 jours en archive
- Immunité : tags `critical`/`decision`, `access_count >= 3`, keywords `DECISION:`/`IMPORTANT:`
- Auto-restore : `peek()` restaure automatiquement les chunks archivés

---

## Skills RLM

Claude utilise ces patterns automatiquement quand pertinent (aucune action humaine requise).

### /rlm-analyze

Analyser un chunk avec un sub-agent dédié (contexte isolé).

### /rlm-parallel

Analyser plusieurs chunks en parallèle et fusionner les résultats.
Pattern "Partition + Map" du paper MIT RLM.

- 3 analyses parallèles (Task tools Sonnet)
- 1 merger qui synthétise avec citations [chunk_id]
- Détection automatique des contradictions

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

# Phase 4: Auto-summary si pas de summary fourni
rlm_chunk("Mon contenu ici...", tags="auto")
# → Summary auto-généré depuis la première ligne

# Phase 4: Détection des doublons
rlm_chunk("Même contenu...")  # → "Duplicate detected"

# Voir ce qui est stocké (avec access_count Phase 4)
rlm_list_chunks()

# Lire un chunk spécifique (incrémente access_count)
rlm_peek("2026-01-18_001")

# Chercher dans l'historique (regex)
rlm_grep("business plan")

# Phase 5.2: Recherche fuzzy (tolère les typos)
rlm_grep("buisness", fuzzy=True)           # → trouve "business"
rlm_grep("validaton", fuzzy=True)          # → trouve "validation"
rlm_grep("senario", fuzzy=True, fuzzy_threshold=70)  # Plus tolérant

# Phase 5.5c: Filtrer par projet/domaine
rlm_grep("equipment", project="JoyJuice", domain="bp")

# Recherche BM25 par pertinence (Phase 5)
rlm_search("discussion sur le business plan")
# → Retourne les chunks triés par score de pertinence
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
│   ├── hooks_settings.json    # Config hooks à copier
│   ├── CLAUDE_RLM_SNIPPET.md  # Instructions CLAUDE.md
│   └── skills/
│       ├── rlm-analyze/
│       │   └── skill.md       # Skill analyse 1 chunk
│       └── rlm-parallel/
│           └── skill.md       # Skill analyse parallèle
│
├── context/                   # Stockage (créé à l'install)
│   ├── session_memory.json    # Insights stockés (local, git-ignored)
│   ├── index.json             # Index des chunks (local, git-ignored)
│   ├── sessions.json          # Index des sessions (local, git-ignored)
│   ├── domains.json           # Domaines suggérés (local, auto-généré)
│   ├── domains.json.example   # Exemple avec domaines Joy Juice
│   ├── chunks/                # Historique découpé
│   ├── archive/               # Chunks archivés .gz (Phase 5.6)
│   ├── archive_index.json     # Index des archives (Phase 5.6)
│   └── purge_log.json         # Log des purges (Phase 5.6)
│
├── install.sh                 # Script installation
├── README.md                  # Documentation (English)
├── README.fr.md               # Documentation (Français)
├── SESSION_CONTEXT.md         # Contexte de reprise
└── ROADMAP.md                 # Pistes futures
```

---

## Configuration

### Personnalisation des Domaines

Les domaines sont des suggestions pour organiser vos chunks par thème.
Un fichier `domains.json` générique est créé automatiquement au premier lancement.

Pour personnaliser :

```bash
# Voir l'exemple complet (Joy Juice)
cat context/domains.json.example

# Éditer votre fichier local
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

Note : Vous pouvez utiliser n'importe quel domaine, même s'il n'est pas dans la liste.

### Hooks Claude Code (v0.9.0)

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
- `PreCompact` crée un chunk automatique avant /compact (manual ou auto)
- Hook `Stop` supprimé en v0.9.0 (pas de reminders automatiques)
- L'utilisateur décide quand chunker, le système sauvegarde avant perte

---

## Troubleshooting

### "MCP server not found"

```bash
claude mcp list                    # Vérifier les serveurs
claude mcp remove rlm-server       # Supprimer si existe
claude mcp add rlm-server -- python3 /path/to/mcp_server/server.py
```

### "Hooks ne fonctionnent pas"

```bash
# Tester manuellement
python3 ~/.claude/rlm/hooks/auto_chunk_check.py
cat ~/.claude/rlm/chunk_state.json

# Vérifier settings.json
cat ~/.claude/settings.json | grep -A 10 "hooks"
```

### "Skill /rlm-analyze non trouvé"

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
- [x] **Phase 5** : Avancé
  - [x] 5.1 : BM25 search (rlm_search)
  - [x] 5.2 : Fuzzy grep (v0.6.1 - tolère typos)
  - [x] 5.3 : Sub-agents parallèles (/rlm-parallel)
  - [x] 5.5 : Multi-sessions (sessions, domains, filtres project/domain)
  - [x] **5.6 : Rétention** (v0.7.0 - archive/purge)
- [ ] **Phase 6** : Production-Ready (tests, CI/CD, PyPI)

Voir [ROADMAP.md](ROADMAP.md) pour les détails.

---

## Références

- [Paper RLM (MIT CSAIL)](https://arxiv.org/abs/2512.24601) - Zhang et al., Dec 2025
- [Prime Intellect Blog](https://www.primeintellect.ai/blog/rlm)
- [Letta/MemGPT](https://github.com/letta-ai/letta)
- [MCP Specification](https://modelcontextprotocol.io/specification)
- [Claude Code Hooks](https://docs.anthropic.com/claude-code/hooks)

---

## Auteurs

- Ahmed MAKNI ([@EncrEor](https://github.com/EncrEor))
- Claude Opus 4.5 (R&D conjointe)

## Licence

MIT License - voir [LICENSE](LICENSE)
