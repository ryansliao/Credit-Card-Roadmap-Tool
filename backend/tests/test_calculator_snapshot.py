"""Regression snapshot for `compute_wallet`.

Each scenario is a hand-built, DB-free `CardData` fixture that exercises
one concept documented in CLAUDE.md's Core Concepts section. Outputs are
serialized to committed JSON under `tests/fixtures/`.

Intentional calculator changes should rerun with `--snapshot-update` and
commit the fixture diff as its own commit so reviewers see exactly what
shifted.

    cd backend
    ../.venv/bin/python -m pytest tests/test_calculator_snapshot.py
    ../.venv/bin/python -m pytest tests/test_calculator_snapshot.py --snapshot-update
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pytest

from app.calculator import CardData, CurrencyData, WalletResult, compute_wallet

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Shared currency builders
# ---------------------------------------------------------------------------


def _ur_currency() -> CurrencyData:
    return CurrencyData(
        id=1,
        name="Chase Ultimate Rewards",
        reward_kind="points",
        cents_per_point=1.8,
        comparison_cpp=1.8,
    )


def _mr_currency() -> CurrencyData:
    return CurrencyData(
        id=2,
        name="Amex Membership Rewards",
        reward_kind="points",
        cents_per_point=1.7,
        comparison_cpp=1.7,
    )


def _cash_currency() -> CurrencyData:
    return CurrencyData(
        id=3,
        name="Cash",
        reward_kind="cash",
        cents_per_point=1.0,
        comparison_cpp=1.0,
    )


# ---------------------------------------------------------------------------
# Shared card builders
# ---------------------------------------------------------------------------


def _csp_card() -> CardData:
    """Chase Sapphire Preferred — SUB-bearing transfer-enabler."""
    return CardData(
        id=101,
        name="Chase Sapphire Preferred",
        issuer_name="Chase",
        currency=_ur_currency(),
        annual_fee=95.0,
        sub_points=60000,
        sub_cash=0.0,
        sub_secondary_points=0,
        sub_min_spend=4000,
        sub_months=3,
        sub_spend_earn=4000,
        annual_bonus=0,
        multipliers={"All Other": 1.0, "Dining": 3.0, "Travel": 2.0},
        transfer_enabler=True,
    )


def _gold_card() -> CardData:
    """Amex Gold — high earn on food, own currency."""
    return CardData(
        id=102,
        name="Amex Gold",
        issuer_name="American Express",
        currency=_mr_currency(),
        annual_fee=325.0,
        sub_points=60000,
        sub_cash=0.0,
        sub_secondary_points=0,
        sub_min_spend=6000,
        sub_months=6,
        sub_spend_earn=6000,
        annual_bonus=0,
        multipliers={"All Other": 1.0, "Dining": 4.0, "Groceries": 4.0},
        credit_lines=[],
        has_foreign_transaction_fee=False,
        network_name="Amex",
    )


def _cash_flat_card() -> CardData:
    """Flat 2% cash-back card — no SUB, no fee."""
    return CardData(
        id=103,
        name="Citi Double Cash",
        issuer_name="Citi",
        currency=_cash_currency(),
        annual_fee=0.0,
        sub_points=0,
        sub_cash=0.0,
        sub_secondary_points=0,
        sub_min_spend=None,
        sub_months=None,
        sub_spend_earn=0,
        annual_bonus=0,
        multipliers={"All Other": 2.0},
        network_name="Mastercard",
    )


SPEND = {
    "All Other": 15000.0,
    "Dining": 6000.0,
    "Travel": 4000.0,
    "Groceries": 5000.0,
}


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def _simple_path_result() -> WalletResult:
    cards = [_csp_card(), _gold_card(), _cash_flat_card()]
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=SPEND,
        years=2,
        foreign_spend_pct=0.0,
    )


def _segmented_path_result() -> WalletResult:
    csp = _csp_card()
    csp.wallet_added_date = date(2026, 1, 1)
    csp.sub_projected_earn_date = date(2026, 3, 15)

    gold = _gold_card()
    gold.wallet_added_date = date(2026, 4, 1)
    gold.sub_projected_earn_date = date(2026, 8, 1)

    cash = _cash_flat_card()
    cash.wallet_added_date = date(2025, 1, 1)

    cards = [csp, gold, cash]
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=SPEND,
        years=2,
        window_start=date(2026, 1, 1),
        window_end=date(2027, 12, 31),
        sub_priority_card_ids={csp.id, gold.id},
        foreign_spend_pct=0.0,
    )


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------


SCENARIOS: dict[str, Callable[[], WalletResult]] = {
    "simple_path": _simple_path_result,
    "segmented_path": _segmented_path_result,
}


# ---------------------------------------------------------------------------
# Serialization + snapshot plumbing
# ---------------------------------------------------------------------------


def _round_floats(obj: Any, ndigits: int = 4) -> Any:
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return str(obj)
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v, ndigits) for v in obj]
    return obj


def _serialize(result: WalletResult) -> dict[str, Any]:
    def convert(obj: Any) -> Any:
        if is_dataclass(obj) and not isinstance(obj, type):
            return {k: convert(v) for k, v in asdict(obj).items()}
        if isinstance(obj, dict):
            return {str(k): convert(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [convert(v) for v in obj]
        if isinstance(obj, (set, frozenset)):
            return sorted(convert(v) for v in obj)
        if isinstance(obj, date):
            return obj.isoformat()
        return obj

    return _round_floats(convert(result))


def _assert_snapshot(name: str, result: WalletResult, update: bool) -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURE_DIR / f"{name}.json"
    current = _serialize(result)

    if update or not path.exists():
        path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        if not update:
            pytest.skip(f"Wrote initial snapshot {path.name}; re-run to assert.")
        return

    committed = json.loads(path.read_text())
    if committed != current:
        diff_hint = _first_diff(committed, current)
        pytest.fail(
            f"Snapshot {path.name} drifted. First diff: {diff_hint}\n"
            f"If this change is intentional rerun with --snapshot-update."
        )


def _first_diff(a: Any, b: Any, path: str = "") -> str:
    if type(a) is not type(b):
        return f"{path or '<root>'}: type {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                return f"{path}.{k}: missing in committed"
            if k not in b:
                return f"{path}.{k}: missing in current"
            if a[k] != b[k]:
                return _first_diff(a[k], b[k], f"{path}.{k}")
        return "(no diff found)"
    if isinstance(a, list):
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return _first_diff(x, y, f"{path}[{i}]")
        if len(a) != len(b):
            return f"{path}: length {len(a)} vs {len(b)}"
        return "(no diff found)"
    return f"{path}: {a!r} vs {b!r}"


# ---------------------------------------------------------------------------
# Parametrized test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_scenario_snapshot(scenario: str, snapshot_update: bool) -> None:
    result = SCENARIOS[scenario]()
    _assert_snapshot(scenario, result, snapshot_update)
