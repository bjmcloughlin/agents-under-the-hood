# Tool error handling

Companion code for two articles:

- [Tools fail. Your agent shouldn't.](https://benmcloughlin.com/learning/tool-error-handling) — the mental model: every failure handled at the layer that can act on it, four buckets collapsing to three outcomes
- [Catching tool errors at the right layer](https://benmcloughlin.com/learning/tool-error-handling-implementation) — the implementation: classification in the tools, a three-exception vocabulary, a harness that dispatches and never inspects

A tool-calling agent whose errors are classified by **disposition** (what the harness should do), not by source (where they came from). Three exceptions are the whole vocabulary — `Retryable`, `ToolInputError`, `FatalToolError` — and each tool translates its own native failures into them at the edge, where the failure modes are actually known. The harness never imports httpx, Tavily, or a regex; it dispatches on type.

## What's different from `parallel-tool-calling/`

This folder builds on the async loop from [`parallel-tool-calling/`](../parallel-tool-calling/) — `AsyncAnthropic`, async tools, every tool call in a turn executed concurrently — and adds the recovery layer on top:

- **The three-exception vocabulary** — sized to the three things a harness can do with a failure: retry it, hand it to the model, or end the run
- **Edge translation** — `web_search` catches real Tavily exceptions and re-raises harness types; the pure-compute interest calculator can only ever raise `ToolInputError`. Adding a tool never touches the harness
- **`ToolRegistry`** — the repo's first class: maps tool names to callables plus the specs sent to the model
- **Retry with jittered exponential backoff** — honoring the server's `retry_after` when given; exhausted retries escalate to fatal
- **`CircuitBreaker`** — per-tool consecutive-failure counter (trips at 3, resets on success), checked in harness code so stopping never depends on the model agreeing
- **Batch-safe fatals** — concurrent tool calls are gathered with `return_exceptions=True`, so a `FatalToolError` in one call can't orphan its still-running sibling: every call completes, then outcomes are dispatched in order and any fatal in the batch wins
- **A real external tool** — Tavily web search, because the design's whole argument is that the tool author knows what a real vendor exception means. This is the first folder needing a second API key ([Tavily has a free tier](https://tavily.com))
- **SDK retry delegation** — `Anthropic(max_retries=4)` handles transient *model-call* failures; the harness only handles *tool* failures

## Structure

The first multi-module folder in the repo — the file boundaries mirror the design layers, per the agent design best practices in Anthropic's [Building Effective AI Agents](https://resources.anthropic.com/hubfs/Building%20Effective%20AI%20Agents-%20Architecture%20Patterns%20and%20Implementation%20Frameworks.pdf) guide ("practice modular design", "tools as discrete reusable modules"):

```
errors.py          the vocabulary — the contract both sides speak
tools.py           tools as discrete modules: each owns its translation block
harness.py         retry, dispatch, circuit breaker — imports errors + stdlib ONLY
main.py            the agent: the loop that wires model → harness → tools
test_harness.py    offline tests for every error path (no API keys needed)
```

The import graph *is* the argument: open `harness.py` — its complete import list is `asyncio`, `json`, `random`, and the vocabulary. No tavily, no httpx, no regex. The article's claim that the harness "cannot be broken by a vendor rewording an error message, because it never reads one" is a checkable property of this layout, not a promise. Adding a tool touches `tools.py` and nothing else.

## Three guards, three failure shapes

| Guard | Lives in | Catches | Fires |
|---|---|---|---|
| Retry + backoff | `execute_tool` | one call failing transiently | within a call, invisible to the model |
| Circuit breaker | `handle_tool_call` | the loop failing — same tool erroring repeatedly across turns | at 3 consecutive failures, turn ~3 |
| `MAX_STEPS` | `run_agent` | the run failing — too many turns, errors or not | at the global budget, turn 10 |

None substitutes for another: the retry counter restarts on every fresh model attempt (only cross-call state sees a stuck loop), and the breaker never fires on an error-free loop that just isn't converging (only the step budget sees that).

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env                     # then add BOTH keys
python main.py
```

## Test it

The harness is fully testable offline — no keys, no network:

```bash
python test_harness.py
```

Covers every path the happy-path run can't show: validation errors, retry exhaustion, mid-retry recovery, breaker trip/reset/escalation, unknown-tool recovery, and a mixed batch where one call goes fatal without orphaning its sibling.

## What to look for in the output

- **A healthy run** shows none of the machinery: `[STEP]`s, `[TOOL]` calls, `[RESULT]`s, a final answer. The error handling earns its keep by being invisible.
- **`[RETRY]`** lines appear only when a tool raises `Retryable` — the model never sees these turns.
- **`(error)` results** are `ToolInputError`s going back to the model as observations it can self-correct from.
- **`[BREAKER]` + `[FATAL]`** mean the run died deliberately: three consecutive failures of one tool, or a failure nothing can fix (try it: set `TAVILY_API_KEY` to garbage and watch the auth error translate to a clean abort instead of a stack trace).
