"""Regression test for invoice tax calculation."""

import unittest

from src.invoice import total_with_tax


class InvoiceTotalTests(unittest.TestCase):
    def test_applies_basis_points_as_one_hundredth_of_a_percent(self) -> None:
        self.assertEqual(total_with_tax(10_000, 825), 10_825)


if __name__ == "__main__":
    unittest.main()
