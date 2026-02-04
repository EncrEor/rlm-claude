## RLM - PERSISTENT MEMORY (v0.10.0)

### Philosophy

The user decides when to chunk. The system automatically saves before /compact.

### Session startup (required)

```python
# 1. Load universal rules
rlm_recall(importance="critical")

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

### Auto-save

The PreCompact hook creates a minimal chunk before each /compact.
After compaction, you can read this chunk and enrich it if needed.

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
rlm_recall(importance="critical")  # all universal rules
```
