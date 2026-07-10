"""
The harness vocabulary: tool errors classified by DISPOSITION (what the harness
should do about them), not by SOURCE (where they came from). There are exactly
three dispositions, expressed as three exceptions.

Each tool translates its own native failures into these three at the edge,
where the failure modes are actually known. The harness only ever knows about
this vocabulary — never about httpx, Tavily, or Python builtins.
"""


class Retryable(Exception):
    """The world blinked. The harness retries; the model never sees it."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after  # seconds, if the API told us


class ToolInputError(Exception):
    """The model can fix this: bad argument, missing resource. Returned as is_error."""


class FatalToolError(Exception):
    """Nothing left to try. Ends the run."""
