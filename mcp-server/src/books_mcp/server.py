import logging
import os
import sys
from urllib.parse import urlsplit

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from books_mcp import auth
from books_mcp.audit import log_tool_calls
from books_mcp.client import OpenLibraryClient
from books_mcp.tools import book_detail, search_books

NAME = "books"
# Open Library asks regular callers to identify themselves with a contact address.
# It is the one setting this server treats as a secret, so that there is one to manage.
CONTACT = os.environ.get("OPENLIBRARY_CONTACT", "learning example")
USER_AGENT = f"books-mcp-example/0.1 ({CONTACT})"

INSTRUCTIONS = """Open Library is a public catalogue of books.
Find a book with search_books, then pass its work_id to book_detail for the description.
Give the book's link when you describe it."""


def build_server(**options) -> MCPServer:
    # stdout carries the protocol in stdio mode, so every log line goes to stderr
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format=f"%(asctime)s %(levelname)s {NAME} %(name)s: %(message)s",
    )
    app = MCPServer(name=NAME, instructions=INSTRUCTIONS, middleware=[log_tool_calls], **options)
    # One client shared by every tool, so they share a connection pool
    client = OpenLibraryClient(USER_AGENT)
    for tool in (search_books, book_detail):
        tool.register(app, client)
    return app


def main():
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        build_server().run(transport="stdio")
        return

    # Over HTTP anyone who can reach the port can call the tools, so there is
    # no way to start without auth: from_env() exits if a setting is missing.
    settings, verifier = auth.from_env()
    public_host = urlsplit(os.environ["MCP_PUBLIC_URL"]).netloc
    build_server(auth=settings, token_verifier=verifier).run(
        transport="streamable-http",
        host=os.environ.get("MCP_HOST", "127.0.0.1"),
        port=int(os.environ.get("MCP_PORT", "8000")),
        # Only answer requests addressed to the server's own public name
        transport_security=TransportSecuritySettings(allowed_hosts=[public_host]),
    )


if __name__ == "__main__":
    main()
