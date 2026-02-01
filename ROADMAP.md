# RLM - Roadmap

> Pistes futures pour RLM - Memoire infinie pour Claude Code
> **Derniere MAJ** : 2026-01-24 (v0.9.0 - Systeme Simplifie)

---

## Vue d'ensemble

| Phase | Statut | Description |
|-------|--------|-------------|
| **Phase 1** | VALIDEE | Memory tools (remember/recall/forget/status) |
| **Phase 2** | VALIDEE | Navigation tools (chunk/peek/grep/list) |
| **Phase 3** | VALIDEE (v0.9.0) | Auto-chunking simplifie (PreCompact + user-driven) |
| **Phase 4** | VALIDEE | Production (auto-summary, dedup, access tracking) |
| **Phase 5** | VALIDEE | Avance (BM25, fuzzy, multi-sessions, retention) |
| **Phase 6** | EN COURS | Production-Ready (tests, CI/CD, PyPI) |

---

## Phase 4 : Production

**Objectif** : Rendre RLM production-ready avec optimisations et metriques.

### 4.1 Resumes automatiques

| Tache | Description | Priorite |
|-------|-------------|----------|
| Auto-summarization | Resume automatique des chunks longs | P1 |
| Hierarchie de resumes | Resume de resumes pour navigation rapide | P2 |
| Titre intelligent | Generation automatique de titres pertinents | P2 |

**Implementation proposee** :
```python
# Dans navigation.py
def auto_summarize(content: str, max_tokens: int = 200) -> str:
    """Generate a summary using local model or simple extraction."""
    # Option 1: Extraction des premieres phrases
    # Option 2: Appel a un modele local (llama.cpp)
    pass
```

### 4.2 Compression et deduplication

| Tache | Description | Priorite |
|-------|-------------|----------|
| Detection doublons | Eviter de stocker le meme contenu 2 fois | P1 |
| Compression | Compresser les vieux chunks (gzip) | P2 |
| Archivage | Deplacer vieux chunks vers archive | P3 |

### 4.3 Metriques d'usage

| Tache | Description | Priorite |
|-------|-------------|----------|
| Token counter | Compter les tokens reellement utilises | P1 |
| Usage stats | Frequence d'acces aux chunks | P2 |
| Dashboard | Visualisation simple des stats | P3 |

---

## Phase 5 : RLM Authentique

**Objectif** : Suivre le paper MIT avec BM25 + sub-agents, embeddings en backup.

**Changement strategique (2026-01-18)** : Apres recherche approfondie, on decouvre que le paper RLM MIT n'utilise PAS d'embeddings. Letta benchmark confirme : filesystem + grep = 74% accuracy > embeddings.

### 5.1 BM25 Ranking - FAIT

| Tache | Description | Statut |
|-------|-------------|--------|
| Tool `rlm_search` | Recherche BM25S (500x plus rapide) | FAIT |
| Tokenization FR/EN | Stopwords, normalisation | FAIT |
| Scoring pertinence | Trier par score BM25 | FAIT |

**Implementation** : BM25S avec tokenizer FR/EN zero dependance
- `mcp_server/tools/search.py`
- `mcp_server/tools/tokenizer_fr.py`

### 5.2 Grep++ (Fuzzy Search) - FAIT (v0.6.1)

**Objectif** : Ameliorer `rlm_grep` avec tolerance aux typos et scoring de pertinence.

**Implemente le 2026-01-19** :
- `grep_fuzzy()` dans `navigation.py`
- Parametres `fuzzy=True, fuzzy_threshold=80` dans `rlm_grep`
- Dependance optionnelle `thefuzz>=0.22.1`
- 16 tests dans `tests/test_grep_fuzzy.py`

**Pourquoi c'etait necessaire** :
- Avec 100+ chunks, les typos deviennent un vrai probleme
- "buget" ne trouve pas "budget", "validaton" ne trouve pas "validation"
- BM25 aide mais ne resout pas les typos dans les patterns de recherche

---

#### 5.2.1 Fuzzy Matching

**Dependance** : `thefuzz>=0.22.1` (ex-fuzzywuzzy, plus maintenu)

**Implementation proposee** :

```python
# Dans mcp_server/tools/navigation.py

from thefuzz import fuzz, process

def grep_fuzzy(
    pattern: str,
    threshold: int = 80,
    limit: int = 10
) -> dict:
    """
    Fuzzy grep - trouve des matches meme avec typos.

    Args:
        pattern: Texte a chercher (pas regex)
        threshold: Score minimum de similarite (0-100, default 80)
        limit: Nombre max de resultats

    Returns:
        Matches tries par score de similarite
    """
    matches = []

    for chunk_file in CHUNKS_DIR.glob("*.md"):
        content = chunk_file.read_text()

        # Chercher ligne par ligne
        for i, line in enumerate(content.split('\n')):
            # Score de similarite partielle (trouve sous-chaines)
            score = fuzz.partial_ratio(pattern.lower(), line.lower())

            if score >= threshold:
                matches.append({
                    "chunk_id": chunk_file.stem,
                    "line": i + 1,
                    "score": score,
                    "text": line.strip()[:100]  # Tronquer pour lisibilite
                })

    # Trier par score decroissant
    matches.sort(key=lambda x: x["score"], reverse=True)

    return {"matches": matches[:limit]}
```

