# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.9.x   | :white_check_mark: |
| < 0.9   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in RLM, please report it responsibly:

1. **Do NOT open a public issue**
2. Use [GitHub Private Vulnerability Reporting](https://github.com/EncrEor/rlm-claude/security/advisories/new)
3. Or email: ahmed@joyjuice.co

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response timeline

- **Acknowledgment**: within 48 hours
- **Initial assessment**: within 7 days
- **Fix release**: as soon as possible, depending on severity

## Security Measures

RLM includes built-in protections (see `mcp_server/tools/fileutil.py`):

- **Path traversal prevention** - Chunk IDs validated against strict allowlist, resolved paths checked
- **Atomic writes** - Write-to-temp-then-rename prevents corruption
- **File locking** - `fcntl.flock` exclusive locks for concurrent access
- **Content size limits** - 2 MB chunks, 10 MB decompression cap
- **SHA-256 hashing** - For content deduplication

## Scope

RLM is a local MCP server. All data is stored on disk in `~/.claude/rlm/context/`. No data is sent to external services.
