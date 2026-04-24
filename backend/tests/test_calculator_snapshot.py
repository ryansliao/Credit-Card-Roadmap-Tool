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
from dataclasses import asdict, is_dataclass, replace
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


def _ur_cash_currency() -> CurrencyData:
    """UR Cash earns cash that upgrades to Chase UR when a direct UR earner
    is present in the wallet."""
    return CurrencyData(
        id=4,
        name="Chase UR Cash",
        reward_kind="cash",
        cents_per_point=1.0,
        comparison_cpp=1.0,
        converts_to_currency=_ur_currency(),
        converts_at_rate=1.0,
    )


def _bilt_points_currency() -> CurrencyData:
    return CurrencyData(
        id=5,
        name="Bilt Points",
        reward_kind="points",
        cents_per_point=1.5,
        comparison_cpp=1.5,
    )


def _bilt_cash_currency() -> CurrencyData:
    """Bilt Cash: 1 unit = $1. Kept at 100 cpp so flat redemption is 1:1."""
    return CurrencyData(
        id=6,
        name="Bilt Cash",
        reward_kind="cash",
        cents_per_point=100.0,
        comparison_cpp=100.0,
    )


# ---------------------------------------------------------------------------
# Shared card builders (reused across scenarios)
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


def _rotating_group_result() -> WalletResult:
    """Discover-IT-style rotating card with cap well above spend, so the
    pool never binds. Exercises frequency-weighted allocation only."""
    freedom = CardData(
        id=201,
        name="Chase Freedom Flex",
        issuer_name="Chase",
        currency=_cash_currency(),
        annual_fee=0.0,
        sub_points=0, sub_cash=200.0, sub_secondary_points=0,
        sub_min_spend=500, sub_months=3, sub_spend_earn=500,
        annual_bonus=0,
        multipliers={"All Other": 1.0},
        multiplier_groups=[
            # (mult, categories, top_n, group_id, cap_amt, cap_period_months,
            #  is_rotating, rotation_weights, is_additive)
            (
                5.0,
                ["Dining", "Groceries", "Gas", "Streaming"],
                None,
                1,
                1500.0,
                3,
                True,
                {"Dining": 0.25, "Groceries": 0.25, "Gas": 0.25, "Streaming": 0.25},
                False,
            ),
        ],
        network_name="Mastercard",
    )
    flat = _cash_flat_card()
    cards = [freedom, flat]
    spend = {
        "All Other": 8000.0,
        "Dining": 2000.0,
        "Groceries": 2000.0,
        "Gas": 1200.0,
        "Streaming": 600.0,
    }
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=spend,
        years=2,
        foreign_spend_pct=0.0,
    )


def _rotating_pool_overflow_result() -> WalletResult:
    """Same rotating card, but total quarterly bonus spend far exceeds the
    $1,500/qtr pool cap. Exercises the overflow path."""
    freedom = CardData(
        id=202,
        name="Chase Freedom Flex (heavy)",
        issuer_name="Chase",
        currency=_cash_currency(),
        annual_fee=0.0,
        sub_points=0, sub_cash=0.0, sub_secondary_points=0,
        sub_min_spend=None, sub_months=None, sub_spend_earn=0,
        annual_bonus=0,
        multipliers={"All Other": 1.0},
        multiplier_groups=[
            (
                5.0,
                ["Dining", "Groceries", "Gas", "Streaming"],
                None,
                1,
                1500.0,
                3,
                True,
                {"Dining": 0.25, "Groceries": 0.25, "Gas": 0.25, "Streaming": 0.25},
                False,
            ),
        ],
        network_name="Mastercard",
    )
    flat = _cash_flat_card()
    cards = [freedom, flat]
    spend = {
        "All Other": 5000.0,
        "Dining": 6000.0,
        "Groceries": 6000.0,
        "Gas": 3000.0,
        "Streaming": 1200.0,
    }
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=spend,
        years=2,
        foreign_spend_pct=0.0,
    )


def _currency_upgrade_result() -> WalletResult:
    """Chase Freedom Unlimited earns UR-Cash that upgrades to Chase UR when
    CSP is in the wallet. The Freedom's earn should be valued at UR CPP."""
    freedom_unl = CardData(
        id=301,
        name="Chase Freedom Unlimited",
        issuer_name="Chase",
        currency=_ur_cash_currency(),
        annual_fee=0.0,
        sub_points=0, sub_cash=200.0, sub_secondary_points=0,
        sub_min_spend=500, sub_months=3, sub_spend_earn=500,
        annual_bonus=0,
        multipliers={"All Other": 1.5, "Dining": 3.0, "Travel": 5.0},
        network_name="Visa",
    )
    csp = _csp_card()  # adds direct UR earn → triggers upgrade
    cards = [freedom_unl, csp]
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=SPEND,
        years=2,
        foreign_spend_pct=0.0,
    )