**Nouveau parametre `rlm_grep`** :

```python
@mcp.tool()
def rlm_grep(
    pattern: str,
    limit: int = 10,
    fuzzy: bool = False,        # NOUVEAU
    fuzzy_threshold: int = 80,  # NOUVEAU
    project: str = "",
    domain: str = ""
) -> str:
    """
    Search pattern across chunks.

    Args:
        pattern: Regex pattern OR text (if fuzzy=True)
        limit: Max results
        fuzzy: Enable fuzzy matching (tolerates typos)
        fuzzy_threshold: Min similarity score 0-100 (default 80)
        project: Filter by project
        domain: Filter by domain
    """
    if fuzzy:
        return grep_fuzzy(pattern, fuzzy_threshold, limit)
    else:
        return grep_exact(pattern, limit, project, domain)
```

**Exemples d'usage** :

```python
# Recherche exacte (actuel)
rlm_grep("business plan")

# Recherche fuzzy (nouveau)
rlm_grep("buisness plan", fuzzy=True)  # Trouve "business plan"
rlm_grep("validaton", fuzzy=True)       # Trouve "validation"
rlm_grep("scenario", fuzzy=True, fuzzy_threshold=70)  # Plus tolerant
```

---

#### 5.2.2 Multi-pattern (AND/OR)

**Objectif** : Chercher plusieurs termes simultanement.

```python
def grep_multi(
    patterns: list[str],
    mode: str = "AND",  # "AND" ou "OR"
    limit: int = 10
) -> dict:
    """
    Multi-pattern grep.

    AND mode: Toutes les patterns doivent matcher
    OR mode: Au moins une pattern doit matcher
    """
    matches = []

    for chunk_file in CHUNKS_DIR.glob("*.md"):
        content = chunk_file.read_text().lower()

        if mode == "AND":
            if all(p.lower() in content for p in patterns):
                matches.append({"chunk_id": chunk_file.stem})
        else:  # OR
            if any(p.lower() in content for p in patterns):
                matches.append({"chunk_id": chunk_file.stem})

    return {"matches": matches[:limit]}
```

**Syntaxe proposee** :

```python
rlm_grep("business AND plan")      # Les deux termes
rlm_grep("odoo OR erp")            # L'un ou l'autre
rlm_grep("joy juice NOT tunisie")  # Exclusion (P2)
```

---

#### 5.2.3 Scoring et Ranking

**Objectif** : Trier les resultats grep par pertinence (comme BM25).

```python
def grep_scored(pattern: str, limit: int = 10) -> dict:
    """
    Grep avec scoring de pertinence.

    Score = nombre d'occurrences * position bonus
    """
    matches = []

    for chunk_file in CHUNKS_DIR.glob("*.md"):
        content = chunk_file.read_text()
        occurrences = len(re.findall(pattern, content, re.IGNORECASE))

        if occurrences > 0:
            # Bonus si match dans le summary (debut du fichier)
            summary_match = 1.5 if pattern.lower() in content[:200].lower() else 1.0
            score = occurrences * summary_match

            matches.append({
                "chunk_id": chunk_file.stem,
                "occurrences": occurrences,
                "score": score
            })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return {"matches": matches[:limit]}
```

---

#### 5.2.4 Tests de validation

```python
# tests/test_grep_fuzzy.py

def test_fuzzy_finds_typos():
    """Fuzzy grep trouve malgre les typos."""
    # Setup: chunk avec "validation"
    create_chunk("test_001", "La validation du process est complete.")

    # Typo dans la recherche
    result = grep_fuzzy("validaton", threshold=80)
    assert len(result["matches"]) >= 1
    assert result["matches"][0]["chunk_id"] == "test_001"

def test_fuzzy_threshold():
    """Le threshold controle la tolerance."""
    create_chunk("test_002", "Configuration du systeme.")

    # Threshold eleve = strict
    result_strict = grep_fuzzy("config", threshold=90)
    # Threshold bas = tolerant
    result_tolerant = grep_fuzzy("konfig", threshold=60)

    assert len(result_tolerant["matches"]) >= len(result_strict["matches"])

def test_multi_pattern_and():
    """AND mode requiert tous les termes."""
    create_chunk("test_003", "Business plan Joy Juice 2026")
    create_chunk("test_004", "Business meeting notes")

    result = grep_multi(["business", "juice"], mode="AND")
    assert "test_003" in [m["chunk_id"] for m in result["matches"]]
    assert "test_004" not in [m["chunk_id"] for m in result["matches"]]
```

