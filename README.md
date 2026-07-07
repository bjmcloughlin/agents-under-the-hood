# Agents Under the Hood

Runnable companion code for the articles at [benmcloughlin.com](https://benmcloughlin.com) — how LLM agents actually work, one concept at a time.

Each folder is a **self-contained implementation of one concept**: no shared packages, no framework, no imports between folders. Copy a folder, install its requirements, run it, read it top to bottom.

```bash
cd react-loop
pip install -r requirements.txt
python agent.py
```

## Index

| # | Concept | Article | Code |
|---|---------|---------|------|
| 1 | Chain of thought — why making the model show its working works | [Show your working](https://benmcloughlin.com/learning/chain-of-thought) | [`chain-of-thought/`](chain-of-thought/) |
| 2 | The ReAct loop running inside every agent | [The loop](https://benmcloughlin.com/learning/react-loop) | [`react-loop/`](react-loop/) |
| 3 | Parallel tool calling — fan out independent calls in one turn | [Do it all at once](https://benmcloughlin.com/learning/parallel-tool-calling) | [`parallel-tool-calling/`](parallel-tool-calling/) |
| 4 | Tool error handling — concept & implementation | [Tools fail. Your agent shouldn't.](https://benmcloughlin.com/learning/tool-error-handling) · [Catching errors at the right layer](https://benmcloughlin.com/learning/tool-error-handling-implementation) | [`tool-error-handling/`](tool-error-handling/) |
| 5 | The parts of an agent harness | [The parts of a harness](https://benmcloughlin.com/learning/harness-engineering) | [`harness-engineering/`](harness-engineering/) |
| 6 | Prompt caching — stop paying to re-read the same prompt | [You're paying to re-read the same prompt](https://benmcloughlin.com/learning/prompt-caching) | [`prompt-caching/`](prompt-caching/) |

## What this is (and isn't)

- **Is:** minimal, annotated implementations built to teach. Each one is the smallest complete version of the idea that actually runs.
- **Isn't:** production code. No retries-of-retries, no auth layers, no framework abstractions. Take the ideas, not the files, into production.

## Setup

Implementations use Python and the [Anthropic API](https://docs.anthropic.com) unless a folder's README says otherwise. You'll need an API key:

```bash
export ANTHROPIC_API_KEY=your-key-here
```

Dependencies are pinned **per folder** — there is deliberately no root `requirements.txt`.

## License

[MIT](LICENSE) — use anything here however you like.
