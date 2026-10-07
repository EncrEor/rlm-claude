## RLM - PERSISTENT MEMORY (v0.11.0)

### Philosophy

Chunking is a deliberate act: nothing is ever chunked automatically. The hooks only make sure an unsaved session cannot go unnoticed.

### Session startup (required)

```python
# 1. Load universal rules — pass a limit above your critical count.
#    The default is 10, and a recall returning 10 of 34 rules looks
#    exactly like a complete one.
rlm_recall(importance="critical", limit=50)

# 2. If working on a specific topic, load context
rlm_recall(query="the_topic")

# 3. Memory status
rlm_status()
```

### When to chunk (Claude reflex)

**Chunk proactively when:**
- Important decision made
- Task completed successfully
- Insight or rule discovered
- Major topic change
- Bug fixed (document the cause)

**Chunk on user instruction:**
- "remember this"
- "chunk this discussion"
- "rlm_remember this decision"

### Chunk types (chunk_type)

| Type | Usage |
|------|-------|
| `session` | Session log (default) |
| `snapshot` | State of a topic at a point in time |
| `debug` | Bug + solution |
| `insight` | Redirected to `rlm_remember()` |

### Importance levels (insights)

| Importance | When to use |
|------------|------------|
| `critical` | Universal rule (applies regardless of topic) |
| `high` | Topic-specific rule |
| `medium` | Useful info, not blocking |

**Test**: "Does this apply even when working on a completely different topic?" → `critical`

### Safety nets (hooks)

- **Manual `/compact` is blocked** when nothing was chunked in the last 15 minutes: chunk, then re-run it. Auto-compact is never blocked, only warned — so chunk at milestones, not at the end.
- **Unsaved sessions are reported at startup**: a past session that changed files (or ran a notable program) and ended without a chunk is listed with its transcript path. Tell the user, then either recover it (have a subagent read the transcript and `rlm_chunk()` the summary) or, if it holds nothing worth keeping, acknowledge it:
  `python3 ~/.claude/rlm/hooks/session_orphans.py --ack <session_id> "reason"`. Ask the user before either.

### This memory is YOURS

You don't need permission to:
- Chunk conversation history
- Save insights
- Search your memory

It's your personal context management tool.

### Useful commands

```python
# Save a universal insight
rlm_remember("content", category="decision", importance="critical", tags="universal")

# Save a topic-specific insight
rlm_remember("content", category="finding", importance="high", tags="topic,subtopic")

# Chunk a discussion (typed)
rlm_chunk("summary", summary="Session 04/02", tags="session", chunk_type="session")

# Search history
rlm_search("topic")
rlm_recall(query="keyword")
rlm_recall(importance="critical", limit=50)  # all universal rules (default limit is 10)
```
