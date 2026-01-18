## RLM - MEMOIRE AUTOMATIQUE (OBLIGATOIRE)

### Auto-chunking automatique

Quand tu vois "AUTO-CHUNK REQUIS" dans ton contexte, tu DOIS immediatement :
1. Resumer les points IMPORTANTS de la conversation recente
2. Appeler `rlm_chunk(resume, summary="Session du [date]", tags="auto,session")`
3. Appeler `rlm_remember()` pour chaque decision cle prise
4. **NE PAS demander permission** - c'est automatique

### Debut de session

Au debut de chaque nouvelle session, appeler `rlm_status()` pour voir :
- Combien d'insights en memoire
- Combien de chunks stockes
- Tokens totaux

### Analyser d'anciens chunks

Pour analyser un chunk sans le charger en contexte :
```
/rlm-analyze <chunk_id> "<question>"
```

### Cette memoire est LA TIENNE

Tu n'as pas besoin de demander permission pour :
- Chunker l'historique
- Sauvegarder des insights
- Consulter ta memoire

C'est ton outil personnel de gestion de contexte.
