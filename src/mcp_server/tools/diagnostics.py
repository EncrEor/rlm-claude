# ABOUTME: Minimal append-only warning log so degraded operations stop being silent.
# ABOUTME: Optional features (semantic search) may fail; they must still leave a trace.
"""
RLM Diagnostics - Never fail silently.

Optional subsystems (embeddings, semantic search) are allowed to fail without
blocking a chunk write. They are NOT allowed to fail without saying so: a
silent degradation is indistinguishable from correct behaviour, and stays
invisible until someone audits the data months later.

Writes to CONTEXT_DIR/rlm.log (append-only, capped). Reading it back is what
`rlm_status` uses to surface recent problems.
"""

from datetime import datetime

from .fileutil import CONTEXT_DIR

LOG_FILE = CONTEXT_DIR / "rlm.log"
MAX_LOG_BYTES = 512 * 1024  # Rotate once past this; keeps the tail, drops the head


def log_warning(component: str, message: str) -> None:
    """Append a warning line to the RLM log. Never raises.

    Args:
        component: Subsystem reporting the problem (e.g. "embeddings")
        message: What went wrong, in plain terms
    """
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_BYTES:
            tail = LOG_FILE.read_text(encoding="utf-8", errors="replace")[-MAX_LOG_BYTES // 2 :]
            LOG_FILE.write_text(tail, encoding="utf-8")

        stamp = datetime.now().isoformat(timespec="seconds")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{stamp} [{component}] {message}\n")
    except Exception:
        pass  # A logger that breaks the caller is worse than no logger


def recent_warnings(limit: int = 5) -> list[str]:
    """Return the most recent warning lines, newest last. Never raises."""
    try:
        if not LOG_FILE.exists():
            return []
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        return [line for line in lines if line.strip()][-limit:]
    except Exception:
        return []
