from pydantic import BaseModel
from typing import Dict

# Pricing per million tokens (standard Gemini rate estimates as of 2025/2026)
# Gemini 2.5 Flash / 1.5 Flash: ~$0.075 / 1M input, ~$0.30 / 1M output
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-3.8-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-2.5-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-2.0-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-1.5-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-1.5-pro": {"input_per_million": 1.25, "output_per_million": 5.00},
}

class UsageMetrics(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    duration_seconds: float = 0.0
    retries: int = 0

class CostTracker:
    """Tracks token consumption and enforces document-level spend limits."""

    def __init__(self, max_tokens: int = 100000, max_cost_usd: float = 0.25):
        self.max_tokens = max_tokens
        self.max_cost_usd = max_cost_usd
        self.current_metrics = UsageMetrics(model="unknown")

    def record_usage(self, model: str, input_tokens: int, output_tokens: int, duration: float, retries: int = 0):
        self.current_metrics.model = model
        self.current_metrics.input_tokens += input_tokens
        self.current_metrics.output_tokens += output_tokens
        self.current_metrics.total_tokens += (input_tokens + output_tokens)
        self.current_metrics.duration_seconds += duration
        self.current_metrics.retries += retries

        # Calculate estimated cost
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["gemini-2.5-flash"])
        cost = (
            (self.current_metrics.input_tokens / 1_000_000.0) * pricing["input_per_million"] +
            (self.current_metrics.output_tokens / 1_000_000.0) * pricing["output_per_million"]
        )
        self.current_metrics.estimated_cost_usd = round(cost, 6)

        # Enforce budget guardrails
        if self.current_metrics.total_tokens > self.max_tokens:
            raise PermissionError(
                f"Document token limit exceeded: {self.current_metrics.total_tokens} > {self.max_tokens}"
            )
        if self.current_metrics.estimated_cost_usd > self.max_cost_usd:
            raise PermissionError(
                f"Document spending limit exceeded: ${self.current_metrics.estimated_cost_usd:.4f} > ${self.max_cost_usd}"
            )

    def get_metrics(self) -> UsageMetrics:
        return self.current_metrics
