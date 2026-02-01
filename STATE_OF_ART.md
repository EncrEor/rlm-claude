# État de l'Art : Recursive Language Models (RLM) et Mémoire Infinie LLM

> **Dernière mise à jour** : 2026-02-01
> **Objectif** : Comprendre et implémenter une solution pour les contextes longs

---

## 1. Le Problème Fondamental

### 1.1 Dégradation avec le contexte long

Les LLMs actuels souffrent de plusieurs limitations avec les contextes longs :

| Phénomène | Description | Impact |
|-----------|-------------|--------|
| **Lost in the Middle** | Performance dégradée sur les informations au milieu du contexte | Information critique ignorée |
| **Attention Dilution** | L'attention se disperse sur trop de tokens | Réponses moins précises |
| **Context Rot** | Dégradation progressive de la qualité | ~60% contexte = début des problèmes |
| **Coût quadratique** | O(n²) pour l'attention standard | Latence et coût explosent |

### 1.2 Solutions traditionnelles et leurs limites

| Solution | Principe | Limite |
|----------|----------|--------|
| **Extended Windows** | Augmenter la fenêtre de contexte | Coût + dégradation quand même |
| **RAG** | Récupérer les chunks pertinents | Perte de contexte, pas de suivi |
| **Summarization** | Résumer pour comprimer | Perte d'information |
| **Sliding Window** | Garder les N derniers tokens | Perte de l'historique |

---

## 2. RLM : Recursive Language Models (MIT CSAIL, 2025)

### 2.1 Le papier fondateur

