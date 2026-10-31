"""Cost estimation from measured token counts.

Prices verified 2026-10-31 (docs/evidence/assumption-ledger.md #12), USD per
1M tokens (input, output). Unknown models fall back to Flash-Lite pricing.
"""

_PRICES: dict[str, tuple[float, float]] = {
    "gemini-3.1-flash-lite": (0.30, 2.50),
    "google/gemini-flash-latest": (0.75, 3.75),
    "gemini-embedding-001": (0.15, 0.0),
}

_FALLBACK = (0.30, 2.50)


def estimate_cost(
    model: str | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> float | None:
    if not model or prompt_tokens is None:
        return None
    price_in, price_out = _PRICES.get(model, _FALLBACK)
    cost = prompt_tokens / 1e6 * price_in
    if completion_tokens:
        cost += completion_tokens / 1e6 * price_out
    return round(cost, 8)
