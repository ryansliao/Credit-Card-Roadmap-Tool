"""
Seed the database with all credit cards from pandas DataFrames.

Run directly (from the backend/ directory):
    python -m app.seed_data

Or from the project root:
    cd backend && python -m app.seed_data

Seeding order (respects FK dependencies):
    1. Issuers
    2. Currencies          (FK -> issuers; converts_to_points / converts_to_currency_id set from card boost data)
    3. Spend categories
    4. Cards               (FK -> issuers, currencies); anchors_cashback_conversion set from Anchors sheet
    5. CardCategoryMultipliers / CardCredits
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionLocal, create_tables
from app.models import (
    Card,
    CardCategoryMultiplier,
    CardCredit,
    CardEcosystem,
    Currency,
    Ecosystem,
    Issuer,
    SpendCategory,
    User,
)

# ---------------------------------------------------------------------------
# Reference data path (data/reference.xlsx at project root)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REFERENCE_XLSX = _PROJECT_ROOT / "data" / "reference.xlsx"

# Default DataFrames / structures when reference.xlsx is missing or not used
_CARDS_DF_DEFAULT = pd.DataFrame(
    columns=[
        "name",
        "issuer_name",
        "currency_name",
        "ecosystem_boost_name",
        "annual_fee",
        "sub_points",
        "sub_min_spend",
        "sub_months",
        "sub_spend_points",
        "annual_bonus_points",
    ]
)
_MULTIPLIERS_DF_DEFAULT = pd.DataFrame(columns=["card_name", "category", "multiplier"])
_CREDITS_DF_DEFAULT = pd.DataFrame(columns=["card_name", "credit_type", "label", "value"])
_ANCHORS_DF_DEFAULT = pd.DataFrame(columns=["boost_name", "card_name"])


def _load_reference_data() -> tuple[
    list[str],
    list[tuple[str, str, float, bool, bool]],
    list[tuple[str, str, str, str]],
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Load issuers, currencies, boosts, and DataFrames from data/reference.xlsx.
    Returns (issuers, currencies, ecosystem_boosts, cards_df, multipliers_df, credits_df, spend_df, anchors_df).
    If the file is missing or a sheet is invalid, the corresponding tuple entries are None and DataFrames are defaults.
    """
    _empty_spend = pd.DataFrame(columns=["category", "annual_spend"])
    if not REFERENCE_XLSX.exists():
        return (
            [],
            [],
            [],
            _CARDS_DF_DEFAULT.copy(),
            _MULTIPLIERS_DF_DEFAULT.copy(),
            _CREDITS_DF_DEFAULT.copy(),
            _empty_spend.copy(),
            _ANCHORS_DF_DEFAULT.copy(),
        )

    issuers_list: list[tuple[str, Optional[str], Optional[str]]] = []
    currencies_list: list[tuple[str, str, float, bool, bool, float]] = []
    boosts_list: list[tuple[str, str, str, str]] = []
    cards_df = _CARDS_DF_DEFAULT.copy()
    multipliers_df = _MULTIPLIERS_DF_DEFAULT.copy()
    credits_df = _CREDITS_DF_DEFAULT.copy()
    spend_df = _empty_spend.copy()
    anchors_df = _ANCHORS_DF_DEFAULT.copy()

    try:
        # Issuers: (name, co_brand_partner?, network?)
        df = pd.read_excel(REFERENCE_XLSX, sheet_name="Issuers", engine="openpyxl")
        if not df.empty and "name" in df.columns:
            has_extra = "co_brand_partner" in df.columns and "network" in df.columns
            if has_extra:
                issuers_list = [
                    (
                        str(row["name"]).strip(),
                        str(row["co_brand_partner"]).strip() if pd.notna(row.get("co_brand_partner")) and str(row.get("co_brand_partner")).strip() else None,
                        str(row["network"]).strip() if pd.notna(row.get("network")) and str(row.get("network")).strip() else None,
                    )
                    for _, row in df.iterrows()
                    if pd.notna(row.get("name"))
                ]
            else:
                issuers_list = [
                    (n, None, None)
                    for n in df["name"].dropna().astype(str).str.strip().tolist()
                ]

        # Currencies
        df = pd.read_excel(REFERENCE_XLSX, sheet_name="Currencies", engine="openpyxl")
        if not df.empty and "issuer_name" in df.columns and "currency_name" in df.columns:
            rows = []
            for _, row in df.iterrows():
                rows.append(
                    (
                        str(row["issuer_name"]).strip(),
                        str(row["currency_name"]).strip(),
                        float(row.get("cents_per_point", 1.0) or 1.0),
                        bool(row.get("is_cashback", False)),
                        bool(row.get("is_transferable", False)),
                    )
                )
            currencies_list = rows

        # EcosystemBoosts
        df = pd.read_excel(REFERENCE_XLSX, sheet_name="EcosystemBoosts", engine="openpyxl")
        if not df.empty and "issuer_name" in df.columns and "boost_name" in df.columns:
            rows = []
            for _, row in df.iterrows():
                rows.append(
                    (
                        str(row["issuer_name"]).strip(),
                        str(row["boost_name"]).strip(),
                        str(row.get("boosted_currency_name", "")).strip(),
                        str(row.get("description", "") or ""),
                    )
                )
            boosts_list = rows

        # SpendCategories
        df = pd.read_excel(REFERENCE_XLSX, sheet_name="SpendCategories", engine="openpyxl")
        if not df.empty and "category" in df.columns:
            spend_df = df[["category", "annual_spend"]] if "annual_spend" in df.columns else df
            if "annual_spend" not in spend_df.columns:
                spend_df["annual_spend"] = 0.0

        # Cards
        df = pd.read_excel(REFERENCE_XLSX, sheet_name="Cards", engine="openpyxl")
        if not df.empty:
            cards_df = df

        # Multipliers
        df = pd.read_excel(REFERENCE_XLSX, sheet_name="Multipliers", engine="openpyxl")
        if not df.empty and "card_name" in df.columns and "category" in df.columns:
            multipliers_df = df

        # Credits
        df = pd.read_excel(REFERENCE_XLSX, sheet_name="Credits", engine="openpyxl")
        if not df.empty and "card_name" in df.columns:
            credits_df = df

        # Anchors
        df = pd.read_excel(REFERENCE_XLSX, sheet_name="Anchors", engine="openpyxl")
        if not df.empty and "boost_name" in df.columns and "card_name" in df.columns:
            anchors_df = df
    except Exception:
        # On any read error, fall back to empty data for this run
        return (
            [],
            [],
            [],
            _CARDS_DF_DEFAULT.copy(),
            _MULTIPLIERS_DF_DEFAULT.copy(),
            _CREDITS_DF_DEFAULT.copy(),
            pd.DataFrame(columns=["category", "annual_spend"]),
            _ANCHORS_DF_DEFAULT.copy(),
        )

    return (
        issuers_list,
        currencies_list,
        boosts_list,
        cards_df,
        multipliers_df,
        credits_df,
        spend_df,
        anchors_df,
    )


