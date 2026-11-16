import re

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from books_mcp.client import OpenLibraryClient, OpenLibraryError
from books_mcp.tools._errors import openlibrary_errors

WORK_ID = re.compile(r"OL\d+W")
MAX_SUBJECTS = 10


def register(app: MCPServer, client: OpenLibraryClient):
    @app.tool()
    @openlibrary_errors
    def book_detail(work_id: str) -> dict:
        """
        Returns the description and subjects of one book.
        - work_id: an Open Library work id such as OL59800W, taken from search_books.
        Use this tool after search_books, when the user wants to know what a specific book is
        about. Don't guess a work_id: search for the book first.
        Not every book has a description. When it is null, say so.
        """
        if not WORK_ID.fullmatch(work_id.strip().upper()):
            raise ToolError(
                f"'{work_id}' is not a work id. They look like OL59800W and come from search_books."
            )
        work_id = work_id.strip().upper()
        try:
            work = client.work(work_id)
        except OpenLibraryError as e:
            if e.is_not_found:
                raise ToolError(
                    f"No book found with work id {work_id}. Check it with search_books."
                ) from e
            raise

        # The description is a plain string on some works and {"type", "value"} on others
        description = work.get("description")
        if isinstance(description, dict):
            description = description.get("value")
        return {
            "work_id": work_id,
            "title": work.get("title"),
            "description": description,
            "subjects": work.get("subjects", [])[:MAX_SUBJECTS],
            "link": f"https://openlibrary.org/works/{work_id}",
        }
