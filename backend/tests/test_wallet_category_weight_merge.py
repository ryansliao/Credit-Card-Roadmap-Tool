"""Unit tests for the per-wallet weight override merge helper.

Pure function, no DB. Verifies the override layer + normalization
behavior the calculator relies on.
"""
from __future__ import annotations

from app.services.wallet_category_weight_service import apply_weight_overrides


def test_no_overrides_returns_defaults():
    # Travel (id=10) -> Flights (12, 0.5), Hotels (13, 0.3), Travel-other (14, 0.2)
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.3), (14, "Travel-other", 0.2)],
    }
    overrides: dict[tuple[int, int], float] = {}
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.5), ("Hotels", 0.3), ("Travel-other", 0.2)],
    }


def test_full_override_replaces_all_weights():
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.3), (14, "Travel-other", 0.2)],
    }
    overrides = {
        (10, 12): 0.8,
        (10, 13): 0.1,
        (10, 14): 0.1,
    }
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.8), ("Hotels", 0.1), ("Travel-other", 0.1)],
    }


def test_partial_override_mixes_with_defaults():
    # Override only Flights; Hotels and Travel-other keep their defaults.
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.3), (14, "Travel-other", 0.2)],
    }
    overrides = {(10, 12): 0.9}
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.9), ("Hotels", 0.3), ("Travel-other", 0.2)],
    }


def test_orphan_overrides_for_missing_earn_categories_are_ignored():
    # Override row for an earn category not in the current default mapping
    # set (e.g. category was removed from YAML after override was saved).
    # Should be silently ignored — calculator only iterates the live
    # default mapping set.
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.5)],
    }
    overrides = {
        (10, 12): 0.7,
        (10, 99): 0.3,  # orphan — earn_category 99 not in defaults
    }
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.7), ("Hotels", 0.5)],
    }


def test_overrides_for_other_user_categories_dont_leak():
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.5)],
        20: [(15, "Groceries", 1.0)],
    }
    overrides = {(10, 12): 0.9}  # only Travel
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.9), ("Hotels", 0.5)],
        20: [("Groceries", 1.0)],
    }


def test_zero_override_is_respected():
    # Setting a weight to 0 in the editor should set it to 0 (not be
    # treated as "absence"). The calculator's later normalization
    # excludes the row by giving it 0 share.
    defaults = {
        10: [(12, "Flights", 0.5), (13, "Hotels", 0.5)],
    }
    overrides = {(10, 13): 0.0}
    result = apply_weight_overrides(defaults, overrides)
    assert result == {
        10: [("Flights", 0.5), ("Hotels", 0.0)],
    }
