# mcp-server

A small [Model Context Protocol](https://modelcontextprotocol.io) server with two tools over the [Open Library](https://openlibrary.org/developers/api) API, which is free and needs no key. Companion code for [Building an MCP server](https://benmcloughlin.com/learning/building-mcp-servers) and [Hosting an MCP server](https://benmcloughlin.com/learning/hosting-mcp-servers).

It is laid out the way a server you'd keep would be, at the smallest size that still shows the layers:

```
src/books_mcp/
├── server.py           # build_server() wires it together, main() picks stdio or HTTP
├── client.py           # the only file that talks to Open Library
├── auth.py             # part two: checks the access token on every HTTP request
├── audit.py            # part two: one log line per tool call
└── tools/
    ├── _errors.py      # turns upstream failures into errors the model can act on
    ├── search_books.py # one module per tool
    └── book_detail.py
```

## Setup

You need Python 3.12+, [uv](https://docs.astral.sh/uv/) and, for the Inspector, Node.js.

```bash
cd mcp-server
uv sync
```

## Run it

```bash
uv run books-mcp
```

Started by hand, the process sits there and prints nothing. It's waiting for a client to speak the protocol on stdin. `Ctrl+C` stops it.

## Try it in the MCP Inspector

The [Inspector](https://github.com/modelcontextprotocol/inspector) starts the server for you and gives you a browser page to list and call its tools:

```bash
npx @modelcontextprotocol/inspector uv run books-mcp
```

Open the URL it prints, click **Connect**, open **Tools** and list them.

| Tool | Input | What you should get |
|------|-------|---------------------|
| `search_books` | `query`: `left hand of darkness` | Results with a `work_id` each |
| `book_detail` | `work_id`: `OL59800W` | Title, description, subjects, link |
| `book_detail` | `work_id`: `banana` | An error telling the model what a work id looks like |
| `book_detail` | `work_id`: `OL99999999999W` | An error saying no book has that id |

To see what happens when the upstream API is down, point the server at an address nothing is listening on:

```bash
OPENLIBRARY_URL=http://127.0.0.1:9 npx @modelcontextprotocol/inspector uv run books-mcp
```

Every call now comes back as "Open Library is temporarily unavailable", and the real cause is in the server's log.

## Part two: run it over HTTP in a container

Over HTTP the server refuses to start without auth settings. To try it without a cloud tenant, `scripts/local_issuer.py` stands in for an identity provider: it makes a signing key, serves the public half and prints test tokens. You need Docker for this part.

In one terminal, start the issuer and keep it running. It prints `export` lines for four tokens:

```bash
uv run python scripts/local_issuer.py
```

In a second terminal, build and run the server. The container reaches the issuer on your machine through `host.docker.internal`:

```bash
docker build -t books-mcp:local .
docker run --rm --name books-mcp-test -p 8080:8000 \
  -e MCP_AUTH_ISSUER=http://localhost:9000 \
  -e MCP_AUTH_JWKS_URL=http://host.docker.internal:9000/jwks.json \
  -e MCP_AUTH_AUDIENCE=http://localhost:8080/mcp \
  -e MCP_PUBLIC_URL=http://localhost:8080/mcp \
  books-mcp:local
```

In a third, paste the `export` lines from the issuer, then call the server:

```bash
# No token: 401, with a pointer to the metadata that says where to sign in
curl -si -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# A valid token, through the Inspector's command line mode
npx @modelcontextprotocol/inspector --cli http://localhost:8080/mcp --transport http \
  --header "Authorization: Bearer $GOOD" \
  --method tools/call --tool-name search_books --tool-arg query="left hand of darkness"
```

Swap `$GOOD` for `$WRONG_AUDIENCE` or `$EXPIRED` (both 401) or `$NO_SCOPE` (403). Each call the server accepts writes a `tool_call` line to the container's log.

The local issuer is for testing only. Its key lives in memory and it hands a token to anyone who runs it.

## Part two: the Azure file

`infra/main.bicep` declares everything one hosted server needs: a registry, a vault, a managed identity, a log workspace and the container app. It compiles (`az bicep build --file infra/main.bicep`) but has not been deployed, so use it to read how the parts connect, not as a tested template.
