"""
Tools as discrete reusable modules. Each tool owns its translation: catch
native errors, raise one of the three harness exceptions from errors.py.
Anything left untranslated falls through to a safe default in the harness
(returned to the model, not retried, never crashes the loop).

Adding a new tool means writing its function, translation block, and spec here
— the harness is never touched.
"""

import os

from dotenv import load_dotenv, find_dotenv
from tavily import AsyncTavilyClient

from errors import Retryable, ToolInputError, FatalToolError

load_dotenv(find_dotenv())

tavily_client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])


# Tavily's exception names vary across tavily-python versions; alias-or-stub them
# so this file runs regardless. Verify the names against your installed version.
try:
    from tavily import UsageLimitExceededError, InvalidAPIKeyError, MissingAPIKeyError
except ImportError:
    try:
        from tavily.errors import (
            UsageLimitExceededError,
            InvalidAPIKeyError,
            MissingAPIKeyError,
        )
    except ImportError:
        class _TavilyExcStub(Exception):
            ...
        UsageLimitExceededError = InvalidAPIKeyError = MissingAPIKeyError = _TavilyExcStub


# ------------------------------- Tool registry --------------------------------

class ToolRegistry:
    """Maps a tool name to a callable plus the spec sent to the model."""

    def __init__(self):
        self.fns = {}
        self.specs = []

    def add(self, fn, spec):
        self.fns[spec["name"]] = fn
        self.specs.append(spec)


registry = ToolRegistry()


# ---------------------------------- Tools -------------------------------------

async def web_search(query: str) -> dict:
    try:
        resp = await tavily_client.search(
            query=query,
            include_answer="basic",
            search_depth="advanced",
            max_results=5,
        )
    except UsageLimitExceededError as exc:                   # rate / quota -> retry
        raise Retryable(f"tavily usage limit: {exc}") from exc
    except (InvalidAPIKeyError, MissingAPIKeyError) as exc:  # misconfig -> fatal
        raise FatalToolError(f"tavily auth: {exc}") from exc
    # NOTE: add your HTTP client's timeout / connection errors here as Retryable
    #       once you confirm whether tavily-python sits on requests or httpx,
    #       e.g. `except httpx.TimeoutException as exc: raise Retryable(...)`.

    results = resp.get("results", [])
    if not results and not resp.get("answer"):
        return {"status": "no_results", "query": query}
    return {
        "status": "success",
        "answer": resp.get("answer"),
        "results": [
            {"title": r["title"], "snippet": r["content"][:500], "source": r["url"]}
            for r in results[:5]
        ],
    }


registry.add(
    web_search,
    {
        "name": "web_search",
        "description": (
            "Search the web for current, up-to-date information. Provide a search "
            "query; returns a list of results plus a short summary answer. Use this "
            "when you need information that may have changed since training."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The web search query."}
            },
            "required": ["query"],
        },
    },
)


async def calculate_compound_interest(principal, monthly_deposit, annual_rate, years) -> dict:
    # Pure compute: it can never rate-limit or time out, so it never raises
    # Retryable. Its only realistic failures are bad inputs -> ToolInputError.
    if annual_rate <= 0:
        raise ToolInputError("annual_rate must be > 0, given as a decimal (0.05 = 5%).")
    if years <= 0 or principal < 0 or monthly_deposit < 0:
        raise ToolInputError(
            "principal and monthly_deposit must be >= 0, and years must be > 0."
        )

    n = 12  # compounding periods per year
    growth = (1 + annual_rate / n) ** (n * years)
    balance_principal = principal * growth
    balance_deposits = monthly_deposit * (growth - 1) / (annual_rate / n)

    total_balance = balance_principal + balance_deposits
    total_deposited = principal + monthly_deposit * n * years
    return {
        "total_balance": round(total_balance, 2),
        "total_deposited": round(total_deposited, 2),
        "total_interest": round(total_balance - total_deposited, 2),
    }


registry.add(
    calculate_compound_interest,
    {
        "name": "calculate_compound_interest",
        "description": (
            "Calculate the future value of an investment with regular monthly "
            "deposits under monthly compounding. Use only for compound interest, "
            "not for other investment maths."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "principal": {
                    "type": "integer",
                    "description": "Initial lump-sum deposit, as a whole number.",
                },
                "monthly_deposit": {
                    "type": "integer",
                    "description": "Recurring monthly contribution, as a whole number.",
                },
                "annual_rate": {
                    "type": "number",
                    "description": "Annual interest rate as a decimal, e.g. 0.05 for 5%.",
                },
                "years": {
                    "type": "integer",
                    "description": "Number of years to compound over, as a whole number.",
                },
            },
            "required": ["principal", "monthly_deposit", "annual_rate", "years"],
        },
    },
)
