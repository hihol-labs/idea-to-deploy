"""Invoice total calculation for the captured brownfield example."""


def total_with_tax(subtotal_cents: int, tax_basis_points: int) -> int:
    """Return the subtotal plus tax, both expressed as integer cents."""
    return subtotal_cents + (subtotal_cents * tax_basis_points // 100)
