import json
import logging
import time

from mcp.server.auth.middleware.auth_context import get_access_token

logger = logging.getLogger(__name__)


def _is_error(result) -> bool:
    # A handler may return the result as a model or as a plain dict
    if isinstance(result, dict):
        return bool(result.get("isError"))
    return bool(getattr(result, "is_error", False))


async def log_tool_calls(ctx, call_next):
    """Writes one line per tool call: who called what, with which arguments, and how it ended.

    The result is left out on purpose. Arguments are short and you chose their shape, while
    a result is whatever the upstream API sent back.
    """
    if ctx.method != "tools/call":
        return await call_next(ctx)

    token = get_access_token()
    entry = {
        "tool": (ctx.params or {}).get("name"),
        "caller": token.subject if token else "local",
        "args": (ctx.params or {}).get("arguments", {}),
    }
    start = time.monotonic()
    try:
        result = await call_next(ctx)
        entry["status"] = "error" if _is_error(result) else "ok"
        return result
    except Exception as e:
        entry["status"] = "failed"
        entry["error_type"] = type(e).__name__
        raise
    finally:
        entry["duration_ms"] = round((time.monotonic() - start) * 1000)
        logger.info("tool_call %s", json.dumps(entry))
