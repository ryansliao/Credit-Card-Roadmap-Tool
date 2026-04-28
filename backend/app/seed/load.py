"""Load backend/seed/*.yaml into the DB.

Idempotent upsert by natural key (name / category / credit_name). FK-dependent
fields that self-reference (Currency.converts_to, SpendCategory.parent) are
resolved in a second pass so forward references work regardless of YAML order.

Per-card nested state (multipliers, groups, rotating, portal links) is synced
in-place: `CardMultiplierGroup` rows are matched by their category-set
signature so groups referenced by `WalletCardGroupSelection` are preserved
across re-loads; other children are delete-and-recreate since nothing else
references them by ID.
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
    CardCredit,
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


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        print(f"  skipped {path.name} (missing)")
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    print(f"  read {path.relative_to(SEED_DIR.parent)}")
    return data


async def load_all() -> None:
    """Run every per-entity loader. Each step commits before the next so
    cross-FK lookups in later steps see freshly-assigned autoincrement IDs."""
    async with AsyncSessionLocal() as db:
        await _load_networks(db)
        await db.commit()
        await _load_co_brands(db)
        await db.commit()
        await _load_issuers(db)
        await db.commit()
        await _load_currencies(db)
        await db.commit()
        await _load_spend_categories(db)
        await db.commit()
        await _load_user_spend_categories(db)
        await db.commit()
        await _load_travel_portals(db)
        await db.commit()
        await _load_cards(db)
        await db.commit()
        await _load_credits(db)
        await db.commit()
    print(f"Loaded seed data from {SEED_DIR}")


async def _upsert_by_unique(
    db, model, key_field: str, key_value: Any, **fields: Any
):
    """Upsert a row by a single unique natural-key field. Returns the row."""
    stmt = select(model).where(getattr(model, key_field) == key_value)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        for k, v in fields.items():
            setattr(existing, k, v)
        return existing
    obj = model(**{key_field: key_value, **fields})
    db.add(obj)
    await db.flush()
    return obj


async def _load_networks(db) -> None:
    data = _load_yaml(SEED_DIR / "networks.yaml")

    name_to_net: dict[str, Network] = {}
    for n in data.get("networks", []) or []:
        net = await _upsert_by_unique(db, Network, "name", n["name"])
        name_to_net[n["name"]] = net

    desired_tiers: dict[str, int | None] = {}
    for n in data.get("networks", []) or []:
        for tier_name in n.get("tiers", []) or []:
            desired_tiers[tier_name] = name_to_net[n["name"]].id
    for tier_name in data.get("orphan_tiers", []) or []:
        desired_tiers[tier_name] = None

    for tier_name, network_id in desired_tiers.items():
        await _upsert_by_unique(
            db, NetworkTier, "name", tier_name, network_id=network_id
        )


async def _load_co_brands(db) -> None:
    data = _load_yaml(SEED_DIR / "co_brands.yaml")
    for cb in data.get("co_brands", []) or []:
        await _upsert_by_unique(db, CoBrand, "name", cb["name"])


async def _load_issuers(db) -> None:
    data = _load_yaml(SEED_DIR / "issuers.yaml")
    for iss_data in data.get("issuers", []) or []:
        iss = await _upsert_by_unique(db, Issuer, "name", iss_data["name"])
        await _sync_issuer_rules(db, iss.id, iss_data.get("application_rules", []) or [])
    await _sync_issuer_rules(db, None, data.get("global_application_rules", []) or [])


async def _sync_issuer_rules(
    db, issuer_id: int | None, rules_data: list[dict[str, Any]]
) -> None:
    stmt = select(IssuerApplicationRule)
    stmt = (
        stmt.where(IssuerApplicationRule.issuer_id == issuer_id)
        if issuer_id is not None
        else stmt.where(IssuerApplicationRule.issuer_id.is_(None))
    )
    existing = (await db.execute(stmt)).scalars().all()
    by_name = {r.rule_name: r for r in existing}
    desired_names: set[str] = set()

    for rd in rules_data:
        name = rd["rule_name"]
        desired_names.add(name)
        fields = {
            "description": rd.get("description"),
            "max_count": rd["max_count"],
            "period_days": rd["period_days"],
            "personal_only": rd.get("personal_only", False),
            "scope_all_issuers": rd.get("scope_all_issuers", False),
        }
        if name in by_name:
            for k, v in fields.items():
                setattr(by_name[name], k, v)
        else:
            db.add(
                IssuerApplicationRule(issuer_id=issuer_id, rule_name=name, **fields)
            )

    for name, row in by_name.items():
        if name not in desired_names:
            await db.delete(row)
    await db.flush()


async def _load_currencies(db) -> None:
    data = _load_yaml(SEED_DIR / "currencies.yaml")
    currencies_in = data.get("currencies", []) or []

    # Pass 1: upsert everything *without* converts_to, so the reference target
    # always exists for pass 2.
    for cd in currencies_in:
        await _upsert_by_unique(
            db,
            Currency,
            "name",
            cd["name"],
            photo_slug=cd.get("photo_slug"),
            reward_kind=cd.get("reward_kind", "points"),
            cents_per_point=cd.get("cents_per_point", 1.0),
            partner_transfer_rate=cd.get("partner_transfer_rate"),
            cash_transfer_rate=cd.get("cash_transfer_rate"),
            converts_at_rate=cd.get("converts_at_rate"),
            no_transfer_cpp=cd.get("no_transfer_cpp"),
            no_transfer_rate=cd.get("no_transfer_rate"),
        )
    await db.flush()

    all_cur = (await db.execute(select(Currency))).scalars().all()
    by_name = {c.name: c for c in all_cur}
    for cd in currencies_in:
        target = cd.get("converts_to")
        cur = by_name[cd["name"]]
        cur.converts_to_currency_id = by_name[target].id if target else None
    await db.flush()


async def _load_spend_categories(db) -> None:
    data = _load_yaml(SEED_DIR / "spend_categories.yaml")
    categories_in = data.get("spend_categories", []) or []

    # Pass 1: upsert without parent.
    for sc_data in categories_in:
        await _upsert_by_unique(
            db,
            SpendCategory,
            "category",
            sc_data["category"],
            is_system=sc_data.get("is_system", False),
            is_housing=sc_data.get("is_housing", False),
            is_foreign_eligible=sc_data.get("is_foreign_eligible", False),
        )
    await db.flush()

    all_sc = (await db.execute(select(SpendCategory))).scalars().all()
    by_name = {sc.category: sc for sc in all_sc}
    for sc_data in categories_in:
        parent_name = sc_data.get("parent")
        sc = by_name[sc_data["category"]]
        sc.parent_id = by_name[parent_name].id if parent_name else None
    await db.flush()


async def _load_user_spend_categories(db) -> None:
    """Sync UserSpendCategory and its mappings from YAML.

    User categories are upserted by name (preserves id so
    WalletSpendItem.user_spend_category_id references stay valid). Mappings
    are delete-and-recreate per user category because nothing else references
    UserSpendCategoryMapping by id.

    Categories present in the DB but not in YAML are left alone — removal
    should go through a migration that also handles WalletSpendItem fallout.
    """
    data = _load_yaml(SEED_DIR / "user_spend_categories.yaml")
    categories_in = data.get("user_spend_categories", []) or []

    # Pass 1: upsert user categories (without mappings yet).
    for cat_data in categories_in:
        await _upsert_by_unique(
            db,
            UserSpendCategory,
            "name",
            cat_data["name"],
            description=cat_data.get("description"),
            display_order=cat_data.get("display_order", 0),
            is_system=cat_data.get("is_system", False),
        )
    await db.flush()

    # Pass 2: resolve references and sync mappings.
    all_user = (await db.execute(select(UserSpendCategory))).scalars().all()
    user_by_name = {u.name: u for u in all_user}
    all_spend = (await db.execute(select(SpendCategory))).scalars().all()
    spend_by_name = {s.category: s for s in all_spend}

    for cat_data in categories_in:
        user_cat = user_by_name[cat_data["name"]]

        existing = (
            await db.execute(
                select(UserSpendCategoryMapping).where(
                    UserSpendCategoryMapping.user_category_id == user_cat.id
                )
            )
        ).scalars().all()
        for m in existing:
            await db.delete(m)
        await db.flush()

        for m_data in cat_data.get("mappings", []) or []:
            earn_cat = spend_by_name.get(m_data["earn_category"])
            if earn_cat is None:
                continue
            db.add(
                UserSpendCategoryMapping(
                    user_category_id=user_cat.id,
                    earn_category_id=earn_cat.id,
                    default_weight=m_data["weight"],
                )
            )
    await db.flush()


async def _load_travel_portals(db) -> None:
    data = _load_yaml(SEED_DIR / "travel_portals.yaml")
    for p in data.get("travel_portals", []) or []:
        await _upsert_by_unique(db, TravelPortal, "name", p["name"])


async def _load_cards(db) -> None:
    data = _load_yaml(SEED_DIR / "cards.yaml")

    issuers = {
        i.name: i.id for i in (await db.execute(select(Issuer))).scalars().all()
    }
    co_brands = {
        c.name: c.id for c in (await db.execute(select(CoBrand))).scalars().all()
    }
    currencies = {
        c.name: c.id for c in (await db.execute(select(Currency))).scalars().all()
    }
    network_tiers = {
        n.name: n.id for n in (await db.execute(select(NetworkTier))).scalars().all()
    }
    categories = {
        s.category: s.id
        for s in (await db.execute(select(SpendCategory))).scalars().all()
    }
    travel_portals = {
        p.name: p for p in (await db.execute(select(TravelPortal))).scalars().all()
    }

    for cd in data.get("cards", []) or []:
        await _upsert_card(
            db, cd, issuers, co_brands, currencies, network_tiers, categories, travel_portals
        )


def _card_fields(
    cd: dict[str, Any],
    issuers: dict[str, int],
    co_brands: dict[str, int],
    currencies: dict[str, int],
    network_tiers: dict[str, int],
) -> dict[str, Any]:
    return {
        "issuer_id": issuers[cd["issuer"]],
        "currency_id": currencies[cd["currency"]],
        "co_brand_id": co_brands[cd["co_brand"]] if cd.get("co_brand") else None,
        "network_tier_id": (
            network_tiers[cd["network_tier"]] if cd.get("network_tier") else None
        ),
        "annual_fee": cd.get("annual_fee", 0),
        "first_year_fee": cd.get("first_year_fee"),
        "business": cd.get("business", False),
        "sub_points": cd.get("sub_points"),
        "sub_min_spend": cd.get("sub_min_spend"),
        "sub_months": cd.get("sub_months"),
        "sub_spend_earn": cd.get("sub_spend_earn"),
        "sub_cash": cd.get("sub_cash"),
        "sub_secondary_points": cd.get("sub_secondary_points"),
        "sub_recurrence_months": cd.get("sub_recurrence_months"),
        "sub_family": cd.get("sub_family"),
        "annual_bonus": cd.get("annual_bonus") or 0,
        "annual_bonus_percent": cd.get("annual_bonus_percent"),
        "annual_bonus_first_year_only": cd.get("annual_bonus_first_year_only", False),
        "transfer_enabler": cd.get("transfer_enabler", False),
        "secondary_currency_id": (
            currencies[cd["secondary_currency"]]
            if cd.get("secondary_currency")
            else None
        ),
        "secondary_currency_rate": cd.get("secondary_currency_rate"),
        "secondary_currency_cap_rate": cd.get("secondary_currency_cap_rate"),
        "accelerator_cost": cd.get("accelerator_cost"),
        "accelerator_spend_limit": cd.get("accelerator_spend_limit"),
        "accelerator_bonus_multiplier": cd.get("accelerator_bonus_multiplier"),
        "accelerator_max_activations": cd.get("accelerator_max_activations"),
        "housing_tiered_enabled": cd.get("housing_tiered_enabled", False),
        "photo_slug": cd.get("photo_slug"),
        "foreign_transaction_fee": cd.get("foreign_transaction_fee", False),
        "housing_fee_waived": cd.get("housing_fee_waived", False),
    }


async def _upsert_card(
    db,
    cd: dict[str, Any],
    issuers: dict[str, int],
    co_brands: dict[str, int],
    currencies: dict[str, int],
    network_tiers: dict[str, int],
    categories: dict[str, int],
    travel_portals: dict[str, TravelPortal],
) -> None:
    name = cd["name"]
    fields = _card_fields(cd, issuers, co_brands, currencies, network_tiers)

    existing = (
        await db.execute(
            select(Card)
            .options(
                selectinload(Card.multipliers),
                selectinload(Card.multiplier_groups).selectinload(
                    CardMultiplierGroup.categories
                ),
                selectinload(Card.rotating_categories),
                selectinload(Card.travel_portals),
            )
            .where(Card.name == name)
        )
    ).scalar_one_or_none()

    if existing is not None:
        for k, v in fields.items():
            setattr(existing, k, v)
        card = existing
    else:
        card = Card(name=name, **fields)
        db.add(card)
        await db.flush()

    await _sync_card_groups_and_multipliers(db, card, cd, categories)
    await _sync_card_rotating(db, card, cd.get("rotating_categories", []) or [], categories)
    await _sync_card_travel_portals(db, card, cd.get("travel_portals", []) or [], travel_portals)


def _desired_group_signature(
    gd: dict[str, Any], categories_in_group: set[str]
) -> tuple:
    """Stable key for matching a YAML group to an existing DB group.

    Uses the category set (which categories belong to this group) as the
    primary distinguisher, plus the group's multiplier and top_n so groups
    that only differ in those don't collide.
    """
    return (
        frozenset(categories_in_group),
        float(gd.get("multiplier", 1.0)),
        gd.get("top_n_categories"),
    )


def _existing_group_signature(g: CardMultiplierGroup) -> tuple:
    return (
        frozenset(m.spend_category.category for m in g.categories if m.spend_category),
        float(g.multiplier),
        g.top_n_categories,
    )


async def _sync_card_groups_and_multipliers(
    db, card: Card, cd: dict[str, Any], categories: dict[str, int]
) -> None:
    """Sync multiplier groups (match by category-set signature to preserve IDs
    referenced by WalletCardGroupSelection) and the category-multiplier rows
    (match in place by (card_id, category_id, multiplier_group_id) so IDs are
    preserved across re-loads)."""

    desired_groups = cd.get("multiplier_groups", []) or []
    desired_mults = cd.get("multipliers", []) or []

    # Categories-per-group-index, built from the multipliers list.
    group_categories: dict[int, set[str]] = {i: set() for i in range(len(desired_groups))}
    for md in desired_mults:
        gi = md.get("group_index")
        if gi is not None:
            group_categories[gi].add(md["category"])

    # Existing groups (with their categories loaded).
    existing_groups_q = await db.execute(
        select(CardMultiplierGroup)
        .options(
            selectinload(CardMultiplierGroup.categories).selectinload(
                CardCategoryMultiplier.spend_category
            )
        )
        .where(CardMultiplierGroup.card_id == card.id)
    )
    existing_groups = existing_groups_q.scalars().all()
    existing_by_sig: dict[tuple, CardMultiplierGroup] = {
        _existing_group_signature(g): g for g in existing_groups
    }

    desired_by_index: dict[int, CardMultiplierGroup] = {}
    matched_ids: set[int] = set()

    for i, gd in enumerate(desired_groups):
        sig = _desired_group_signature(gd, group_categories.get(i, set()))
        match = existing_by_sig.get(sig)
        fields = {
            "multiplier": gd.get("multiplier", 1.0),
            "cap_per_billing_cycle": gd.get("cap_per_billing_cycle"),
            "cap_period_months": gd.get("cap_period_months"),
            "top_n_categories": gd.get("top_n_categories"),
            "is_rotating": gd.get("is_rotating", False),
            "is_additive": gd.get("is_additive", False),
        }
        if match is not None and match.id not in matched_ids:
            for k, v in fields.items():
                setattr(match, k, v)
            desired_by_index[i] = match
            matched_ids.add(match.id)
        else:
            g = CardMultiplierGroup(card_id=card.id, **fields)
            db.add(g)
            desired_by_index[i] = g

    await db.flush()

    # Match existing category-multiplier rows in place by
    # (category_id, multiplier_group_id, is_portal). Keying on `is_portal` is
    # necessary because a card can legitimately have both a non-portal
    # baseline row and a portal-elevated row on the same (card, category) —
    # e.g. CSP with Travel 2x (base) and Travel 5x (portal). Keying only on
    # (category_id, group_id) would collapse those and strand the second row
    # as an orphan on re-load.
    key_t = tuple[int, int | None, bool]
    existing_mults_by_key: dict[key_t, list[CardCategoryMultiplier]] = {}
    for m in card.multipliers:
        existing_mults_by_key.setdefault(
            (m.category_id, m.multiplier_group_id, bool(m.is_portal)), []
        ).append(m)
    desired_keys: set[key_t] = set()

    for md in desired_mults:
        gi = md.get("group_index")
        group_id = desired_by_index[gi].id if gi is not None else None
        category_id = categories[md["category"]]
        is_portal = bool(md.get("is_portal", False))
        key: key_t = (category_id, group_id, is_portal)
        desired_keys.add(key)
        fields = {
            "multiplier": md.get("multiplier", 1.0),
            "is_portal": is_portal,
            "is_additive": md.get("is_additive", False),
            "cap_per_billing_cycle": md.get("cap_per_billing_cycle"),
            "cap_period_months": md.get("cap_period_months"),
        }
        bucket = existing_mults_by_key.get(key) or []
        if bucket:
            match = bucket.pop(0)
            for k, v in fields.items():
                setattr(match, k, v)
        else:
            db.add(
                CardCategoryMultiplier(
                    card_id=card.id,
                    category_id=category_id,
                    multiplier_group_id=group_id,
                    **fields,
                )
            )

    # Anything left over in the buckets (either an unmatched key or extra
    # duplicate rows under a matched key) is stale — delete it.
    for bucket in existing_mults_by_key.values():
        for m in bucket:
            await db.delete(m)
    await db.flush()

    # Delete orphaned groups (not matched to any desired group). May fail if a
    # WalletCardGroupSelection still references the group — that's intentional:
    # deleting would silently corrupt wallet state.
    for g in existing_groups:
        if g.id not in matched_ids:
            await db.delete(g)
    await db.flush()


async def _sync_card_rotating(
    db,
    card: Card,
    rotating_data: list[dict[str, Any]],
    categories: dict[str, int],
) -> None:
    """Match rotating-category rows in place by their natural key
    (card_id, year, quarter, spend_category_id) per the UniqueConstraint on
    RotatingCategory. The row has no non-key value fields, so there's nothing
    to update — just add missing and delete unmatched."""
    existing = (
        await db.execute(
            select(RotatingCategory).where(RotatingCategory.card_id == card.id)
        )
    ).scalars().all()
    existing_by_key: dict[tuple[int, int, int], RotatingCategory] = {
        (r.year, r.quarter, r.spend_category_id): r for r in existing
    }
    desired_keys: set[tuple[int, int, int]] = set()

    for rd in rotating_data:
        category_id = categories[rd["category"]]
        key = (rd["year"], rd["quarter"], category_id)
        desired_keys.add(key)
        if key not in existing_by_key:
            db.add(
                RotatingCategory(
                    card_id=card.id,
                    year=rd["year"],
                    quarter=rd["quarter"],
                    spend_category_id=category_id,
                )
            )

    for key, r in existing_by_key.items():
        if key not in desired_keys:
            await db.delete(r)
    await db.flush()


async def _sync_card_travel_portals(
    db,
    card: Card,
    portal_names: list[str],
    travel_portals: dict[str, TravelPortal],
) -> None:
    card.travel_portals = [
        travel_portals[n] for n in portal_names if n in travel_portals
    ]
    await db.flush()


async def _load_credits(db) -> None:
    data = _load_yaml(SEED_DIR / "credits.yaml")
    currencies = {
        c.name: c.id for c in (await db.execute(select(Currency))).scalars().all()
    }
    cards = {
        c.name: c.id for c in (await db.execute(select(Card))).scalars().all()
    }

    for cr_data in data.get("credits", []) or []:
        # Seed credits are system-scoped (NULL owner). Match by name within
        # that scope so a user-created credit sharing the name doesn't get
        # picked up and accidentally promoted to a system credit.
        stmt = select(Credit).where(
            Credit.credit_name == cr_data["credit_name"],
            Credit.owner_user_id.is_(None),
        )
        credit = (await db.execute(stmt)).scalar_one_or_none()
        fields = dict(
            value=cr_data.get("value"),
            excludes_first_year=cr_data.get("excludes_first_year", False),
            is_one_time=cr_data.get("is_one_time", False),
            credit_currency_id=(
                currencies[cr_data["currency"]] if cr_data.get("currency") else None
            ),
        )
        if credit is None:
            credit = Credit(
                credit_name=cr_data["credit_name"],
                owner_user_id=None,
                **fields,
            )
            db.add(credit)
            await db.flush()
        else:
            for k, v in fields.items():
                setattr(credit, k, v)
        await _sync_credit_card_links(db, credit, cr_data.get("cards", []) or [], cards)


async def _sync_credit_card_links(
    db,
    credit: Credit,
    links_data: list[dict[str, Any]],
    cards: dict[str, int],
) -> None:
    existing = (
        await db.execute(
            select(CardCredit).where(CardCredit.credit_id == credit.id)
        )
    ).scalars().all()
    for link in existing:
        await db.delete(link)
    await db.flush()

    for ld in links_data:
        card_id = cards.get(ld["card"])
        if card_id is None:
            continue
        db.add(
            CardCredit(
                credit_id=credit.id,
                card_id=card_id,
                value=ld.get("value"),
            )
        )
    await db.flush()
