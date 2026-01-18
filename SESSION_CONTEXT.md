# RLM - Contexte de Session

> **Fichier de reprise** : A lire au debut de chaque session pour restaurer le contexte complet.
> **Derniere MAJ** : 2026-01-18 (Phase 4 validee)

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

### Phase 4 : Production - VALIDEE (2026-01-18)

| Tache | Statut |
|-------|--------|
| `_auto_summarize()` - generation auto de resume | OK |
| `_content_hash()` - hash MD5 normalise | OK |
| `_check_duplicate()` - detection doublons | OK |
| `_increment_access()` - compteur d'acces | OK |
| Mise a jour `chunk()` avec Phase 4 | OK |
| Mise a jour `peek()` avec tracking | OK |
| Mise a jour `list_chunks()` avec metrics | OK |
| Mise a jour `rlm_status()` avec stats usage | OK |
| Tests valides | OK |
| GitHub push | OK |

**Nouveautes Phase 4** :
- Auto-summarization : Resume genere si non fourni (premiere ligne)
- Deduplication : Hash MD5 du contenu normalise evite les doublons
- Access tracking : Compteur d'acces et `last_accessed` pour chaque chunk
- Stats usage : `rlm_status()` affiche les chunks les plus accedes

**Bug fixes** :
- Hook `Stop` ne supporte PAS les matchers → retirer `"matcher": "*"`
- Hook `Stop` format JSON : utiliser `systemMessage` (pas `hookSpecificOutput.additionalContext`)
- Fix applique dans `~/.claude/rlm/hooks/auto_chunk_check.py`

**Tests Phase 4 valides** :
```
rlm_chunk("contenu", tags="test")  → Auto-summary genere ✅
rlm_chunk("meme contenu")          → Doublon detecte ✅
rlm_peek("chunk_id")               → access_count incremente ✅
rlm_status()                       → "Most accessed" affiche ✅
```

### Phase 5 : RLM Authentique - EN COURS (2026-01-18)

**Changement strategique** : Suite a recherche approfondie, Phase 5 redesignee pour suivre le paper MIT.

**Decouverte cle** : Le paper RLM MIT n'utilise PAS d'embeddings. C'est delibere.
Letta benchmark : filesystem + grep = 74% accuracy > Mem0 avec embeddings (68.5%).

| Sous-phase | Description | Statut |
|------------|-------------|--------|
| **5.1 BM25S** | Ranking par pertinence (500x plus rapide) | FAIT |
| **5.2 Grep++** | Fuzzy matching + scoring | A FAIRE |
| **5.3 Sub-agents** | Analyse parallele (Partition + Map) | EN COURS |
| **5.4 Embeddings** | BACKUP seulement si BM25 < 70% | OPTIONNEL |
| **5.5 Multi-sessions** | Format enrichi + cross-session | A FAIRE |
| **5.6 Retention** | LRU-Soft + immunite auto | A FAIRE |

**Phase 5.1 implementee** (2026-01-18) :
- `mcp_server/tools/tokenizer_fr.py` - Tokenization FR/EN zero dependance
- `mcp_server/tools/search.py` - BM25S search avec scoring
- `mcp_server/server.py` - Tool `rlm_search` ajoute
- Tests valides : tokenizer + search fonctionnent correctement

**Decisions validees (Session 2026-01-18 apres-midi)** :

1. **Multi-sessions** : Format `{date}_{project}_{seq}_{ticket}_{domain}`
   - Ticket optionnel (Trello, GitHub...)
   - Domaines : 23 valeurs (listes Trello + labels + custom)
     - Listes : finance, legal, operations, commercial, marketing, rh, r&d
     - Themes : admin, qualite, expertise, performance, visibilite, notoriete, ventes, fidelisation, scaling, deck
     - Custom : website, seo, blog, erp, bp, bi
   - Syntaxe cross-session : `@2026-01-17_RLM_001:003`

2. **Retention** : 3 zones (Actif → Archive .gz → Purge)
   - Archive apres 30j si access_count == 0
   - Purge apres 180j en archive
   - Immunite auto : tags critical/decision, access >= 3, ticket ouvert

3. **Tokenization** : Zero dependance (regex + stopwords FR/EN)
   - Normalisation accents (`realiste` = `réaliste`)
   - Split mots composes (`jus-de-fruits` → `[jus, fruits]`)

4. **Dataset test** : V1 (10 queries) puis V2 (+25 chunks synthetiques)
   - Seuil : P@1 >= 70% sinon activer embeddings

**Documentation complete** : `docs/PHASE5_PLAN.md`

**Phase 5.3 implementee** (2026-01-18) :
- `templates/skills/rlm-parallel/skill.md` - Skill analyse parallele
- Pattern "Partition + Map" : 3 Task tools paralleles + 1 merger
- Modele : Sonnet (preference utilisateur)
- Cout : $0 (Task tools inclus dans abonnement Claude Code Pro/Max)
- Note : MCP Sampling non supporte par Claude Code (issue #1785) → Skill = seule option
- `install.sh` mis a jour pour installer /rlm-parallel automatiquement

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

### Phase 5 - Search (BM25)

| Tool | Description | Statut |
|------|-------------|--------|
| `rlm_search` | Recherche BM25 par pertinence (FR/EN) | OK |

### Phase 3 - Auto-chunking & Skills

| Composant | Description | Statut |
|-----------|-------------|--------|
| Hook Stop | Detection auto-chunk (10 tours / 30 min) | OK |
| Hook PostToolUse | Reset compteur apres chunk | OK |
| Skill `/rlm-analyze` | Analyser 1 chunk avec sub-agent | OK |
| Skill `/rlm-parallel` | Analyser 3 chunks en parallele + merger | OK |

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
| `templates/skills/rlm-analyze/skill.md` | Skill analyse 1 chunk |
| `templates/skills/rlm-parallel/skill.md` | Skill analyse parallele (3 chunks) |
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

**Phase 5.3 : Sub-agents** - EN COURS

Fait :
- Skill `/rlm-parallel` cree
- `install.sh` mis a jour

A faire :
- Tester le skill manuellement
- Installer via copie manuelle ou `./install.sh`
- Valider les 3 tests du plan
- Commit + push GitHub

**Prochaines phases** :
- **5.2 Grep++** : Fuzzy matching + scoring
- **5.5 Multi-sessions** : Format enrichi + cross-session
- **5.6 Retention** : LRU-Soft + immunite auto

**Pour tester les tools existants** :
```
rlm_status()           -> Insights + Chunks stats + Most accessed
rlm_list_chunks()      -> Liste des chunks avec access_count
rlm_recall()           -> Insights sauvegardes
rlm_chunk("content")   -> Auto-summary + dedup
rlm_search("query")    -> Recherche BM25 (Phase 5.1)
/rlm-analyze chunk_id "question"  -> Analyser 1 chunk
/rlm-parallel "question"          -> Analyser 3 chunks en parallele
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
| "Cherche dans plusieurs chunks" | `/rlm-parallel "question"` | Analyse parallele + fusion |

---

**Auteur** : Ahmed + Claude
**Repo** : https://github.com/EncrEor/rlm-claude
