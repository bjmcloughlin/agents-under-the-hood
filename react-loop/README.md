# The ReAct loop

Companion code for [The loop: how ReAct actually works inside every agent](https://benmcloughlin.com/learning/react-loop).

A minimal ReAct agent — Thought → Action → Observation, repeating until the model produces a final answer — built directly on Anthropic's tool-use API, with no framework. The two tools (`list_emails`, `create_calendar_event`) are mocked with hardcoded returns, so the only external dependency is an Anthropic API key.

## Article vs repo

The article shows just the loop — the part that teaches the mechanic. This folder holds the **full runnable file** around it: the tool definitions, the setup, and the pieces the article cuts for readability:

- **Tool error handling** — `run_tool` returns `(result, is_error)`, and failures flow back to the model as `is_error` tool results it can react to, instead of crashing the loop
- **`.env.example`** — copy to `.env` and add your key

The loop is the production shape: a single `while True` with one API call site and explicit exit conditions (final answer, `MAX_STEPS` safety net), handling every tool call in a turn and returning all results in one user message — the same structure as [Anthropic's quickstart agent](https://github.com/anthropics/anthropic-quickstarts/blob/main/agents/agent.py). Later implementations in this repo extend this loop rather than replace it.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env                     # then add your key
python react_loop.py                     # export ANTHROPIC_API_KEY=... also works
```

## What to look for in the output

- **The `[THINKING]` line on the first turn** — the model's chain of thought before acting. Nothing in the prompt tells it to fetch emails first; the reasoning step works out that it needs addresses before it can fill in `attendees`, resolves "next Wednesday" to a concrete date, and plans the full two-call sequence.
- **The second turn has no `[THINKING]` line** — that's not a bug. `thinking={"type": "adaptive"}` decides per turn whether reasoning would change the answer. The first turn already made every hard decision, so the second is purely mechanical and the model correctly skips thinking.
- **The exit** — the loop ends when a turn comes back with no `tool_use` blocks: the `MAX_STEPS` ceiling never fires, no rule in the host code decides the task is done, the model just produces its final answer.

The article walks through each of these in detail, including the failure modes that show up when the observation step is treated as an afterthought.
