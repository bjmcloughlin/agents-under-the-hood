from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from books_mcp.client import OpenLibraryClient
from books_mcp.tools._errors import openlibrary_errors

MAX_LIMIT = 20


def register(app: MCPServer, client: OpenLibraryClient):
    @app.tool()
    @openlibrary_errors
    def search_books(query: str, limit: int = 5) -> dict:
        """
        Searches Open Library for books by title, author or both, best match first.
        - query: words from the title and/or the author's name, e.g. "left hand of darkness".
        - limit: how many results to return, 1 to 20.
        Each result has a work_id, the title, the authors, the year it was first published and
        how many editions exist.
        Use this tool first whenever the user names a book or an author. To get a book's
        description and subjects, pass its work_id to book_detail.
        If nothing matches, the results list is empty: tell the user rather than guessing.
        """
        if not query.strip():
            raise ToolError("query is empty. Pass words from the title or the author's name.")
        if not 1 <= limit <= MAX_LIMIT:
            raise ToolError(f"limit must be between 1 and {MAX_LIMIT}.")

        data = client.search(query, limit)
        return {
            "total_matches": data.get("numFound", 0),
            "results": [
                {
                    "work_id": doc["key"].removeprefix("/works/"),
                    "title": doc.get("title"),
                    "authors": doc.get("author_name", []),
                    "first_published": doc.get("first_publish_year"),
                    "editions": doc.get("edition_count"),
                }
                for doc in data.get("docs", [])
            ],
        }