> **Titre** : Recursive Language Models
> **Auteurs** : Alex L. Zhang, Tim Kraska, Omar Khattab (MIT CSAIL)
> **Date** : 31 décembre 2025
> **arXiv** : [2512.24601](https://arxiv.org/abs/2512.24601)

### 2.2 Le concept révolutionnaire

Au lieu de charger tout le contexte dans l'attention, RLM :

1. **Traite le contexte comme un objet externe** - Le texte devient une variable Python
2. **Donne au LLM un REPL Python** - Il peut exécuter du code pour explorer
3. **Permet les appels récursifs** - Sub-LLMs pour paralléliser
4. **Laisse le LLM décider** - Pas de règles fixes, stratégies émergentes

```
┌────────────────────────────────────────────────────────────┐
│                    Architecture RLM                        │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   Query          ┌─────────────┐                           │
│      ─────────▶  │  Root LLM   │                           │
│                  │  (depth=0)  │                           │
│                  └──────┬──────┘                           │
│                         │                                  │
│                         ▼                                  │
│                  ┌─────────────┐                           │
│                  │ Python REPL │                           │
│                  │  + Context  │                           │
│                  └──────┬──────┘                           │
│                         │                                  │
│           ┌─────────────┼─────────────┐                    │
│           ▼             ▼             ▼                    │
│      ┌─────────┐  ┌─────────┐  ┌─────────┐                │
│      │Sub-LLM 1│  │Sub-LLM 2│  │Sub-LLM 3│                │
│      │(depth=1)│  │(depth=1)│  │(depth=1)│                │
│      └────┬────┘  └────┬────┘  └────┬────┘                │
│           │            │            │                      │
│           └────────────┼────────────┘                      │
│                        ▼                                   │
│                  ┌─────────────┐                           │
│                  │  Aggregate  │                           │
│                  │   Results   │                           │
│                  └─────────────┘                           │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### 2.3 Mécanisme détaillé

#### Le REPL Python

```python
# Le contexte est stocké comme variable
context = """[... 10M tokens de texte ...]"""

# Le LLM peut exécuter du code
print(len(context))  # Voir la taille
print(context[:1000])  # Peek au début
import re
matches = re.findall(r"Joy Juice", context)  # Chercher
```

#### Les appels récursifs

```python
def llm_query(prompt, context_chunk):
    """Appeler un sub-LLM sur un chunk spécifique"""
    return sub_llm.complete(prompt + context_chunk)

# Le LLM principal peut paralléliser
chunks = [context[i:i+10000] for i in range(0, len(context), 10000)]
results = [llm_query("Résume ce passage:", chunk) for chunk in chunks]
final = llm_query("Synthétise ces résumés:", "\n".join(results))
```

### 2.4 Stratégies émergentes

Sans entraînement explicite, les RLMs développent naturellement :

| Stratégie | Description | Quand utilisée |
|-----------|-------------|----------------|
| **Peeking** | Regarder le début/fin du contexte | Comprendre la structure |
| **Grepping** | Recherche regex par mots-clés | Trouver l'info pertinente |
| **Partition + Map** | Découper et traiter en parallèle | Tâches distribuables |
| **Verification** | Double-checker via sub-calls | Tâches critiques |
| **Summarization** | Résumer des portions | Compression locale |

### 2.5 Benchmarks et résultats

| Benchmark | Tâche | RLM(GPT-5-mini) | GPT-5 Base | Amélioration |
|-----------|-------|-----------------|------------|--------------|
| S-NIAH | Needle in haystack | Stable à 10M+ | Dégradation | 2× |
| BrowseComp+ | Raisonnement web | 91.33% | 0.00% | Massif |
| OOLONG | Long-context QA | 56.50% | 44.00% | +28% |
| OOLONG-Pairs | QA comparatif | 58.00% | 0.04% | Massif |
| CodeQA | Code understanding | 62% | 24% | +158% |

### 2.6 Limitations connues

| Limitation | Description | Mitigation |
|------------|-------------|------------|
| **Code Fragility** | Bugs Python = échec | Validation syntaxe |
| **Hallucination Propagation** | Erreur sub-LLM → erreur finale | Vérification croisée |
| **Sequential Execution** | Pas d'async actuellement | Implémentation future |
| **Model Dependency** | Nécessite bon coding skills | Utiliser Claude/GPT-4+ |
| **Coût variable** | Trajectoires longues = plus cher | Optimiser les stratégies |

---

## 3. Letta (ex-MemGPT) : Mémoire Hiérarchique

### 3.1 Concept

Letta s'inspire des systèmes d'exploitation : mémoire RAM (rapide, limitée) + Disk (lent, illimité).

```
┌─────────────────────────────────────────────────────────────┐
│                    Architecture Letta                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Primary Context (RAM)                      │   │
│  │  ┌──────────────┬──────────────┬──────────────────┐ │   │
│  │  │ System Prompt│Working Memory│  Message Buffer  │ │   │
│  │  │   (Fixed)    │ (Scratchpad) │    (FIFO)       │ │   │
│  │  └──────────────┴──────────────┴──────────────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           External Context (Disk)                    │   │
│  │  ┌────────────────────┬────────────────────────┐    │   │
│  │  │   Recall Storage   │   Archival Storage    │    │   │
│  │  │ (Full History Log) │ (Vector DB, Search)   │    │   │
│  │  └────────────────────┴────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Fonctionnalités clés

| Feature | Description |
|---------|-------------|
| **Self-Directed Memory** | Le LLM décide quoi stocker/oublier |
| **Memory Blocks** | Création/suppression dynamique |
| **Semantic Search** | Récupération par similarité vectorielle |
| **Multi-Provider** | OpenAI, Anthropic, local models |

### 3.3 Intégration Claude 4.5

Claude 4.5 Sonnet est le premier modèle entraîné pour être "context-aware" :
- Meilleure gestion de ses propres limites de contexte
- Outil `memory` natif pour gestion mémoire
- Intégration native avec Letta

### 3.4 RLM vs Letta

| Aspect | RLM | Letta |
|--------|-----|-------|
| **Approche** | Code execution | Memory management |
| **Persistance** | Session only | Persistant |
| **Complexité** | Plus simple | Plus feature-rich |
| **Use case** | Tâches longues, documents | Agents persistants |
| **Overhead** | Minimal | Vector DB + storage |

---

## 4. TTT-E2E (NVIDIA) : Compression dans les Poids

### 4.1 Concept

Test-Time Training compresse le contexte directement dans les poids du modèle.

### 4.2 Mécanisme

1. **Phase Meta-Learning** : Préparer le modèle pour TTT
2. **Phase Inference** : Le contexte devient "training data" temporaire
3. **Résultat** : Les poids encodent l'information contextuelle

### 4.3 Performance

| Métrique | Résultat |
|----------|----------|
| **Latence 128K** | 2.7× plus rapide que full attention |
| **Latence 2M** | 35× plus rapide |
| **Scaling** | Constant, indépendant de la longueur |

### 4.4 Limitation pour nous

**Non applicable à Claude API** - Nécessite accès aux poids du modèle.

---

## 5. Autres Approches Notables

### 5.1 M+ (ICML 2025)

- Extension de MemoryLLM
- De 20k à 160k tokens (8× amélioration)
- Retriever co-entraîné avec mémoire latente

### 5.2 SimpleMem

- Compression sémantique dialogue → faits indépendants
- Résolution explicite des ambiguïtés temporelles/référentielles
- Pour agents "lifelong"

### 5.3 A-MEM (Agentic Memory)

- 85-93% réduction tokens vs MemGPT
- 5.4s processing avec GPT-4o-mini
- 1.1s avec Llama 3.2 local

### 5.4 KVzip

- Compression 3-4× de la mémoire KV
- Jusqu'à 170k tokens
- Réutilisation sans recompression

### 5.5 Titans (Google)

- Architecture mémoire profonde
- Meilleur scaling avec la longueur
- Recherche fondamentale

---

## 6. Nouveaux Papiers Analysés (Février 2026)

> **Date de la recherche** : 01/02/2026
> **Objectif** : Trouver des papiers transformables en outils concrets pour Claude Code

### 6.1 MAGMA — Multi-Graph Agentic Memory Architecture

> **arXiv** : [2601.03236](https://arxiv.org/abs/2601.03236) — Janvier 2026
> **Auteurs** : Jiang, Li, Li, Li (UT Dallas, U. Florida)
> **Code** : [github.com/FredJiang0324/MAMGA](https://github.com/FredJiang0324/MAMGA)

Sépare la mémoire en 4 graphes orthogonaux : sémantique, temporel, causal, et entités.
Routing intelligent des requêtes vers le bon graphe selon l'intent.

| Métrique | Résultat |
|----------|----------|
| Précision vs baselines | +18.6% à +45.5% |
| Réduction tokens | -95% |
| Latence requête | -40% |

**Décision pour RLM** : Upgrade chirurgical — prendre filtre temporel + extraction d'entités.
Ne PAS implémenter le graphe complet (overkill pour notre échelle).

### 6.2 MCP-Zero — Active Tool Discovery

> **arXiv** : [2506.01056](https://arxiv.org/abs/2506.01056) — Juin 2025
> **Auteurs** : Fei, Zheng, Feng
> **Code** : [github.com/xfey/MCP-Zero](https://github.com/xfey/MCP-Zero)

L'agent demande activement les outils dont il a besoin au lieu de recevoir toutes les descriptions.
Routing sémantique hiérarchique. -98% de tokens sur le toolset.

**Décision pour RLM** : **Rejeté** — Ahmed gère manuellement l'activation/désactivation des MCP.

### 6.3 MemSearcher — Mémoire Compacte Auto-optimisée

> **arXiv** : [2511.02805](https://arxiv.org/abs/2511.02805) — Novembre 2025
> **Auteurs** : Yuan et al. (CAS)
> **Code** : [github.com/icip-cas/MemSearcher](https://github.com/icip-cas/MemSearcher)

Maintient une mémoire compacte mise à jour à chaque tour via RL (multi-context GRPO).
Le modèle 3B surpasse les baselines 7B — preuve que l'architecture compte plus que la taille.

**Décision pour RLM** : Pattern intéressant mais RL difficile à reproduire. À surveiller.

### 6.4 MAKER — 1M d'Étapes LLM Zéro Erreurs

> **arXiv** : [2511.09030](https://arxiv.org/abs/2511.09030) — Novembre 2025
> **Auteurs** : Meyerson et al. (Cognizant AI Labs)

MAKER = Maximal Agentic decomposition + first-to-ahead-by-K Error correction + Red-flagging.
Décomposition extrême en micro-agents avec vote multi-agent et red-flagging des outputs suspects.
Résout 1M d'étapes (Towers of Hanoi 20 disques) avec zéro erreurs.

**Décision pour RLM** : Pattern de fiabilité pertinent pour tâches longues.
Le voting + red-flagging pourrait s'ajouter au skill `/rlm-parallel`.

### 6.5 EverMemOS — OS Mémoire avec Engrams

> **arXiv** : [2601.02163](https://arxiv.org/abs/2601.02163) — Janvier 2026
> **Auteurs** : Hu et al.
> **Code** : [github.com/EverMind-AI/EverMemOS](https://github.com/EverMind-AI/EverMemOS)

Inspiré de la neurobiologie : les souvenirs passent par 3 stades :
1. Formation épisodique (MemCells)
2. Consolidation sémantique (MemScenes)
3. Reconstruction reconstructive (retrieval guidé)

SOTA sur LoCoMo et LongMemEval.

**Décision pour RLM** : Concept MemScenes (regroupement thématique auto) intéressant pour Phase 8+.

### 6.6 LADDER — Auto-amélioration Récursive

> **arXiv** : [2503.00735](https://arxiv.org/abs/2503.00735) — Mars 2025

Framework pour auto-amélioration via décomposition récursive et RL (GRPO).
Un modèle 7B passe de 2% à 82% en maths. Pas directement applicable comme outil MCP.

### 6.7 CREATOR — Création Autonome d'Outils

> **arXiv** : [2305.14318](https://arxiv.org/abs/2305.14318) — 2023, mis à jour 2024
> **Auteurs** : Qian et al. (Tsinghua, UIUC)

Le LLM crée ses propres outils (code + documentation) quand aucun outil existant ne convient.
4 étapes : Creation → Decision → Execution → Rectification.
Pertinent si on veut que Claude Code auto-génère de nouveaux outils MCP à la volée.

### 6.8 Surveys et Méta-analyses

| Paper | arXiv | Sujet |
|-------|-------|-------|
| Memory in the Age of AI Agents | [2512.13564](https://arxiv.org/abs/2512.13564) | Survey mémoire agents (taxonomie factuel/expérientiel/working) |
| Agentic RAG | [2501.09136](https://arxiv.org/abs/2501.09136) | RAG avec agents autonomes (reflection, planning, tool use) |
| AI Agentic Programming | [2508.11126](https://arxiv.org/abs/2508.11126) | Survey agents de codage autonomes |
| Impact of AGENTS.md | [2601.20404](https://arxiv.org/abs/2601.20404) | Étude sur les fichiers de contexte agent (60k+ repos) |

### 6.9 Stress Test RLM (01/02/2026)

Test des limites de BM25 sur 100 chunks / 146 insights :

| Requête | Score top-1 | Verdict |
|---------|-------------|---------|
| "pourquoi layout produit changé" | 3.70 ✅ | BM25 suffisant |
| "tous les bugs website_joyjuice" | 3.11 ⚠️ | Pertinent mais incomplet |
| "décisions entre 25 et 30 janvier" | 2.92 ❌ | **Échec** — retourne le 18 janvier |

**Conclusion** : BM25 marche à 80%. Échoue sur requêtes temporelles et agrégation.
→ Décision : implémenter filtre temporel (Phase 7.1) + extraction entités (Phase 7.2).

---

## 7. Implémentations Open Source

### 7.1 RLM Officiel

| Repo | Description | Lien |
|------|-------------|------|
| **rlm** | Implémentation principale | [github.com/alexzhang13/rlm](https://github.com/alexzhang13/rlm) |
| **rlm-minimal** | POC minimal | [github.com/alexzhang13/rlm-minimal](https://github.com/alexzhang13/rlm-minimal) |

### 7.2 Communauté

| Repo | Description |
|------|-------------|
| **ysz/recursive-llm** | Python simplifié |
| **fullstackwebdev/rlm_repl** | POC avec REPL |
| **codecrack3/RLM-DSpy** | Intégration DSPy |

### 7.3 Letta

| Repo | Description |
|------|-------------|
| **letta-ai/letta** | Framework principal |

---

## 8. Synthèse : Quelle Approche pour Joy Juice ?

### 8.1 Notre contexte spécifique

- **Conversations longues** avec Claude Code
- **Documents de référence** (CLAUDE.md, PROJECT_*.md, etc.)
- **Historique de session** qui s'accumule
- **Pas besoin de persistance** entre sessions (fichiers suffisent)

### 8.2 Recommandation : RLM adapté

**Pourquoi RLM plutôt que Letta ?**

1. Plus léger (pas de vector DB)
2. Plus adapté aux conversations (vs agents persistants)
3. Python REPL déjà disponible dans Claude Code
4. Moins d'overhead d'infrastructure

**Ce qu'on doit adapter :**

1. Utiliser les fichiers comme "context store" au lieu de variables Python
2. Intégrer avec les tools Claude Code existants (Read, Grep, Glob)
3. Créer un mécanisme de chunking intelligent pour l'historique

---

## 9. Sources et Références

### Papers
- Zhang et al. (2025). "Recursive Language Models". arXiv:2512.24601
- Packer et al. (2023). "MemGPT: Towards LLMs as Operating Systems". arXiv:2310.08560
- NVIDIA (2025). "TTT-E2E: Test-Time Training for Long Context". arXiv:2512.23675

### Articles
- [Prime Intellect: RLM - The Paradigm of 2026](https://www.primeintellect.ai/blog/rlm)
- [Alex Zhang: Recursive Language Models](https://alexzhang13.github.io/blog/2025/rlm/)
- [The Neuron: RLM Explainer](https://www.theneuron.ai/explainer-articles/recursive-language-models-rlms)
- [Letta: V1 Agent Architecture](https://www.letta.com/blog/letta-v1-agent)

### Implémentations
- [github.com/alexzhang13/rlm](https://github.com/alexzhang13/rlm)
- [github.com/letta-ai/letta](https://github.com/letta-ai/letta)
- [github.com/test-time-training/e2e](https://github.com/test-time-training/e2e)

---

**Version** : 2.0
**Auteur** : Ahmed + Claude
**Dernière MAJ** : 2026-02-01
**Licence** : Usage interne Joy Juice