# Module-level DataFrames (overwritten at seed() from reference.xlsx when present)
CARDS_DF = _CARDS_DF_DEFAULT.copy()
MULTIPLIERS_DF = _MULTIPLIERS_DF_DEFAULT.copy()
CREDITS_DF = _CREDITS_DF_DEFAULT.copy()
SPEND_DF = pd.DataFrame(columns=["category", "annual_spend"])
ANCHORS_DF = _ANCHORS_DF_DEFAULT.copy()


def _cards_from_dfs(
    cards_df: pd.DataFrame,
    multipliers_df: pd.DataFrame,
    credits_df: pd.DataFrame,
) -> dict:
    """Build the same card dict structure that seed() expects from the three DataFrames."""
    categories = (
        multipliers_df["category"].dropna().unique().tolist()
        if not multipliers_df.empty and "category" in multipliers_df.columns
        else []
    )
    all_cards: dict = {}
    for _, row in cards_df.iterrows():
        name = row["name"]
        if pd.isna(name) or not name:
            continue
        name = str(name).strip()
        mults = (
            multipliers_df[multipliers_df["card_name"] == name]
            .set_index("category")["multiplier"]
            .to_dict()
            if not multipliers_df.empty and "card_name" in multipliers_df.columns
            else {}
        )
        multipliers = {cat: float(mults.get(cat, 1.0)) for cat in categories}

        credits: dict[str, dict] = {}
        if not credits_df.empty and "card_name" in credits_df.columns:
            card_credits = credits_df[credits_df["card_name"] == name]
            for _, cr in card_credits.iterrows():
                ctype = cr.get("credit_type", "")
                if pd.notna(ctype) and (pd.notna(cr.get("label")) or (pd.notna(cr.get("value")) and cr.get("value", 0) != 0)):
                    credits[str(ctype)] = {
                        "label": str(cr["label"]) if pd.notna(cr.get("label")) else "",
                        "value": float(cr["value"]) if pd.notna(cr.get("value")) else 0.0,
                    }

        all_cards[name] = {
            "name": name,
            "issuer_name": str(row["issuer_name"]).strip() if pd.notna(row.get("issuer_name")) else None,
            "currency_name": str(row["currency_name"]).strip() if pd.notna(row.get("currency_name")) else None,
            "ecosystem_boost_name": str(row["ecosystem_boost_name"]).strip() if pd.notna(row.get("ecosystem_boost_name")) else None,
            "annual_fee": float(row.get("annual_fee", 0) or 0),
            "sub_points": int(row.get("sub_points", 0) or 0),
            "sub_min_spend": int(row["sub_min_spend"]) if pd.notna(row.get("sub_min_spend")) else None,
            "sub_months": int(row["sub_months"]) if pd.notna(row.get("sub_months")) else None,
            "sub_spend_points": int(row.get("sub_spend_points", 0) or 0),
            "annual_bonus_points": int(row.get("annual_bonus_points", 0) or 0),
            "multipliers": multipliers,
            "credits": credits,
        }
    return all_cards


