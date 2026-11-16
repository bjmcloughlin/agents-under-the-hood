import logging
import sys

from mcp.server.mcpserver import MCPServer

from books_mcp.client import OpenLibraryClient
from books_mcp.tools import book_detail, search_books

NAME = "books"
USER_AGENT = "books-mcp-example/0.1 (learning example)"

INSTRUCTIONS = """Open Library is a public catalogue of books.
Find a book with search_books, then pass its work_id to book_detail for the description.
Give the book's link when you describe it."""


def build_server() -> MCPServer:
    # stdout carries the protocol in stdio mode, so every log line goes to stderr
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format=f"%(asctime)s %(levelname)s {NAME} %(name)s: %(message)s",
    )
    app = MCPServer(name=NAME, instructions=INSTRUCTIONS)
    # One client shared by every tool, so they share a connection pool
    client = OpenLibraryClient(USER_AGENT)
    for tool in (search_books, book_detail):
        tool.register(app, client)
    return app


def main():
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
