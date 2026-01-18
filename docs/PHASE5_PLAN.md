# Phase 5 : RLM Authentique - Plan Detaille

> **Document de planification R&D** - A valider avant implementation
> **Auteurs** : Ahmed + Claude (session 2026-01-18)
> **Statut** : IMPLEMENTATION EN COURS - Phase 5.5

---

## Avancement Phase 5

| Sous-phase | Description | Statut |
|------------|-------------|--------|
| **5.1** | BM25 Ranking | FAIT |
| **5.2** | Grep Optimise | A FAIRE |
| **5.3** | Sub-agents Paralleles | FAIT |
| **5.4** | Embeddings (backup) | OPTIONNEL |
| **5.5** | Multi-sessions | EN COURS |
| **5.6** | Retention | A FAIRE |

---

## Contexte et Justification

### Decouverte cle de la recherche

Le paper RLM MIT (arXiv:2512.24601) **n'utilise pas d'embeddings**. C'est un choix delibere :

> "Unlike semantic retrieval tools, the RLM with REPL can look for keywords or regex patterns to narrow down lines of interest."

### Validation par benchmark

Le benchmark Letta montre que **filesystem + grep atteint 74.0% sur LoCoMo**, surpassant Mem0 (68.5%) avec des embeddings specialises.

### Decision strategique

**Approche choisie** : Suivre le paper MIT avec BM25 + sub-agents, embeddings en backup (Phase 5.4).

---

## Architecture Phase 5

```
                    PHASE 5 : RLM AUTHENTIQUE
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Phase 5.1 : BM25 Ranking                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  rlm_search(query) → BM25 score → Top-K chunks      │   │
│  │  - Tokenization (FR/EN)                              │   │
│  │  - Score pertinence                                  │   │
│  │  - Tri par score                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Phase 5.2 : Grep Optimise                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  rlm_grep amélioré :                                │   │
│  │  - Fuzzy matching (fuzzywuzzy)                      │   │
│  │  - Multi-pattern                                     │   │
│  │  - Scoring des resultats                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Phase 5.3 : Sub-agents Paralleles                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  rlm_parallel_analyze(chunk_ids, question)          │   │
│  │                                                      │   │
│  │  [Chunk 1] [Chunk 2] [Chunk 3]                      │   │
│  │      ↓         ↓         ↓                          │   │
│  │  Sub-LLM   Sub-LLM   Sub-LLM   (Haiku parallele)   │   │
│  │      ↓         ↓         ↓                          │   │
│  │  Reponse A  Reponse B  Reponse C                   │   │
│  │              ↓                                       │   │
│  │         Merger intelligent                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Phase 5.4 : Embeddings (Backup)                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  SEULEMENT si BM25 + grep insuffisant               │   │
│  │  - Nomic Embed v2 MoE (384 dims)                    │   │
│  │  - LanceDB (stockage local)                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 5.1 : BM25 Ranking

### Objectif

Ajouter un tool `rlm_search` qui utilise BM25 pour scorer et trier les chunks par pertinence.

### Pourquoi BM25

| Critere | BM25 | Embeddings |
|---------|------|------------|
| Storage | 0 (tokenized on-the-fly) | 16KB/chunk (768d) |
| Latence | <10ms | 50-200ms |
| CPU/GPU | CPU only | GPU prefere |
| Explicabilite | Haute (term frequency) | Faible (vecteurs) |
| Queries keyword-driven | Excellent | Moyen |

### Implementation proposee

```python
# Nouveau fichier : mcp_server/tools/search.py

from rank_bm25 import BM25Okapi
import re