def _top_n_group_result() -> WalletResult:
    """Amex-Gold-style: 5 categories in a top-N group with top_n=3.
    Only the 3 highest-spend categories should earn the bonus rate; the
    other 2 fall back to All Other."""
    card = CardData(
        id=401,
        name="Top-3 of 5",
        issuer_name="TestBank",
        currency=_mr_currency(),
        annual_fee=695.0,
        sub_points=0, sub_cash=0.0, sub_secondary_points=0,
        sub_min_spend=None, sub_months=None, sub_spend_earn=0,
        annual_bonus=0,
        multipliers={"All Other": 1.0},
        multiplier_groups=[
            (
                4.0,
                ["Dining", "Groceries", "Gas", "Streaming", "Transit"],
                3,
                1,
                None,
                None,
                False,
                {},
                False,
            ),
        ],
        network_name="Amex",
    )
    flat = _cash_flat_card()
    cards = [card, flat]
    spend = {
        "All Other": 5000.0,
        "Dining": 4000.0,       # high → in top 3
        "Groceries": 3500.0,    # high → in top 3
        "Gas": 3000.0,          # high → in top 3
        "Streaming": 500.0,     # low → falls back
        "Transit": 400.0,       # low → falls back
    }
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=spend,
        years=2,
        foreign_spend_pct=0.0,
    )


def _foreign_spend_split_result() -> WalletResult:
    """Wallet with 20% foreign spend. FTF card loses foreign categories to
    the no-FTF Visa card (Freedom Unlimited)."""
    freedom_unl = CardData(
        id=501,
        name="Chase Freedom Unlimited (no FTF)",
        issuer_name="Chase",
        currency=_cash_currency(),
        annual_fee=0.0,
        sub_points=0, sub_cash=0.0, sub_secondary_points=0,
        sub_min_spend=None, sub_months=None, sub_spend_earn=0,
        annual_bonus=0,
        multipliers={"All Other": 1.5},
        has_foreign_transaction_fee=False,
        network_name="Visa",
    )
    gold = _gold_card()
    gold.has_foreign_transaction_fee = False  # Amex Gold no FTF, non-V/MC
    flat = _cash_flat_card()
    flat.has_foreign_transaction_fee = True   # pretend this card charges FTF
    cards = [freedom_unl, gold, flat]
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=SPEND,
        years=2,
        foreign_spend_pct=20.0,
        foreign_eligible_categories={"Dining", "Travel", "All Other"},
    )


def _bilt_card(card_id: int, name: str, *, accelerator: bool = True) -> CardData:
    """Shared Bilt 2.0 card builder. Housing_tiered_enabled=True, 3x Dining
    (strong enough to beat Citi's 2x cash in allocation), Bilt Cash as
    secondary at 4%, cap_rate 0.75, accelerator optional."""
    return CardData(
        id=card_id,
        name=name,
        issuer_name="Bilt",
        currency=_bilt_points_currency(),
        annual_fee=0.0,
        sub_points=0, sub_cash=0.0, sub_secondary_points=0,
        sub_min_spend=None, sub_months=None, sub_spend_earn=0,
        annual_bonus=0,
        multipliers={"All Other": 1.0, "Rent": 1.0, "Mortgage": 1.0, "Dining": 3.0},
        network_name="Mastercard",
        secondary_currency=_bilt_cash_currency(),
        secondary_currency_rate=0.04,
        secondary_currency_cap_rate=0.75,
        accelerator_cost=200 if accelerator else 0,
        accelerator_spend_limit=1000.0 if accelerator else 0.0,
        accelerator_bonus_multiplier=1.0 if accelerator else 0.0,
        accelerator_max_activations=5 if accelerator else 0,
        housing_tiered_enabled=True,
        housing_fee_waived=True,  # Bilt waives the 3% rent-platform fee
    )


def _bilt_tiered_mode_result() -> WalletResult:
    """Ratio ≥ 1.0 + no accelerator → Tiered mode at 1.25x on Rent wins
    over Bilt Cash's Tier-1-only bonus (1.25 × housing > 1.0 × housing)."""
    bilt = _bilt_card(601, "Bilt (tiered-wins)", accelerator=False)
    flat = _cash_flat_card()
    cards = [bilt, flat]
    # Non-housing $10k on Bilt / housing $10k → ratio 1.0 → 1.25x tier
    # Tiered: Rent 10k × 1.25 = 12500 BP + Dining base
    # Bilt Cash: Tier 1 cap 7.5k → bonus 10000 BP + Dining base
    # Tiered wins by 2500 BP/yr.
    spend = {
        "All Other": 8000.0,   # goes to Citi
        "Dining": 10000.0,     # goes to Bilt (3x > 2x cash)
        "Rent": 10000.0,
    }
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=spend,
        years=2,
        housing_category_names={"Rent", "Mortgage"},
        foreign_spend_pct=0.0,
    )


