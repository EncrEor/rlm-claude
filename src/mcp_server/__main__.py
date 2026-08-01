"""Allow running as: python -m mcp_server

Also exposes where the bundled hooks and templates live. Someone who installed
with `pip install` has no repo checkout, so printing the path is the only way
for them to wire the hooks into Claude Code's settings.json.
"""

import sys
from pathlib import Path

from mcp_server.server import main

USAGE = """RLM MCP server.

  python -m mcp_server                  start the server (default)
  python -m mcp_server --hooks-dir      print the bundled hooks directory
  python -m mcp_server --templates-dir  print the bundled templates directory
"""


def bundled_path(name: str) -> Path:
    """Return the path to a directory shipped inside the installed package."""
    return Path(__file__).resolve().parent / name


def cli(argv: list[str]) -> int:
    if "--help" in argv or "-h" in argv:
        print(USAGE, end="")
        return 0

    for flag, name in (("--hooks-dir", "hooks"), ("--templates-dir", "templates")):
        if flag in argv:
            path = bundled_path(name)
            if not path.is_dir():
                # Editable/source installs keep these at the repo root instead.
                fallback = Path(__file__).resolve().parents[2] / name
                if fallback.is_dir():
                    print(fallback)
                    return 0
                print(f"{name} directory not found in this install", file=sys.stderr)
                return 1
            print(path)
            return 0

    main()
    return 0


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