def _spend_from_df(spend_df: pd.DataFrame) -> list[dict]:
    """Build list of {category, annual_spend} from spend DataFrame."""
    if spend_df.empty or "category" not in spend_df.columns:
        return []
    return [
        {"category": row["category"], "annual_spend": float(row.get("annual_spend", 0) or 0)}
        for _, row in spend_df.iterrows()
    ]


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _upsert_issuer(
    session: AsyncSession,
    name: str,
    co_brand_partner: Optional[str] = None,
    network: Optional[str] = None,
) -> Issuer:
    existing = await session.execute(select(Issuer).where(Issuer.name == name))
    obj = existing.scalar_one_or_none()
    if obj is None:
        obj = Issuer(
            name=name,
            co_brand_partner=co_brand_partner,
            network=network,
        )
        session.add(obj)
        await session.flush()
    else:
        if co_brand_partner is not None:
            obj.co_brand_partner = co_brand_partner
        if network is not None:
            obj.network = network
    return obj


async def _upsert_currency(
    session: AsyncSession,
    issuer: Optional[Issuer],
    name: str,
    cpp: float,
    is_cashback: bool,
    is_transferable: bool,
) -> Currency:
    existing = await session.execute(select(Currency).where(Currency.name == name))
    obj = existing.scalar_one_or_none()
    issuer_id = issuer.id if issuer else None
    if obj is None:
        obj = Currency(
            issuer_id=issuer_id,
            name=name,
            cents_per_point=cpp,
            is_cashback=is_cashback,
            is_transferable=is_transferable,
        )
        session.add(obj)
        await session.flush()
    else:
        obj.issuer_id = issuer_id
        obj.cents_per_point = cpp
        obj.is_cashback = is_cashback
        obj.is_transferable = is_transferable
        await session.flush()
    return obj


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------


