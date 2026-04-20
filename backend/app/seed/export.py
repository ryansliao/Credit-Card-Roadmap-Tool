"""Export DB reference data to backend/seed/*.yaml.

Each entity is written to its own file; cross-references use natural keys
(name / category / credit_name) so the YAML is human-editable and
IDs don't leak into the committed data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..database import AsyncSessionLocal
from ..models import (
    Card,
    CardCategoryMultiplier,
    CardMultiplierGroup,
    CoBrand,
    Credit,
    Currency,
    Issuer,
    IssuerApplicationRule,
    Network,
    NetworkTier,
    RotatingCategory,
    SpendCategory,
    TravelPortal,
    UserSpendCategory,
    UserSpendCategoryMapping,
)
from . import SEED_DIR


def _dump(path: Path, data: dict[str, Any]) -> None:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(
            data,
            f,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=120,
        )
    print(f"  wrote {path.relative_to(SEED_DIR.parent)}")


async def export_all() -> None:
    """Run every per-entity exporter in a single session."""
    async with AsyncSessionLocal() as db:
        await _export_networks(db)
        await _export_co_brands(db)
        await _export_issuers(db)
        await _export_currencies(db)
        await _export_spend_categories(db)
        await _export_user_spend_categories(db)
        await _export_travel_portals(db)
        await _export_cards(db)
        await _export_credits(db)
    print(f"Exported seed data to {SEED_DIR}")


async def _export_networks(db) -> None:
    networks = (await db.execute(select(Network).order_by(Network.name))).scalars().all()
    tiers = (await db.execute(select(NetworkTier).order_by(NetworkTier.name))).scalars().all()
    tiers_by_network: dict[int | None, list[str]] = {}
    for t in tiers:
        tiers_by_network.setdefault(t.network_id, []).append(t.name)

    data: dict[str, Any] = {
        "networks": [
            {"name": n.name, "tiers": tiers_by_network.get(n.id, [])}
            for n in networks
        ],
    }
    orphan = tiers_by_network.get(None, [])
    if orphan:
        data["orphan_tiers"] = orphan
    _dump(SEED_DIR / "networks.yaml", data)


async def _export_co_brands(db) -> None:
    rows = (await db.execute(select(CoBrand).order_by(CoBrand.name))).scalars().all()
    _dump(SEED_DIR / "co_brands.yaml", {"co_brands": [{"name": cb.name} for cb in rows]})


def _rule_to_dict(r: IssuerApplicationRule) -> dict[str, Any]:
    d: dict[str, Any] = {
        "rule_name": r.rule_name,
        "max_count": r.max_count,
        "period_days": r.period_days,
    }
    if r.description:
        d["description"] = r.description
    if r.personal_only:
        d["personal_only"] = True
    if r.scope_all_issuers:
        d["scope_all_issuers"] = True
    return d


async def _export_issuers(db) -> None:
    issuers = (
        await db.execute(
            select(Issuer)
            .options(selectinload(Issuer.application_rules))
            .order_by(Issuer.name)
        )
    ).scalars().all()
    global_rules = (
        await db.execute(
            select(IssuerApplicationRule)
            .where(IssuerApplicationRule.issuer_id.is_(None))
            .order_by(IssuerApplicationRule.rule_name)
        )
    ).scalars().all()

    data: dict[str, Any] = {
        "issuers": [
            {
                "name": iss.name,
                "application_rules": [
                    _rule_to_dict(r)
                    for r in sorted(iss.application_rules, key=lambda x: x.rule_name)
                ],
            }
            for iss in issuers
        ],
    }
    if global_rules:
        data["global_application_rules"] = [_rule_to_dict(r) for r in global_rules]
    _dump(SEED_DIR / "issuers.yaml", data)


async def _export_currencies(db) -> None:
    rows = (await db.execute(select(Currency).order_by(Currency.name))).scalars().all()
    by_id = {c.id: c.name for c in rows}

    def to_dict(c: Currency) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": c.name,
        }
        if c.photo_slug is not None:
            d["photo_slug"] = c.photo_slug
        d["reward_kind"] = c.reward_kind
        d["cents_per_point"] = c.cents_per_point
        if c.partner_transfer_rate is not None:
            d["partner_transfer_rate"] = c.partner_transfer_rate
        if c.cash_transfer_rate is not None:
            d["cash_transfer_rate"] = c.cash_transfer_rate
        if c.converts_to_currency_id is not None:
            d["converts_to"] = by_id.get(c.converts_to_currency_id)
        if c.converts_at_rate is not None:
            d["converts_at_rate"] = c.converts_at_rate
        if c.no_transfer_cpp is not None:
            d["no_transfer_cpp"] = c.no_transfer_cpp
        if c.no_transfer_rate is not None:
            d["no_transfer_rate"] = c.no_transfer_rate
        return d

    _dump(SEED_DIR / "currencies.yaml", {"currencies": [to_dict(c) for c in rows]})


async def _export_spend_categories(db) -> None:
    rows = (
        await db.execute(select(SpendCategory).order_by(SpendCategory.id))
    ).scalars().all()
    by_id = {sc.id: sc.category for sc in rows}

    def to_dict(sc: SpendCategory) -> dict[str, Any]:
        d: dict[str, Any] = {"category": sc.category}
        if sc.parent_id is not None:
            d["parent"] = by_id.get(sc.parent_id)
        if sc.is_system:
            d["is_system"] = True
        if sc.is_housing:
            d["is_housing"] = True
        if sc.is_foreign_eligible:
            d["is_foreign_eligible"] = True
        return d

    _dump(
        SEED_DIR / "spend_categories.yaml",
        {"spend_categories": [to_dict(sc) for sc in rows]},
    )


async def _export_user_spend_categories(db) -> None:
    rows = (
        await db.execute(
            select(UserSpendCategory)
            .options(
                selectinload(UserSpendCategory.mappings).selectinload(
                    UserSpendCategoryMapping.earn_category
                )
            )
            .order_by(UserSpendCategory.display_order)
        )
    ).scalars().all()

    def to_dict(cat: UserSpendCategory) -> dict[str, Any]:
        d: dict[str, Any] = {"name": cat.name}
        if cat.description:
            d["description"] = cat.description
        d["display_order"] = cat.display_order
        if cat.is_system:
            d["is_system"] = True
        if cat.mappings:
            d["mappings"] = [
                {
                    "earn_category": m.earn_category.category,
                    "weight": m.default_weight,
                }
                for m in sorted(
                    cat.mappings,
                    key=lambda x: (-x.default_weight, x.earn_category.category),
                )
            ]
        return d

    _dump(
        SEED_DIR / "user_spend_categories.yaml",
        {"user_spend_categories": [to_dict(c) for c in rows]},
    )


async def _export_travel_portals(db) -> None:
    rows = (
        await db.execute(select(TravelPortal).order_by(TravelPortal.name))
    ).scalars().all()
    _dump(
        SEED_DIR / "travel_portals.yaml",
        {"travel_portals": [{"name": p.name} for p in rows]},
    )


def _card_to_dict(c: Card) -> dict[str, Any]:
    d: dict[str, Any] = {
        "name": c.name,
        "issuer": c.issuer.name,
        "currency": c.currency_obj.name,
    }
    if c.co_brand is not None:
        d["co_brand"] = c.co_brand.name
    if c.network_tier is not None:
        d["network_tier"] = c.network_tier.name

    d["annual_fee"] = c.annual_fee
    if c.first_year_fee is not None:
        d["first_year_fee"] = c.first_year_fee
    if c.business:
        d["business"] = True

    for f in (
        "sub_points",
        "sub_min_spend",
        "sub_months",
        "sub_spend_earn",
        "sub_cash",
        "sub_secondary_points",
        "sub_recurrence_months",
        "sub_family",
    ):
        v = getattr(c, f)
        if v is not None:
            d[f] = v

    if c.annual_bonus:
        d["annual_bonus"] = c.annual_bonus
    if c.annual_bonus_percent is not None:
        d["annual_bonus_percent"] = c.annual_bonus_percent
    if c.annual_bonus_first_year_only:
        d["annual_bonus_first_year_only"] = True
    if c.transfer_enabler:
        d["transfer_enabler"] = True

    if c.secondary_currency_obj is not None:
        d["secondary_currency"] = c.secondary_currency_obj.name
        if c.secondary_currency_rate is not None:
            d["secondary_currency_rate"] = c.secondary_currency_rate
        if c.secondary_currency_cap_rate is not None:
            d["secondary_currency_cap_rate"] = c.secondary_currency_cap_rate

    for f in (
        "accelerator_cost",
        "accelerator_spend_limit",
        "accelerator_bonus_multiplier",
        "accelerator_max_activations",
    ):
        v = getattr(c, f)
        if v is not None:
            d[f] = v

    if c.housing_tiered_enabled:
        d["housing_tiered_enabled"] = True
    if c.photo_slug:
        d["photo_slug"] = c.photo_slug
    if c.foreign_transaction_fee:
        d["foreign_transaction_fee"] = True
    if c.housing_fee_waived:
        d["housing_fee_waived"] = True

    groups_sorted = sorted(c.multiplier_groups, key=lambda g: g.id)
    group_idx: dict[int, int] = {g.id: i for i, g in enumerate(groups_sorted)}
    if groups_sorted:
        group_list: list[dict[str, Any]] = []
        for g in groups_sorted:
            gd: dict[str, Any] = {"multiplier": g.multiplier}
            if g.cap_per_billing_cycle is not None:
                gd["cap_per_billing_cycle"] = g.cap_per_billing_cycle
            if g.cap_period_months is not None:
                gd["cap_period_months"] = g.cap_period_months
            if g.top_n_categories is not None:
                gd["top_n_categories"] = g.top_n_categories
            if g.is_rotating:
                gd["is_rotating"] = True
            if g.is_additive:
                gd["is_additive"] = True
            group_list.append(gd)
        d["multiplier_groups"] = group_list

    mults_sorted = sorted(
        c.multipliers,
        key=lambda m: (
            m.multiplier_group_id if m.multiplier_group_id is not None else -1,
            m.spend_category.category if m.spend_category is not None else "",
        ),
    )
    if mults_sorted:
        mult_list: list[dict[str, Any]] = []
        for m in mults_sorted:
            md: dict[str, Any] = {
                "category": m.spend_category.category,
                "multiplier": m.multiplier,
            }
            if m.is_portal:
                md["is_portal"] = True
            if m.is_additive:
                md["is_additive"] = True
            if m.cap_per_billing_cycle is not None:
                md["cap_per_billing_cycle"] = m.cap_per_billing_cycle
            if m.cap_period_months is not None:
                md["cap_period_months"] = m.cap_period_months
            if m.multiplier_group_id is not None:
                md["group_index"] = group_idx[m.multiplier_group_id]
            mult_list.append(md)
        d["multipliers"] = mult_list

    if c.rotating_categories:
        d["rotating_categories"] = [
            {
                "year": r.year,
                "quarter": r.quarter,
                "category": r.spend_category.category,
            }
            for r in sorted(
                c.rotating_categories,
                key=lambda x: (x.year, x.quarter, x.spend_category.category),
            )
        ]

    if c.travel_portals:
        d["travel_portals"] = sorted(p.name for p in c.travel_portals)

    return d


async def _export_cards(db) -> None:
    rows = (
        await db.execute(
            select(Card)
            .options(
                selectinload(Card.issuer),
                selectinload(Card.co_brand),
                selectinload(Card.currency_obj),
                selectinload(Card.secondary_currency_obj),
                selectinload(Card.network_tier),
                selectinload(Card.multipliers).selectinload(CardCategoryMultiplier.spend_category),
                selectinload(Card.multiplier_groups),
                selectinload(Card.rotating_categories).selectinload(RotatingCategory.spend_category),
                selectinload(Card.travel_portals),
            )
            .order_by(Card.name)
        )
    ).scalars().all()
    _dump(SEED_DIR / "cards.yaml", {"cards": [_card_to_dict(c) for c in rows]})


async def _export_credits(db) -> None:
    credits_q = await db.execute(
        select(Credit)
        .options(selectinload(Credit.card_links))
        .order_by(Credit.credit_name)
    )
    credits = credits_q.scalars().all()

    card_rows = (await db.execute(select(Card.id, Card.name))).all()
    card_by_id: dict[int, str] = {cid: cname for cid, cname in card_rows}
    cur_rows = (await db.execute(select(Currency.id, Currency.name))).all()
    cur_by_id: dict[int, str] = {cid: cname for cid, cname in cur_rows}

    def to_dict(cr: Credit) -> dict[str, Any]:
        d: dict[str, Any] = {"credit_name": cr.credit_name}
        if cr.value is not None:
            d["value"] = cr.value
        if cr.excludes_first_year:
            d["excludes_first_year"] = True
        if cr.is_one_time:
            d["is_one_time"] = True
        if cr.credit_currency_id is not None:
            d["currency"] = cur_by_id.get(cr.credit_currency_id)
        if cr.card_links:
            links: list[dict[str, Any]] = []
            for link in sorted(
                cr.card_links, key=lambda x: card_by_id.get(x.card_id, "")
            ):
                ld: dict[str, Any] = {"card": card_by_id.get(link.card_id)}
                if link.value is not None:
                    ld["value"] = link.value
                links.append(ld)
            d["cards"] = links
        return d

    _dump(SEED_DIR / "credits.yaml", {"credits": [to_dict(cr) for cr in credits]})
