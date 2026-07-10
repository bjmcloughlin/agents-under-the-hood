"""
Offline tests for the error-handling harness. No API keys, no network.

Run: python test_harness.py

errors.py and harness.py import with no environment at all — that's the design:
the harness knows nothing about vendors. Only tools.py needs a (dummy) key, for
the two registry-based cases.
"""

import asyncio
import os

from errors import Retryable, ToolInputError, FatalToolError
from harness import CircuitBreaker, execute_tool, handle_tool_call

os.environ.setdefault("TAVILY_API_KEY", "dummy-key-for-import")
from tools import registry, calculate_compound_interest


class FakeToolUse:
    def __init__(self, name, id, input):
        self.name, self.id, self.input = name, id, input


BAD_INPUT = {"principal": 1000, "monthly_deposit": 100, "annual_rate": -1, "years": 5}
GOOD_INPUT = {"principal": 1000, "monthly_deposit": 100, "annual_rate": 0.05, "years": 5}


async def main():
    # 1. ToolInputError from validation
    for kwargs, tag in [
        (dict(principal=1000, monthly_deposit=100, annual_rate=-0.05, years=10), "bad rate"),
        (dict(principal=1000, monthly_deposit=100, annual_rate=0.05, years=0), "bad years"),
    ]:
        try:
            await calculate_compound_interest(**kwargs)
            raise AssertionError(f"no ToolInputError on {tag}")
        except ToolInputError:
            print(f"OK  ToolInputError on {tag}")

    result = await calculate_compound_interest(5000, 200, 0.05, 20)
    assert result["total_balance"] == 95769.94
    print("OK  compound interest maths")

    # 2. CircuitBreaker: trips at threshold, resets on success
    b = CircuitBreaker(threshold=3)
    seq = [b.record("t", ok=False), b.record("t", ok=False), b.record("t", ok=True),
           b.record("t", ok=False), b.record("t", ok=False), b.record("t", ok=False)]
    assert seq == [False, False, False, False, False, True]
    print("OK  breaker trips at 3 consecutive failures, resets on success")

    # 3. Retry exhaustion escalates to FatalToolError
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        raise Retryable("simulated 429", retry_after=0.05)

    try:
        await execute_tool(flaky, {}, max_attempts=3, base_delay=0.01)
        raise AssertionError("no FatalToolError after retries")
    except FatalToolError:
        assert calls["n"] == 3
        print("OK  retries exhausted -> FatalToolError after 3 attempts")

    # 4. Recovery when a retry succeeds
    calls = {"n": 0}

    async def flaky_then_ok():
        calls["n"] += 1
        if calls["n"] < 3:
            raise Retryable("blip", retry_after=0.05)
        return {"ok": True}

    assert await execute_tool(flaky_then_ok, {}, max_attempts=3) == {"ok": True}
    print("OK  recovered on attempt 3")

    # 5. handle_tool_call: is_error results, then breaker escalates to Fatal
    b = CircuitBreaker(threshold=3)
    bad = FakeToolUse("calculate_compound_interest", "tu_1", BAD_INPUT)
    r1 = await handle_tool_call(bad, registry, b)
    r2 = await handle_tool_call(bad, registry, b)
    assert r1["is_error"] and r2["is_error"]
    try:
        await handle_tool_call(bad, registry, b)
        raise AssertionError("breaker did not trip")
    except FatalToolError:
        print("OK  breaker escalated to FatalToolError on 3rd consecutive failure")

    # 6. Unknown tool name -> recoverable is_error
    ghost = FakeToolUse("ghost_tool", "tu_2", {})
    r = await handle_tool_call(ghost, registry, CircuitBreaker())
    assert r["is_error"] and "Unknown tool" in r["content"]
    print("OK  unknown tool returned as recoverable is_error")

    # 7. gather batch: a fatal call can't orphan its sibling
    b = CircuitBreaker(threshold=1)  # trip immediately on first failure
    good = FakeToolUse("calculate_compound_interest", "tu_3", GOOD_INPUT)
    outcomes = await asyncio.gather(
        handle_tool_call(good, registry, b),
        handle_tool_call(bad, registry, b),
        return_exceptions=True,
    )
    assert isinstance(outcomes[0], dict) and not outcomes[0].get("is_error")
    assert isinstance(outcomes[1], FatalToolError)
    print("OK  gather batch: sibling completed, fatal captured (not orphaned)")

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
