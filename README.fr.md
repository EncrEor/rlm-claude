# RLM - Mémoire Infinie pour Claude Code

> Vos sessions Claude Code oublient tout après `/compact`. RLM règle ça.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io)
[![CI](https://github.com/EncrEor/rlm-claude/actions/workflows/ci.yml/badge.svg)](https://github.com/EncrEor/rlm-claude/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/EncrEor/rlm-claude/branch/main/graph/badge.svg)](https://codecov.io/gh/EncrEor/rlm-claude)
[![PyPI version](https://img.shields.io/pypi/v/mcp-rlm-server.svg)](https://pypi.org/project/mcp-rlm-server/)

[English](README.md) | Français | [日本語](README.ja.md)

---

## Le Problème

Claude Code a une **limite de fenêtre de contexte**. Quand elle est atteinte :
- `/compact` efface votre historique de conversation
- Les décisions, insights et contexte précédents sont **perdus**
- Vous vous répétez. Claude refait les mêmes erreurs. La productivité chute.

## La Solution

**RLM** est un serveur MCP qui donne à Claude Code une **mémoire persistante entre les sessions** :

```
Vous : "Retiens que le client préfère les bouteilles de 500ml"
     → Sauvegardé. Pour toujours. Dans toutes les sessions.

Vous : "Qu'est-ce qu'on avait décidé pour l'architecture API ?"
     → Claude cherche dans sa mémoire et trouve la réponse.
```

**3 lignes pour installer. 14 outils. Zéro configuration.**

---

## Installation rapide

### Via PyPI (recommandé)

```bash
pip install mcp-rlm-server[all]
```

### Via Git

```bash
git clone https://github.com/EncrEor/rlm-claude.git
cd rlm-claude
./install.sh
```

Relancez Claude Code. C'est prêt.

**Prérequis** : Python 3.10+, Claude Code CLI

### Mise à jour depuis v0.9.0 ou antérieur

La v0.9.1 a déplacé le code source de `mcp_server/` vers `src/mcp_server/` (bonne pratique PyPA). Un lien symbolique de compatibilité est inclus, mais nous recommandons de relancer l'installeur :

```bash
cd rlm-claude
git pull
./install.sh          # reconfigure le chemin du serveur MCP
```

Vos données (`~/.claude/rlm/`) ne sont pas touchées. Seul le chemin du serveur est mis à jour.

---

## Comment ça marche

```
                    ┌─────────────────────────┐
                    │     Claude Code CLI      │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    Serveur MCP RLM       │
                    │    (14 outils)           │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
    ┌─────────▼────────┐ ┌──────▼──────┐ ┌──────────▼─────────┐
    │    Insights       │ │   Chunks    │ │    Rétention        │
    │ (décisions clés,  │ │ (historique │ │ (auto-archivage,    │
    │  faits, prefs)    │ │  complet)   │ │  restauration,      │
    └──────────────────┘ └─────────────┘ │  purge)             │
                                          └────────────────────┘
```

### Sauvegarde automatique avant perte de contexte

RLM intercepte l'événement `/compact` de Claude Code. Avant que votre contexte ne soit effacé, RLM **sauvegarde automatiquement un snapshot**. Rien à faire.

### Deux systèmes de mémoire

| Système | Ce qu'il stocke | Comment l'utiliser |
|---------|----------------|-------------------|
| **Insights** | Décisions clés, faits, préférences | `rlm_remember()` / `rlm_recall()` |
| **Chunks** | Segments de conversation complets | `rlm_chunk()` / `rlm_peek()` / `rlm_grep()` |

---

## Fonctionnalités

### Mémoire et Insights
- **`rlm_remember`** - Sauvegarder des décisions, faits, préférences avec catégories et niveaux d'importance
- **`rlm_recall`** - Rechercher des insights par mot-clé (multi-mots tokenisés), catégorie ou importance
- **`rlm_forget`** - Supprimer un insight
- **`rlm_status`** - Vue d'ensemble du système (nombre d'insights, stats chunks, métriques d'accès)

### Historique de conversation
- **`rlm_chunk`** - Sauvegarder des segments de conversation avec catégorisation typée (`snapshot`, `session`, `debug` ; `insight` redirige vers `rlm_remember`)
- **`rlm_peek`** - Lire un chunk (entier ou partiel par plage de lignes)
- **`rlm_grep`** - Recherche regex dans tous les chunks (+ recherche floue pour tolérance aux typos)
- **`rlm_search`** - Recherche hybride : BM25 + similarité cosinus sémantique (FR/EN, accents normalisés, chunks + insights)
- **`rlm_list_chunks`** - Lister tous les chunks avec métadonnées

### Organisation multi-projet
- **`rlm_sessions`** - Parcourir les sessions par projet ou domaine
- **`rlm_domains`** - Lister les domaines disponibles pour la catégorisation
- Auto-détection du projet depuis git ou le répertoire de travail
- Filtrage cross-projet sur tous les outils de recherche

### Rétention intelligente
- **`rlm_retention_preview`** - Prévisualiser ce qui serait archivé (dry-run)
- **`rlm_retention_run`** - Archiver les vieux chunks inutilisés, purger les anciens
- **`rlm_restore`** - Restaurer des chunks archivés
- Cycle de vie en 3 zones : **Actif** &rarr; **Archive** (.gz) &rarr; **Purge**
- Système d'immunité : les tags critiques, l'accès fréquent et certains mots-clés protègent un chunk de l'archivage

### Auto-Chunking (Hooks)
- **Hook PreCompact** : Snapshot automatique avant `/compact` ou auto-compact
- **Hook PostToolUse** : Suivi des stats après opérations sur les chunks
- Philosophie user-driven : vous décidez quand chunker, le système sauvegarde avant la perte

### Recherche sémantique (optionnel)
- **Hybride BM25 + cosinus** - Combine le matching par mots-clés avec la similarité vectorielle
- **Auto-embedding** - Les nouveaux chunks sont automatiquement embeddés à la création
- **Deux providers** - Model2Vec (rapide, 256d) ou FastEmbed (précis, 384d)
- **Dégradation gracieuse** - Retombe sur BM25 pur si les dépendances sémantiques ne sont pas installées

#### Comparaison des providers (benchmark sur 108 chunks)

| | Model2Vec (défaut) | FastEmbed |
|---|---|---|
| **Modèle** | `potion-multilingual-128M` | `paraphrase-multilingual-MiniLM-L12-v2` |
| **Dimensions** | 256 | 384 |
| **Embedding 108 chunks** | 0.06s | 1.30s |
| **Latence recherche** | 0.1ms/requête | 1.5ms/requête |
| **Mémoire** | 0.1 Mo | 0.3 Mo |
| **Disque (modèle)** | ~35 Mo | ~230 Mo |
| **Qualité sémantique** | Bonne (orientée mots-clés) | Meilleure (vrai sémantique) |
| **Vitesse** | **21x plus rapide** | Référence |

Chevauchement Top-5 entre providers : ~1.6/5 (résultats différents pour 7/8 requêtes). FastEmbed capture mieux le sens sémantique, Model2Vec penche vers la similarité par mots-clés. La fusion BM25 + cosinus compense les faiblesses des deux.

**Recommandation** : Commencez avec Model2Vec (défaut). Passez à FastEmbed uniquement si vous avez besoin d'une meilleure précision sémantique et pouvez accepter un démarrage plus lent.

```bash
# Model2Vec (défaut) — rapide, ~35 Mo
pip install mcp-rlm-server[semantic]

# FastEmbed — plus précis, ~230 Mo, plus lent
pip install mcp-rlm-server[semantic-fastembed]
export RLM_EMBEDDING_PROVIDER=fastembed

# Comparer les deux providers sur vos données
python3 scripts/benchmark_providers.py

# Backfill des chunks existants (à lancer une fois après installation)
python3 scripts/backfill_embeddings.py
```

### Skills Sub-Agent
- **`/rlm-analyze`** - Analyser un chunk avec un sub-agent isolé
- **`/rlm-parallel`** - Analyser plusieurs chunks en parallèle (pattern Map-Reduce du paper MIT RLM)

---

## Comparaison

| Fonctionnalité | Contexte brut | Letta/MemGPT | **RLM** |
|---------------|---------------|--------------|---------|
| Mémoire persistante | Non | Oui | **Oui** |
| Fonctionne avec Claude Code | N/A | Non (runtime propre) | **MCP natif** |
| Auto-save avant compact | Non | N/A | **Oui (hooks)** |
| Recherche (regex + BM25 + sémantique) | Non | Basique | **Oui** |
| Recherche floue (tolérance typos) | Non | Non | **Oui** |
| Support multi-projet | Non | Non | **Oui** |
| Rétention intelligente (archive/purge) | Non | Basique | **Oui** |
| Analyse sub-agent | Non | Non | **Oui** |
| Installation sans config | N/A | Complexe | **3 lignes** |
| Support FR/EN | N/A | EN uniquement | **Les deux** |
| Coût | Gratuit | Self-hosted | **Gratuit** |

---

## Exemples d'utilisation

### Démarrage de session (recommandé)

```python
# Charger les règles universelles (applicables quel que soit le sujet)
rlm_recall(importance="critical")

# Charger le contexte du sujet en cours
rlm_recall(query="deployment")

# Vérifier l'état de la mémoire
rlm_status()
```

### Sauvegarder et retrouver des insights

```python
# Sauvegarder une règle universelle (chargée à chaque session)
rlm_remember("Toujours déployer LOCAL → VPS, jamais en direct",
             category="decision", importance="critical",
             tags="deploy,workflow")

# Sauvegarder un insight lié à un sujet
rlm_remember("WeasyPrint nécessite du CSS inline pour le rendu PDF",
             category="finding", importance="high",
             tags="weasyprint,pdf")

# Retrouver des insights
rlm_recall(query="source de vérité")
rlm_recall(category="decision")
rlm_recall(importance="critical")    # toutes les règles universelles
```

### Niveaux d'importance

| Niveau | Quand l'utiliser | Chargement |
|--------|-----------------|------------|
| `critical` | Règle universelle (s'applique quel que soit le sujet) | Chaque session |
| `high` | Règle liée à un sujet spécifique | Quand on travaille sur ce sujet |
| `medium` | Info utile, pas bloquante | Sur recherche explicite |

**Test** : "Cette règle s'applique même si on travaille sur un tout autre sujet ?" Si oui → `critical`.

### Gérer l'historique de conversation

```python
# Sauvegarder une discussion importante (typée)
rlm_chunk("Discussion sur le redesign de l'API... [contenu long]",
          summary="Décisions architecture API v2",
          tags="api,architecture",
          chunk_type="session")        # ou "snapshot", "debug"

# Chercher dans tout l'historique
rlm_search("décisions architecture API")      # Classement BM25 + sémantique
rlm_grep("authentication", fuzzy=True)         # Tolérant aux typos

# Lire un chunk spécifique
rlm_peek("2026-01-18_MonProjet_001")
```

### Organisation multi-projet

```python
# Filtrer par projet
rlm_search("problèmes de déploiement", project="MonApp")
rlm_grep("database", project="MonApp", domain="infra")

# Parcourir les sessions
rlm_sessions(project="MonApp")
```

---

## Structure du projet

```
rlm-claude/
├── src/mcp_server/
│   ├── server.py              # Serveur MCP (14 outils)
│   └── tools/
│       ├── memory.py          # Insights (remember/recall/forget)
│       ├── navigation.py      # Chunks (chunk/peek/grep/list)
│       ├── search.py          # Moteur de recherche BM25 + sémantique
│       ├── tokenizer_fr.py    # Tokenisation FR/EN
│       ├── sessions.py        # Gestion multi-sessions
│       ├── retention.py       # Cycle de vie archive/restauration/purge
│       ├── embeddings.py      # Providers d'embedding (Model2Vec, FastEmbed)
│       ├── vecstore.py        # Stockage vectoriel (.npz) pour recherche sémantique
│       └── fileutil.py        # I/O sécurisé (écritures atomiques, validation chemins, verrous)
│
├── hooks/                     # Hooks Claude Code
│   ├── pre_compact_chunk.py   # Auto-save avant /compact (hook PreCompact)
│   └── reset_chunk_counter.py # Reset stats après chunk (hook PostToolUse)
│
├── templates/
│   ├── hooks_settings.json    # Template de config hooks
│   ├── CLAUDE_RLM_SNIPPET.md  # Instructions CLAUDE.md
│   └── skills/                # Skills sub-agent
│
├── context/                   # Stockage (créé à l'install, git-ignored)
│   ├── session_memory.json    # Insights
│   ├── index.json             # Index des chunks
│   ├── chunks/                # Historique de conversation
│   ├── archive/               # Archives compressées (.gz)
│   ├── embeddings.npz         # Vecteurs sémantiques (Phase 8)
│   └── sessions.json          # Index des sessions
│
├── install.sh                 # Installeur en une commande
└── README.md
```

---

## Configuration

### Configuration des hooks

L'installeur configure automatiquement les hooks dans `~/.claude/settings.json` :

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "manual",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/pre_compact_chunk.py" }]
      },
      {
        "matcher": "auto",
        "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/pre_compact_chunk.py" }]
      }
    ],
    "PostToolUse": [{
      "matcher": "mcp__rlm-server__rlm_chunk",
      "hooks": [{ "type": "command", "command": "python3 ~/.claude/rlm/hooks/reset_chunk_counter.py" }]
    }]
  }
}
```

### Domaines personnalisés

Organisez vos chunks par sujet avec des domaines personnalisés :

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

Éditez `context/domains.json` après l'installation.

---

## Installation manuelle

Si vous préférez installer manuellement :

```bash
pip install -e ".[all]"
claude mcp add rlm-server -- python3 -m mcp_server
mkdir -p ~/.claude/rlm/hooks
cp hooks/*.py ~/.claude/rlm/hooks/
chmod +x ~/.claude/rlm/hooks/*.py
mkdir -p ~/.claude/skills/rlm-analyze ~/.claude/skills/rlm-parallel
cp templates/skills/rlm-analyze/skill.md ~/.claude/skills/rlm-analyze/
cp templates/skills/rlm-parallel/skill.md ~/.claude/skills/rlm-parallel/
```

Puis configurez les hooks dans `~/.claude/settings.json` (voir ci-dessus).

## Désinstallation

```bash
./uninstall.sh              # Interactif (choix de garder ou supprimer les données)
./uninstall.sh --keep-data  # Supprime la config RLM, garde vos chunks/insights
./uninstall.sh --all        # Supprime tout
./uninstall.sh --dry-run    # Prévisualiser ce qui serait supprimé
```

---

## Sécurité

RLM inclut des protections intégrées pour un fonctionnement sûr :

- **Prévention du path traversal** - Les IDs de chunks sont validés par une allowlist stricte (`[a-zA-Z0-9_.-&]`), et les chemins résolus sont vérifiés pour rester dans le répertoire de stockage
- **Écritures atomiques** - Tous les fichiers JSON et chunks utilisent le pattern write-to-temp-then-rename, empêchant la corruption en cas d'interruption ou de crash
- **Verrouillage fichier** - Les opérations concurrentes de lecture-modification-écriture sur les index partagés utilisent des verrous exclusifs `fcntl.flock`
- **Limites de taille** - Les chunks sont limités à 2 Mo, et la décompression gzip (restauration d'archive) est plafonnée à 10 Mo pour prévenir l'épuisement des ressources
- **Hachage SHA-256** - La déduplication de contenu utilise SHA-256 (pas MD5)

Toutes les primitives de sécurité I/O sont centralisées dans `mcp_server/tools/fileutil.py`.

---

## Dépannage

### "MCP server not found"

```bash
claude mcp list                    # Vérifier les serveurs
claude mcp remove rlm-server       # Supprimer si existe
claude mcp add rlm-server -- python3 -m mcp_server
```

### "Les hooks ne fonctionnent pas"

```bash
cat ~/.claude/settings.json | grep -A 10 "PreCompact"  # Vérifier la config hooks
ls ~/.claude/rlm/hooks/                                  # Vérifier les hooks installés
```

---

## Roadmap

- [x] **Phase 1** : Outils mémoire (remember/recall/forget/status)
- [x] **Phase 2** : Outils navigation (chunk/peek/grep/list)
- [x] **Phase 3** : Auto-chunking + skills sub-agent
- [x] **Phase 4** : Production (auto-résumé, dédup, suivi d'accès)
- [x] **Phase 5** : Avancé (recherche BM25, grep flou, multi-sessions, rétention)
- [x] **Phase 6** : Production-ready (tests, CI/CD, PyPI)
- [x] **Phase 7** : Inspiré MAGMA (filtrage temporel, extraction d'entités)
- [x] **Phase 8** : Recherche sémantique hybride (BM25 + cosinus, Model2Vec)
- [x] **Phase 9** : Chunking typé — paramètre `chunk_type` (snapshot/session/debug/redirection insight)

Voir [ROADMAP.md](ROADMAP.md) pour les détails.

---

## Inspiré par

### Articles de recherche
- [Paper RLM (MIT CSAIL)](https://arxiv.org/abs/2512.24601) - Zhang et al., Dec 2025 - "Recursive Language Models" — architecture fondatrice (chunk/peek/grep, analyse sub-agent)
- [MAGMA (arXiv:2601.03236)](https://arxiv.org/abs/2601.03236) - Jan 2026 - "Memory-Augmented Generation with Memory Agents" — filtrage temporel, extraction d'entités (Phase 7)

### Bibliothèques & outils
- [Model2Vec](https://github.com/MinishLab/model2vec) - Embeddings statiques pour recherche sémantique rapide (Phase 8)
- [BM25S](https://github.com/xhluca/bm25s) - Implémentation BM25 rapide en Python pur (Phase 5)
- [FastEmbed](https://github.com/qdrant/fastembed) - Embeddings ONNX, provider optionnel (Phase 8)
- [Letta/MemGPT](https://github.com/letta-ai/letta) - Framework mémoire pour agents IA — inspiration initiale

### Standards & plateforme
- [MCP Specification](https://modelcontextprotocol.io/specification) - Model Context Protocol
- [Claude Code Hooks](https://docs.anthropic.com/claude-code/hooks) - Hooks PreCompact / PostToolUse

---

## Contribuer

### Traductions

Le dépôt est maintenu en anglais. Les fichiers destinés aux utilisateurs peuvent être traduits dans votre langue :

| Fichier | Rôle | Traductions bienvenues |
|---------|------|----------------------|
| `README.md` | Documentation principale | `README.xx.md` (ex : `README.fr.md`, `README.ja.md`) |
| `templates/CLAUDE_RLM_SNIPPET.md` | Instructions CLAUDE.md | `CLAUDE_RLM_SNIPPET.xx.md` |

Le code, les commentaires et les messages de commit restent en anglais.

---

## Auteurs

- Ahmed MAKNI ([@EncrEor](https://github.com/EncrEor))
- Claude Opus 4.5 (R&D conjointe)

## Licence

MIT License - voir [LICENSE](LICENSE)
