from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


class PaidApiDisabled(RuntimeError):
    """Raised when both paid-execution gates are not enabled."""


class BudgetExceeded(RuntimeError):
    """Raised before a request whose worst-case cost exceeds remaining budget."""


@dataclass(frozen=True, slots=True)
class ModelPricing:
    model: str
    input_usd_per_million_tokens: Decimal
    cached_input_usd_per_million_tokens: Decimal
    output_usd_per_million_tokens: Decimal

    @classmethod
    def from_dict(cls, model: str, data: dict[str, Any]) -> ModelPricing:
        required = {
            "input_usd_per_million_tokens",
            "cached_input_usd_per_million_tokens",
            "output_usd_per_million_tokens",
        }
        missing = required - data.keys()
        if missing:
            raise ValueError(f"pricing is missing fields: {sorted(missing)}")
        return cls(
            model=model,
            input_usd_per_million_tokens=Decimal(
                str(data["input_usd_per_million_tokens"])
            ),
            cached_input_usd_per_million_tokens=Decimal(
                str(data["cached_input_usd_per_million_tokens"])
            ),
            output_usd_per_million_tokens=Decimal(
                str(data["output_usd_per_million_tokens"])
            ),
        )


@dataclass(frozen=True, slots=True)
class UsageRecord:
    request_id: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    cost_usd: Decimal

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": str(self.cost_usd),
        }


class BudgetLedger:
    def __init__(
        self,
        *,
        pricing: ModelPricing,
        max_cost_usd: Decimal,
        config_allows_paid_api: bool,
        cli_allows_paid_api: bool,
    ) -> None:
        if max_cost_usd <= 0:
            raise ValueError("max_cost_usd must be positive")
        self.pricing = pricing
        self.max_cost_usd = max_cost_usd
        self.config_allows_paid_api = config_allows_paid_api
        self.cli_allows_paid_api = cli_allows_paid_api
        self.records: list[UsageRecord] = []

    @property
    def spent_usd(self) -> Decimal:
        return sum((record.cost_usd for record in self.records), Decimal("0"))

    @staticmethod
    def conservative_token_estimate(character_count: int) -> int:
        if character_count < 0:
            raise ValueError("character_count must be non-negative")
        return math.ceil(character_count / 3)

    def calculate_cost(
        self, *, input_tokens: int, cached_input_tokens: int, output_tokens: int
    ) -> Decimal:
        if min(input_tokens, cached_input_tokens, output_tokens) < 0:
            raise ValueError("token counts must be non-negative")
        if cached_input_tokens > input_tokens:
            raise ValueError("cached_input_tokens cannot exceed input_tokens")
        uncached_input_tokens = input_tokens - cached_input_tokens
        million = Decimal("1000000")
        return (
            Decimal(uncached_input_tokens)
            * self.pricing.input_usd_per_million_tokens
            + Decimal(cached_input_tokens)
            * self.pricing.cached_input_usd_per_million_tokens
            + Decimal(output_tokens)
            * self.pricing.output_usd_per_million_tokens
        ) / million

    def authorize_request(
        self, *, prompt_character_count: int, max_output_tokens: int
    ) -> Decimal:
        if not (self.config_allows_paid_api and self.cli_allows_paid_api):
            raise PaidApiDisabled(
                "paid API calls require both config allow_paid_api and "
                "the CLI --allow-paid-api flag"
            )
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        projected = self.calculate_cost(
            input_tokens=self.conservative_token_estimate(prompt_character_count),
            cached_input_tokens=0,
            output_tokens=max_output_tokens,
        )
        if self.spent_usd + projected > self.max_cost_usd:
            raise BudgetExceeded(
                "request rejected: worst-case projected run cost exceeds budget"
            )
        return projected

    def record_actual(
        self,
        *,
        request_id: str,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
    ) -> UsageRecord:
        if not request_id:
            raise ValueError("request_id is required")
        cost = self.calculate_cost(
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
        )
        record = UsageRecord(
            request_id=request_id,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )
        self.records.append(record)
        if self.spent_usd > self.max_cost_usd:
            raise BudgetExceeded(
                "actual recorded usage exceeded the run budget; no further "
                "requests are permitted"
            )
        return record

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.pricing.model,
            "max_cost_usd": str(self.max_cost_usd),
            "spent_usd": str(self.spent_usd),
            "remaining_usd": str(self.max_cost_usd - self.spent_usd),
            "config_allows_paid_api": self.config_allows_paid_api,
            "cli_allows_paid_api": self.cli_allows_paid_api,
            "records": [record.to_dict() for record in self.records],
        }

