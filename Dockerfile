FROM python:3.12-slim

WORKDIR /app

# Copy package files
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

# Install with search and fuzzy dependencies (no semantic to keep image small)
RUN pip install --no-cache-dir ".[search,fuzzy]"

# Data volume for persistent storage
VOLUME /data
ENV RLM_CONTEXT_DIR=/data

# MCP server runs on stdio
ENTRYPOINT ["mcp-rlm-server"]