---

#### 5.2.5 Dependances

```toml
# pyproject.toml
[project.optional-dependencies]
fuzzy = ["thefuzz>=0.22.1"]
all = ["mcp-rlm-server[search,fuzzy,dev]"]
```

**Note** : `thefuzz` est pure Python, pas de dependance C.
Alternative si performance critique : `rapidfuzz` (Cython, 10x plus rapide).

---

#### 5.2.6 Checklist Phase 5.2

| Tache | Priorite | Statut |
|-------|----------|--------|
| Ajouter dependance `thefuzz` | P0 | FAIT |
| Implementer `grep_fuzzy()` | P0 | FAIT |
| Ajouter params `fuzzy` a `rlm_grep` | P0 | FAIT |
| Tests fuzzy matching | P0 | FAIT (16 tests) |
| Implementer multi-pattern (AND/OR) | P1 | A FAIRE |
| Implementer scoring | P2 | FAIT (score dans resultats) |
| Documentation usage | P1 | FAIT |

**Complete en 1 session (2026-01-19)**

---

### 5.3 Sub-agents Paralleles - FAIT

| Tache | Description | Statut |
|-------|-------------|--------|
| Partition + Map | Analyser 3 chunks en parallele | FAIT |
| Skill `/rlm-parallel` | Pattern auto-applique par Claude | FAIT |
| Merger intelligent | Synthetiser avec citations [chunk_id] | FAIT |

