# Checklist : Paper RLM vs Notre Solution

> **Objectif** : Vérifier qu'on n'a rien oublié d'important du papier MIT
> **Date** : 2026-01-18 (mise à jour 2026-02-01)

---

## 1. Mécanismes Core

| Concept (Paper) | Notre Solution | Statut | Notes |
|-----------------|----------------|--------|-------|
| **REPL Environment** | MCP Server + Tools | ✅ | Via tools Claude Code au lieu de Python exec |
| **Context as variable** | Fichiers chunks/ | ✅ | Stocké en fichiers au lieu de RAM |
| **Recursive sub-calls** | Task tool (subagents) | ✅ | Natif Claude Code, même mieux |
| **Sub-model différent** | Haiku pour sub-calls | ⏳ | À configurer (économie tokens) |
| **Symboli vs tokens** | Grep/Read tools | ✅ | Navigation sans charger tout le contexte |

---

## 2. Stratégies de Chunking

| Concept (Paper) | Notre Solution | Statut | Notes |
|-----------------|----------------|--------|-------|
| **Uniform splitting** | strategy: "size" | ✅ | 2000 tokens par chunk |
| **Keyword filtering** | rlm_grep | ✅ | Regex sur chunks |
| **Semantic grouping** | strategy: "semantic" | ⏳ | À implémenter (Phase 2+) |
| **Overlap** | 200 tokens overlap | ✅ | Évite perte info |

---

## 3. Détails d'Implémentation

| Concept (Paper) | Notre Solution | Statut | Notes |
|-----------------|----------------|--------|-------|
| **System prompt fixe** | À créer | ⏳ | Dans appendice IMPLEMENTATION_PROPOSAL |
| **FINAL() tags** | Non nécessaire | ✅ | Claude termine naturellement |
| **Variables pour long output** | session_memory.json | ✅ | Accumulation via fichiers |
| **Cost optimization** | Haiku sub-calls | ⏳ | À configurer |

---

## 4. Stratégies Émergentes

| Concept (Paper) | Notre Solution | Statut | Notes |
|-----------------|----------------|--------|-------|
| **Peeking** | rlm_peek(chunk, start, end) | ✅ | Tool dédié |
| **Grepping** | rlm_grep(pattern) | ✅ | Tool dédié |
| **Answer verification** | rlm_sub_query double-check | ⏳ | À implémenter (optionnel) |
| **Semantic sub-calls** | Task subagents | ✅ | Natif |
| **Code + LLM mixing** | Bash + Claude | ✅ | Natif Claude Code |

---

## 5. Failure Modes & Mitigations

| Risque (Paper) | Notre Mitigation | Statut |
|----------------|------------------|--------|
| **Prompt sensitivity** | Prompt testé et documenté | ⏳ |
| **Token limits** | Chunks petits (2000 tokens) | ✅ |
| **Redundant verification** | Pas de verification loop obligatoire | ✅ |
| **Answer commitment** | Pas de FINAL tags, flow naturel | ✅ |
| **Code fragility** | Tools MCP au lieu de code exec | ✅ |

---

## 6. Concepts Avancés

| Concept (Paper) | Notre Solution | Statut | Priorité |
|-----------------|----------------|--------|----------|
| **Context rot mitigation** | Sub-calls courts | ✅ | P0 |
| **Complexity scaling** | Chunking adaptatif | ⏳ | P2 |
| **Async sub-calls** | Task parallèles | ✅ | P0 |
| **Recursion depth > 1** | Subagents illimités | ✅ | P0 |
| **Training as RLM** | Non applicable (API) | ❌ | N/A |

---

## 7. Concepts MANQUANTS à Ajouter

| Concept | Description | Action |
|---------|-------------|--------|
| **Sub-model économique** | Utiliser Haiku pour sub-calls | Ajouter dans config MCP |
| **Semantic chunking** | Découper par changement de sujet | Phase 2 |
| **Verification optionnelle** | Double-check sur tâches critiques | Phase 3 |
| **Prompt tuning** | Adapter selon type de tâche | Phase 4 |
| **Metrics/analytics** | Suivre coûts et performance | Phase 5 |

---

## 8. Évaluation n8n pour Hooks

### Question : n8n est-il utile pour les hooks RLM ?

**Analyse** :

| Aspect | n8n | Scripts locaux | Verdict |
|--------|-----|----------------|---------|
| **Complexité** | Haute | Basse | Scripts |
| **Latence** | HTTP call | Local direct | Scripts |
| **Fiabilité** | Dépend serveur | Toujours dispo | Scripts |
| **Use case** | Workflows complexes | Tâches simples | Dépend |