class RLMSearch:
    def __init__(self, chunks_dir: Path):
        self.chunks_dir = chunks_dir
        self.index = None
        self.chunk_ids = []

    def build_index(self):
        """Construit l'index BM25 a partir des chunks."""
        documents = []
        self.chunk_ids = []

        for chunk_file in self.chunks_dir.glob("*.md"):
            content = self._extract_content(chunk_file)
            tokens = self._tokenize(content)
            documents.append(tokens)
            self.chunk_ids.append(chunk_file.stem)

        self.index = BM25Okapi(documents)

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize FR/EN avec normalisation."""
        text = text.lower()
        # Garder les accents francais mais normaliser
        tokens = re.findall(r'\b\w+\b', text)
        # Filtrer stopwords basiques
        stopwords = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une',
                     'et', 'ou', 'the', 'a', 'an', 'and', 'or', 'is', 'are'}
        return [t for t in tokens if t not in stopwords and len(t) > 2]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Recherche BM25 dans les chunks."""
        if self.index is None:
            self.build_index()

        query_tokens = self._tokenize(query)
        scores = self.index.get_scores(query_tokens)

        # Trier par score
        ranked = sorted(
            zip(self.chunk_ids, scores),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        return [
            {"chunk_id": cid, "score": float(score)}
            for cid, score in ranked if score > 0
        ]
```

### Tool MCP

```python
@mcp.tool()
def rlm_search(query: str, limit: int = 5) -> str:
    """
    Search chunks using BM25 ranking.

    More effective than grep for natural language queries.
    Returns chunks ranked by relevance score.

    Args:
        query: Natural language search query
        limit: Maximum results (default: 5)

    Returns:
        Ranked list of matching chunks with scores
    """
    searcher = RLMSearch(CHUNKS_DIR)
    results = searcher.search(query, top_k=limit)

    if not results:
        return "No matching chunks found."

    output = f"Top {len(results)} results for '{query}':\n"
    for r in results:
        output += f"  - {r['chunk_id']} (score: {r['score']:.2f})\n"

    return output
```

### Dependances

```
bm25s>=0.2.0  # 500x plus rapide que rank_bm25, Scipy sparse matrices
```

**Pourquoi BM25S au lieu de rank_bm25** :
- [BM25S](https://bm25s.github.io/) : jusqu'a 500x plus rapide
- Pure Python (Scipy + Numpy)
- Pas de Java/serveur requis
- Performance comparable a ElasticSearch
- Support Numba optionnel pour encore plus de vitesse

Sources : [HuggingFace Blog](https://huggingface.co/blog/xhluca/bm25s), [GitHub BM25S](https://github.com/xhluca/bm25s)

### Tests de validation

```python
def test_bm25_basic():
    # Setup
    create_test_chunks([
        ("chunk1", "Discussion sur le business plan Joy Juice"),
        ("chunk2", "Configuration Odoo et modules"),
        ("chunk3", "Le plan strategique pour 2026")
    ])

    searcher = RLMSearch(CHUNKS_DIR)

    # Test 1 : Exact match
    results = searcher.search("business plan")
    assert results[0]["chunk_id"] == "chunk1"

    # Test 2 : Semantic overlap
    results = searcher.search("strategie 2026")
    assert "chunk3" in [r["chunk_id"] for r in results[:2]]
```

---

## Phase 5.2 : Grep Optimise

### Objectif

Ameliorer `rlm_grep` existant avec :
- Fuzzy matching (tolerance aux typos)
- Multi-pattern (chercher plusieurs termes)
- Scoring des resultats

### Implementation proposee

```python
# Modifications dans mcp_server/tools/navigation.py

from thefuzz import fuzz  # ou fuzzywuzzy

def grep_enhanced(
    pattern: str,
    limit: int = 10,
    fuzzy: bool = False,
    fuzzy_threshold: int = 80
) -> dict:
    """
    Enhanced grep with fuzzy matching and scoring.

    Args:
        pattern: Search pattern (regex or text)
        limit: Max results
        fuzzy: Enable fuzzy matching
        fuzzy_threshold: Min similarity score (0-100)
    """
    matches = []

    for chunk_file in CHUNKS_DIR.glob("*.md"):
        content = chunk_file.read_text()

        if fuzzy:
            # Fuzzy line-by-line matching
            for i, line in enumerate(content.split('\n')):
                score = fuzz.partial_ratio(pattern.lower(), line.lower())
                if score >= fuzzy_threshold:
                    matches.append({
                        "chunk_id": chunk_file.stem,
                        "line": i + 1,
                        "score": score,
                        "text": line.strip()
                    })
        else:
            # Regex matching (existant)
            for m in re.finditer(pattern, content, re.IGNORECASE):
                matches.append({
                    "chunk_id": chunk_file.stem,
                    "position": m.start(),
                    "text": m.group()
                })

    # Trier par score si fuzzy
    if fuzzy:
        matches.sort(key=lambda x: x["score"], reverse=True)

    return {"matches": matches[:limit]}
```

### Dependances

```
thefuzz>=0.22.1  # ou fuzzywuzzy avec python-Levenshtein
```

---

## Phase 5.3 : Sub-agents Paralleles

### Objectif

Implementer le pattern "Partition + Map" du paper RLM pour analyser plusieurs chunks en parallele.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    rlm_parallel_analyze                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Input: chunk_ids=["001", "002", "003"], question="..."    │
│                                                              │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐                   │
│   │ Chunk 1 │   │ Chunk 2 │   │ Chunk 3 │                   │
│   └────┬────┘   └────┬────┘   └────┬────┘                   │
│        │             │             │                         │
│        ▼             ▼             ▼                         │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐                   │
│   │ Haiku 1 │   │ Haiku 2 │   │ Haiku 3 │  (parallele)      │
│   └────┬────┘   └────┬────┘   └────┬────┘                   │
│        │             │             │                         │
│        ▼             ▼             ▼                         │
│   ┌─────────────────────────────────────┐                   │
│   │           Merger (Haiku)            │                   │
│   │   Combine et synthetise les 3      │                   │
│   │   reponses partielles               │                   │
│   └─────────────────────────────────────┘                   │
│                       │                                      │
│                       ▼                                      │
│   Output: Reponse unifiee avec sources                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Options d'implementation

#### Option A : Skill Claude Code (actuel)

Le skill `/rlm-analyze` utilise deja le Task tool. On pourrait :
1. Creer un skill `/rlm-parallel` qui lance N Task tools en parallele
2. Chaque Task analyse un chunk
3. Un dernier Task merge les reponses

**Avantage** : Zero dependance, utilise l'infra existante
**Inconvenient** : Pas vraiment parallele (sequentiel dans le skill)

#### Option B : MCP Sampling (futur)

Quand Claude Code supportera MCP Sampling ([#1785](https://github.com/anthropics/claude-code/issues/1785)) :

```python
@mcp.tool()
async def rlm_parallel_analyze(chunk_ids: list, question: str) -> str:
    # Lancer N sub-queries en parallele
    tasks = [
        ctx.session.create_message(
            model="claude-3-haiku",
            messages=[{"role": "user", "content": f"Analyse ce chunk:\n{chunk}\n\nQuestion: {question}"}]
        )
        for chunk in chunks
    ]

    responses = await asyncio.gather(*tasks)

    # Merger les reponses
    merged = await ctx.session.create_message(
        model="claude-3-haiku",
        messages=[{"role": "user", "content": f"Synthetise ces reponses:\n{responses}"}]
    )

    return merged
```

**Avantage** : Vrai parallelisme, API propre
**Inconvenient** : Pas encore disponible

#### Option C : API Anthropic direct (payant)

Stocker une cle API et appeler Claude directement depuis le MCP server.

**Avantage** : Fonctionne maintenant
**Inconvenient** : Cout ($), latence reseau, complexite

### Recommandation

**Court terme** : Option A (Skill ameliore avec parallelisme natif)
**Moyen terme** : Attendre Option B (MCP Sampling)
**Si urgent** : Option C (API direct)

### Detail Option A : Parallelisme natif Claude Code

Claude Code peut lancer **plusieurs Task tools dans un seul message**, ce qui les execute en parallele.

```markdown
# Skill /rlm-parallel

## Usage
/rlm-parallel "<question>" [chunk_ids...]

## Comportement

1. Si chunk_ids fournis, les utiliser
2. Sinon, utiliser rlm_search pour trouver les top-5 chunks pertinents

3. Lancer N Task tools EN PARALLELE dans un seul message :
   - Chaque Task analyse un chunk avec la question
   - subagent_type="Explore" (lecture seule)
   - model="haiku" (economique)

4. Collecter les N reponses

5. Lancer un dernier Task (merger) qui synthetise :
   - Combine les insights des N reponses
   - Identifie les contradictions
   - Produit une reponse unifiee

## Exemple de prompt interne

Pour chaque chunk (en parallele) :
---
Analyse ce chunk et reponds a la question.

Question: {question}

Chunk {chunk_id}:
{content}

Instructions:
- Extrais les informations pertinentes
- Cite les passages cles
- Indique si rien de pertinent
---

Pour le merger :
---
Synthetise ces analyses partielles.

Question originale: {question}

Analyse 1 ({chunk_id_1}):
{response_1}

Analyse 2 ({chunk_id_2}):
{response_2}

...

Instructions:
- Combine les insights
- Signale les contradictions
- Produis une reponse coherente avec sources
---
```

**Avantage** : Parallelisme reel sans dependance externe
**Cout estime** : ~$0.005 par query (3 Haiku + 1 merger)

---

## Phase 5.4 : Embeddings (Backup)

### Quand activer

Activer les embeddings **seulement si** :
1. BM25 retourne trop de faux positifs (precision < 70%)
2. Queries semantiques pures echouent ("trouve les discussions optimistes")
3. Volume de chunks > 10k (BM25 scale moins bien)

### Stack recommandee (si necessaire)

| Composant | Choix | Justification |
|-----------|-------|---------------|
| Modele | Nomic Embed v2 MoE | Multilingue FR/EN, Matryoshka, leger |
| Dimensions | 384 | Bon compromis (tronque de 768) |
| Vector DB | LanceDB | Rust, leger, schema, pip install |
| Quantization | int8 ONNX | CPU-friendly |

### Implementation (si necessaire)

```python
# mcp_server/tools/semantic.py (Phase 5.4 seulement)

import lancedb
from sentence_transformers import SentenceTransformer

class SemanticSearch:
    def __init__(self, db_path: Path):
        self.db = lancedb.connect(str(db_path))
        self.model = SentenceTransformer('nomic-ai/nomic-embed-text-v1.5')

    def index_chunk(self, chunk_id: str, content: str, metadata: dict):
        embedding = self.model.encode(content)

        table = self.db.open_table("chunks")
        table.add([{
            "id": chunk_id,
            "vector": embedding[:384],  # Matryoshka truncate
            **metadata
        }])

    def search(self, query: str, top_k: int = 5, filters: dict = None):
        query_vec = self.model.encode(query)[:384]

        table = self.db.open_table("chunks")
        results = table.search(query_vec).limit(top_k)

        if filters:
            results = results.where(filters)

        return results.to_list()
```

---

## Criteres de Succes

### Phase 5.1 (BM25)
- [ ] `rlm_search` fonctionne avec queries FR/EN
- [ ] Temps de reponse < 50ms sur 1000 chunks
- [ ] Precision top-5 > 80% sur cas de test

### Phase 5.2 (Grep optimise)
- [ ] Fuzzy matching detecte "buget" → "budget"
- [ ] Multi-pattern supporte "business AND plan"
- [ ] Scoring coherent avec BM25

### Phase 5.3 (Sub-agents)
- [ ] 3 chunks analyses en parallele
- [ ] Merge coherent des reponses
- [ ] Cout < $0.01 par query (Haiku)

### Phase 5.4 (Embeddings si necessaire)
- [ ] Precision semantique > BM25 sur queries abstraites
- [ ] Latence < 200ms end-to-end
- [ ] Storage < 1MB pour 1000 chunks

---

## Planning Estime

| Phase | Effort | Prerequis |
|-------|--------|-----------|
| 5.1 BM25 | 1 session | rank_bm25 |
| 5.2 Grep++ | 1 session | thefuzz |
| 5.3 Sub-agents | 2 sessions | Design + impl |
| 5.4 Embeddings | 2 sessions | Seulement si besoin |

**Total minimum** : 4 sessions (sans embeddings)
**Total maximum** : 6 sessions (avec embeddings)

---

## Decisions Validees (Session 2026-01-18)

Les questions ouvertes ont ete explorees et resolues.

---

### 1. Multi-sessions : Format enrichi

**Format d'ID de session** :

```
{date}_{project}_{sequence}_{ticket}_{domain}

Exemple : 2026-01-18_RLM_001_TIC-123_bp
```

| Composant | Source | Optionnel | Exemple |
|-----------|--------|-----------|---------|
| `date` | Auto (systeme) | Non | `2026-01-18` |
| `project` | Git root ou cwd | Non | `RLM`, `Joy_Claude` |
| `sequence` | Compteur auto | Non | `001`, `002` |
| `ticket` | Manuel ou detecte | Oui | `TIC-123`, `#456` |
| `domain` | Liste predefinee | Oui | `bp`, `seo`, `website` |

**Domaines disponibles** (source: listes + labels Trello) :

```python
# Listes Trello (departements)
DOMAINS_LISTS = [
    "finance",      # 💰 Finance
    "legal",        # ⚖️ Legal/Admin
    "operations",   # 🏭 Operations
    "commercial",   # 🤝 Commercial
    "marketing",    # 📣 Marketing
    "rh",           # 👥 RH
    "r&d",          # 🧪 R&D/Innovation
]

# Labels Trello (themes)
DOMAINS_THEMES = [
    "admin",        # Administratif - demarches, creation SAS
    "qualite",      # Qualite - HACCP, process, compliance
    "expertise",    # Expertise - Blog, contenu expert
    "performance",  # Performance - PageSpeed, optimisation
    "visibilite",   # Visibilite - SEO, reseaux, acquisition
    "notoriete",    # Notoriete - Branding, image
    "ventes",       # Stimulation ventes - Conversion, promos
    "fidelisation", # Fidelisation - Retention, loyalty
    "scaling",      # Scaling - Croissance, equipement
    "deck",         # Deck commercial - Pitch, catalogue
]

# Domaines supplementaires (usage courant Joy Juice)
DOMAINS_CUSTOM = [
    "website",      # Site web, templates
    "seo",          # Referencement specifique
    "blog",         # Articles blog
    "erp",          # Odoo, modules
    "bp",           # Business Plan
    "bi",           # Analytics, reporting
]

DOMAINS = DOMAINS_LISTS + DOMAINS_THEMES + DOMAINS_CUSTOM
```

**Nouveau fichier `sessions.json`** :

```json
{
  "current_session": "2026-01-18_RLM_001_TIC-123_r&d",
  "sessions": {
    "2026-01-18_RLM_001_TIC-123_r&d": {
      "project": "RLM",
      "path": "/Users/amx/Documents/Joy_Claude/RLM",
      "ticket": "TIC-123",
      "domain": "r&d",
      "started": "2026-01-18T09:15:00Z",
      "chunks": ["2026-01-18_001", "2026-01-18_005"],
      "tags": ["phase5", "bm25"]
    }
  }
}
```

**Syntaxe cross-session** :

```python
# Lister les sessions
rlm_sessions(limit=10)
rlm_sessions(project="Joy_Claude")
rlm_sessions(domain="bp")

# Acceder a un chunk d'une autre session
rlm_peek("@2026-01-17_Joy_Claude_001:003")  # @session:chunk

# Recherche cross-session
rlm_grep("business plan", sessions="all")
rlm_grep("equipment", domain="bp")
```

---

### 2. Retention : Strategie LRU-Soft avec Immunite Automatique

**Architecture 3 zones** :

```
┌─────────────────────────────────────────────────────────────┐
│                    CHUNKS ACTIFS                             │
│  context/chunks/*.md                                         │
│  - Cherchables via rlm_grep                                 │
│  - Compteur d'acces actif                                   │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ 30 jours + access_count == 0 + pas immune
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    CHUNKS ARCHIVES                           │
│  context/archive/*.md.gz (gzip)                             │
│  - Toujours cherchables (decompression lazy)                │
│  - Restauration auto si rlm_peek                            │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ 180 jours en archive
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    CHUNKS PURGES                             │
│  Suppression definitive                                      │
│  - Log conserve : date, summary, tags                        │
└─────────────────────────────────────────────────────────────┘
```

**Regles d'immunite automatique** (zero intervention manuelle) :

| Condition | Immunite | Justification |
|-----------|----------|---------------|
| Tag `critical` ou `decision` | Oui | Marque explicite d'importance |
| Tag `keep` | Oui | Demande de conservation |
| Categorie insight = `decision` | Oui | Decisions strategiques |
| Contient "IMPORTANT" ou "DECISION" | Oui | Detection par contenu |
| Lie a un ticket non-ferme | Oui | Travail en cours |
| `access_count >= 3` | Oui | Chunk frequemment utilise |

**Implementation** :

```python
def is_immune(chunk: dict) -> bool:
    """Determine si un chunk est protege de l'archivage."""

    # Tags protecteurs
    protected_tags = {"critical", "decision", "keep"}
    if set(chunk.get("tags", [])) & protected_tags:
        return True

    # Contenu protecteur
    content = chunk.get("content", "").upper()
    if "IMPORTANT" in content or "DECISION" in content:
        return True

    # Acces frequent
    if chunk.get("access_count", 0) >= 3:
        return True

    # Ticket non-ferme (a implementer avec Trello MCP)
    # if chunk.get("ticket") and not is_ticket_closed(chunk["ticket"]):
    #     return True

    return False
```

**Commandes** :

```python
rlm_retention_preview()  # Dry-run : montre ce qui serait archive
rlm_retention_run()      # Execute l'archivage
rlm_restore("chunk_id")  # Restaure un archive
```

**Compression gzip** : 100% lisible

```python
import gzip
with gzip.open("chunk.md.gz", "rt") as f:  # "rt" = read text
    content = f.read()  # Decompression transparente
```

---

### 3. Dataset de Test BM25

**Approche en 2 phases** :

| Phase | Chunks | Queries | But |
|-------|--------|---------|-----|
| **V1 Smoke** | 5 existants | 10 | Validation basique |
| **V2 Benchmark** | +25 synthetiques | 30 | Mesure precision reelle |

**Types de queries (proportions)** :

| Type | % | Exemple |
|------|---|---------|
| Exact keyword | 35% | "Phase 4 RLM" |
| Multi-termes | 25% | "recette jus gingembre bio" |
| Semantique | 15% | "combien ca coute" |
| Accents FR | 10% | "scenario realiste" |
| Fuzzy/typos | 10% | "validaton", "businss" |
| Negation | 5% | "pas d'embeddings" |

**Format dataset JSON** :

```json
{
  "version": "1.0",
  "queries": [
    {
      "id": "Q001",
      "query": "Phase 4 RLM",
      "type": "exact_keyword",
      "expected_top1": "2026-01-18_003",
      "expected_top3": ["2026-01-18_003", "2026-01-18_002"]
    }
  ],
  "metrics": {
    "precision_at_1": {"target": 0.75, "minimum": 0.60},
    "precision_at_3": {"target": 0.70, "minimum": 0.55},
    "mrr": {"target": 0.80, "minimum": 0.65}
  }
}
```

**Seuils de succes** :

| Metrique | Minimum | Cible | Excellent |
|----------|---------|-------|-----------|
| P@1 | 60% | 75% | 85% |
| P@3 | 55% | 70% | 80% |
| MRR | 0.65 | 0.80 | 0.90 |

**Regle** : Si P@1 < 70%, activer Phase 5.4 (embeddings).

---

### 4. Tokenization Francaise : Zero Dependance

**Approche choisie** : Regex + Stopwords custom (pas NLTK, pas spaCy).

**Justification** :

| Critere | Regex+Stopwords | NLTK | spaCy |
|---------|-----------------|------|-------|
| Dependances | 0 | ~50MB | ~100MB |
| Temps init | 0ms | ~500ms | ~2s |
| Qualite FR | 85% | 90% | 95% |

Pour des chunks courts avec code mixing FR/EN, **85% suffit**.

**Implementation** :

```python
# tokenizer_fr.py - Zero dependance

import re
import unicodedata

STOPWORDS_FR = {
    "le", "la", "les", "l", "un", "une", "des", "du", "de", "d",
    "et", "ou", "mais", "donc", "car", "que", "qui", "quoi",
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils",
    "ce", "cette", "ces", "mon", "ton", "son", "notre", "votre",
    "est", "sont", "a", "ont", "fait", "peut", "doit",
    "ne", "pas", "plus", "tres", "bien", "tout", "tous",
    "pour", "dans", "sur", "avec", "sans", "par", "entre",
}

STOPWORDS_EN = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "i", "you", "he", "she", "it", "we", "they", "this", "that",
    "of", "in", "to", "for", "with", "on", "at", "by", "from",
    "and", "or", "but", "if", "not", "no", "yes",
}

STOPWORDS = STOPWORDS_FR | STOPWORDS_EN


def normalize_accent(text: str) -> str:
    """'realiste' -> 'realiste' (pour matching)."""
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


def tokenize_fr(text: str, remove_stopwords: bool = True) -> list[str]:
    """
    Tokenize FR/EN pour BM25.

    Exemples:
        "Le jus-de-fruits realiste" -> ["jus", "fruits", "realiste"]
        "Deploy v19.0.2 on VPS" -> ["deploy", "v19", "vps"]
    """
    text = text.lower()
    text = normalize_accent(text)

    # Extraction tokens (mots + tirets internes)
    raw_tokens = re.findall(r'[a-z0-9]+(?:-[a-z0-9]+)*', text)

    # Split mots composes
    tokens = []
    for token in raw_tokens:
        if '-' in token:
            tokens.extend(token.split('-'))
        else:
            tokens.append(token)

    # Filtrer stopwords et mots courts
    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS and len(t) >= 2]

    return tokens
```

**Tests** :

```python
assert tokenize_fr("Le jus d'orange est tres realiste") == ["jus", "orange", "realiste"]
assert tokenize_fr("Le jus-de-fruits presse a froid") == ["jus", "fruits", "presse", "froid"]
assert tokenize_fr("Deploy v19.0.2 on VPS Odoo") == ["deploy", "v19", "vps", "odoo"]
```

---

## Questions Ouvertes Restantes

| Question | Options | Priorite |
|----------|---------|----------|
| Detection ticket | Regex Trello/GitHub ? MCP Trello ? | P2 |
| Detection domaine | Manuel / Auto via keywords ? | P2 |
| Coherence contradictions | Timestamp gagne / Flag / Merge ? | P3 |
| Privacy chunks sensibles | Encryption ? Exclusion patterns ? | P3 |

---

## References

- [Paper RLM MIT](https://arxiv.org/abs/2512.24601) - Zhang et al., Dec 2025
- [Letta Benchmark](https://www.letta.com/blog/benchmarking-ai-agent-memory) - Filesystem vs Embeddings
- [rank_bm25](https://github.com/dorianbrown/rank_bm25) - Implementation Python
- [LanceDB](https://lancedb.github.io/lancedb/) - Vector DB Rust
- [Nomic Embed v2](https://www.nomic.ai/blog/posts/nomic-embed-text-v2) - Modele embeddings

---

**Derniere MAJ** : 2026-01-18
**Statut** : DRAFT - En attente de validation