async def seed(session: AsyncSession) -> None:
    """Upsert all reference data and cards. Loads from data/reference.xlsx when present."""

    (
        issuers_from_file,
        currencies_from_file,
        boosts_from_file,
        cards_df,
        multipliers_df,
        credits_df,
        spend_df,
        anchors_df,
    ) = _load_reference_data()

    issuers_list = issuers_from_file or []
    currencies_list = currencies_from_file or []
    boosts_list = boosts_from_file or []

    # 0. Default user (for single-tenant Wallet Tool)
    default_user = await session.execute(select(User).where(User.id == 1))
    if default_user.scalar_one_or_none() is None:
        session.add(User(id=1, name="Default User"))
        await session.flush()
        print("  User: default user created (id=1)")
    else:
        print("  User: default user exists")

    # 1. Issuers
    issuer_objs: dict[str, Issuer] = {}
    for name, co_brand_partner, network in issuers_list:
        issuer_objs[name] = await _upsert_issuer(session, name, co_brand_partner, network)
    print(f"  Issuers:  {len(issuer_objs)}")

    # 2. Currencies (issuer optional, e.g. for Cash)
    currency_objs: dict[str, Currency] = {}
    for issuer_name, cur_name, cpp, is_cb, is_tf in currencies_list:
        issuer = issuer_objs.get(str(issuer_name).strip()) if issuer_name and str(issuer_name).strip() else None
        currency_objs[cur_name] = await _upsert_currency(
            session,
            issuer,
            cur_name,
            cpp,
            is_cb,
            is_tf,
        )
    print(f"  Currencies: {len(currency_objs)}")

    # boost_name -> point currency name (for setting currency.converts_to_points on cashback currencies)
    boost_name_to_point_currency: dict[str, str] = {
        row[1]: row[2] for row in boosts_list
    }

    # 3. Spend categories
    spend_cats = _spend_from_df(spend_df)
    for sc in spend_cats:
        existing = await session.execute(
            select(SpendCategory).where(SpendCategory.category == sc["category"])
        )
        obj = existing.scalar_one_or_none()
        if obj is None:
            session.add(SpendCategory(**sc))
        else:
            obj.annual_spend = sc["annual_spend"]
    print(f"  SpendCategories: {len(spend_cats)}")

    # 4. Cards
    all_cards_raw = _cards_from_dfs(cards_df, multipliers_df, credits_df)
    card_objs: dict[str, Card] = {}

    for card_name, card_data in all_cards_raw.items():
        multipliers = card_data.pop("multipliers")
        credits_data = card_data.pop("credits")
        issuer_name = card_data.pop("issuer_name", None)
        currency_name = card_data.pop("currency_name", None)
        boost_name = card_data.pop("ecosystem_boost_name", None)

        if not issuer_name or not currency_name:
            raise ValueError(
                f"Card '{card_name}' must have issuer_name and currency_name in CARDS_DF."
            )

        issuer = issuer_objs.get(issuer_name)
        if issuer is None:
            # Dynamically create unknown issuers
            issuer = await _upsert_issuer(session, issuer_name)
            issuer_objs[issuer_name] = issuer

        currency = currency_objs.get(currency_name)
        if currency is None:
            raise ValueError(
                f"Currency '{currency_name}' not found for card '{card_name}'. "
                "Add it to the Currencies sheet in data/reference.xlsx."
            )

        # If this card had an ecosystem boost, mark its (cashback) currency as converts_to_points
        if boost_name and currency_name and boost_name in boost_name_to_point_currency:
            point_cur_name = boost_name_to_point_currency[boost_name]
            point_currency = currency_objs.get(point_cur_name)
            if point_currency is not None:
                currency.converts_to_points = True
                currency.converts_to_currency_id = point_currency.id
                await session.flush()

        existing = await session.execute(
            select(Card).where(Card.name == card_data["name"])
        )
        card = existing.scalar_one_or_none()

        if card is None:
            card = Card(
                issuer_id=issuer.id,
                currency_id=currency.id,
                **card_data,
            )
            session.add(card)
            await session.flush()
        else:
            card.issuer_id = issuer.id
            card.currency_id = currency.id
            for k, v in card_data.items():
                setattr(card, k, v)
            await session.flush()

        card_objs[card_name] = card

        # Refresh multipliers and credits
        await session.execute(
            CardCategoryMultiplier.__table__.delete().where(
                CardCategoryMultiplier.card_id == card.id
            )
        )
        await session.execute(
            CardCredit.__table__.delete().where(CardCredit.card_id == card.id)
        )
        for cat, mult in multipliers.items():
            session.add(CardCategoryMultiplier(card_id=card.id, category=cat, multiplier=mult))
        for ctype, cinfo in credits_data.items():
            session.add(
                CardCredit(
                    card_id=card.id,
                    credit_name=f"{ctype}: {cinfo['label']}".strip(": "),
                    credit_value=cinfo["value"],
                )
            )

    print(f"  Cards: {len(card_objs)}")

    # 5. Ecosystems and card memberships (from boosts + anchors)
    # Build one Ecosystem per boost; link beneficiary cards and key (anchor) cards
    if boosts_list and boost_name_to_point_currency:
        ecosystem_objs: dict[str, Ecosystem] = {}
        for issuer_name, boost_name, boosted_cur_name, _ in boosts_list:
            if not boost_name or boost_name not in boost_name_to_point_currency:
                continue
            point_cur_name = boost_name_to_point_currency[boost_name]
            point_currency = currency_objs.get(point_cur_name)
            if point_currency is None:
                continue
            cash_currency = currency_objs.get("Cash")
            cashback_currency_id = cash_currency.id if cash_currency else None
            if boost_name in ecosystem_objs:
                continue
            eco = Ecosystem(
                name=boost_name,
                points_currency_id=point_currency.id,
                cashback_currency_id=cashback_currency_id,
            )
            session.add(eco)
            await session.flush()
            ecosystem_objs[boost_name] = eco

        # Beneficiaries: cards with this ecosystem_boost_name -> key_card=False
        for card_name, card in card_objs.items():
            boost_name = all_cards_raw.get(card_name, {}).get("ecosystem_boost_name")
            if boost_name and boost_name in ecosystem_objs:
                session.add(
                    CardEcosystem(
                        card_id=card.id,
                        ecosystem_id=ecosystem_objs[boost_name].id,
                        key_card=False,
                    )
                )
        # Key cards: from Anchors sheet -> key_card=True (ecosystem = one where points_currency == card's currency)
        if not anchors_df.empty and "card_name" in anchors_df.columns:
            for _, row in anchors_df.iterrows():
                anchor_name = row.get("card_name")
                if pd.isna(anchor_name):
                    continue
                anchor_name = str(anchor_name).strip()
                anchor_card = card_objs.get(anchor_name)
                if anchor_card is None:
                    continue
                for eco in ecosystem_objs.values():
                    if eco.points_currency_id == anchor_card.currency_id:
                        session.add(
                            CardEcosystem(
                                card_id=anchor_card.id,
                                ecosystem_id=eco.id,
                                key_card=True,
                            )
                        )
                        break
        await session.flush()
        print(f"  Ecosystems: {len(ecosystem_objs)}; card memberships set")

    await session.commit()
    print("Seed complete.")


async def main() -> None:
    await create_tables()
    async with AsyncSessionLocal() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
