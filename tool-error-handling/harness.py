"""
The harness: retry, dispatch, and the circuit breaker.

Nothing in this file inspects an error message or imports a vendor library —
that's the design. Tools translate their native failures into the three-word
vocabulary in errors.py; this file only dispatches on type. It cannot be broken
by a vendor rewording an error message, because it never reads one.
"""

import asyncio
import json
import random

from errors import Retryable, ToolInputError, FatalToolError

MAX_ERROR_CHARS = 300  # tool error text is untrusted input: truncate, no tracebacks


class CircuitBreaker:
    """Per-tool consecutive-failure counter. Resets on success, trips at the threshold."""

    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.failures: dict[str, int] = {}

    def record(self, tool_name: str, ok: bool) -> bool:
        if ok:
            self.failures[tool_name] = 0
            return False
        self.failures[tool_name] = self.failures.get(tool_name, 0) + 1
        return self.failures[tool_name] >= self.threshold


async def execute_tool(fn, tool_input, max_attempts=3, base_delay=0.5):
    """Run a tool, retrying ONLY Retryable failures with jittered backoff.

    ToolInputError / FatalToolError propagate untouched. Exhausting retries is
    treated as fatal here — a deliberate choice. To degrade instead (e.g. let the
    model carry on without search results), catch FatalToolError per-tool in
    handle_tool_call and return an is_error result rather than re-raising.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(**tool_input)
        except Retryable as exc:
            if attempt == max_attempts:
                raise FatalToolError(
                    f"{fn.__name__} still failing after {max_attempts} attempts: {exc}"
                ) from exc
            delay = (
                exc.retry_after
                if exc.retry_after is not None
                else base_delay * 2 ** (attempt - 1)
            )
            delay += random.uniform(0, delay * 0.25)
            print(f"[RETRY] {fn.__name__} attempt {attempt}/{max_attempts} failed ({exc}); sleeping {delay:.1f}s")
            await asyncio.sleep(delay)


def _error_result(tool_use_id, message):
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "is_error": True,
        "content": message[:MAX_ERROR_CHARS],
    }


async def handle_tool_call(tool_use, registry, breaker):
    fn = registry.fns.get(tool_use.name)
    if fn is None:  # model invented a tool name — recoverable and able to be reasoned upon, inform model
        return _error_result(tool_use.id, f"Unknown tool: {tool_use.name}")
    try:
        result = await execute_tool(fn, tool_use.input)
        breaker.record(tool_use.name, ok=True)
        return {
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": json.dumps(result),
        }
    except ToolInputError as exc:
        if breaker.record(tool_use.name, ok=False):
            print(f"[BREAKER] {tool_use.name} tripped after {breaker.threshold} consecutive failures")
            raise FatalToolError(
                f"{tool_use.name} failed {breaker.threshold} times in a row — breaking the loop"
            ) from exc
        return _error_result(tool_use.id, str(exc))
    except FatalToolError:
        raise  # abort the run — caught in run_agent
    except Exception as exc:  # untranslated: degrade safely, don't crash, don't retry
        if breaker.record(tool_use.name, ok=False):
            print(f"[BREAKER] {tool_use.name} tripped after {breaker.threshold} consecutive failures")
            raise FatalToolError(
                f"{tool_use.name} failed {breaker.threshold} times in a row — breaking the loop"
            ) from exc
        return _error_result(tool_use.id, f"Unexpected error in {tool_use.name}: {exc}")
