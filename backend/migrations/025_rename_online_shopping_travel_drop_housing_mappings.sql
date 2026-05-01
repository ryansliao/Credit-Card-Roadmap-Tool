-- Migration 025: Rename "Online Shopping" → "Misc. Online Shopping" and
-- "Travel" → "Misc. Travel" in spend_categories; drop the Housing user
-- category's earn-category mappings (the wallet-level housing_type toggle
-- now drives 100% of housing spend to Rent or Mortgage, so the YAML 50/50
-- mappings are dead weight); rewrite the Online Retail user-category
-- mappings to fan out across PayPal / Amazon / Misc. Online Shopping.
--
-- The seed loader upserts spend_categories by `category` name, so renaming
-- via YAML alone would create new rows and orphan the old ones (along with
-- their CardCategoryMultiplier / UserSpendCategoryMapping FK references).
-- This migration renames in place so existing FKs survive.
--
-- Idempotent: every step is guarded on existence.

-- 1. Rename "Online Shopping" → "Misc. Online Shopping".
IF EXISTS (
    SELECT 1 FROM spend_categories WHERE category = N'Online Shopping'
)
AND NOT EXISTS (
    SELECT 1 FROM spend_categories WHERE category = N'Misc. Online Shopping'
)
BEGIN
    UPDATE spend_categories
    SET category = N'Misc. Online Shopping'
    WHERE category = N'Online Shopping';
END
GO

-- 2. Rename "Travel" → "Misc. Travel".
IF EXISTS (
    SELECT 1 FROM spend_categories WHERE category = N'Travel'
)
AND NOT EXISTS (
    SELECT 1 FROM spend_categories WHERE category = N'Misc. Travel'
)
BEGIN
    UPDATE spend_categories
    SET category = N'Misc. Travel'
    WHERE category = N'Travel';
END
GO

-- 3. Drop the Housing user-category mappings. Calculator
--    `load_wallet_spend_items` clobbers them anyway based on
--    `wallet.housing_type`, but keeping them in the DB is misleading and
--    re-seeded by the YAML on every load. Truncate them here so the
--    seed (with no `mappings` block on Housing) becomes the source of
--    truth.
DELETE FROM user_spend_category_mappings
WHERE user_category_id IN (
    SELECT id FROM user_spend_categories WHERE LOWER(LTRIM(RTRIM(name))) = N'housing'
);
GO

-- 4. Rewrite Online Retail mappings: PayPal 0.30, Amazon 0.40,
--    Misc. Online Shopping 0.30. Done as delete-then-insert under a guard
--    so re-runs don't duplicate.
DECLARE @OnlineRetailId INT = (
    SELECT id FROM user_spend_categories WHERE name = N'Online Retail'
);
DECLARE @PayPalId INT = (
    SELECT id FROM spend_categories WHERE category = N'PayPal'
);
DECLARE @AmazonId INT = (
    SELECT id FROM spend_categories WHERE category = N'Amazon'
);
DECLARE @MiscOnlineId INT = (
    SELECT id FROM spend_categories WHERE category = N'Misc. Online Shopping'
);

IF @OnlineRetailId IS NOT NULL
   AND @PayPalId IS NOT NULL
   AND @AmazonId IS NOT NULL
   AND @MiscOnlineId IS NOT NULL
BEGIN
    DELETE FROM user_spend_category_mappings
    WHERE user_category_id = @OnlineRetailId;

    INSERT INTO user_spend_category_mappings
        (user_category_id, earn_category_id, default_weight)
    VALUES
        (@OnlineRetailId, @PayPalId,     0.30),
        (@OnlineRetailId, @AmazonId,     0.40),
        (@OnlineRetailId, @MiscOnlineId, 0.30);
END
GO
