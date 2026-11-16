import functools
import logging

from mcp.server.mcpserver.exceptions import ToolError

from books_mcp.client import OpenLibraryError

logger = logging.getLogger(__name__)


def openlibrary_errors(fn):
    """Turns an upstream failure the model can do something about into a ToolError."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except OpenLibraryError as e:
            if e.is_transient:
                logger.warning("%s transient failure: %s", fn.__name__, e)
                raise ToolError(
                    "Open Library is temporarily unavailable. Try again in a minute."
                ) from e
            # Anything else is a bug in this server, so let it surface as a crash
            logger.error("%s failed: %s", fn.__name__, e)
            raise

    return wrapper
