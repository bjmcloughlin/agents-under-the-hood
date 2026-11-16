# mcp-server

A small [Model Context Protocol](https://modelcontextprotocol.io) server with two tools over the [Open Library](https://openlibrary.org/developers/api) API, which is free and needs no key. Companion code for [Building an MCP server](https://benmcloughlin.com/learning/building-mcp-servers).

It is laid out the way a server you'd keep would be, at the smallest size that still shows the layers:

```
src/books_mcp/
├── server.py           # build_server() wires it together, main() runs it over stdio
├── client.py           # the only file that talks to Open Library
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
