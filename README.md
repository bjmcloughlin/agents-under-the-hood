# Agents Under the Hood

Runnable companion code for the articles at [benmcloughlin.com](https://benmcloughlin.com) — how LLM agents actually work, one concept at a time.

Each folder is a **self-contained implementation of one concept**: no shared packages, no framework, no imports between folders. Copy a folder, install its requirements, run it, read it top to bottom.

```bash
cd react-loop
pip install -r requirements.txt
python react_loop.py
```

## Index

| # | Concept | Article | Code |
|---|---------|---------|------|
| 1 | Chain of thought — why making the model show its working works | [Show your working](https://benmcloughlin.com/learning/chain-of-thought) | *article only* |
| 2 | The ReAct loop running inside every agent | [The loop](https://benmcloughlin.com/learning/react-loop) | [`react-loop/`](react-loop/) |
| 3 | Parallel tool calling — fan out independent calls in one turn | [Do it all at once](https://benmcloughlin.com/learning/parallel-tool-calling) | [`parallel-tool-calling/`](parallel-tool-calling/) |
| 4 | Tool error handling — concept & implementation | [Tools fail. Your agent shouldn't.](https://benmcloughlin.com/learning/tool-error-handling) · [Catching errors at the right layer](https://benmcloughlin.com/learning/tool-error-handling-implementation) | [`tool-error-handling/`](tool-error-handling/) |
| 5 | The parts of an agent harness | [The parts of a harness](https://benmcloughlin.com/learning/harness-engineering) | *article only* |
| 6 | Prompt caching — stop paying to re-read the same prompt | [You're paying to re-read the same prompt](https://benmcloughlin.com/learning/prompt-caching) | [`prompt-caching/`](prompt-caching/) |
| 7 | Building an MCP server — tools in a process of their own, tested with the Inspector | [Building an MCP server](https://benmcloughlin.com/learning/building-mcp-servers) | [`mcp-server/`](mcp-server/) |
| 8 | Hosting an MCP server — HTTP, token checks, secrets and identities, with Azure as the example | [Hosting an MCP server](https://benmcloughlin.com/learning/hosting-mcp-servers) | [`mcp-server/`](mcp-server/) |

## How this relates to the articles

The articles show the **quick, trimmed listings** — the smallest version of each idea that keeps the mechanics visible on a page. The folders here hold the **full implementations**: the same code, plus the pieces the articles discuss but cut for readability (step limits, error handling, environment setup). Read the article to understand the idea; clone the folder to run and extend it.

Implementations build on each other: once a concept is introduced it stays in — after [`parallel-tool-calling/`](parallel-tool-calling/), concurrent async tool execution is the standard for every later implementation. Not every article has a folder; pure concept pieces are marked *article only* in the index.

Everything here deliberately tracks Anthropic's own reference patterns: the loop shape and tool-result handling follow the [anthropic-quickstarts agent](https://github.com/anthropics/anthropic-quickstarts/blob/main/agents/agent.py), and the structure follows the guidance in [Building Effective AI Agents](https://resources.anthropic.com/hubfs/Building%20Effective%20AI%20Agents-%20Architecture%20Patterns%20and%20Implementation%20Frameworks.pdf) — start simple, add complexity only when it earns its place, tools as discrete modules.

## What this is (and isn't)

- **Is:** complete, annotated, runnable implementations built to teach.
- **Isn't:** production code. No retries-of-retries, no auth layers, no framework abstractions. Take the ideas, not the files, into production.

## Setup

Implementations use Python and the [Anthropic API](https://docs.anthropic.com) unless a folder's README says otherwise. You'll need an API key:

```bash
export ANTHROPIC_API_KEY=your-key-here
```

Dependencies are pinned **per folder** — there is deliberately no root `requirements.txt`.

## License

[MIT](LICENSE) — use anything here however you like.