def _bilt_cash_mode_result() -> WalletResult:
    """Moderate ratio + accelerator active → Bilt Cash's Tier-1+Tier-2
    lump-sum bonus beats Tiered's 1.25x on smaller Rent."""
    bilt = _bilt_card(602, "Bilt (cash-wins)", accelerator=True)
    flat = _cash_flat_card()
    cards = [bilt, flat]
    # Rent $4k → 1.25x tiered = 5000 BP/yr
    # Bilt Cash: Tier 1 cap 0.75×4k = $3k, bonus ~4000 BP; Tier 2 = 5 acts
    # = $5k, bonus 5000 BP; total bonus ≈ 9000 BP → beats tiered.
    spend = {
        "All Other": 5000.0,
        "Dining": 15000.0,  # Bilt wins this
        "Rent": 4000.0,
    }
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=spend,
        years=2,
        housing_category_names={"Rent", "Mortgage"},
        foreign_spend_pct=0.0,
    )


def _recurring_pct_bonus_result() -> WalletResult:
    """CSP-style 10% anniversary bonus — recurring, adds to every year."""
    csp = _csp_card()
    csp = replace(csp, annual_bonus_percent=10.0, annual_bonus_first_year_only=False)
    flat = _cash_flat_card()
    cards = [csp, flat]
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=SPEND,
        years=2,
        foreign_spend_pct=0.0,
    )


def _first_year_pct_bonus_result() -> WalletResult:
    """Discover-IT-style 100% first-year cashback match, simple path, 2-year
    projection → the first-year bonus amortises over both years."""
    discover = CardData(
        id=701,
        name="Discover IT",
        issuer_name="Discover",
        currency=_cash_currency(),
        annual_fee=0.0,
        sub_points=0, sub_cash=0.0, sub_secondary_points=0,
        sub_min_spend=None, sub_months=None, sub_spend_earn=0,
        annual_bonus=0,
        annual_bonus_percent=100.0,
        annual_bonus_first_year_only=True,
        multipliers={"All Other": 1.0},
        multiplier_groups=[
            (
                5.0,
                ["Dining", "Groceries", "Gas", "Streaming"],
                None,
                1,
                1500.0,
                3,
                True,
                {"Dining": 0.25, "Groceries": 0.25, "Gas": 0.25, "Streaming": 0.25},
                False,
            ),
        ],
        network_name="Discover",
    )
    flat = _cash_flat_card()
    cards = [discover, flat]
    spend = {
        "All Other": 8000.0,
        "Dining": 2000.0,
        "Groceries": 2000.0,
        "Gas": 1200.0,
        "Streaming": 600.0,
    }
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=spend,
        years=2,
        foreign_spend_pct=0.0,
    )


def _sub_opp_cost_result() -> WalletResult:
    """Two SUB-bearing cards with overlapping, tight windows that require
    combined monthly spend > the baseline rate → forces extra spend and
    produces non-zero opp cost."""
    csp = _csp_card()
    csp = replace(csp, sub_min_spend=10000, sub_months=3)
    csp.wallet_added_date = date(2026, 1, 1)
    csp.sub_projected_earn_date = date(2026, 3, 31)

    gold = _gold_card()
    gold = replace(gold, sub_min_spend=12000, sub_months=3)
    gold.wallet_added_date = date(2026, 1, 1)
    gold.sub_projected_earn_date = date(2026, 3, 31)

    cards = [csp, gold]
    # Baseline $30k/yr = $2.5k/mo. Combined SUB req = ($10k+$12k)/3mo
    # = $7.3k/mo — $4.8k/mo above baseline → meaningful opp cost.
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


def _priority_category_pin_result() -> WalletResult:
    """Gold has 4x Dining, CSP has 3x Dining with a priority_categories pin.
    The pin should force Dining to CSP regardless of the 4x > 3x ordering."""
    csp = _csp_card()
    csp = replace(csp, priority_categories=frozenset({"dining"}))
    gold = _gold_card()
    flat = _cash_flat_card()
    cards = [csp, gold, flat]
    return compute_wallet(
        all_cards=cards,
        selected_ids={c.id for c in cards},
        spend=SPEND,
        years=2,
        foreign_spend_pct=0.0,
    )


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------


SCENARIOS: dict[str, Callable[[], WalletResult]] = {
    "simple_path": _simple_path_result,
    "segmented_path": _segmented_path_result,
    "rotating_group": _rotating_group_result,
    "rotating_pool_overflow": _rotating_pool_overflow_result,
    "currency_upgrade": _currency_upgrade_result,
    "top_n_group": _top_n_group_result,
    "foreign_spend_split": _foreign_spend_split_result,
    "bilt_tiered_mode": _bilt_tiered_mode_result,
    "bilt_cash_mode": _bilt_cash_mode_result,
    "recurring_pct_bonus": _recurring_pct_bonus_result,
    "first_year_pct_bonus": _first_year_pct_bonus_result,
    "sub_opp_cost": _sub_opp_cost_result,
    "priority_category_pin": _priority_category_pin_result,
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
