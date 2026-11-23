FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# Install exactly what the lock file says, without dev tools
RUN uv sync --frozen --no-dev

# In a container the server speaks HTTP and listens on every interface.
# Nothing secret is set here: auth settings and credentials arrive at run time.
ENV PATH="/app/.venv/bin:$PATH" \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

# Don't run as root
USER nobody
EXPOSE 8000
CMD ["books-mcp"]