**Implementation** : Task tools paralleles (natif Claude Code, $0)
**Note** : MCP Sampling non supporte par Claude Code (issue #1785) → Skill = seule option

### 5.4 Embeddings (BACKUP)

**Activer SEULEMENT SI** : BM25 < 70% precision ou queries semantiques pures echouent.

| Tache | Description | Priorite |
|-------|-------------|----------|
| Nomic Embed v2 MoE | Modele multilingue leger | P3 |
| LanceDB | Stockage vectoriel Rust | P3 |
| Dimensions Matryoshka | 384 dims (tronque de 768) | P3 |

### 5.5 Multi-sessions - COMPLETE

**Objectif** : Organiser les chunks par projet/domaine pour navigation cross-session.

| Sous-phase | Description | Statut |
|------------|-------------|--------|
| **5.5a** | Format ID enrichi + detection projet | FAIT |
| **5.5b** | Sessions tracking + tools | FAIT |
| **5.5c** | Filtres project/domain dans grep/search | FAIT |

**Nouveau format ID** : `{date}_{project}_{seq}[_{ticket}][_{domain}]`
- Exemple : `2026-01-18_RLM_001_r&d`
- Exemple : `2026-01-18_JoyJuice_005_TIC-123_bp`

**Implementation complete** (2026-01-18) :
- `_detect_project()` - Detection auto via env/git/cwd
- `parse_chunk_id()` - Parser flexible format 1.0 & 2.0
- `_generate_chunk_id(project, ticket, domain)` - Nouveau format
- `sessions.py` - Gestion sessions (list_sessions, list_domains)
- `rlm_sessions` / `rlm_domains` - Tools MCP
- `rlm_grep` / `rlm_search` - Filtres project/domain ajoutes
- `domains.json.example` - Exemple Joy Juice (template)
- `domains.json` - Auto-genere localement (generique)

**Decisions validees** :
- Chunks existants restent en format 1.0 (backward compat)
- Domaines flexibles (pas de validation stricte)
- Detection auto projet via git root ou cwd
- Portabilite : domains.json/sessions.json sont locaux (git-ignored)

### 5.6 Retention (Gestion du cycle de vie) - FAIT (v0.7.0)

**Objectif** : Eviter l'accumulation infinie de chunks avec archivage intelligent et purge automatique.

**Implemente le 2026-01-19** :
- `mcp_server/tools/retention.py` - Core logic (~420 LOC)
- 3 nouveaux tools MCP : `rlm_retention_preview`, `rlm_retention_run`, `rlm_restore`
- Auto-restore dans `peek()` - Chunks archives restaures automatiquement
- 20 tests dans `tests/test_retention.py`

**Pourquoi c'etait necessaire** :
- 17 chunks en une demi-journee → 100+ en quelques jours d'usage intensif
- Sans retention, le grep/search devient lent et bruite
- Besoin de garder les chunks importants et archiver/purger les autres

---

#### 5.6.1 Architecture 3 Zones

```
┌─────────────────────────────────────────────────────────────┐
│                    ZONE 1 : ACTIFS                           │
│  context/chunks/*.md                                         │
│  - Cherchables via rlm_grep / rlm_search                    │
│  - Compteur d'acces actif                                   │
│  - Pas de limite de taille                                  │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Regles d'archivage (voir 5.6.2)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    ZONE 2 : ARCHIVES                         │
│  context/archive/*.md.gz (gzip)                             │
│  - Toujours cherchables (decompression lazy)                │
│  - Restauration auto si rlm_peek                            │
│  - Compression ~70% reduction taille                        │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ 180 jours en archive sans acces
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    ZONE 3 : PURGES                           │
│  Suppression definitive                                      │
│  - Log conserve : date, summary, tags (pas le contenu)      │
│  - context/purge_log.json                                   │
└─────────────────────────────────────────────────────────────┘
```

---

#### 5.6.2 Regles d'Archivage

Un chunk est **candidat a l'archivage** si :
- Age > 30 jours depuis creation
- `access_count == 0` (jamais consulte)
- Pas d'immunite (voir 5.6.3)

**Implementation** :

```python
from datetime import datetime, timedelta

ARCHIVE_AFTER_DAYS = 30
PURGE_AFTER_DAYS = 180

def get_archive_candidates() -> list[dict]:
    """Retourne les chunks candidats a l'archivage."""
    index = load_index()
    candidates = []
    threshold = datetime.now() - timedelta(days=ARCHIVE_AFTER_DAYS)

    for chunk in index["chunks"]:
        created = datetime.fromisoformat(chunk["created"])
        if (
            created < threshold and
            chunk.get("access_count", 0) == 0 and
            not is_immune(chunk)
        ):
            candidates.append(chunk)

    return candidates
```

---

#### 5.6.3 Immunite Automatique

Un chunk est **immune** (jamais archive/purge) si :

| Condition | Justification |
|-----------|---------------|
| Tag `critical` ou `decision` | Marque explicite d'importance |
| Tag `keep` ou `important` | Demande de conservation |
| Contient "DECISION:" ou "IMPORTANT:" | Detection par contenu |
| `access_count >= 3` | Chunk frequemment utilise |
| Lie a un ticket non-ferme | Travail en cours (optionnel) |

**Implementation** :

```python
PROTECTED_TAGS = {"critical", "decision", "keep", "important"}
PROTECTED_KEYWORDS = ["DECISION:", "IMPORTANT:", "A RETENIR:"]

def is_immune(chunk: dict) -> bool:
    """Determine si un chunk est protege de l'archivage."""

    # Tags protecteurs
    chunk_tags = set(chunk.get("tags", []))
    if chunk_tags & PROTECTED_TAGS:
        return True

    # Acces frequent
    if chunk.get("access_count", 0) >= 3:
        return True

    # Contenu protecteur (necessite lecture du fichier)
    chunk_file = CHUNKS_DIR / f"{chunk['id']}.md"
    if chunk_file.exists():
        content = chunk_file.read_text().upper()
        if any(kw in content for kw in PROTECTED_KEYWORDS):
            return True

    return False
```

---

#### 5.6.4 Compression Gzip

```python
import gzip
import shutil

def archive_chunk(chunk_id: str) -> bool:
    """Archive un chunk (compression gzip)."""
    src = CHUNKS_DIR / f"{chunk_id}.md"
    dst = ARCHIVE_DIR / f"{chunk_id}.md.gz"

    if not src.exists():
        return False

    ARCHIVE_DIR.mkdir(exist_ok=True)

    # Compression
    with open(src, 'rb') as f_in:
        with gzip.open(dst, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    # Supprimer original
    src.unlink()

    # Mettre a jour index
    update_index_archived(chunk_id)

    return True

def restore_chunk(chunk_id: str) -> bool:
    """Restaure un chunk archive."""
    src = ARCHIVE_DIR / f"{chunk_id}.md.gz"
    dst = CHUNKS_DIR / f"{chunk_id}.md"

    if not src.exists():
        return False

    # Decompression
    with gzip.open(src, 'rb') as f_in:
        with open(dst, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    # Supprimer archive
    src.unlink()

    # Mettre a jour index
    update_index_restored(chunk_id)

    return True
```

---

#### 5.6.5 Nouveaux Tools MCP

```python
@mcp.tool()
def rlm_retention_preview() -> str:
    """
    Preview retention actions without executing.

    Shows what would be archived or purged based on current rules.
    Use this to validate before running rlm_retention_run().
    """
    candidates = get_archive_candidates()
    purge_candidates = get_purge_candidates()

    output = "Retention Preview (dry-run)\n"
    output += "=" * 40 + "\n\n"

    output += f"Archive candidates ({len(candidates)}):\n"
    for c in candidates[:10]:
        output += f"  - {c['id']} ({c.get('summary', 'No summary')[:40]})\n"

    output += f"\nPurge candidates ({len(purge_candidates)}):\n"
    for c in purge_candidates[:10]:
        output += f"  - {c['id']} (archived {c.get('archived_date', 'unknown')})\n"

    return output

@mcp.tool()
def rlm_retention_run(archive: bool = True, purge: bool = False) -> str:
    """
    Execute retention actions.

    Args:
        archive: Archive old unused chunks (default: True)
        purge: Purge very old archives (default: False, requires explicit)

    Returns:
        Summary of actions taken
    """
    results = {"archived": 0, "purged": 0, "errors": []}

    if archive:
        for chunk in get_archive_candidates():
            try:
                archive_chunk(chunk["id"])
                results["archived"] += 1
            except Exception as e:
                results["errors"].append(f"{chunk['id']}: {e}")

    if purge:
        for chunk in get_purge_candidates():
            try:
                purge_chunk(chunk["id"])
                results["purged"] += 1
            except Exception as e:
                results["errors"].append(f"{chunk['id']}: {e}")

    return f"Retention complete: {results['archived']} archived, {results['purged']} purged"

@mcp.tool()
def rlm_restore(chunk_id: str) -> str:
    """
    Restore an archived chunk back to active storage.

    Args:
        chunk_id: ID of the archived chunk

    Returns:
        Confirmation message
    """
    if restore_chunk(chunk_id):
        return f"Chunk {chunk_id} restored to active storage"
    else:
        return f"Chunk {chunk_id} not found in archives"
```

---

#### 5.6.6 Auto-restore sur Peek

Quand on fait `rlm_peek` sur un chunk archive, il est automatiquement restaure :

```python
def peek(chunk_id: str, start: int = 0, end: int = -1) -> dict:
    chunk_file = CHUNKS_DIR / f"{chunk_id}.md"

    # Si pas dans actifs, chercher dans archives
    if not chunk_file.exists():
        archive_file = ARCHIVE_DIR / f"{chunk_id}.md.gz"
        if archive_file.exists():
            # Auto-restore
            restore_chunk(chunk_id)
        else:
            return {"status": "error", "message": f"Chunk {chunk_id} not found"}

    # ... reste du code peek normal
```

---

#### 5.6.7 Structure Fichiers

```
context/
├── chunks/              # Zone 1 - Actifs
│   ├── 2026-01-18_001.md
│   └── ...
├── archive/             # Zone 2 - Archives (NOUVEAU)
│   ├── 2025-12-01_001.md.gz
│   └── ...
├── index.json           # Index actifs
├── archive_index.json   # Index archives (NOUVEAU)
└── purge_log.json       # Log des purges (NOUVEAU)
```

---

#### 5.6.8 Configuration

```python
# Dans mcp_server/tools/retention.py

# Delais configurables
ARCHIVE_AFTER_DAYS = 30    # Archiver apres 30 jours sans acces
PURGE_AFTER_DAYS = 180     # Purger apres 180 jours en archive

# Seuils
MIN_ACCESS_FOR_IMMUNITY = 3  # Chunks accedes 3+ fois sont immunises

# Tags proteges
PROTECTED_TAGS = {"critical", "decision", "keep", "important"}
```

---

#### 5.6.9 Tests de validation

```python
# tests/test_retention.py

def test_archive_candidate_detection():
    """Chunks vieux et non-accedes sont candidats."""
    # Setup: chunk de 35 jours, jamais accede
    create_old_chunk("old_001", days_ago=35, access_count=0)

    candidates = get_archive_candidates()
    assert "old_001" in [c["id"] for c in candidates]

def test_immunity_by_tag():
    """Chunks avec tag critical sont immunises."""
    create_old_chunk("critical_001", days_ago=60, access_count=0, tags=["critical"])

    candidates = get_archive_candidates()
    assert "critical_001" not in [c["id"] for c in candidates]

def test_immunity_by_access():
    """Chunks frequemment accedes sont immunises."""
    create_old_chunk("popular_001", days_ago=60, access_count=5)

    candidates = get_archive_candidates()
    assert "popular_001" not in [c["id"] for c in candidates]

def test_archive_and_restore():
    """Archivage puis restauration fonctionne."""
    create_chunk("test_archive", "Contenu test")

    # Archive
    assert archive_chunk("test_archive")
    assert not (CHUNKS_DIR / "test_archive.md").exists()
    assert (ARCHIVE_DIR / "test_archive.md.gz").exists()

    # Restore
    assert restore_chunk("test_archive")
    assert (CHUNKS_DIR / "test_archive.md").exists()
    assert not (ARCHIVE_DIR / "test_archive.md.gz").exists()

def test_auto_restore_on_peek():
    """Peek sur archive declenche auto-restore."""
    create_chunk("auto_restore", "Contenu auto")
    archive_chunk("auto_restore")

    # Peek devrait restaurer automatiquement
    result = peek("auto_restore")
    assert result["status"] == "ok"
    assert (CHUNKS_DIR / "auto_restore.md").exists()
```

---

#### 5.6.10 Checklist Phase 5.6

| Tache | Priorite | Statut |
|-------|----------|--------|
| Creer `mcp_server/tools/retention.py` | P0 | FAIT |
| Implementer `is_immune()` | P0 | FAIT |
| Implementer `archive_chunk()` / `restore_chunk()` | P0 | FAIT |
| Implementer `get_archive_candidates()` | P0 | FAIT |
| Tool `rlm_retention_preview` | P0 | FAIT |
| Tool `rlm_retention_run` | P0 | FAIT |
| Tool `rlm_restore` | P0 | FAIT |
| Auto-restore dans `peek()` | P1 | FAIT |
| `archive_index.json` gestion | P1 | FAIT |
| `purge_log.json` gestion | P2 | FAIT |
| Tests complets (20 tests) | P0 | FAIT |
| Documentation usage | P1 | FAIT |

**Complete en 1 session (2026-01-19)**

---

### 5.7 Export et Import (Bonus)

| Tache | Description | Priorite |
|-------|-------------|----------|
| Export JSON | Exporter toute la memoire en JSON | P3 |
| Import | Restaurer depuis export | P3 |
| Backup automatique | Sauvegarder periodiquement (cron) | P3 |

**Note** : P3 = nice-to-have, pas requis pour MVP+.

**Documentation complete** : `docs/PHASE5_PLAN.md`

---

## Phase 6 : Production-Ready (MVP+ Communaute)

**Objectif** : Preparer RLM pour distribution publique et adoption communautaire.

**Criteres de succes** :
- Tests automatises avec coverage >= 80%
- CI/CD fonctionnel (tests + lint sur chaque PR)
- Publication PyPI : `uvx mcp-rlm-server` fonctionne
- Documentation complete avec exemples
- Zero regression sur features existantes

---

### 6.1 Tests Automatises - P0

**Structure proposee** :

```
tests/
├── conftest.py              # Fixtures (temp dirs, sample data)
├── test_memory.py           # rlm_remember, rlm_recall, rlm_forget
├── test_navigation.py       # rlm_chunk, rlm_peek, rlm_grep
├── test_search.py           # rlm_search (BM25)
├── test_sessions.py         # rlm_sessions, rlm_domains
├── test_tokenizer.py        # tokenize_fr, normalize_accent
└── integration/
    └── test_mcp_server.py   # Tests end-to-end FastMCP
```

**Types de tests** :

| Type | Couverture | Outils |
|------|------------|--------|
| Unit | Logique metier isolee | pytest, mocks |
| Integration | Client-serveur in-memory | FastMCP Client |
| Regression | Features existantes | pytest markers |

**Exemples de tests critiques** :

```python
# test_memory.py
def test_remember_recall_cycle():
    """Insight cree puis retrouve."""
    result = remember("Test insight", category="fact")
    assert "created" in result

    recalled = recall(query="Test")
    assert len(recalled) >= 1

# test_navigation.py
def test_chunk_deduplication():
    """Meme contenu = meme chunk (pas de doublon)."""
    r1 = chunk("Contenu identique")
    r2 = chunk("Contenu identique")
    assert r1["chunk_id"] == r2["chunk_id"]

# test_search.py
def test_bm25_french_accents():
    """'realiste' trouve 'réaliste'."""
    chunk("Scenario realiste pour 2026", tags="test")
    results = search("réaliste")
    assert len(results) >= 1
```

**Dependances test** :

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=4.0",
]
```

---

### 6.2 CI/CD GitHub Actions - P0

**Fichier `.github/workflows/ci.yml`** :

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest --cov=mcp_server --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff
      - run: ruff check mcp_server/
```

