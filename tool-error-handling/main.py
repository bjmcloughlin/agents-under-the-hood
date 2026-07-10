"""
The agent: the loop that wires the model to the tools through the harness.

The loop is inherited from parallel-tool-calling/: async, with every tool call
in a turn executed concurrently. Three guards, three failure shapes:

    retry (in harness.execute_tool)  -> one call failing transiently
    circuit breaker                  -> the loop failing: same tool erroring repeatedly
    MAX_STEPS                        -> the run failing: too many turns, errors or not
"""

import asyncio
import json

import anthropic
from dotenv import load_dotenv, find_dotenv

from errors import FatalToolError
from harness import CircuitBreaker, handle_tool_call
from tools import registry

load_dotenv(find_dotenv())

# The SDK retries transient LLM-call failures (429 / 500 / overloaded) internally
# with backoff that already respects Retry-After. We delegate that boundary to it
# rather than reinventing it; raise max_retries if you want a longer ceiling.
client = anthropic.AsyncAnthropic(max_retries=4)

MODEL = "claude-sonnet-4-6"

# Safety net: a runaway loop needs a hard ceiling, whatever the cause.
MAX_STEPS = 10


def _final_text(response):
    return "".join(b.text for b in response.content if b.type == "text")


async def run_agent(user_input, registry):
    breaker = CircuitBreaker()  # scoped to one run; the next task gets a clean slate
    messages = [{"role": "user", "content": user_input}]

    print(f"[USER] {user_input}")

    step = 1
    while True:
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                tools=registry.specs,
                messages=messages,
            )
        except anthropic.APIError as exc:
            # The SDK already retried transient LLM-call failures; this is terminal.
            print(f"\n[FATAL] The model call failed: {exc}")
            return f"The model call failed: {exc}"

        # Preserve the full assistant turn
        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        print(f"\n[STEP {step}]" if tool_uses else "\n[FINAL]")

        for block in response.content:
            if block.type == "thinking" and block.thinking:
                print(f"[THINKING] {block.thinking.strip()}")
            elif block.type == "text":
                print(f"[CLAUDE] {block.text.strip()}")

        if not tool_uses:
            return _final_text(response)

        if step > MAX_STEPS:
            print(f"[MAX STEPS] Cut off after {MAX_STEPS} steps without a final answer.")
            return "I couldn't complete that within the step budget."

        for tu in tool_uses:
            print(f"[TOOL] {tu.name}({json.dumps(tu.input)})")

        # Run every tool call in this turn concurrently (inherited from
        # parallel-tool-calling/). return_exceptions=True means one fatal call
        # can't orphan its still-running sibling mid-flight — every call
        # completes, then the outcomes are dispatched in order: results pass
        # through, and any FatalToolError in the batch wins and aborts.
        outcomes = await asyncio.gather(
            *(handle_tool_call(tu, registry, breaker) for tu in tool_uses),
            return_exceptions=True,
        )

        tool_results = []
        for outcome in outcomes:
            if isinstance(outcome, FatalToolError):
                print(f"\n[FATAL] {outcome}")
                return f"I couldn't complete that — {outcome}"
            if isinstance(outcome, BaseException):
                raise outcome  # a bug in the harness itself — surface it loudly
            label = "[RESULT] (error)" if outcome.get("is_error") else "[RESULT]"
            print(f"{label} {outcome['content']}")
            tool_results.append(outcome)

        messages.append({"role": "user", "content": tool_results})
        step += 1


if __name__ == "__main__":
    asyncio.run(run_agent("What's the latest on Cash ISAs in the UK?", registry))
