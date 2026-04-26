-- Migration 011: Rename "Local Transportation" → "Local Transit" and apply
-- the new display_order for user_spend_categories.
--
-- The seed loader upserts user_spend_categories by name, so renaming via YAML
-- alone would create a fresh "Local Transit" row and leave the old "Local
-- Transportation" row behind (along with its WalletSpendItem references).
-- This migration renames the row in place so existing FK references survive,
-- then sets display_order to match the YAML source of truth.
--
-- Idempotent: rename is guarded on existence; display_order updates are
-- safe to re-run.

-- 1. Rename the row in place if the old name still exists and the new name
--    isn't already present.
IF EXISTS (
    SELECT 1 FROM user_spend_categories WHERE name = N'Local Transportation'
)
AND NOT EXISTS (
    SELECT 1 FROM user_spend_categories WHERE name = N'Local Transit'
)
BEGIN
    UPDATE user_spend_categories
    SET name = N'Local Transit',
        description = N'Transit and rideshare'
    WHERE name = N'Local Transportation';
END
GO

-- 2. Apply the new display_order to existing rows. No-op if the rows don't
--    exist yet (a fresh DB will be populated by the seed loader, which carries
--    the same display_order values from the YAML).
UPDATE user_spend_categories SET display_order = 0  WHERE name = N'All Other';
UPDATE user_spend_categories SET display_order = 1  WHERE name = N'Groceries';
UPDATE user_spend_categories SET display_order = 2  WHERE name = N'Dining';
UPDATE user_spend_categories SET display_order = 3  WHERE name = N'Live Entertainment';
UPDATE user_spend_categories SET display_order = 4  WHERE name = N'Streaming';
UPDATE user_spend_categories SET display_order = 5  WHERE name = N'Online Retail';
UPDATE user_spend_categories SET display_order = 6  WHERE name = N'Gas & EV Charging';
UPDATE user_spend_categories SET display_order = 7  WHERE name = N'Local Transit';
UPDATE user_spend_categories SET display_order = 8  WHERE name = N'Airlines';
UPDATE user_spend_categories SET display_order = 9  WHERE name = N'Hotels';
UPDATE user_spend_categories SET display_order = 10 WHERE name = N'Other Travel';
UPDATE user_spend_categories SET display_order = 11 WHERE name = N'Health';
UPDATE user_spend_categories SET display_order = 12 WHERE name = N'Housing';
UPDATE user_spend_categories SET display_order = 13 WHERE name = N'Phone & Internet';
UPDATE user_spend_categories SET display_order = 14 WHERE name = N'Software & Cloud Services';
UPDATE user_spend_categories SET display_order = 15 WHERE name = N'Office & Shipping';
UPDATE user_spend_categories SET display_order = 16 WHERE name = N'Advertising & Marketing';
GO
