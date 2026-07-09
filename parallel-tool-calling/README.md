# Parallel tool calling

Companion code for [Do it all at once: parallel tool calls and how to build them](https://benmcloughlin.com/learning/parallel-tool-calling).

The same ReAct agent as [`react-loop/`](../react-loop/), given tools that are independent of each other — so the model returns several `tool_use` blocks in a single turn, and the agent runs them concurrently. Tools are mocked (with simulated 1s network latency), so the only external dependency is an Anthropic API key.

## What's different from `react-loop/`

Deliberately almost nothing — that's the article's point. Parallel tool calling is the **default behavior of the Anthropic API**; there is no setting to turn on. The model decides to fan out whenever the calls are independent. The diff:

- **The scenario** — a `check_calendar` tool that gets called once per attendee. Independent calls are what trigger the fan-out; the react-loop demo could never parallelize because its second tool depended on the first.
- **Concurrent execution** — the client is `AsyncAnthropic`, `run_tool` is a coroutine, and the per-turn tool calls run through `asyncio.gather()` (the same pattern as [Anthropic's quickstart agent](https://github.com/anthropics/anthropic-quickstarts/blob/main/agents/agent.py)). `gather` preserves order, so every `tool_result` lines up with its `tool_use` — and all results still go back in one user message.
- **Simulated latency** — each tool sleeps 1s standing in for a real network call, and the loop prints `[ELAPSED]` per turn, so the trace *shows* the speed-up instead of asserting it.

The loop's structure — single `while True`, exit on no tool calls, `MAX_STEPS` safety net, all results in one message — is unchanged.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env                     # then add your key
python parallel_tools.py                 # export ANTHROPIC_API_KEY=... also works
```

## What to look for in the output

- **The fan-out turn** — under `[STEP 2]`, two `[TOOL] check_calendar(...)` lines land in a single turn: one assistant response carrying two `tool_use` blocks. Nothing asked for this; the model judged the two calendar checks independent and batched them.
- **`[ELAPSED] 2 tool call(s) in 1.00s`** — the entire point. Two 1-second calls finished in the time of one, because `asyncio.gather` ran them together. Sequential execution would read `2.00s`.
- **The turns that don't fan out** — `list_emails` runs alone (nothing else can happen until the addresses exist) and `create_calendar_event` runs alone (it needs both calendar results). Parallelism only appears where the work is genuinely independent, and it's the model drawing that line.

Mock calendars are generated relative to today's date, so the availability-checking in the trace stays coherent no matter when you run it.
