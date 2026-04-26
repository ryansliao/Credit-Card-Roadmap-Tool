-- Migration 012: Merge orphan "Local Transportation" row into "Local Transit".
--
-- Migration 011 was meant to rename "Local Transportation" → "Local Transit"
-- in place. But on the dev DB the seed loader had already created a fresh
-- "Local Transit" row (the YAML had been updated and `python -m app.seed
-- load` ran first), so 011's rename guard saw both names existing and
-- skipped. The result: two rows for the same concept, with WalletSpendItem
-- references split across them.
--
-- This migration handles the four states idempotently:
--   1. Both names exist  → move all wallet_spend_items to Local Transit
--                          (keeping max amount per wallet on conflict),
--                          drop Local Transportation's mappings, delete it.
--   2. Only old name     → rename in place (this is what 011 should have
--                          done; safety net for environments where 011 ran
--                          before the YAML changed).
--   3. Only new name     → no-op.
--   4. Neither exists    → no-op (fresh DB; seed loader will create
--                          "Local Transit" with the YAML's display_order).

DECLARE @oldId INT = (SELECT id FROM user_spend_categories WHERE name = N'Local Transportation');
DECLARE @newId INT = (SELECT id FROM user_spend_categories WHERE name = N'Local Transit');

IF @oldId IS NOT NULL AND @newId IS NOT NULL
BEGIN
    -- Where a wallet has rows under both ids, take the larger amount onto
    -- the new-id row. (Manual entries land on whichever id was canonical at
    -- the time, so the non-zero one is the user's real value.)
    UPDATE wsi_new
    SET amount = (
        SELECT MAX(t.amount)
        FROM wallet_spend_items t
        WHERE t.wallet_id = wsi_new.wallet_id
          AND t.user_spend_category_id IN (@oldId, @newId)
    )
    FROM wallet_spend_items wsi_new
    WHERE wsi_new.user_spend_category_id = @newId
      AND EXISTS (
        SELECT 1 FROM wallet_spend_items t
        WHERE t.wallet_id = wsi_new.wallet_id
          AND t.user_spend_category_id = @oldId
      );

    -- Drop the now-redundant old-id rows for wallets that also have a
    -- new-id row.
    DELETE FROM wallet_spend_items
    WHERE user_spend_category_id = @oldId
      AND wallet_id IN (
          SELECT wallet_id FROM wallet_spend_items WHERE user_spend_category_id = @newId
      );

    -- Repoint remaining old-id rows (wallets that only had Local
    -- Transportation) to the new id.
    UPDATE wallet_spend_items
    SET user_spend_category_id = @newId
    WHERE user_spend_category_id = @oldId;

    -- Drop the old category's mappings; the new category already has
    -- its own from the YAML.
    DELETE FROM user_spend_category_mappings WHERE user_category_id = @oldId;

    -- Drop the orphan category row.
    DELETE FROM user_spend_categories WHERE id = @oldId;
END
ELSE IF @oldId IS NOT NULL AND @newId IS NULL
BEGIN
    UPDATE user_spend_categories
    SET name = N'Local Transit', description = N'Transit and rideshare'
    WHERE id = @oldId;
END
GO

-- Normalise display_order (idempotent; matches the YAML).
UPDATE user_spend_categories SET display_order = 7 WHERE name = N'Local Transit';
GO