**Badges README** :

```markdown
[![Tests](https://github.com/EncrEor/rlm-claude/actions/workflows/ci.yml/badge.svg)](https://github.com/EncrEor/rlm-claude/actions)
[![Coverage](https://codecov.io/gh/EncrEor/rlm-claude/branch/main/graph/badge.svg)](https://codecov.io/gh/EncrEor/rlm-claude)
[![PyPI](https://img.shields.io/pypi/v/mcp-rlm-server)](https://pypi.org/project/mcp-rlm-server/)
```

---

### 6.3 Distribution PyPI - P1

**Fichier `pyproject.toml`** (remplace requirements.txt) :

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mcp-rlm-server"
version = "0.6.0"
description = "Infinite memory for Claude Code - MCP server with auto-chunking"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
authors = [
    { name = "Ahmed MAKNI", email = "ahmed@joyjuice.co" }
]
keywords = ["mcp", "claude", "memory", "llm", "context-management"]
classifiers = [
    "Development Status :: 4 - Beta",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]
dependencies = [
    "mcp>=1.0.0,<2.0.0",
    "pydantic>=2.0.0,<3.0.0",
]

[project.optional-dependencies]
search = ["bm25s>=0.2.0"]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
]
all = ["mcp-rlm-server[search,dev]"]

