"""
RLM File Utilities - Safe I/O operations.

Provides:
- Atomic writes (write-to-temp-then-rename)
- File locking for concurrent access
- Chunk ID validation against path traversal
- JSON loading with structure validation
"""

import fcntl
import json
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

# Chunk ID format: alphanumeric, hyphens, underscores, dots, ampersands
# Blocks path traversal sequences like "../" or absolute paths
CHUNK_ID_PATTERN = re.compile(r"^[\w.&-]+$")


def resolve_context_dir() -> Path:
    """Resolve the context directory for RLM storage.

    Strategy (first match wins):
    1. ~/.claude/rlm/context/ if it has data (chunks/ non-empty or index.json exists with chunks)
    2. Project root context/ (git clone layout: walk up from this file to find context/)
    3. ~/.claude/rlm/context/ as fallback (fresh install)
    """
    # Option 1: User-level storage with existing data
    user_dir = Path.home() / ".claude" / "rlm" / "context"
    if user_dir.exists():
        index = user_dir / "index.json"
        if index.exists():
            try:
                data = json.loads(index.read_text())
                if data.get("chunks"):
                    return user_dir
            except (json.JSONDecodeError, OSError):
                pass

    # Option 2: Project-root context/ (git clone with src/ layout)
    # __file__ = .../src/mcp_server/tools/fileutil.py → 4 parents up = project root
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    project_context = project_root / "context"
    if project_context.exists():
        return project_context

    # Option 3: Fallback to user-level (fresh install or pip install)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


# Shared resolved context directory
CONTEXT_DIR = resolve_context_dir()

# Maximum sizes
MAX_CHUNK_CONTENT_SIZE = 2 * 1024 * 1024  # 2 MB
MAX_DECOMPRESSED_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_chunk_id(chunk_id: str) -> bool:
    """
    Validate chunk ID format to prevent path traversal.

    Allows: alphanumeric, hyphens, underscores, dots, ampersands.
    Blocks: slashes, "..", null bytes, and other special characters.

    Args:
        chunk_id: The chunk ID to validate

    Returns:
        True if valid, False otherwise
    """
    if not chunk_id or len(chunk_id) > 200:
        return False
    return bool(CHUNK_ID_PATTERN.match(chunk_id))


def safe_path(base_dir: Path, chunk_id: str, suffix: str = ".md") -> Path | None:
    """
    Build a safe file path from chunk ID, validating against traversal.

    Args:
        base_dir: The directory the file must remain within
        chunk_id: The chunk ID
        suffix: File extension (default: ".md")

    Returns:
        Safe Path object, or None if validation fails
    """
    if not validate_chunk_id(chunk_id):
        return None

    file_path = base_dir / f"{chunk_id}{suffix}"

    # Double-check: resolved path must be under base_dir
    try:
        file_path.resolve().relative_to(base_dir.resolve())
    except ValueError:
        return None

    return file_path


def atomic_write_json(filepath: Path, data: dict, ensure_ascii: bool = False) -> None:
    """
    Write JSON atomically using write-to-temp-then-rename.

    On POSIX systems, rename is atomic, so the file is never in a
    half-written state.

    Args:
        filepath: Target file path
        data: Dictionary to serialize as JSON
        ensure_ascii: Whether to escape non-ASCII characters
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory (same filesystem = atomic rename)
    fd, tmp_path = tempfile.mkstemp(dir=filepath.parent, prefix=f".{filepath.name}.", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=ensure_ascii)
        Path(tmp_path).replace(filepath)  # Atomic on POSIX
    except BaseException:
        # Clean up temp file on any error
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def atomic_write_text(filepath: Path, content: str) -> None:
    """
    Write text file atomically using write-to-temp-then-rename.

    Args:
        filepath: Target file path
        content: Text content to write
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=filepath.parent, prefix=f".{filepath.name}.", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(content)
        Path(tmp_path).replace(filepath)
    except BaseException:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


@contextmanager
def locked_json_update(filepath: Path, default: dict | None = None):
    """
    Context manager for locked read-modify-write on a JSON file.

    Acquires an exclusive lock, yields the data for modification,
    then writes back atomically.

    Usage:
        with locked_json_update(INDEX_FILE, default={"chunks": []}) as data:
            data["chunks"].append(new_chunk)

    Args:
        filepath: Path to JSON file
        default: Default data if file doesn't exist
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Create file if it doesn't exist
    if not filepath.exists() and default is not None:
        atomic_write_json(filepath, default)

    # Open with exclusive lock
    lock_file = filepath.with_suffix(filepath.suffix + ".lock")
    lock_fd = open(lock_file, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        # Read current data
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = default.copy() if default else {}

        # Yield for modification
        yield data

        # Write back atomically
        atomic_write_json(filepath, data)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        try:
            lock_file.unlink(missing_ok=True)
        except OSError:
            pass


def load_json_safe(
    filepath: Path, default: dict | None = None, required_keys: list | None = None
) -> dict:
    """
    Load JSON with basic structure validation.

    Args:
        filepath: Path to JSON file
        default: Default to return if file doesn't exist
        required_keys: Keys that must be present in the loaded dict

    Returns:
        Loaded dictionary

    Raises:
        ValueError: If structure validation fails
    """
    if not filepath.exists():
        return default.copy() if default else {}

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected dict in {filepath.name}, got {type(data).__name__}")

    if required_keys:
        missing = [k for k in required_keys if k not in data]
        if missing:
            raise ValueError(f"Missing keys in {filepath.name}: {missing}")

    return data
