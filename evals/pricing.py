"""Cost of the engine's LLM calls, from the `llm_call` events it emits.

Prices in USD per million tokens, from the Anthropic pricing table (checked 2026-10-14
via the claude-api reference, cached 2026-10-06). Cache reads and writes are priced as
multiples of the input price, except where the table lists a cache-read price.
"""

from screening.schemas import Event

PRICES: dict[str, dict[str, float]] = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20},
}
CACHE_WRITE_MULTIPLIER = 1.25


def call_cost(data: dict) -> float:
    """USD for one `llm_call` event's data. Unknown models cost 0 and are reported by the run."""
    price = PRICES.get(data["model"])
    if price is None:
        return 0.0
    read = data.get("cache_read_tokens", 0)
    write = data.get("cache_write_tokens", 0)
    uncached = data["input_tokens"] - read - write  # input_tokens is the total (CONTRACTS §3)
    dollars = (
        uncached * price["input"]
        + read * price["cache_read"]
        + write * price["input"] * CACHE_WRITE_MULTIPLIER
        + data["output_tokens"] * price["output"]
    )
    return dollars / 1_000_000


def events_cost(events: list[Event]) -> float:
    return sum(call_cost(e.data) for e in events if e.type == "llm_call")