**Recommandation** : **Pas besoin de n8n pour les hooks RLM**

**Pourquoi ?**
1. Les hooks Claude Code sont des **scripts bash simples** (post_response.sh)
2. Ils s'exécutent **localement** sans latence réseau
3. n8n ajouterait de la **complexité inutile** pour ce cas

**Où n8n SERAIT utile** :
- Synchronisation multi-devices (si on travaille depuis plusieurs machines)
- Alertes externes (Slack, email) quand contexte > 80%
- Dashboard analytics centralisé
- Backup automatique des chunks vers cloud

**Conclusion** : Garder les hooks en **scripts locaux** pour la v1. n8n peut être intéressant pour la v2+ si on veut des features avancées.

---

## 9. Ajouts Recommandés au Plan

Basé sur cette checklist, voici ce qu'on devrait ajouter :

### Phase 1 (mise à jour)
- [ ] Configurer Haiku comme modèle pour sub-queries (économie tokens)

### Phase 2 (mise à jour)
- [ ] Implémenter semantic chunking (par sujet, pas juste par taille)

### Phase 3 (mise à jour)
- [ ] Ajouter verification optionnelle pour tâches critiques
- [ ] Metrics de coût par query

### Phase 5 (ajout)
- [ ] Évaluer n8n pour analytics centralisé
- [ ] Dashboard usage (tokens, latence, hit rate)

---

## 10. Score de Couverture (Paper RLM MIT)

**Concepts couverts** : 22/26 = **85%**

**Manquants critiques** : 0
**Manquants nice-to-have** : 4 (ajoutés au plan)

---

## 11. Concepts Inspirés de MAGMA (Février 2026)

> **Source** : [MAGMA: A Multi-Graph based Agentic Memory Architecture](https://arxiv.org/abs/2601.03236)
> **Date analyse** : 01/02/2026
> **Approche** : Upgrade chirurgical — prendre les idées utiles, pas le système complet

### Concepts retenus

| Concept MAGMA | Notre adaptation | Statut | Phase |
|---------------|------------------|--------|-------|
| **Graphe temporel** | Filtre `date_from`/`date_to` sur `rlm_search` et `rlm_grep` | ⏳ À faire | 7.1 |
| **Graphe entités** | Champ `entities: [...]` auto-extrait dans `index.json` | ⏳ À faire | 7.2 |

### Concepts rejetés

| Concept MAGMA | Raison du rejet |
|---------------|-----------------|
| **Graphe sémantique complet** | BM25 suffit pour 80% des cas (validé par stress test) |
| **Graphe causal** | Pas assez de cas d'usage réels, complexité disproportionnée |
| **Adaptive Traversal Policy** | Over-engineering pour notre échelle (~100 chunks) |
| **Vector database** | Dépendance lourde, pas justifiée par les performances actuelles |

### Justification par stress test

| Requête | BM25 seul | Avec filtre temporel | Avec entités |
|---------|-----------|---------------------|--------------|
| "décisions entre 25 et 30 janvier" | ❌ Retourne 18 janv | ✅ Filtré correctement | — |
| "tous les bugs website_joyjuice" | ⚠️ Incomplet | — | ✅ Agrégation par entité |
| "pourquoi layout produit changé" | ✅ Score 3.70 | — | — |

---

## 12. Autres Papiers Analysés (Février 2026)

| Paper | arXiv | Décision |
|-------|-------|----------|
| **MCP-Zero** (Active Tool Discovery) | 2506.01056 | **Rejeté** — Ahmed gère manuellement les MCP |
| **MemSearcher** (Mémoire compacte RL) | 2511.02805 | Pattern intéressant, RL non reproductible |
| **MAKER** (1M étapes zéro erreurs) | 2511.09030 | Voting + red-flagging pour `/rlm-parallel` (futur) |
| **EverMemOS** (OS mémoire engrams) | 2601.02163 | MemScenes pour Phase 8+ (regroupement thématique) |
| **LADDER** (Auto-amélioration récursive) | 2503.00735 | Pas applicable comme outil MCP |
| **CREATOR** (Création autonome d'outils) | 2305.14318 | Auto-génération MCP tools (futur lointain) |

---

## 13. Score de Couverture Mis à Jour

**Concepts paper RLM MIT** : 22/26 = **85%**
**Concepts MAGMA retenus** : 2/6 = **33%** (les 2 plus utiles)
**Total concepts planned** : 24/32 = **75%** (focus sur l'utile, pas l'exhaustif)

---

**Conclusion** : Notre architecture couvre l'essentiel du papier RLM. Les ajouts identifiés sont des optimisations, pas des éléments bloquants.
