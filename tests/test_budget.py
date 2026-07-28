from __future__ import annotations

import unittest
from decimal import Decimal

from intuition_map_eval.budget import (
    BudgetExceeded,
    BudgetLedger,
    ModelPricing,
    PaidApiDisabled,
)


class BudgetLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pricing = ModelPricing(
            model="test-model",
            input_usd_per_million_tokens=Decimal("1"),
            cached_input_usd_per_million_tokens=Decimal("0.1"),
            output_usd_per_million_tokens=Decimal("2"),
        )

    def test_both_paid_gates_are_required(self) -> None:
        ledger = BudgetLedger(
            pricing=self.pricing,
            max_cost_usd=Decimal("1"),
            config_allows_paid_api=True,
            cli_allows_paid_api=False,
        )
        with self.assertRaises(PaidApiDisabled):
            ledger.authorize_request(
                prompt_character_count=300, max_output_tokens=10
            )

    def test_worst_case_request_is_rejected_before_spend(self) -> None:
        ledger = BudgetLedger(
            pricing=self.pricing,
            max_cost_usd=Decimal("0.00001"),
            config_allows_paid_api=True,
            cli_allows_paid_api=True,
        )
        with self.assertRaises(BudgetExceeded):
            ledger.authorize_request(
                prompt_character_count=300, max_output_tokens=100
            )
        self.assertEqual(ledger.spent_usd, Decimal("0"))

    def test_actual_usage_is_costed_and_recorded(self) -> None:
        ledger = BudgetLedger(
            pricing=self.pricing,
            max_cost_usd=Decimal("1"),
            config_allows_paid_api=True,
            cli_allows_paid_api=True,
        )
        projected = ledger.authorize_request(
            prompt_character_count=300, max_output_tokens=100
        )
        self.assertEqual(projected, Decimal("0.0003"))
        record = ledger.record_actual(
            request_id="request-1",
            input_tokens=100,
            cached_input_tokens=20,
            output_tokens=10,
        )
        self.assertEqual(record.cost_usd, Decimal("0.000102"))
        self.assertEqual(ledger.spent_usd, Decimal("0.000102"))


if __name__ == "__main__":
    unittest.main()