[project.scripts]
mcp-rlm-server = "mcp_server.server:main"

[project.urls]
Homepage = "https://github.com/EncrEor/rlm-claude"
Documentation = "https://github.com/EncrEor/rlm-claude#readme"
Repository = "https://github.com/EncrEor/rlm-claude"
Issues = "https://github.com/EncrEor/rlm-claude/issues"

[tool.hatch.build.targets.wheel]
packages = ["mcp_server"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py310"
```

**Installation utilisateur** :

```bash
# Installation rapide (recommande)
uvx mcp-rlm-server

# Installation permanente
pip install mcp-rlm-server

# Avec recherche BM25
pip install mcp-rlm-server[search]
```

**Publication** :

```bash
# Build
python -m build

# Test sur TestPyPI
twine upload --repository testpypi dist/*

# Publication finale
twine upload dist/*
```

---

### 6.4 Robustesse - P1

**6.4.1 Logging systeme**

```python
# mcp_server/utils/logging.py
import logging
from pathlib import Path

LOG_DIR = Path.home() / ".claude" / "rlm" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "rlm.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("rlm")
```

**6.4.2 Atomic file writes**

```python
# Remplacer les writes directs par :
import tempfile
import shutil

def atomic_write(path: Path, content: str):
    """Ecriture atomique (evite corruption si crash)."""
    fd, tmp_path = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        shutil.move(tmp_path, path)
    except:
        os.unlink(tmp_path)
        raise
```

**6.4.3 Error handling centralise**

```python
# Exceptions custom
class RLMError(Exception):
    """Base exception for RLM."""
    pass

class ChunkNotFoundError(RLMError):
    """Chunk ID does not exist."""
    pass

class InvalidPatternError(RLMError):
    """Invalid regex pattern."""
    pass

# Usage dans tools
try:
    regex = re.compile(pattern)
except re.error as e:
    raise InvalidPatternError(f"Invalid regex: {e}")
```

---

### 6.5 Documentation - P1

**6.5.1 CHANGELOG.md** (retrospectif)

```markdown
# Changelog

All notable changes to RLM are documented here.

## [0.6.0] - 2026-01-18 - Phase 5.5 Multi-sessions

### Added
- `rlm_sessions` - List sessions by project/domain
- `rlm_domains` - List available domains
- New chunk ID format: `{date}_{project}_{seq}_{ticket}_{domain}`
- Project auto-detection via git/cwd
- Cross-session filtering in `rlm_grep` and `rlm_search`

### Fixed
- Session tracking now properly registers chunks (bugfix b691d9f)

## [0.5.1] - 2026-01-18 - Phase 5.1 BM25

### Added
- `rlm_search` - BM25 ranking search
- French/English tokenization with accent normalization
- Zero-dependency tokenizer

## [0.5.0] - 2026-01-18 - Phase 5.3 Sub-agents

### Added
- Skill `/rlm-parallel` for parallel chunk analysis
- Pattern "Partition + Map" from MIT paper

## [0.4.0] - 2026-01-18 - Phase 4 Production

### Added
- Auto-summarization when no summary provided
- Duplicate detection via content hash
- Access counting for chunks
- Most-accessed chunks in `rlm_status`

### Fixed
- Hook Stop format (systemMessage instead of additionalContext)

## [0.3.0] - 2026-01-18 - Phase 3 Auto-chunking

### Added
- Auto-chunking via Claude Code hooks
- Skill `/rlm-analyze` for sub-agent analysis
- `install.sh` one-command installation

## [0.2.0] - 2026-01-18 - Phase 2 Navigation

### Added
- `rlm_chunk` - Save content to external chunk
- `rlm_peek` - Read chunk content
- `rlm_grep` - Search patterns across chunks
- `rlm_list_chunks` - List available chunks

## [0.1.0] - 2026-01-18 - Phase 1 Memory

### Added
- `rlm_remember` - Save insights
- `rlm_recall` - Retrieve insights
- `rlm_forget` - Delete insights
- `rlm_status` - System status
```

**6.5.2 README badges et section Dev**

Ajouter en haut du README :

```markdown
[![Tests](https://github.com/EncrEor/rlm-claude/actions/workflows/ci.yml/badge.svg)](https://github.com/EncrEor/rlm-claude/actions)
[![Coverage](https://codecov.io/gh/EncrEor/rlm-claude/branch/main/graph/badge.svg)](https://codecov.io/gh/EncrEor/rlm-claude)
[![PyPI](https://img.shields.io/pypi/v/mcp-rlm-server)](https://pypi.org/project/mcp-rlm-server/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-rlm-server)](https://pypi.org/project/mcp-rlm-server/)
```

Ajouter section Development :

```markdown
## Development

### Setup

git clone https://github.com/EncrEor/rlm-claude.git
cd rlm-claude
pip install -e ".[dev]"

### Run tests

pytest                          # All tests
pytest --cov=mcp_server         # With coverage
pytest -k "test_memory"         # Specific tests

### Lint

ruff check mcp_server/
ruff format mcp_server/

### Contributing

1. Fork the repo
2. Create feature branch
3. Add tests for new features
4. Run `pytest` and `ruff check`
5. Submit PR
```

---

### 6.6 Checklist MVP+ Release

| Tache | Priorite | Statut |
|-------|----------|--------|
| Structure `tests/` avec conftest.py | P0 | FAIT |
| Tests tokenizer (19 tests) | P0 | FAIT |
| Tests fuzzy grep (16 tests) | P0 | FAIT |
| Tests retention (20 tests) | P0 | FAIT |
| Tests memory (remember/recall/forget) | P0 | A FAIRE |
| Tests navigation (chunk/peek/grep) | P0 | A FAIRE |
| Tests search (BM25) | P0 | A FAIRE |
| Tests sessions | P0 | A FAIRE |
| Coverage >= 80% | P0 | A FAIRE (37% actuel) |
| `.github/workflows/ci.yml` | P0 | FAIT (verte) |
| `pyproject.toml` | P1 | FAIT (v0.9.0) |
| `CHANGELOG.md` | P1 | FAIT |
| README anglais + badges | P1 | FAIT |
| GitHub Topics + Release v0.9.0 | P1 | FAIT |
| Soumission annuaires MCP | P1 | EN COURS |
| `uninstall.sh` | P1 | A FAIRE |
| Publication TestPyPI | P1 | A FAIRE |
| Publication PyPI | P1 | A FAIRE |
| Logging systeme | P2 | A FAIRE |
| Atomic file writes | P2 | A FAIRE |
| Error handling centralise | P2 | A FAIRE |

---

### Timeline estimee Phase 6

| Sous-phase | Effort | Notes |
|------------|--------|-------|
| 6.1 Tests | 2 sessions | Structure + tests critiques |
| 6.2 CI/CD | 1 session | GitHub Actions + Codecov |
| 6.3 PyPI | 1 session | pyproject.toml + publication |
| 6.4 Robustesse | 1 session | Optionnel pour MVP |
| 6.5 Documentation | 1 session | CHANGELOG + README |

**Total MVP+ : 5-6 sessions**

---

## Pistes R&D (non planifiees)

### Option : API Haiku direct (OBSOLETE)

**Cette option n'est plus necessaire.**

Les Task tools de Claude Code sont inclus dans l'abonnement Pro/Max = **$0 supplementaire**.
Le skill `/rlm-parallel` utilise ce mecanisme natif.

### Support MCP Sampling

Quand Claude Code supportera le sampling ([#1785](https://github.com/anthropics/claude-code/issues/1785)) :

1. Ajouter `rlm_sub_query` utilisant `ctx.session.create_message()`
2. Retirer le skill `/rlm-analyze` (ou le garder en fallback)
3. UX identique, implementation plus elegante

**Tracking** : Surveiller le GitHub issue pour savoir quand implementer.

### Integration n8n (optionnel)

Pour des workflows plus complexes :
- Webhook quand un chunk important est cree
- Dashboard analytics externe
- Notifications

---

## Non-goals (explicites)

Ce que RLM ne fera PAS :

| Non-goal | Raison |
|----------|--------|
| Remplacer tools natifs | RLM est complementaire, pas un remplacement |
| Cloud storage | Tout reste local pour la privacy |
| Interface graphique | CLI first, simplicity wins |
| Multi-user | Un utilisateur = une instance |

---

## Contribution

Pour contribuer a RLM :

1. Fork le repo
2. Creer une branche pour votre feature
3. Implementer avec tests
4. PR avec description claire

**Guidelines** :
- Keep it simple
- Zero dependencies externes si possible
- Documentation en francais ou anglais
- Tests pour toute nouvelle fonction

---

## Timeline estimee

| Phase | Estimation | Notes |
|-------|------------|-------|
| Phase 4.1 (resumes) | 1-2 sessions | Simple extraction d'abord |
| Phase 4.2 (compression) | 1 session | Optionnel |
| Phase 4.3 (metriques) | 1 session | Simple compteur |
| Phase 5.1 (embeddings) | 2-3 sessions | Necessite choix librairie |
| Phase 5.2 (multi-sessions) | 2 sessions | Architecture a definir |

**Note** : Ces estimations sont indicatives. L'approche RLM est iterative - on implemente ce qui est utile quand c'est necessaire.

---

## References

- [Paper RLM (MIT CSAIL)](https://arxiv.org/abs/2512.24601) - Zhang et al., Dec 2025
- [MCP Sampling Spec](https://modelcontextprotocol.io/specification/2025-06-18/client/sampling)
- [Claude Code Sampling Issue](https://github.com/anthropics/claude-code/issues/1785)
- [sentence-transformers](https://www.sbert.net/)
- [FAISS](https://github.com/facebookresearch/faiss)
- [ChromaDB](https://www.trychroma.com/)

---

**Auteur** : Ahmed + Claude
**Repo** : https://github.com/EncrEor/rlm-claude
